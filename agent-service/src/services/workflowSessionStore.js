const fs = require('fs-extra');
const path = require('path');

class WorkflowSessionStore {
  sessionPath(workspaceDir) {
    return path.join(workspaceDir, 'AI_MEMORY', 'SESSION_STATE.json');
  }

  async read(workspaceDir) {
    const target = this.sessionPath(workspaceDir);
    if (!await fs.pathExists(target)) {
      return this.defaultState();
    }

    try {
      return {
        ...this.defaultState(),
        ...await fs.readJson(target)
      };
    } catch {
      return this.defaultState();
    }
  }

  async update(workspaceDir, updates = {}) {
    const current = await this.read(workspaceDir);
    const next = {
      ...current,
      ...updates,
      attempts: {
        ...(current.attempts || {}),
        ...(updates.attempts || {})
      },
      updatedAt: new Date().toISOString()
    };

    await fs.ensureDir(path.dirname(this.sessionPath(workspaceDir)));
    await fs.writeJson(this.sessionPath(workspaceDir), next, { spaces: 2 });
    return next;
  }

  defaultState() {
    return {
      version: 1,
      status: 'idle',
      currentStage: 'idle',
      currentAgent: 'Orchestrator',
      currentService: '',
      task: '',
      workspaceId: '',
      threadId: '',
      targetServices: [],
      completedSteps: [],
      lastError: '',
      attempts: {},
      updatedAt: new Date(0).toISOString()
    };
  }
}

module.exports = new WorkflowSessionStore();
