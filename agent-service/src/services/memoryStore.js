const fs = require('fs-extra');
const path = require('path');

const MEMORY_FILES = [
  'PROJECT_STATE.md',
  'FILE_INDEX.json',
  'SERVICE_MAP.json',
  'DEPENDENCY_RULES.json',
  'SERVICE_COMMUNICATION.md',
  'FAILURE_PATTERNS.json',
  'SESSION_STATE.json'
];

class MemoryStore {
  memoryDir(workspaceDir) {
    return path.join(workspaceDir, 'AI_MEMORY');
  }

  async ensure(workspaceDir) {
    await fs.ensureDir(this.memoryDir(workspaceDir));
  }

  async read(workspaceDir) {
    await this.ensure(workspaceDir);
    const files = {};
    const parsed = {};

    for (const fileName of MEMORY_FILES) {
      const absolutePath = path.join(this.memoryDir(workspaceDir), fileName);
      if (!await fs.pathExists(absolutePath)) {
        files[fileName] = '';
        continue;
      }

      const content = await fs.readFile(absolutePath, 'utf8');
      files[fileName] = content;

      if (fileName.endsWith('.json') && content.trim()) {
        try {
          parsed[fileName] = JSON.parse(content);
        } catch {
          parsed[fileName] = null;
        }
      }
    }

    return {
      files,
      parsed,
      summary: this.createSummary(files, parsed)
    };
  }

  createSummary(files, parsed) {
    return {
      fileNames: Object.keys(files),
      hasProjectState: Boolean(files['PROJECT_STATE.md']),
      indexedFiles: Array.isArray(parsed['FILE_INDEX.json']) ? parsed['FILE_INDEX.json'].length : 0,
      servicesTracked: parsed['SERVICE_MAP.json'] ? Object.keys(parsed['SERVICE_MAP.json']).length : 0,
      failurePatterns: Array.isArray(parsed['FAILURE_PATTERNS.json']) ? parsed['FAILURE_PATTERNS.json'].length : 0,
      currentStage: parsed['SESSION_STATE.json']?.currentStage || 'idle'
    };
  }

  async updateWorkspaceMemory({
    workspace,
    plan,
    index,
    audit = {},
    generation,
    thread,
    failurePatterns = []
  }) {
    if (!workspace) {
      throw new Error('updateWorkspaceMemory requires a workspace');
    }

    await this.ensure(workspace.appDir);

    const projectState = this.buildProjectState(plan, audit, generation, thread);
    const fileIndex = (index?.files || []).map((file) => ({
      path: file.path,
      kind: file.kind,
      service: file.service,
      imports: file.imports
    }));
    const serviceMap = this.buildServiceMap(plan);
    const dependencyRules = this.buildDependencyRules(plan);
    const serviceCommunication = this.buildServiceCommunication(plan);
    const mergedFailures = await this.mergeFailurePatterns(workspace.appDir, failurePatterns);

    const payloads = {
      'PROJECT_STATE.md': projectState,
      'FILE_INDEX.json': JSON.stringify(fileIndex, null, 2),
      'SERVICE_MAP.json': JSON.stringify(serviceMap, null, 2),
      'DEPENDENCY_RULES.json': JSON.stringify(dependencyRules, null, 2),
      'SERVICE_COMMUNICATION.md': serviceCommunication,
      'FAILURE_PATTERNS.json': JSON.stringify(mergedFailures, null, 2)
    };

    for (const [fileName, content] of Object.entries(payloads)) {
      await fs.writeFile(path.join(this.memoryDir(workspace.appDir), fileName), content, 'utf8');
    }

    return this.read(workspace.appDir);
  }

  buildProjectState(plan, audit, generation, thread) {
    const services = (plan?.services || []).map((service) => {
      const serviceAudit = audit?.services?.[service.name];
      const suffix = serviceAudit?.missingFiles?.length
        ? ` (missing: ${serviceAudit.missingFiles.join(', ')})`
        : '';
      return `- ${service.name}: port ${service.port}${suffix}`;
    }).join('\n');

    const pending = Object.entries(audit?.services || {})
      .filter(([, serviceAudit]) => serviceAudit.missingFiles && serviceAudit.missingFiles.length > 0)
      .map(([serviceName, serviceAudit]) => `- ${serviceName}: ${serviceAudit.missingFiles.join(', ')}`)
      .join('\n') || '- none';

    return `# PROJECT_STATE

Updated: ${new Date().toISOString()}
Thread: ${thread?.title || 'n/a'}
Task: ${generation?.task || 'Initial generation'}
Status: ${generation?.status || 'pending'}

## Stack
- ${plan?.projectName || 'generated-app'}
- ${plan?.description || 'No description provided'}
- MERN Stack Microservices

## Services
${services || '- none'}

## Pending
${pending}

## Naming Rules
- Backend flow: Route -> Controller -> Service -> Model
- Shared env vars: PORT, MONGO_URL, SEKRET_KEY, SERVER_URL
- Internal service URLs use *_SERVICE_URL env variables
`;
  }

  buildServiceMap(plan) {
    const result = {};

    for (const service of plan?.services || []) {
      result[service.name] = {
        port: service.port,
        entities: service.entities || [],
        controllers: service.controllers || [],
        routes: (service.routes || []).map((route) => ({
          method: route.method,
          path: route.path
        })),
        packageDependencies: service.packageDependencies || [],
        devDependencies: service.devDependencies || [],
        serviceDependencies: service.serviceDependencies || [],
        envVars: service.envVars || [],
        requiredFiles: service.requiredFiles || []
      };
    }

    return result;
  }

  buildDependencyRules(plan) {
    const rules = {};
    for (const service of plan?.services || []) {
      rules[service.name] = {
        packageDependencies: service.packageDependencies || [],
        devDependencies: service.devDependencies || [],
        forbiddenPackages: service.serviceDependencies || []
      };
    }
    return rules;
  }

  buildServiceCommunication(plan) {
    const sections = (plan?.services || []).map((service) => {
      const calls = (service.serviceCalls || []).map((call) => {
        return `- ${call.service}: ${call.envVar} -> ${call.baseUrl || 'unknown'}`;
      }).join('\n') || '- none';

      return `## ${service.name}
Base URL: http://localhost:${service.port}
Depends on:
${calls}`;
    });

    return `# SERVICE_COMMUNICATION

${sections.join('\n\n') || 'No service communication recorded yet.'}
`;
  }

  async mergeFailurePatterns(workspaceDir, failurePatterns = []) {
    const current = await this.read(workspaceDir);
    const existing = Array.isArray(current.parsed['FAILURE_PATTERNS.json'])
      ? current.parsed['FAILURE_PATTERNS.json']
      : [];

    const merged = [...existing];
    for (const pattern of failurePatterns) {
      if (!pattern || !pattern.code) continue;
      const alreadyExists = merged.some((item) => item.code === pattern.code && item.message === pattern.message);
      if (!alreadyExists) {
        merged.push(pattern);
      }
    }

    return merged;
  }
}

module.exports = new MemoryStore();
