const path = require('path');

class ArtifactValidator {
  buildAudit(service, files = []) {
    const serviceRoot = `${service.name}/`;
    const normalizedPaths = files.map((file) => this.normalizePath(file.path, serviceRoot));
    const normalizedPathSet = new Set(normalizedPaths.map((filePath) => filePath.toLowerCase()));
    const expectedFiles = service.requiredFiles || [];
    const matchedActualPaths = new Set();

    const foundFiles = expectedFiles.filter((filePath) => {
      const matched = this.findMatchingActualPath(filePath, normalizedPathSet);
      if (matched) {
        matchedActualPaths.add(matched);
        return true;
      }
      return false;
    });
    const missingFiles = expectedFiles.filter((filePath) => !foundFiles.includes(filePath));

    return {
      service: service.name,
      expectedFiles,
      foundFiles,
      missingFiles,
      extraFiles: normalizedPaths.filter((filePath) => !matchedActualPaths.has(filePath.toLowerCase()))
    };
  }

  validateService(service, files = [], packageJson = null) {
    const audit = this.buildAudit(service, files);
    const issues = [];
    const serviceFiles = files
      .filter((file) => this.normalizePath(file.path).startsWith(`${service.name}/`) || !file.path.includes('/'))
      .map((file) => ({
        ...file,
        relativePath: this.normalizePath(file.path, `${service.name}/`)
      }));

    if (serviceFiles.length === 0) {
      issues.push(this.issue('critical', 'zero-files-generated', 'No source files were generated for this service.'));
    }

    if (audit.missingFiles.length > 0) {
      issues.push(this.issue(
        'critical',
        'missing-required-files',
        `Missing required files: ${audit.missingFiles.join(', ')}`
      ));
    }

    if ((service.entities || []).length > 0 && !serviceFiles.some((file) => file.relativePath.includes('models/'))) {
      issues.push(this.issue('critical', 'missing-model-file', 'Entity-bearing services must generate at least one model file.'));
    }

    if (!serviceFiles.some((file) => file.relativePath === '.env.example' || file.relativePath === '.env')) {
      issues.push(this.issue('critical', 'missing-env-example', 'Service is missing .env.example.'));
    }

    const serverFile = serviceFiles.find((file) => file.relativePath.toLowerCase() === 'server.js');
    if (!serverFile) {
      issues.push(this.issue('critical', 'missing-server', 'Service is missing Server.js.'));
    } else if (!/express\.json\(|bodyParser\.json\(/.test(serverFile.content || '')) {
      issues.push(this.issue('high', 'missing-json-middleware', 'Server.js is missing JSON body parsing middleware.'));
    }

    if (packageJson) {
      const combinedDeps = {
        ...(packageJson.dependencies || {}),
        ...(packageJson.devDependencies || {})
      };
      const invalidDeps = Object.keys(combinedDeps).filter((dep) => /-service$/i.test(dep));
      if (invalidDeps.length > 0) {
        issues.push(this.issue(
          'critical',
          'internal-service-in-package-json',
          `Internal service names must not be installed from npm: ${invalidDeps.join(', ')}`
        ));
      }
    }

    const importIssues = this.validateImports(serviceFiles);
    issues.push(...importIssues);

    return {
      ok: issues.filter((issue) => issue.severity === 'critical').length === 0,
      issues,
      audit
    };
  }

  validateImports(files = []) {
    const issues = [];
    const fileSet = new Set(files.map((file) => String(file.relativePath || '').toLowerCase()));
    const importRegex = /import\s+[^'"]*['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\)/g;

    for (const file of files) {
      const content = file.content || '';
      let match;
      while ((match = importRegex.exec(content)) !== null) {
        const request = match[1] || match[2];
        if (!request || (!request.startsWith('.') && !request.startsWith('/'))) {
          continue;
        }

        const resolved = this.resolveImport(file.relativePath, request);
        if (!resolved.some((candidate) => fileSet.has(String(candidate || '').toLowerCase()))) {
          issues.push(this.issue(
            'critical',
            'unresolved-import',
            `Import "${request}" in ${file.relativePath} does not resolve to a generated file.`
          ));
        }
      }
    }

    return issues;
  }

  resolveImport(fromPath, request) {
    const fromDir = path.posix.dirname(fromPath);
    const base = path.posix.normalize(path.posix.join(fromDir, request));
    const candidates = [base];

    if (!path.posix.extname(base)) {
      candidates.push(`${base}.js`);
      candidates.push(`${base}.jsx`);
      candidates.push(`${base}.json`);
      candidates.push(path.posix.join(base, 'index.js'));
    }

    return Array.from(new Set(candidates));
  }

  findMatchingActualPath(expectedPath, actualPathSet) {
    const candidates = this.aliasCandidates(expectedPath);
    return candidates.find((candidate) => actualPathSet.has(candidate)) || null;
  }

  aliasCandidates(filePath = '') {
    const normalized = this.normalizePath(filePath).toLowerCase();
    const dir = path.posix.dirname(normalized);
    const ext = path.posix.extname(normalized);
    const baseName = ext ? path.posix.basename(normalized, ext) : path.posix.basename(normalized);

    const candidates = new Set([normalized]);

    if (normalized === 'controllers/authcontroller.js' || normalized === 'controllers/auth.controller.js') {
      candidates.add('controllers/authcontroller.js');
      candidates.add('controllers/auth.controller.js');
      return Array.from(candidates);
    }

    if (!['controllers', 'routes', 'models', 'services'].includes(dir)) {
      return Array.from(candidates);
    }

    const stem = this.baseStemForDir(baseName, dir);
    for (const variant of this.stemVariants(stem)) {
      if (dir === 'controllers') {
        candidates.add(`controllers/${variant}.controller.js`);
        candidates.add(`controllers/${variant}controller.js`);
        candidates.add(`controllers/${variant}.js`);
      } else if (dir === 'routes') {
        candidates.add(`routes/${variant}.routes.js`);
        candidates.add(`routes/${variant}routes.js`);
        candidates.add(`routes/${variant}.js`);
      } else if (dir === 'models') {
        candidates.add(`models/${variant}.model.js`);
        candidates.add(`models/${variant}model.js`);
        candidates.add(`models/${variant}.js`);
      } else if (dir === 'services') {
        candidates.add(`services/${variant}.service.js`);
        candidates.add(`services/${variant}service.js`);
        candidates.add(`services/${variant}.js`);
      }
    }

    return Array.from(candidates);
  }

  baseStemForDir(baseName, dir) {
    const withoutKnownSuffix = baseName
      .replace(/\.controller$/i, '')
      .replace(/controller$/i, '')
      .replace(/\.routes?$/i, '')
      .replace(/routes?$/i, '')
      .replace(/\.model$/i, '')
      .replace(/model$/i, '')
      .replace(/\.service$/i, '')
      .replace(/service$/i, '');

    return withoutKnownSuffix
      .replace(/[^a-z0-9]+/gi, '')
      .toLowerCase() || (dir === 'routes' ? 'resource' : 'item');
  }

  stemVariants(stem = '') {
    const variants = new Set([stem]);
    if (stem.endsWith('s') && stem.length > 1) {
      variants.add(stem.slice(0, -1));
    } else if (stem) {
      variants.add(`${stem}s`);
    }
    return Array.from(variants);
  }

  normalizePath(filePath, serviceRoot = '') {
    const normalized = String(filePath || '').replace(/\\/g, '/');
    if (serviceRoot && normalized.startsWith(serviceRoot)) {
      return normalized.slice(serviceRoot.length);
    }
    return normalized;
  }

  issue(severity, code, message) {
    return { severity, code, message };
  }
}

module.exports = new ArtifactValidator();
