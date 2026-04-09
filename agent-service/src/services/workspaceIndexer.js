const fs = require('fs-extra');
const path = require('path');

const SKIP_DIRS = new Set([
  'node_modules',
  '.git',
  '.next',
  'dist',
  'build',
  'coverage',
  '.turbo'
]);

class WorkspaceIndexer {
  async scan(rootDir) {
    const files = [];
    await this._walk(rootDir, rootDir, files);

    const services = {};
    for (const file of files) {
      if (file.service && file.service !== 'workspace') {
        services[file.service] = services[file.service] || { fileCount: 0, kinds: {} };
        services[file.service].fileCount += 1;
        services[file.service].kinds[file.kind] = (services[file.service].kinds[file.kind] || 0) + 1;
      }
    }

    return {
      rootDir,
      files,
      services,
      summary: {
        totalFiles: files.length,
        serviceCount: Object.keys(services).length
      }
    };
  }

  async _walk(rootDir, currentDir, files) {
    if (!await fs.pathExists(currentDir)) return;

    const entries = await fs.readdir(currentDir, { withFileTypes: true });
    for (const entry of entries) {
      if (SKIP_DIRS.has(entry.name)) continue;

      const absolutePath = path.join(currentDir, entry.name);
      const relativePath = path.relative(rootDir, absolutePath).replace(/\\/g, '/');

      if (entry.isDirectory()) {
        await this._walk(rootDir, absolutePath, files);
        continue;
      }

      const content = await this._safeReadFile(absolutePath);
      if (content === null) continue;

      files.push({
        path: relativePath,
        kind: this._classifyKind(relativePath),
        service: this._classifyService(relativePath),
        imports: this._extractImports(content),
        size: content.length
      });
    }
  }

  async _safeReadFile(filePath) {
    try {
      return await fs.readFile(filePath, 'utf8');
    } catch {
      return null;
    }
  }

  _classifyService(relativePath) {
    const [topLevel] = relativePath.split('/');
    if (!topLevel) return 'workspace';
    if (topLevel === 'AI_MEMORY') return 'memory';
    return topLevel;
  }

  _classifyKind(relativePath) {
    const fileName = path.basename(relativePath).toLowerCase();

    if (relativePath.startsWith('AI_MEMORY/')) return 'memory';
    if (fileName === 'package.json') return 'package';
    if (fileName === '.env' || fileName === '.env.example') return 'env';
    if (fileName === 'server.js') return 'server';
    if (fileName === 'dbconnection.js') return 'db';
    if (fileName.includes('.model.')) return 'model';
    if (fileName.includes('.service.')) return 'service';
    if (fileName.includes('.controller.')) return 'controller';
    if (fileName.includes('.route.')) return 'route';
    if (relativePath.includes('/models/')) return 'model';
    if (relativePath.includes('/services/')) return 'service';
    if (relativePath.includes('/controllers/')) return 'controller';
    if (relativePath.includes('/routes/')) return 'route';
    if (relativePath.includes('/src/app/')) return 'frontend';
    if (relativePath.includes('/components/')) return 'component';
    if (fileName.endsWith('.md')) return 'doc';
    return 'file';
  }

  _extractImports(content) {
    const imports = new Set();
    const importRegex = /import\s+[^'"]*['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\)/g;
    let match;

    while ((match = importRegex.exec(content)) !== null) {
      imports.add(match[1] || match[2]);
    }

    return Array.from(imports);
  }
}

module.exports = new WorkspaceIndexer();
