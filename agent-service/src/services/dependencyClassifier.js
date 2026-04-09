const path = require('path');

const DEV_PACKAGES = new Set(['nodemon', 'jest', 'supertest', 'vitest', '@types/node']);

class DependencyClassifier {
  classifyPlan(plan) {
    if (!plan || !Array.isArray(plan.services)) {
      return plan;
    }

    const serviceNames = new Set(plan.services.map((service) => service.name));
    plan.services = plan.services.map((service) => this.classifyService(service, plan, serviceNames));

    if (plan.frontend) {
      plan.frontend.serviceUrls = (plan.services || []).map((service) => {
        const key = this.toServiceEnvKey(service.name, true);
        return `${key}=http://localhost:${service.port}`;
      });
    }

    return plan;
  }

  classifyService(service, plan, serviceNames) {
    const entities = this.unique([
      ...(service.entities || []),
      ...((service.models || []).map((model) => model.name))
    ]);

    const rawPackages = [
      ...(service.packageDependencies || []),
      ...(service.dependencies || [])
    ];
    const rawServiceDeps = [
      ...(service.serviceDependencies || []),
      ...(service.interServiceCalls || [])
    ];

    const packageDependencies = [];
    const devDependencies = [];
    const serviceDependencies = [];

    for (const dep of [...rawPackages, ...rawServiceDeps]) {
      if (!dep) continue;
      if (serviceNames.has(dep) || /-service$/i.test(dep)) {
        serviceDependencies.push(dep);
        continue;
      }

      if (DEV_PACKAGES.has(dep)) {
        devDependencies.push(dep);
        continue;
      }

      packageDependencies.push(dep);
    }

    if (!devDependencies.includes('nodemon')) {
      devDependencies.push('nodemon');
    }

    const controllers = this.unique(service.controllers || this.deriveControllerNames(service.routes || []));
    const requiredFiles = this.mergeRequiredFiles({
      ...service,
      entities,
      controllers
    });

    const envVars = this.unique([
      'PORT',
      'MONGO_URL',
      'SEKRET_KEY',
      'SERVER_URL',
      ...(serviceDependencies.map((dep) => this.toServiceEnvKey(dep)))
    ]);

    const serviceCalls = this.unique(serviceDependencies).map((dep) => {
      const target = (plan.services || []).find((candidate) => candidate.name === dep);
      return {
        service: dep,
        envVar: this.toServiceEnvKey(dep),
        baseUrl: target ? `http://localhost:${target.port}` : ''
      };
    });

    return {
      ...service,
      entities,
      controllers,
      packageDependencies: this.unique(packageDependencies),
      devDependencies: this.unique(devDependencies),
      serviceDependencies: this.unique(serviceDependencies),
      dependencies: this.unique(packageDependencies),
      interServiceCalls: this.unique(serviceDependencies),
      requiredFiles,
      envVars,
      serviceCalls
    };
  }

  deriveControllerNames(routes = []) {
    return routes.map((route) => {
      const resource = this.routeResource(route.path);
      const singular = resource.endsWith('s') ? resource.slice(0, -1) : resource;
      return `${singular}Controller`;
    });
  }

  deriveRequiredFiles(service) {
    const files = [
      'package.json',
      'Server.js',
      'DbConnection.js',
      '.env.example',
      'controllers/authController.js'
    ];

    for (const entity of service.entities || []) {
      const base = this.fileBaseName(entity);
      files.push(`models/${base}.model.js`);
      files.push(`services/${base}.service.js`);
    }

    for (const route of service.routes || []) {
      const resource = this.routeResource(route.path);
      files.push(`controllers/${resource}.controller.js`);
      files.push(`routes/${resource}.routes.js`);
    }

    return this.unique(files);
  }

  mergeRequiredFiles(service) {
    const derivedFiles = this.deriveRequiredFiles(service);
    const providedFiles = (service.requiredFiles || [])
      .map((filePath) => this.normalizeFilePath(filePath))
      .filter((filePath) => this.shouldKeepProvidedRequiredFile(filePath));

    return this.unique([...derivedFiles, ...providedFiles]);
  }

  shouldKeepProvidedRequiredFile(filePath = '') {
    const normalized = this.normalizeFilePath(filePath);
    if (!normalized) return false;

    const alwaysKeep = new Set([
      'package.json',
      'Server.js',
      'DbConnection.js',
      '.env',
      '.env.example',
      'controllers/authController.js',
      'controllers/auth.controller.js'
    ]);

    if (alwaysKeep.has(normalized)) {
      return true;
    }

    return !/^(models|services|controllers|routes)\//i.test(normalized);
  }

  normalizeFilePath(filePath = '') {
    return String(filePath).replace(/\\/g, '/').trim();
  }

  routeResource(routePath = '') {
    const parts = String(routePath).split('/').filter(Boolean);
    const resource = parts[2] || parts[parts.length - 1] || 'resource';
    return resource.replace(/:.*$/, '').replace(/[^a-zA-Z0-9-]/g, '') || 'resource';
  }

  fileBaseName(value = '') {
    return String(value)
      .replace(/([a-z])([A-Z])/g, '$1-$2')
      .replace(/[^a-zA-Z0-9]+/g, '-')
      .toLowerCase()
      .replace(/^-+|-+$/g, '') || 'resource';
  }

  toServiceEnvKey(serviceName, frontend = false) {
    const cleaned = String(serviceName)
      .replace(/-service$/i, '')
      .replace(/-/g, '_')
      .toUpperCase();
    return `${frontend ? 'VITE_' : ''}${cleaned}_SERVICE_URL`;
  }

  unique(items) {
    return Array.from(new Set((items || []).filter(Boolean)));
  }
}

module.exports = new DependencyClassifier();
