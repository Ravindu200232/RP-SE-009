const path = require('path');
const fs = require('fs-extra');
const { v4: uuidv4 } = require('uuid');
const Workspace = require('../models/Workspace');
const Thread = require('../models/Thread');

const GENERATED_APPS_BASE = path.resolve(
  process.env.GENERATED_APPS_DIR || path.join(__dirname, '../../../generated-apps')
);

class WorkspaceService {
  slugify(value) {
    return String(value || 'generated-app')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 80) || 'generated-app';
  }

  createWorkspaceName(input = {}) {
    return input.projectName || input.name || input.title || 'Generated App';
  }

  createWorkspaceDescription(input = {}) {
    return input.description || input.summary || '';
  }

  async ensureWorkspaceDirectories(workspace) {
    await fs.ensureDir(workspace.appDir);
    await fs.ensureDir(workspace.memoryDir);
    return workspace;
  }

  async getWorkspaceById(workspaceId) {
    if (!workspaceId) return null;
    return Workspace.findOne({ workspaceId });
  }

  async listWorkspaces() {
    return Workspace.find().sort({ updatedAt: -1 }).lean();
  }

  async resolveWorkspace({ workspaceId, plan, srs }) {
    if (workspaceId) {
      const existing = await this.getWorkspaceById(workspaceId);
      if (!existing) {
        throw new Error(`Workspace not found: ${workspaceId}`);
      }
      await this.ensureWorkspaceDirectories(existing);
      return existing;
    }

    const source = plan || srs || {};
    const name = this.createWorkspaceName(source);
    const slug = this.slugify(name);
    const existing = await Workspace.findOne({ slug });

    if (existing) {
      existing.name = name;
      existing.description = this.createWorkspaceDescription(source);
      existing.status = 'active';
      await existing.save();
      await this.ensureWorkspaceDirectories(existing);
      return existing;
    }

    const appDir = path.join(GENERATED_APPS_BASE, slug);
    const memoryDir = path.join(appDir, 'AI_MEMORY');
    const workspace = await Workspace.create({
      workspaceId: uuidv4(),
      slug,
      name,
      description: this.createWorkspaceDescription(source),
      stack: source.techStack || source.stack || 'MERN Stack Microservices',
      appDir,
      memoryDir,
      status: 'active'
    });

    await this.ensureWorkspaceDirectories(workspace);
    return workspace;
  }

  async resolveThread({ workspace, threadId, mode = 'new', task = '' }) {
    if (!workspace) {
      throw new Error('resolveThread requires a workspace');
    }

    if (threadId) {
      const existing = await Thread.findOne({ threadId, workspaceId: workspace.workspaceId });
      if (!existing) {
        throw new Error(`Thread not found: ${threadId}`);
      }
      existing.latestTask = task || existing.latestTask;
      existing.mode = mode || existing.mode;
      await existing.save();
      return existing;
    }

    const title = task
      ? task.slice(0, 80)
      : `Workspace thread for ${workspace.name}`;

    const thread = await Thread.create({
      threadId: uuidv4(),
      workspaceId: workspace.workspaceId,
      title,
      mode,
      latestTask: task,
      status: 'active'
    });

    workspace.latestThreadId = thread.threadId;
    await workspace.save();
    return thread;
  }

  async touchWorkspace(workspaceId, updates = {}) {
    if (!workspaceId) return null;
    return Workspace.findOneAndUpdate(
      { workspaceId },
      { $set: updates },
      { new: true }
    );
  }

  async touchThread(threadId, updates = {}) {
    if (!threadId) return null;
    return Thread.findOneAndUpdate(
      { threadId },
      { $set: updates },
      { new: true }
    );
  }
}

module.exports = new WorkspaceService();
