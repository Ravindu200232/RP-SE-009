const path = require('path');
const DeveloperAgent = require('./developerAgent');
const artifactValidator = require('./artifactValidator');

class WorkflowDeveloperService {
  constructor(ollamaService, io) {
    this.io = io;
    this.ollama = ollamaService;
    this.legacyDeveloper = new DeveloperAgent(ollamaService, io);
  }

  async generateService(jobId, service, plan, context = {}, onToken) {
    const packageJson = await this.legacyDeveloper.generatePackageJson(jobId, service, plan, onToken, context);
    const sourceFiles = await this.legacyDeveloper.generateSourceFiles(jobId, service, plan, onToken, context);
    let files = this.ensureDeterministicArtifacts(service, plan, sourceFiles);
    let validation = this.validateGeneratedService(service, files, packageJson);

    if (!validation.ok && validation.audit.missingFiles.length > 0) {
      const targetedFiles = await this.generateMissingArtifacts(
        jobId,
        service,
        plan,
        validation.audit.missingFiles,
        context,
        onToken
      );
      files = this.mergeFiles(files, targetedFiles);
      files = this.ensureDeterministicArtifacts(service, plan, files);
      validation = this.validateGeneratedService(service, files, packageJson);
    }

    if (!validation.ok) {
      const repaired = await this.repairCriticalIssues(
        jobId,
        service,
        plan,
        files,
        packageJson,
        validation,
        context,
        onToken
      );
      files = repaired.files;
      validation = repaired.validation;
    }

    return {
      packageJson,
      files,
      validation
    };
  }

  validateGeneratedService(service, files, packageJson) {
    return artifactValidator.validateService(
      service,
      this.prefixServiceFiles(service.name, files),
      packageJson
    );
  }

  async generateMissingArtifacts(jobId, service, plan, missingFiles, context = {}, onToken) {
    const generated = [];
    for (const missingFile of missingFiles) {
      const result = await this.generateArtifact(jobId, service, plan, missingFile, context, onToken);
      generated.push(...result);
    }
    return generated;
  }

  async generateArtifact(jobId, service, plan, targetFile, context = {}, onToken) {
    const prompt = `Generate ONLY one file for this MERN microservice.

Service: ${service.name}
Description: ${service.description}
Target file: ${targetFile}
Entities: ${(service.entities || []).join(', ') || 'None'}
Routes:
${(service.routes || []).map((route) => `- ${route.method} ${route.path}`).join('\n') || '- none'}

Instruction chain:
${context.instructions?.mergedText || 'Use Route -> Controller -> Service -> Model'}

Compacted context:
${context.compactedContext?.repairPrompt || 'No compacted context.'}

Current project state:
${context.memory?.files?.['PROJECT_STATE.md'] || 'No existing project state.'}

Rules:
- Generate ONLY ${targetFile}
- Use ES modules for generated backend service files
- Internal services must be referenced via *_SERVICE_URL env vars, not npm packages
- Return the file using ===FILE: ${targetFile}=== ... ===END===`;

    const response = await this.ollama.generate(
      jobId,
      prompt,
      `You are a senior full-stack developer. Return exactly one complete file in ===FILE=== format.`,
      'developer',
      `artifact_${service.name}_${targetFile}`,
      onToken,
      context.messageContext
    );

    const files = this.legacyDeveloper.extractFiles(response, service.name)
      .filter((file) => file.path === targetFile || file.path.endsWith(`/${targetFile}`) || file.path.endsWith(targetFile));

    if (files.length > 0) {
      return files;
    }

    if (targetFile === '.env.example') {
      return [{ path: '.env.example', content: this.buildEnvExample(service, plan), service: service.name }];
    }

    return [];
  }

  async repairCriticalIssues(jobId, service, plan, files, packageJson, validation, context = {}, onToken) {
    let repairedFiles = [...files];
    let currentValidation = validation;

    for (let attempt = 0; attempt < 2 && !currentValidation.ok; attempt += 1) {
      let patchFiles = this.buildRepairArtifacts(service, plan, repairedFiles, currentValidation);

      if (patchFiles.length === 0) {
        patchFiles = await this.generateIssueRepairs(
          jobId,
          service,
          plan,
          currentValidation,
          context,
          onToken
        );
      }

      if (patchFiles.length === 0) {
        break;
      }

      repairedFiles = this.mergeFiles(repairedFiles, patchFiles);
      repairedFiles = this.ensureDeterministicArtifacts(service, plan, repairedFiles);
      currentValidation = this.validateGeneratedService(service, repairedFiles, packageJson);
    }

    return {
      files: repairedFiles,
      validation: currentValidation
    };
  }

  buildRepairArtifacts(service, plan, files, validation) {
    const repaired = [];
    const fileMap = new Map(files.map((file) => [this.normalizePath(file.path), file]));

    for (const missingFile of validation.audit?.missingFiles || []) {
      const synthetic = this.buildRequiredArtifact(this.normalizePath(missingFile), service, plan, fileMap);
      if (synthetic) {
        repaired.push(synthetic);
      }
    }

    for (const issue of validation.issues || []) {
      if (issue.code === 'unresolved-import') {
        repaired.push(...this.buildArtifactsForImportIssue(service, plan, fileMap, issue.message));
      }

      if (issue.code === 'missing-model-file') {
        repaired.push(...this.ensureEntityModelArtifacts(service, fileMap));
      }

      if (issue.code === 'missing-json-middleware') {
        const serverFile = fileMap.get('Server.js') || fileMap.get('server.js');
        if (serverFile) {
          repaired.push({
            ...serverFile,
            content: this.injectJsonMiddleware(serverFile.content || '')
          });
        }
      }
    }

    return this.dedupePatchFiles(repaired);
  }

  async generateIssueRepairs(jobId, service, plan, validation, context = {}, onToken) {
    const repairs = [];
    const targetedFiles = new Set(validation.audit?.missingFiles || []);

    for (const issue of validation.issues || []) {
      if (issue.code !== 'unresolved-import') {
        continue;
      }

      const parsed = this.parseImportIssue(issue.message);
      if (!parsed) {
        continue;
      }

      targetedFiles.add(this.resolveImportTargetFile(parsed.importer, parsed.request));
    }

    for (const targetFile of targetedFiles) {
      const generated = await this.generateArtifact(jobId, service, plan, targetFile, context, onToken);
      repairs.push(...generated);
    }

    return repairs;
  }

  ensureDeterministicArtifacts(service, plan, files) {
    let merged = this.mergeFiles(files, [
      {
        path: '.env.example',
        content: this.buildEnvExample(service, plan),
        service: service.name
      },
      {
        path: 'controllers/authController.js',
        content: this.buildAuthController(),
        service: service.name
      },
      {
        path: 'config/env.js',
        content: this.buildEnvModule(service, plan),
        service: service.name
      }
    ]);

    merged = this.stripMarkdownFences(merged);
    merged = this.addCanonicalAliasFiles(service, plan, merged);
    merged = this.rewriteBrokenImports(merged);

    return merged;
  }

  buildEnvExample(service, plan) {
    const serviceEnv = (service.serviceDependencies || []).map((dep) => {
      const target = (plan.services || []).find((candidate) => candidate.name === dep);
      const key = dep.replace(/-service$/, '').replace(/-/g, '_').toUpperCase();
      return `${key}_SERVICE_URL=${target ? `http://localhost:${target.port}` : 'http://localhost:3001'}`;
    }).join('\n');

    return [
      `PORT=${service.port}`,
      `MONGO_URL=${plan.sharedEnv?.MONGO_URL || `mongodb://localhost:27017/${plan.projectName || 'generated-app'}`}`,
      `SEKRET_KEY=${plan.sharedEnv?.SEKRET_KEY || 'shared_secret_key_change_in_production'}`,
      `SERVER_URL=http://localhost:${service.port}`,
      serviceEnv
    ].filter(Boolean).join('\n') + '\n';
  }

  buildAuthController() {
    return `export function checkHasAccount(req) {\n  return Boolean(req.user);\n}\n\nexport function checkAdmin(req) {\n  return req.user?.role === 'admin';\n}\n\nexport function checkCustomer(req) {\n  return req.user?.role === 'customer';\n}\n`;
  }

  buildEnvModule(service, plan) {
    const envVars = ['PORT', 'MONGO_URL', 'SEKRET_KEY', 'SERVER_URL', ...(service.envVars || [])]
      .map((envVar) => String(envVar || '').trim())
      .filter(Boolean);
    const uniqueEnvVars = Array.from(new Set(envVars));

    const exports = uniqueEnvVars.map((envVar) => `export const ${envVar} = process.env.${envVar};`).join('\n');
    const defaults = uniqueEnvVars.map((envVar) => `  ${envVar},`).join('\n');

    return `import dotenv from "dotenv";

dotenv.config();

${exports}

export default {
${defaults}
};
`;
  }

  mergeFiles(existingFiles, newFiles) {
    const map = new Map(existingFiles.map((file) => [file.path, file]));
    for (const file of newFiles) {
      if (file && file.path) {
        map.set(file.path, file);
      }
    }
    return Array.from(map.values());
  }

  prefixServiceFiles(serviceName, files) {
    return files.map((file) => ({
      ...file,
      path: file.path.startsWith(`${serviceName}/`) ? file.path : `${serviceName}/${file.path}`
    }));
  }

  stripMarkdownFences(files) {
    return files.map((file) => ({
      ...file,
      content: this.stripSingleMarkdownFence(file.content || '')
    }));
  }

  stripSingleMarkdownFence(content = '') {
    const trimmed = String(content || '').trim();
    const fencedMatch = trimmed.match(/^```[a-zA-Z0-9_-]*\s*\r?\n([\s\S]*?)\r?\n```$/);
    if (fencedMatch) {
      return fencedMatch[1].trim();
    }
    return trimmed;
  }

  addCanonicalAliasFiles(service, plan, files) {
    let merged = [...files];
    const fileMap = new Map(merged.map((file) => [this.normalizePath(file.path), file]));

    for (const entity of service.entities || []) {
      const canonicalModel = `models/${this.toKebab(entity)}.model.js`;
      const actualModel = this.findAliasSource(fileMap, 'models', entity);
      if (actualModel && actualModel !== canonicalModel && !fileMap.has(canonicalModel)) {
        merged = this.mergeFiles(merged, [{
          path: canonicalModel,
          content: `export { default } from "${this.relativeImport(canonicalModel, actualModel)}";`,
          service: service.name
        }]);
        fileMap.set(canonicalModel, merged.find((file) => this.normalizePath(file.path) === canonicalModel));
      }

      const canonicalService = `services/${this.toKebab(entity)}.service.js`;
      const actualService = this.findAliasSource(fileMap, 'services', entity);
      if (actualService && actualService !== canonicalService && !fileMap.has(canonicalService)) {
        const importPath = this.relativeImport(canonicalService, actualService);
        merged = this.mergeFiles(merged, [{
          path: canonicalService,
          content: `export * from "${importPath}";`,
          service: service.name
        }]);
        fileMap.set(canonicalService, merged.find((file) => this.normalizePath(file.path) === canonicalService));
      }
    }

    for (const route of service.routes || []) {
      const resource = this.routeResource(route.path);

      const canonicalController = `controllers/${resource}.controller.js`;
      const actualController = this.findAliasSource(fileMap, 'controllers', resource);
      if (actualController && actualController !== canonicalController && !fileMap.has(canonicalController)) {
        const importPath = this.relativeImport(canonicalController, actualController);
        merged = this.mergeFiles(merged, [{
          path: canonicalController,
          content: `export * from "${importPath}";`,
          service: service.name
        }]);
        fileMap.set(canonicalController, merged.find((file) => this.normalizePath(file.path) === canonicalController));
      }

      const canonicalRoute = `routes/${resource}.routes.js`;
      const actualRoute = this.findAliasSource(fileMap, 'routes', resource);
      if (actualRoute && actualRoute !== canonicalRoute && !fileMap.has(canonicalRoute)) {
        const importPath = this.relativeImport(canonicalRoute, actualRoute);
        merged = this.mergeFiles(merged, [{
          path: canonicalRoute,
          content: `export { default } from "${importPath}";\nexport * from "${importPath}";`,
          service: service.name
        }]);
        fileMap.set(canonicalRoute, merged.find((file) => this.normalizePath(file.path) === canonicalRoute));
      }
    }

    merged = this.ensureRequiredArtifacts(service, plan, merged);

    return merged;
  }

  ensureRequiredArtifacts(service, plan, files) {
    let merged = [...files];
    let fileMap = new Map(merged.map((file) => [this.normalizePath(file.path), file]));

    for (const expectedFile of service.requiredFiles || []) {
      const normalizedExpected = this.normalizePath(expectedFile);
      if (!normalizedExpected || fileMap.has(normalizedExpected)) {
        continue;
      }

      const synthetic = this.buildRequiredArtifact(normalizedExpected, service, plan, fileMap);
      if (!synthetic) {
        continue;
      }

      merged = this.mergeFiles(merged, [synthetic]);
      fileMap = new Map(merged.map((file) => [this.normalizePath(file.path), file]));
    }

    return merged;
  }

  buildRequiredArtifact(expectedFile, service, plan, fileMap) {
    const dir = path.posix.dirname(expectedFile);
    const routeNames = (service.routes || []).flatMap((route) => this.routeNameVariants(route.path));

    if (dir === 'routes') {
      const source = this.findAliasSource(fileMap, 'routes', [expectedFile, ...routeNames]);
      if (source && source !== expectedFile) {
        const importPath = this.relativeImport(expectedFile, source);
        return {
          path: expectedFile,
          content: `export { default } from "${importPath}";\nexport * from "${importPath}";`,
          service: service.name
        };
      }
    }

    if (dir === 'controllers') {
      const source = this.findAliasSource(fileMap, 'controllers', [expectedFile, ...routeNames]);
      if (source && source !== expectedFile) {
        const importPath = this.relativeImport(expectedFile, source);
        return {
          path: expectedFile,
          content: `export * from "${importPath}";`,
          service: service.name
        };
      }
    }

    if (dir === 'models') {
      const source = this.findAliasSource(fileMap, 'models', [expectedFile, ...(service.entities || [])]);
      if (source && source !== expectedFile) {
        return {
          path: expectedFile,
          content: `export { default } from "${this.relativeImport(expectedFile, source)}";`,
          service: service.name
        };
      }
    }

    if (dir === 'services') {
      const source = this.findAliasSource(fileMap, 'services', [expectedFile, ...(service.entities || []), ...routeNames]);
      if (source && source !== expectedFile) {
        return {
          path: expectedFile,
          content: `export * from "${this.relativeImport(expectedFile, source)}";`,
          service: service.name
        };
      }

      const modelSource = this.findAliasSource(fileMap, 'models', [expectedFile, ...(service.entities || []), ...routeNames]);
      if (modelSource) {
        return {
          path: expectedFile,
          content: this.buildServiceScaffold(expectedFile, modelSource),
          service: service.name
        };
      }
    }

    return null;
  }

  buildServiceScaffold(servicePath, modelPath) {
    const stem = this.baseStem(path.posix.basename(servicePath, '.js'));
    const modelImport = this.relativeImport(servicePath, modelPath);
    const modelName = this.toPascal(stem || 'item');
    const pluralName = this.toCamel(this.pluralizeStem(stem || 'item'));
    const singularName = this.toCamel(stem || 'item');

    return `import ${modelName} from "${modelImport}";

export async function list${this.toPascal(pluralName)}(filter = {}) {
  return ${modelName}.find(filter);
}

export async function get${this.toPascal(singularName)}ById(id) {
  return ${modelName}.findById(id);
}

export async function create${this.toPascal(singularName)}(payload) {
  return ${modelName}.create(payload);
}

export async function update${this.toPascal(singularName)}(id, payload) {
  return ${modelName}.findByIdAndUpdate(id, payload, { new: true });
}

export async function delete${this.toPascal(singularName)}(id) {
  return ${modelName}.findByIdAndDelete(id);
}

export default {
  list${this.toPascal(pluralName)},
  get${this.toPascal(singularName)}ById,
  create${this.toPascal(singularName)},
  update${this.toPascal(singularName)},
  delete${this.toPascal(singularName)}
};
`;
  }

  buildArtifactsForImportIssue(service, plan, fileMap, message = '') {
    const parsed = this.parseImportIssue(message);
    if (!parsed) {
      return [];
    }

    const targetFile = this.resolveImportTargetFile(parsed.importer, parsed.request);
    if (!targetFile) {
      return [];
    }

    const existing = fileMap.get(this.normalizePath(targetFile));
    if (existing) {
      return [];
    }

    if (this.normalizePath(targetFile) === 'config/env.js') {
      return [{
        path: 'config/env.js',
        content: this.buildEnvModule(service, plan),
        service: service.name
      }];
    }

    const dir = path.posix.dirname(targetFile);
    if (dir === 'models') {
      const source = this.findAliasSource(fileMap, 'models', [targetFile, ...(service.entities || [])]);
      if (source) {
        return [{
          path: targetFile,
          content: `export { default } from "${this.relativeImport(targetFile, source)}";`,
          service: service.name
        }];
      }

      const inferredEntity = this.inferEntityName(targetFile, service.entities || []);
      return [{
        path: targetFile,
        content: this.buildModelScaffold(targetFile, inferredEntity),
        service: service.name
      }];
    }

    if (dir === 'services') {
      const source = this.findAliasSource(fileMap, 'services', [targetFile, ...(service.entities || [])]);
      if (source) {
        return [{
          path: targetFile,
          content: `export * from "${this.relativeImport(targetFile, source)}";`,
          service: service.name
        }];
      }

      const modelSource = this.findAliasSource(fileMap, 'models', [targetFile, ...(service.entities || [])]);
      if (modelSource) {
        return [{
          path: targetFile,
          content: this.buildServiceScaffold(targetFile, modelSource),
          service: service.name
        }];
      }
    }

    if (dir === 'controllers') {
      const source = this.findAliasSource(fileMap, 'controllers', [targetFile, ...((service.routes || []).map((route) => this.routeResource(route.path)))]);
      if (source) {
        return [{
          path: targetFile,
          content: `export * from "${this.relativeImport(targetFile, source)}";`,
          service: service.name
        }];
      }
    }

    if (dir === 'routes') {
      const source = this.findAliasSource(fileMap, 'routes', [targetFile, ...((service.routes || []).map((route) => this.routeResource(route.path)))]);
      if (source) {
        return [{
          path: targetFile,
          content: `export { default } from "${this.relativeImport(targetFile, source)}";\nexport * from "${this.relativeImport(targetFile, source)}";`,
          service: service.name
        }];
      }
    }

    return [];
  }

  ensureEntityModelArtifacts(service, fileMap) {
    const repairs = [];
    for (const entity of service.entities || []) {
      const canonicalModel = `models/${this.toKebab(entity)}.model.js`;
      if (fileMap.has(canonicalModel)) {
        continue;
      }

      const source = this.findAliasSource(fileMap, 'models', entity);
      if (source) {
        repairs.push({
          path: canonicalModel,
          content: `export { default } from "${this.relativeImport(canonicalModel, source)}";`,
          service: service.name
        });
        continue;
      }

      repairs.push({
        path: canonicalModel,
        content: this.buildModelScaffold(canonicalModel, entity),
        service: service.name
      });
    }

    return repairs;
  }

  buildModelScaffold(modelPath, entityName = 'Item') {
    const modelName = this.toPascal(entityName || this.baseStem(path.posix.basename(modelPath, '.js')) || 'Item');

    return `import mongoose from "mongoose";

const ${this.toCamel(modelName)}Schema = new mongoose.Schema({}, { timestamps: true });

export default mongoose.model("${modelName}", ${this.toCamel(modelName)}Schema);
`;
  }

  injectJsonMiddleware(serverContent = '') {
    const content = String(serverContent || '');
    if (/express\.json\(|bodyParser\.json\(/.test(content)) {
      return content;
    }

    if (content.includes('app.use(cors())')) {
      return content.replace('app.use(cors())', 'app.use(cors())\napp.use(express.json())');
    }

    if (content.includes('const app = express()')) {
      return content.replace('const app = express()', 'const app = express()\napp.use(express.json())');
    }

    return `import express from "express";\n${content}`;
  }

  dedupePatchFiles(files = []) {
    const map = new Map();
    for (const file of files) {
      const normalized = this.normalizePath(file?.path);
      if (!normalized) {
        continue;
      }
      map.set(normalized, { ...file, path: normalized });
    }
    return Array.from(map.values());
  }

  parseImportIssue(message = '') {
    const match = String(message || '').match(/Import "([^"]+)" in ([^ ]+) does not resolve to a generated file\./);
    if (!match) {
      return null;
    }

    return {
      request: match[1],
      importer: this.normalizePath(match[2])
    };
  }

  resolveImportTargetFile(importer = '', request = '') {
    const importerDir = path.posix.dirname(this.normalizePath(importer));
    const base = this.normalizePath(path.posix.join(importerDir, request));
    if (path.posix.extname(base)) {
      return base;
    }
    return `${base}.js`;
  }

  inferEntityName(targetFile, knownEntities = []) {
    const stem = this.baseStem(path.posix.basename(this.normalizePath(targetFile), '.js'));
    const inferred = this.toPascal(stem || 'Item');
    return knownEntities.find((entity) => this.toPascal(entity) === inferred) || inferred;
  }

  rewriteBrokenImports(files) {
    const normalizedPaths = files.map((file) => this.normalizePath(file.path));
    const normalizedSet = new Set(normalizedPaths.map((filePath) => filePath.toLowerCase()));

    return files.map((file) => {
      const relativePath = this.normalizePath(file.path);
      const rewritten = this.stripSingleMarkdownFence(file.content || '').replace(
        /(import\s+[^'"]*?from\s+['"])([^'"]+)(['"])|(require\(\s*['"])([^'"]+)(['"]\s*\))/g,
        (match, importPrefix, importRequest, importSuffix, requirePrefix, requireRequest, requireSuffix) => {
          const request = importRequest || requireRequest;
          if (!request || (!request.startsWith('.') && !request.startsWith('/'))) {
            return match;
          }

          const resolvedImport = this.resolveBestImportPath(relativePath, request, normalizedSet);
          if (!resolvedImport || resolvedImport === request) {
            return match;
          }

          if (importRequest) {
            return `${importPrefix}${resolvedImport}${importSuffix}`;
          }

          return `${requirePrefix}${resolvedImport}${requireSuffix}`;
        }
      );

      return {
        ...file,
        content: rewritten
      };
    });
  }

  resolveBestImportPath(fromPath, request, actualPathSet) {
    const fromDir = path.posix.dirname(this.normalizePath(fromPath));
    const normalizedRequest = request.replace(/\\/g, '/');
    const base = path.posix.normalize(path.posix.join(fromDir, normalizedRequest));
    const matches = this.importCandidates(base).filter((candidate) => actualPathSet.has(candidate.toLowerCase()));

    if (matches.length === 0) {
      return null;
    }

    const bestMatch = matches.sort((left, right) => left.length - right.length)[0];
    return this.relativeImport(fromPath, bestMatch);
  }

  importCandidates(basePath) {
    const normalized = this.normalizePath(basePath);
    const candidates = new Set([normalized]);
    const ext = path.posix.extname(normalized).toLowerCase();
    const dir = path.posix.dirname(normalized);
    const baseName = ext ? path.posix.basename(normalized, ext) : path.posix.basename(normalized);

    if (!ext || ['.model', '.service', '.controller', '.route', '.routes'].includes(ext)) {
      candidates.add(`${normalized}.js`);
      candidates.add(`${normalized}.jsx`);
      candidates.add(`${normalized}.json`);
      candidates.add(path.posix.join(normalized, 'index.js'));
    }

    if (['models', 'services', 'controllers', 'routes'].includes(dir)) {
      const stem = this.baseStem(baseName);
      const variants = new Set([
        stem,
        stem.toLowerCase(),
        this.toKebab(stem),
        this.toCamel(stem),
        this.toPascal(stem)
      ]);

      if (stem.toLowerCase().endsWith('s')) {
        const singular = stem.slice(0, -1);
        variants.add(singular);
        variants.add(this.toKebab(singular));
        variants.add(this.toCamel(singular));
        variants.add(this.toPascal(singular));
      } else if (stem) {
        const plural = `${stem}s`;
        variants.add(plural);
        variants.add(this.toKebab(plural));
        variants.add(this.toCamel(plural));
        variants.add(this.toPascal(plural));
      }

      for (const variant of variants) {
        if (!variant) continue;
        if (dir === 'models') {
          candidates.add(`models/${variant}.js`);
          candidates.add(`models/${variant}.model.js`);
          candidates.add(`models/${variant}Model.js`);
        } else if (dir === 'services') {
          candidates.add(`services/${variant}.js`);
          candidates.add(`services/${variant}.service.js`);
          candidates.add(`services/${variant}Service.js`);
        } else if (dir === 'controllers') {
          candidates.add(`controllers/${variant}.js`);
          candidates.add(`controllers/${variant}.controller.js`);
          candidates.add(`controllers/${variant}Controller.js`);
        } else if (dir === 'routes') {
          candidates.add(`routes/${variant}.js`);
          candidates.add(`routes/${variant}.routes.js`);
          candidates.add(`routes/${variant}Routes.js`);
        }
      }
    }

    return Array.from(candidates).map((candidate) => this.normalizePath(candidate));
  }

  findAliasSource(fileMap, dir, rawName) {
    const rawNames = Array.isArray(rawName) ? rawName : [rawName];
    const variants = new Set();

    for (const name of rawNames) {
      const normalizedName = this.normalizePath(String(name || ''));
      const stem = this.baseStem(path.posix.basename(normalizedName, path.posix.extname(normalizedName)) || normalizedName);
      variants.add(this.toKebab(stem));
      variants.add(this.toCamel(stem));
      variants.add(this.toPascal(stem));
      variants.add(String(stem || '').toLowerCase());
      if (normalizedName.includes('/')) {
        variants.add(path.posix.basename(normalizedName));
        variants.add(path.posix.basename(normalizedName, '.js'));
      }
    }

    for (const variant of variants) {
      if (!variant) continue;

      const candidates = dir === 'models'
        ? [`models/${variant}.model.js`, `models/${variant}Model.js`, `models/${variant}.js`]
        : dir === 'services'
          ? [`services/${variant}.service.js`, `services/${variant}Service.js`, `services/${variant}.js`]
          : dir === 'controllers'
            ? [`controllers/${variant}.controller.js`, `controllers/${variant}Controller.js`, `controllers/${variant}.js`]
            : [`routes/${variant}.routes.js`, `routes/${variant}Routes.js`, `routes/${variant}.js`];

      for (const candidate of candidates) {
        if (fileMap.has(candidate)) {
          return candidate;
        }
      }
    }

    return null;
  }

  relativeImport(fromPath, toPath) {
    const fromDir = path.posix.dirname(this.normalizePath(fromPath));
    let relative = path.posix.relative(fromDir, this.normalizePath(toPath));
    if (!relative.startsWith('.')) {
      relative = `./${relative}`;
    }
    return relative.replace(/\\/g, '/');
  }

  routeResource(routePath = '') {
    const parts = String(routePath).split('/').filter(Boolean);
    const resource = parts[2] || parts[parts.length - 1] || 'resource';
    return this.toKebab(resource.replace(/:.*$/, '').replace(/[^a-zA-Z0-9-]/g, '') || 'resource');
  }

  routeNameVariants(routePath = '') {
    const parts = String(routePath).split('/').filter(Boolean).slice(2).map((part) => part.replace(/:.*$/, ''));
    if (parts.length === 0) {
      return ['resource'];
    }

    const variants = new Set();
    variants.add(this.toKebab(parts[0]));
    variants.add(this.toKebab(parts[parts.length - 1]));
    variants.add(this.toKebab(parts.join('-')));
    return Array.from(variants).filter(Boolean);
  }

  normalizePath(filePath = '') {
    return String(filePath || '').replace(/\\/g, '/').replace(/^\.\/+/, '').trim();
  }

  toWords(value = '') {
    return String(value || '')
      .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
      .replace(/[^a-zA-Z0-9]+/g, ' ')
      .trim()
      .split(/\s+/)
      .filter(Boolean);
  }

  toKebab(value = '') {
    return this.toWords(value).map((part) => part.toLowerCase()).join('-') || String(value || '').toLowerCase();
  }

  toCamel(value = '') {
    const words = this.toWords(value).map((part) => part.toLowerCase());
    if (words.length === 0) return '';
    return words[0] + words.slice(1).map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join('');
  }

  toPascal(value = '') {
    return this.toWords(value)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
      .join('');
  }

  baseStem(value = '') {
    return String(value || '')
      .replace(/\.model$/i, '')
      .replace(/\.service$/i, '')
      .replace(/\.controller$/i, '')
      .replace(/\.routes?$/i, '')
      .replace(/model$/i, '')
      .replace(/service$/i, '')
      .replace(/controller$/i, '')
      .replace(/routes?$/i, '');
  }

  pluralizeStem(value = '') {
    const words = this.toWords(value);
    if (words.length === 0) return value;
    const last = words[words.length - 1];
    words[words.length - 1] = last.endsWith('s') ? last : `${last}s`;
    return words.join(' ');
  }

  async generateFrontend(jobId, plan, onToken) {
    return this.legacyDeveloper.generateViteFrontend(jobId, plan, onToken);
  }

  generateGateway(plan) {
    return this.legacyDeveloper.generateGateway(plan);
  }
}

module.exports = WorkflowDeveloperService;
