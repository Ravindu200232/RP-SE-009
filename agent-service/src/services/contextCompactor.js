class ContextCompactor {
  build({
    workspace,
    thread,
    task = '',
    instructions = {},
    memory = {},
    index = {},
    plan = null,
    service = null
  } = {}) {
    const instructionSummary = this.summarizeInstructions(instructions.mergedText || '');
    const projectState = this.clip(memory.files?.['PROJECT_STATE.md'] || '', 1800);
    const serviceMap = this.summarizeServiceMap(memory.parsed?.['SERVICE_MAP.json'], plan, service);
    const failureSummary = this.summarizeFailures(memory.parsed?.['FAILURE_PATTERNS.json']);
    const indexSummary = this.summarizeIndex(index, service);
    const sessionSummary = [
      `Workspace: ${workspace?.name || workspace?.slug || 'Generated App'}`,
      `Thread: ${thread?.title || 'Default thread'}`,
      `Task: ${task || 'Initial generation'}`
    ].join('\n');

    const sections = [
      this.section('Session', sessionSummary),
      this.section('Instructions', instructionSummary),
      this.section('Project State', projectState),
      this.section('Workspace Index', indexSummary),
      this.section('Service Map', serviceMap),
      this.section('Failure Memory', failureSummary)
    ].filter(Boolean);

    const summary = sections.join('\n\n');

    return {
      summary,
      plannerPrompt: summary,
      developerPrompt: summary,
      repairPrompt: summary,
      stats: {
        length: summary.length,
        hasFailures: Boolean(failureSummary),
        indexedServices: Object.keys(index.services || {}).length
      }
    };
  }

  section(title, content) {
    const trimmed = String(content || '').trim();
    if (!trimmed) {
      return '';
    }
    return `## ${title}\n${trimmed}`;
  }

  summarizeInstructions(text = '') {
    const lines = String(text || '')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .filter((line) => /^[-#*]/.test(line) || /Route -> Controller -> Service -> Model/i.test(line));

    return this.clip(lines.join('\n'), 1200);
  }

  summarizeServiceMap(serviceMap = {}, plan = null, targetService = null) {
    const map = serviceMap && typeof serviceMap === 'object' ? serviceMap : {};
    const selectedNames = new Set();

    if (targetService?.name) {
      selectedNames.add(targetService.name);
    }

    for (const service of plan?.services || []) {
      if (!targetService || service.name === targetService.name) {
        selectedNames.add(service.name);
      }
    }

    const names = selectedNames.size > 0 ? Array.from(selectedNames) : Object.keys(map).slice(0, 6);
    const entries = names
      .map((name) => {
        const service = map[name];
        if (!service) {
          return '';
        }
        const routes = (service.routes || []).slice(0, 4).map((route) => `${route.method} ${route.path}`).join(', ');
        return `- ${name}: port ${service.port || 'n/a'}, entities=${(service.entities || []).join(', ') || 'none'}, routes=${routes || 'none'}, deps=${(service.serviceDependencies || []).join(', ') || 'none'}`;
      })
      .filter(Boolean);

    return this.clip(entries.join('\n'), 1600);
  }

  summarizeFailures(failures = []) {
    if (!Array.isArray(failures) || failures.length === 0) {
      return '- none';
    }

    const recent = failures.slice(-8).map((failure) => {
      const service = failure.service ? ` [${failure.service}]` : '';
      return `- ${failure.code || 'unknown'}${service}: ${this.clip(failure.message || '', 140)}`;
    });

    return recent.join('\n');
  }

  summarizeIndex(index = {}, targetService = null) {
    const services = index.services || {};
    const selected = targetService?.name
      ? [[targetService.name, services[targetService.name]].filter(Boolean)]
      : Object.entries(services).slice(0, 8);

    const lines = selected
      .filter(([, data]) => data)
      .map(([name, data]) => {
        const kinds = Object.entries(data.kinds || {})
          .map(([kind, count]) => `${kind}:${count}`)
          .join(', ');
        return `- ${name}: files=${data.fileCount || 0}${kinds ? ` (${kinds})` : ''}`;
      });

    if (lines.length === 0) {
      return '- no indexed services yet';
    }

    return lines.join('\n');
  }

  clip(value = '', maxLength = 1000) {
    const text = String(value || '').trim();
    if (text.length <= maxLength) {
      return text;
    }
    return `${text.slice(0, Math.max(0, maxLength - 3)).trim()}...`;
  }
}

module.exports = new ContextCompactor();
