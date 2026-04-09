const fs = require('fs-extra');
const path = require('path');

/**
 * FileWriterService — Writes generated files to disk.
 * Handles directory creation, file encoding, and overwrites.
 */
class FileWriterService {
  constructor(baseDir) {
    this.baseDir = baseDir;
  }

  /**
   * Write a list of {path, content} files to disk under baseDir.
   * File paths are relative to baseDir (e.g. "auth-service/src/index.js").
   */
  async writeFiles(files) {
    const written = [];
    for (const file of files) {
      if (!file.path || file.content === undefined) continue;
      const fullPath = path.join(this.baseDir, file.path);
      await fs.ensureDir(path.dirname(fullPath));
      await fs.writeFile(fullPath, file.content, 'utf8');
      written.push(fullPath);
    }
    return written;
  }

  /**
   * Write a single file.
   */
  async writeFile(relativePath, content) {
    const fullPath = path.join(this.baseDir, relativePath);
    await fs.ensureDir(path.dirname(fullPath));
    await fs.writeFile(fullPath, content, 'utf8');
    return fullPath;
  }

  /**
   * Read all files in a directory recursively.
   * Returns [{path (relative), content}]
   */
  async readAllFiles(subDir = '') {
    const dir = path.join(this.baseDir, subDir);
    if (!await fs.pathExists(dir)) return [];

    const result = [];
    const entries = await fs.readdir(dir, { withFileTypes: true });

    for (const entry of entries) {
      const entryPath = path.join(dir, entry.name);
      const relPath = path.relative(this.baseDir, entryPath);

      if (entry.isDirectory()) {
        // Skip node_modules and .git
        if (['node_modules', '.git', '.next', 'dist', 'build'].includes(entry.name)) continue;
        const subFiles = await this.readAllFiles(relPath);
        result.push(...subFiles);
      } else {
        try {
          const content = await fs.readFile(entryPath, 'utf8');
          result.push({ path: relPath, content });
        } catch {
          // Skip binary files
        }
      }
    }
    return result;
  }

  /**
   * Get the absolute path for a relative path.
   */
  resolve(...parts) {
    return path.join(this.baseDir, ...parts);
  }

  /**
   * Check if a path exists.
   */
  async exists(relativePath) {
    return fs.pathExists(path.join(this.baseDir, relativePath));
  }
}

module.exports = FileWriterService;
