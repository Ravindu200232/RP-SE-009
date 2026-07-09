import { parseSingleFileRepair } from '../artifact/parser';
import { streamOllamaChat, OLLAMA_CODE_MODEL } from '../llm/ollama';
import { buildQualityRepairMessages, buildRepairMessages } from '../llm/repairPrompts';
import { readProjectFiles, readProjectManifest, writeProjectFiles } from '../workspace/fs';
import { collectPageQualityFindings, type PageQualityFinding } from './audit';
import { autofixProject } from './autofix';
import { derivePages, extractPageSpec } from './derivePages';
import { syntaxErrors } from './verify';

export interface QualityRepairResult {
  fixed: number;
  remaining: PageQualityFinding[];
}

export interface QualityRepairEvent {
  type: 'quality-audit' | 'quality-fix';
  round?: number;
  files?: number;
  issues?: number;
  file?: string;
  route?: string;
  status?: 'done' | 'skipped' | 'error';
}

function issuePriority(finding: PageQualityFinding): number {
  const joined = finding.issues.join(' ').toLowerCase();
  if (/placeholder|mock|demo|temporary|dummy/.test(joined)) return 0;
  if (/loading|error|empty|no-data/.test(joined)) return 1;
  if (/form|submit|label/.test(joined)) return 2;
  return 3;
}

async function streamRepairText(
  messages: { system: string; user: string },
  signal?: AbortSignal,
): Promise<string | null> {
  let full = '';
  try {
    for await (const delta of streamOllamaChat(
      [
        { role: 'system', content: messages.system },
        { role: 'user', content: messages.user },
      ],
      { model: OLLAMA_CODE_MODEL, context: 'code', think: false, signal },
    )) {
      full += delta;
    }
    return full;
  } catch {
    return null;
  }
}

async function writeUsableRepair(
  projectId: string,
  targetPath: string,
  originalContent: string,
  text: string | null,
): Promise<boolean> {
  if (!text) return false;
  const fixed = parseSingleFileRepair(text, targetPath);
  if (!fixed || fixed.content.trim().length < 5) return false;
  const isPage =
    fixed.path === 'app/page.tsx' || /^app\/.+\/page\.(tsx|jsx)$/.test(fixed.path);
  if (isPage) {
    const minimum = Math.max(1200, Math.floor(originalContent.trim().length * 0.4));
    if (fixed.content.trim().length < minimum) return false;
  }
  if (syntaxErrors(fixed.path, fixed.content).length > 0) return false;
  await writeProjectFiles(projectId, [fixed]);
  return true;
}

async function repairOneQualityFile(opts: {
  projectId: string;
  finding: PageQualityFinding;
  content: string;
  plans: Record<string, string>;
  hasBackend: boolean;
  manifest: string[];
  signal?: AbortSignal;
}): Promise<'done' | 'skipped' | 'error'> {
  const messages = buildQualityRepairMessages({
    filePath: opts.finding.filePath,
    fileContent: opts.content,
    route: opts.finding.route,
    issues: opts.finding.issues,
    manifest: opts.manifest,
    pageSpec: extractPageSpec(opts.plans.pagewise || '', opts.finding.route),
    plans: opts.plans,
    hasBackend: opts.hasBackend,
  });

  const full = await streamRepairText(messages, opts.signal);
  if (full === null) return 'error';
  if (await writeUsableRepair(opts.projectId, opts.finding.filePath, opts.content, full))
    return 'done';

  const fallback = buildRepairMessages({
    filePath: opts.finding.filePath,
    fileContent: opts.content,
    issues: [
      ...opts.finding.issues,
      'Quality repair output was not usable. Return only the complete corrected file.',
    ],
    manifest: opts.manifest,
  });
  const fallbackFull = await streamRepairText(fallback, opts.signal);
  if (fallbackFull === null) return 'error';
  if (await writeUsableRepair(opts.projectId, opts.finding.filePath, opts.content, fallbackFull))
    return 'done';
  return 'skipped';
}

export async function repairQualityFindings(opts: {
  projectId: string;
  plans: Record<string, string>;
  hasBackend: boolean;
  signal?: AbortSignal;
  maxRounds?: number;
  maxFilesPerRound?: number;
  emit?: (event: QualityRepairEvent) => void;
}): Promise<QualityRepairResult> {
  const maxRounds = Math.max(0, opts.maxRounds ?? Number(process.env.QUALITY_REPAIR_ROUNDS || 3));
  const maxFilesPerRound = Math.max(
    1,
    opts.maxFilesPerRound ?? Number(process.env.QUALITY_REPAIR_FILES || 8),
  );
  const pages = derivePages(opts.plans.pages || '', Number(process.env.MAX_BUILD_PAGES || 60));
  let fixed = 0;
  let remaining: PageQualityFinding[] = [];

  for (let round = 1; round <= maxRounds; round++) {
    const files = await readProjectFiles(opts.projectId);
    const byPath = new Map(files.map((file) => [file.path, file.content]));
    const findings = collectPageQualityFindings(files, pages, opts.hasBackend);
    remaining = findings;
    opts.emit?.({
      type: 'quality-audit',
      round,
      files: findings.length,
      issues: findings.reduce((sum, finding) => sum + finding.issues.length, 0),
    });
    if (!findings.length) break;

    const manifest = await readProjectManifest(opts.projectId);
    const targets = [...findings]
      .sort((a, b) => issuePriority(a) - issuePriority(b))
      .slice(0, maxFilesPerRound);

    let changedThisRound = 0;
    for (const finding of targets) {
      const content = byPath.get(finding.filePath);
      if (!content) continue;
      const status = await repairOneQualityFile({
        projectId: opts.projectId,
        finding,
        content,
        plans: opts.plans,
        hasBackend: opts.hasBackend,
        manifest,
        signal: opts.signal,
      });
      opts.emit?.({
        type: 'quality-fix',
        round,
        file: finding.filePath,
        route: finding.route,
        status,
      });
      if (status === 'done') {
        changedThisRound++;
        fixed++;
      }
    }

    await autofixProject(opts.projectId).catch(() => []);
    if (changedThisRound === 0) break;
  }

  const finalFiles = await readProjectFiles(opts.projectId);
  remaining = collectPageQualityFindings(finalFiles, pages, opts.hasBackend);
  return { fixed, remaining };
}
