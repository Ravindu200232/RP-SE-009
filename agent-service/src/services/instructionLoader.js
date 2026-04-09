const fs = require('fs-extra');
const path = require('path');

const BUILTIN_INSTRUCTIONS = `# Local Workflow Rules
- Work inside the current workspace folder and treat it as the long-term source of truth.
- Read AI_MEMORY before planning, generation, repair, and validation.
- Use the backend pattern Route -> Controller -> Service -> Model.
- Never install internal microservice names with npm.
- Update memory files after accepted code changes.
- Prefer small targeted fixes over full rewrites when a stage fails.`;

class InstructionLoader {
  async load(workspaceDir, memoryBundle = {}) {
    const sources = [{ name: 'builtin', path: 'builtin', content: BUILTIN_INSTRUCTIONS }];
    const workspaceAgentsPath = path.join(workspaceDir, 'AGENTS.md');

    if (await fs.pathExists(workspaceAgentsPath)) {
      sources.push({
        name: 'workspace-agents',
        path: workspaceAgentsPath,
        content: await fs.readFile(workspaceAgentsPath, 'utf8')
      });
    }

    const projectState = memoryBundle.files?.['PROJECT_STATE.md'] || '';
    if (projectState) {
      sources.push({
        name: 'project-state',
        path: path.join(workspaceDir, 'AI_MEMORY', 'PROJECT_STATE.md'),
        content: projectState
      });
    }

    const mergedText = sources.map((source) => `## ${source.name}\n${source.content}`).join('\n\n');

    return {
      sources,
      mergedText,
      summary: {
        sourceCount: sources.length,
        hasWorkspaceAgents: sources.some((source) => source.name === 'workspace-agents'),
        hasProjectState: Boolean(projectState)
      }
    };
  }
}

module.exports = new InstructionLoader();
