const path = require('path');
const fs = require('fs-extra');

const OllamaService = require('./ollamaService');
const WorkflowPlanner = require('./workflowPlanner');
const WorkflowDeveloperService = require('./workflowDeveloperService');
const AnalyzerAgent = require('./analyzerAgent');
const AppRunnerService = require('./appRunnerService');
const FileWriterService = require('./fileWriterService');
const workspaceService = require('./workspaceService');
const memoryStore = require('./memoryStore');
const instructionLoader = require('./instructionLoader');
const workspaceIndexer = require('./workspaceIndexer');
const contextCompactor = require('./contextCompactor');
const workflowSessionStore = require('./workflowSessionStore');
const artifactValidator = require('./artifactValidator');
const bugStoreService = require('./bugStoreService');
const errorFormatter = require('./errorFormatter');
const Generation = require('../models/Generation');

class WorkflowOrchestrator {
  constructor(io) {
    this.io = io;
    this.ollama = new OllamaService(io);
    this.planner = new WorkflowPlanner(this.ollama, io);
    this.developer = new WorkflowDeveloperService(this.ollama, io);
    this.analyzer = new AnalyzerAgent(this.ollama, io);
    this.runner = new AppRunnerService(io);
  }

  async run(jobId, input) {
    const stepResults = [];
    const failurePatterns = [];
    let workspace;
    let thread;
    const model = String(input.model || process.env.OLLAMA_MODEL || 'qwen2.5:14b');
    const timeoutSeconds = Number.isFinite(Number(input.timeoutSeconds))
      ? Math.max(60, Number(input.timeoutSeconds))
      : 900;

    try {
      await bugStoreService.seed();
      this.runner.configureRun({ timeoutMs: timeoutSeconds * 1000 });

      const existingGeneration = await Generation.findOne({ jobId });
      const mode = input.mode || 'new';
      const task = input.task || existingGeneration?.task || '';
      const baseSource = input.srs || existingGeneration?.srs || {};

      workspace = await workspaceService.resolveWorkspace({
        workspaceId: input.workspaceId || existingGeneration?.workspaceId,
        srs: baseSource,
        plan: existingGeneration?.plan
      });

      thread = await workspaceService.resolveThread({
        workspace,
        threadId: input.threadId || existingGeneration?.threadId,
        mode,
        task
      });

      await this.updateGeneration(jobId, {
        workspaceId: workspace.workspaceId,
        threadId: thread.threadId,
        mode,
        task,
        model,
        timeoutSeconds,
        appDir: workspace.appDir,
        stage: 'workspace',
        currentAgent: 'Orchestrator'
      });

      const writer = new FileWriterService(workspace.appDir);
      const memoryBefore = await memoryStore.read(workspace.appDir);
      await workflowSessionStore.update(workspace.appDir, {
        status: 'running',
        currentStage: 'workspace',
        currentAgent: 'Orchestrator',
        task,
        workspaceId: workspace.workspaceId,
        threadId: thread.threadId
      });
      const instructions = await instructionLoader.load(workspace.appDir, memoryBefore);
      const indexBefore = await workspaceIndexer.scan(workspace.appDir);
      const compactedContext = contextCompactor.build({
        workspace,
        thread,
        task,
        instructions,
        memory: memoryBefore,
        index: indexBefore
      });

      await this.recordStep(jobId, stepResults, {
        name: 'workspace-bootstrap',
        stage: 'workspace',
        status: 'success',
        summary: `Workspace ${workspace.slug} ready`,
        details: {
          workspaceId: workspace.workspaceId,
          threadId: thread.threadId,
          indexedFiles: indexBefore.summary.totalFiles
        }
      });

      await this.setStage(jobId, 'planning', 12, 'Planner');
      const currentPlan = existingGeneration?.plan || workspace.latestPlan || null;
      const planContext = {
        projectName: workspace.name,
        description: workspace.description,
        task,
        instructions,
        memory: memoryBefore,
        compactedContext,
        model,
        timeoutSeconds,
        messageContext: {
          workspaceId: workspace.workspaceId,
          threadId: thread.threadId,
          generationId: jobId,
          model,
          timeoutSeconds
        }
      };

      const plan = mode === 'continue' && currentPlan
        ? await this.planner.planContinuation(jobId, task, currentPlan, planContext)
        : await this.planner.plan(jobId, baseSource, planContext);

      const targetServices = this.selectTargetServices(plan, currentPlan, task, indexBefore);
      const generationServices = plan.services.map((service) => ({
        name: service.name,
        port: service.port,
        status: targetServices.some((target) => target.name === service.name) ? 'pending' : 'running',
        routes: (service.routes || []).map((route) => `${route.method} ${route.path}`)
      }));

      await this.updateGeneration(jobId, {
        plan,
        services: generationServices,
        status: 'planning',
        stage: 'plan-ready'
      });

      await workspaceService.touchWorkspace(workspace.workspaceId, {
        latestPlan: plan,
        latestGenerationId: jobId,
        latestThreadId: thread.threadId,
        lastRunSettings: { model, timeoutSeconds },
        lastError: '',
        lastErrorSummary: '',
        serviceNames: plan.services.map((service) => service.name),
        status: 'planning'
      });

      await workspaceService.touchThread(thread.threadId, {
        latestTask: task,
        lastGenerationId: jobId,
        status: 'planning'
      });
      await workflowSessionStore.update(workspace.appDir, {
        currentStage: 'planning',
        currentAgent: 'Planner',
        targetServices: targetServices.map((service) => service.name)
      });

      await this.recordStep(jobId, stepResults, {
        name: 'plan',
        stage: 'planning',
        status: 'success',
        summary: `Plan ready for ${plan.services.length} services`,
        details: {
          targetServices: targetServices.map((service) => service.name)
        }
      });
      this.io.to(jobId).emit('plan:ready', { plan });

      await this.setStage(jobId, 'generating', 22, 'Developer');

      const artifactAudit = { services: {} };
      const generatedThisRun = [];

      for (let index = 0; index < targetServices.length; index += 1) {
        const service = targetServices[index];
        await this.log(jobId, 'Developer', `Generating ${service.name}...`, 'info');
        await workflowSessionStore.update(workspace.appDir, {
          currentStage: 'generation',
          currentAgent: 'Developer',
          currentService: service.name,
          attempts: {
            [service.name]: index + 1
          }
        });

        const serviceContext = {
          ...planContext,
          compactedContext: contextCompactor.build({
            workspace,
            thread,
            task,
            instructions,
            memory: memoryBefore,
            index: indexBefore,
            plan,
            service
          }),
          model,
          timeoutSeconds,
          messageContext: {
            ...planContext.messageContext,
            model,
            timeoutSeconds
          }
        };

        const generationResult = await this.developer.generateService(jobId, service, plan, serviceContext);
        const packageContent = JSON.stringify(generationResult.packageJson, null, 2);
        await writer.writeFile(`${service.name}/package.json`, packageContent);

        const prefixedFiles = this.prefixServiceFiles(service.name, generationResult.files);
        await writer.writeFiles(prefixedFiles);

        const serviceFiles = [
          { path: `${service.name}/package.json`, content: packageContent, service: service.name },
          ...prefixedFiles
        ];

        const validation = artifactValidator.validateService(service, serviceFiles, generationResult.packageJson);
        artifactAudit.services[service.name] = validation.audit;

        if (!validation.ok) {
          const message = validation.issues.map((issue) => issue.message).join('; ');
          failurePatterns.push(...validation.issues.map((issue) => ({
            code: issue.code,
            message: issue.message,
            service: service.name,
            stage: 'validation'
          })));
          throw new Error(`Validation failed for ${service.name}: ${message}`);
        }

        const installResult = await this.installService(service, workspace.appDir, generationResult.packageJson, jobId);
        if (!installResult.success) {
          failurePatterns.push({
            code: 'npm-install-failed',
            message: installResult.error || 'npm install failed',
            service: service.name,
            stage: 'install'
          });
          throw new Error(`npm install failed for ${service.name}: ${installResult.error || installResult.output || 'unknown error'}`);
        }

        generatedThisRun.push(...serviceFiles);
        this.io.to(jobId).emit('files:generated', {
          service: service.name,
          files: serviceFiles.map((file) => file.path)
        });

        await Generation.updateOne(
          { jobId, 'services.name': service.name },
          { $set: { 'services.$.status': 'running' } }
        );

        await this.recordStep(jobId, stepResults, {
          name: `service:${service.name}`,
          stage: 'generation',
          status: 'success',
          summary: `${service.name} generated and validated`,
          details: validation.audit
        });
      }

      const shouldGenerateFrontend = this.shouldGenerateFrontend(mode, task, workspace.appDir);
      if (shouldGenerateFrontend) {
        await this.ensureFrontendScaffold(workspace.appDir, jobId);
        const frontendFiles = await this.developer.generateFrontend(jobId, plan);
        const prefixedFrontend = frontendFiles.map((file) => ({
          ...file,
          path: file.path.startsWith('frontend/') ? file.path : `frontend/${file.path}`,
          service: 'frontend'
        }));
        await writer.writeFiles(prefixedFrontend);
        generatedThisRun.push(...prefixedFrontend);
        this.io.to(jobId).emit('files:generated', {
          service: 'frontend',
          files: prefixedFrontend.map((file) => file.path)
        });
      }

      const gatewayFiles = this.developer.generateGateway(plan);
      await writer.writeFiles(gatewayFiles);
      generatedThisRun.push(...gatewayFiles);
      this.io.to(jobId).emit('files:generated', {
        service: 'gateway',
        files: gatewayFiles.map((file) => file.path)
      });

      await this.setStage(jobId, 'analyzing', 62, 'Analyzer');
      const analysis = await this.analyzer.analyze(jobId, generatedThisRun, plan, undefined, {
        workspaceId: workspace.workspaceId,
        threadId: thread.threadId,
        generationId: jobId,
        model,
        timeoutSeconds
      });
      if (analysis.fixedFiles.length > 0) {
        await writer.writeFiles(analysis.fixedFiles);
      }
      failurePatterns.push(...analysis.issues.slice(0, 10).map((issue) => ({
        code: 'analysis-issue',
        message: issue,
        stage: 'analyze'
      })));

      const workspaceFiles = await writer.readAllFiles();
      const indexAfter = await workspaceIndexer.scan(workspace.appDir);
      const memoryAfter = await memoryStore.updateWorkspaceMemory({
        workspace,
        plan,
        index: indexAfter,
        audit: artifactAudit,
        generation: { task, status: 'running' },
        thread,
        failurePatterns
      });

      await workspaceService.touchWorkspace(workspace.workspaceId, {
        latestPlan: plan,
        latestGenerationId: jobId,
        latestThreadId: thread.threadId,
        lastRunSettings: { model, timeoutSeconds },
        lastError: '',
        lastErrorSummary: '',
        memorySummary: memoryAfter.summary,
        serviceNames: plan.services.map((service) => service.name),
        status: 'running'
      });

      await workspaceService.touchThread(thread.threadId, {
        latestTask: task,
        lastGenerationId: jobId,
        status: 'running',
        messageCount: await this.countThreadMessages(thread.threadId)
      });
      await workflowSessionStore.update(workspace.appDir, {
        currentStage: 'memory',
        currentAgent: 'Orchestrator',
        currentService: '',
        completedSteps: stepResults.map((step) => step.name),
        status: 'running'
      });

      await this.setStage(jobId, 'running', 82, 'Runner');
      const urls = await this.startWorkspaceApps(jobId, workspace.appDir, plan);

      await this.recordStep(jobId, stepResults, {
        name: 'memory-update',
        stage: 'memory',
        status: 'success',
        summary: 'AI memory refreshed',
        details: memoryAfter.summary
      });

      await this.updateGeneration(jobId, {
        status: 'complete',
        progress: 100,
        stage: 'complete',
        currentAgent: 'Orchestrator',
        model,
        timeoutSeconds,
        generatedFiles: workspaceFiles,
        allUrls: urls,
        gatewayUrl: urls.gateway,
        frontendUrl: urls.frontend,
        stepResults,
        memorySummary: memoryAfter.summary,
        artifactAudit
      });
      await workflowSessionStore.update(workspace.appDir, {
        status: 'complete',
        currentStage: 'complete',
        currentAgent: 'Orchestrator',
        currentService: '',
        completedSteps: stepResults.map((step) => step.name),
        lastError: ''
      });

      this.io.to(jobId).emit('generation:complete', {
        jobId,
        urls
      });

      return Generation.findOne({ jobId });
    } catch (error) {
      const errorSummary = errorFormatter.summarize(error.message);
      await this.log(jobId, 'Orchestrator', `Fatal error: ${error.message}`, 'error');
      if (workspace) {
        const indexAfterError = await workspaceIndexer.scan(workspace.appDir);
        const memoryAfterError = await memoryStore.updateWorkspaceMemory({
          workspace,
          plan: (await Generation.findOne({ jobId }))?.plan || workspace.latestPlan || { services: [] },
          index: indexAfterError,
          audit: { services: {} },
          generation: { task: input.task || '', status: 'error' },
          thread,
          failurePatterns: [...failurePatterns, { code: 'workflow-error', message: error.message, stage: 'orchestrator' }]
        });

        await workspaceService.touchWorkspace(workspace.workspaceId, {
          latestGenerationId: jobId,
          latestThreadId: thread?.threadId || '',
          lastRunSettings: { model, timeoutSeconds },
          lastError: error.message,
          lastErrorSummary: errorSummary,
          memorySummary: memoryAfterError.summary,
          status: 'error'
        });
        await workflowSessionStore.update(workspace.appDir, {
          status: 'error',
          currentStage: 'error',
          currentAgent: 'Orchestrator',
          lastError: error.message
        });
      }

      await this.updateGeneration(jobId, {
        status: 'error',
        stage: 'error',
        error: error.message,
        errorSummary,
        model,
        timeoutSeconds,
        stepResults
      });
      this.io.to(jobId).emit('generation:error', { jobId, error: error.message, errorSummary });
      throw error;
    }
  }

  selectTargetServices(plan, currentPlan, task = '', indexBefore = {}) {
    if (!currentPlan || !Array.isArray(currentPlan.services) || currentPlan.services.length === 0) {
      return plan.services;
    }

    const taskLower = String(task || '').toLowerCase();
    const existingNames = new Set((currentPlan.services || []).map((service) => service.name));
    const indexedServices = new Set(Object.keys(indexBefore.services || {}));
    const selected = plan.services.filter((service) => {
      const shortName = service.name.replace(/-service$/, '');
      return taskLower.includes(service.name) ||
        taskLower.includes(shortName) ||
        !existingNames.has(service.name) ||
        !indexedServices.has(service.name);
    });

    return selected.length > 0 ? selected : plan.services;
  }

  shouldGenerateFrontend(mode, task, workspaceDir) {
    if (mode === 'new') return true;
    if (String(task || '').toLowerCase().includes('frontend')) return true;
    return !fs.existsSync(path.join(workspaceDir, 'frontend', 'package.json'));
  }

  async ensureFrontendScaffold(workspaceDir, jobId) {
    const frontendDir = path.join(workspaceDir, 'frontend');
    if (await fs.pathExists(path.join(frontendDir, 'package.json'))) {
      return frontendDir;
    }

    await this.runner.createViteApp(workspaceDir, 'frontend', jobId);
    await this.runner.npmInstall(frontendDir, 'frontend-base', jobId);
    await this.runner.installTailwindPostCSS(frontendDir, jobId);
    await this.runner.installFrontendLibs(frontendDir, jobId);
    return frontendDir;
  }

  async installService(service, workspaceDir, packageJson, jobId) {
    const serviceDir = path.join(workspaceDir, service.name);
    const prodPackages = Object.keys(packageJson.dependencies || {});
    const devPackages = Object.keys(packageJson.devDependencies || {});

    if (prodPackages.length > 0) {
      const prodInstall = await this.runner.npmInstall(serviceDir, service.name, jobId, prodPackages);
      if (!prodInstall.success) return prodInstall;
    }

    if (devPackages.length > 0) {
      const devInstall = await this.runner.runCommand(
        'npm',
        ['install', '-D', ...devPackages],
        serviceDir,
        jobId,
        { timeout: this.runner.withMinimumTimeout(300000) }
      );
      if (!devInstall.success) return devInstall;
    }

    return { success: true };
  }

  async startWorkspaceApps(jobId, workspaceDir, plan) {
    const frontendPort = plan.frontend?.port || 5173;
    const allPorts = [...plan.services.map((service) => service.port), frontendPort, 8080];
    for (const port of allPorts) {
      await this.runner.killPort(port, jobId);
    }

    const runningServices = [];
    for (const service of plan.services) {
      const serviceDir = path.join(workspaceDir, service.name);
      if (!await fs.pathExists(path.join(serviceDir, 'package.json'))) {
        continue;
      }
      const started = await this.runner.startService(serviceDir, service.name, service.port, jobId);
      if (started.success) {
        runningServices.push({ name: service.name, port: service.port, url: started.url });
      }
    }

    const frontendDir = path.join(workspaceDir, 'frontend');
    let frontendUrl = '';
    if (await fs.pathExists(path.join(frontendDir, 'package.json'))) {
      const frontendStart = await this.runner.startService(frontendDir, 'frontend', frontendPort, jobId, { useDevMode: true });
      frontendUrl = frontendStart.success ? frontendStart.url : '';
    }

    const gatewayDir = path.join(workspaceDir, 'gateway');
    let gatewayUrl = '';
    if (await fs.pathExists(path.join(gatewayDir, 'package.json'))) {
      await this.runner.npmInstall(gatewayDir, 'gateway', jobId);
      const gatewayStart = await this.runner.startService(gatewayDir, 'gateway', 8080, jobId);
      gatewayUrl = gatewayStart.success ? gatewayStart.url : '';
    }

    return {
      gateway: gatewayUrl || 'http://localhost:8080',
      frontend: frontendUrl || `http://localhost:${frontendPort}`,
      services: runningServices.reduce((result, service) => {
        result[service.name] = service.url;
        return result;
      }, {}),
      apiRoutes: plan.gateway?.routes?.map((route) => ({
        prefix: route.prefix,
        target: route.target,
        viaGateway: `${gatewayUrl || 'http://localhost:8080'}${route.prefix}`
      })) || []
    };
  }

  prefixServiceFiles(serviceName, files) {
    return files.map((file) => ({
      ...file,
      path: file.path.startsWith(`${serviceName}/`) ? file.path : `${serviceName}/${file.path}`
    }));
  }

  async countThreadMessages(threadId) {
    const Message = require('../models/Message');
    return Message.countDocuments({ threadId });
  }

  async setStage(jobId, status, progress, agent) {
    await this.updateGeneration(jobId, {
      status,
      stage: status,
      progress,
      currentAgent: agent
    });
    this.io.to(jobId).emit('agent:working', {
      agent,
      message: `${agent} is handling the ${status} stage`
    });
    this.io.to(jobId).emit('status:update', { status, progress, agent });
  }

  async recordStep(jobId, stepResults, step) {
    stepResults.push({
      ...step,
      startedAt: step.startedAt || new Date(),
      completedAt: step.completedAt || new Date()
    });
    await Generation.updateOne({ jobId }, { stepResults });
  }

  async updateGeneration(jobId, updates) {
    await Generation.updateOne({ jobId }, { $set: updates });
  }

  async log(jobId, agent, message, type = 'info') {
    this.io.to(jobId).emit('log', {
      level: type,
      agent,
      message,
      timestamp: new Date().toISOString()
    });
    await Generation.updateOne(
      { jobId },
      { $push: { logs: { agent, message, type, timestamp: new Date() } } }
    );
  }
}

module.exports = WorkflowOrchestrator;
