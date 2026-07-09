import type { GeneratedFile, ParsedArtifact } from './types';

/**
 * Parses the model's output. The model is instructed to emit:
 *
 *   <project name="..." description="...">
 *   <file path="app/page.tsx">...content...</file>
 *   ...
 *   </project>
 *
 * The parser is deliberately tolerant: the <project> wrapper is optional,
 * attributes may use single or double quotes, and it works on partial text
 * (mid-stream) so the UI can update live.
 */

// Content is captured up to whichever comes first: the closing </file>, the
// start of the next <file …> block, </project>, or END-OF-TEXT. Terminating on
// the next tag (not just </file>) means a single missing </file> — which the
// local model drops fairly often on large files — no longer swallows the
// following file(s) into the previous one's content. Allowing end-of-text ($)
// as a terminator recovers the common case where the model opens ONE <file>,
// writes the whole file, then ends with a ``` fence and NO </file> at all
// (which previously made the regex fail entirely → 0 files, e.g. the home page).
const FILE_RE =
  /<file\b[^>]*?\bpath\s*=\s*["']([^"']+)["'][^>]*?>([\s\S]*?)(?:<\/file>|(?=<file\b)|(?=<\/project\b)|$)/gi;
const NAME_RE = /<project\b[^>]*?\bname\s*=\s*["']([^"']+)["']/i;
const DESC_RE = /<project\b[^>]*?\bdescription\s*=\s*["']([^"']+)["']/i;

function normalizePath(p: string): string {
  const cleaned = p
    .trim()
    .replace(/\\/g, '/')
    .replace(/^\.\//, '')
    .replace(/^\/+/, '');
  const routePage = cleaned.replace(/^app\/(.+)\.page\.(tsx|jsx|ts|js)$/i, 'app/$1/page.$2');
  if (!routePage.startsWith('app/')) return routePage;
  return routePage
    .split('/')
    .map((part, index, all) => {
      const isFile = index === all.length - 1 && /\.[a-z0-9]+$/i.test(part);
      if (isFile || part.startsWith('_')) return part;
      return part.replace(/_/g, '-');
    })
    .join('/');
}

function stripLeakedThoughtMarkup(text: string): string {
  return text
    .replace(/<_(?:thought|thinking)\b[^>]*>[\s\S]*?<\/_(?:thought|thinking)>/gi, '')
    .replace(/<(?:think|thought|thinking)\b[^>]*>[\s\S]*?<\/(?:think|thought|thinking)>/gi, '')
    .replace(/<\/?_(?:thought|thinking)\b[^>]*>/gi, '')
    .replace(/<\/?(?:think|thought|thinking)\b[^>]*>/gi, '')
    .replace(/<\/?_(?:file|project|artifact)\b[^>]*>/gi, '');
}

function cleanContent(raw: string): string {
  // The model puts the content on its own lines; drop the single newline that
  // immediately follows the opening tag and the one preceding </file>.
  let c = stripLeakedThoughtMarkup(raw)
    .replace(/^\r?\n/, '')
    .replace(/\r?\n[ \t]*$/, '');

  // Strip accidental markdown code fences. The model sometimes wraps a file's
  // content in ```lang … ``` despite being told not to, which leaves an invalid
  // ``` line in the written source. It can even emit SEVERAL stray fence lines
  // back-to-back (e.g. "```\n```" at the end — seen in real builds, where a
  // single .pop() left one behind and the file failed the syntax gate), so keep
  // stripping fence/blank lines from both edges until real content is reached.
  // Fences inside legitimate content are left alone.
  const lines = c.split('\n');
  const isFenceLine = (s: string) => /^`{3,}[a-zA-Z0-9_-]*\s*$/.test(s.trim());
  while (lines.length && (isFenceLine(lines[0]) || lines[0].trim() === '')) lines.shift();
  while (
    lines.length &&
    (isFenceLine(lines[lines.length - 1]) || lines[lines.length - 1].trim() === '')
  ) {
    lines.pop();
  }
  c = lines.join('\n').replace(/\r?\n[ \t]*$/, '');

  return c;
}

function isSafePath(p: string): boolean {
  return !!p && !p.includes('..') && !p.startsWith('/');
}

export function parseArtifact(text: string): ParsedArtifact {
  const files: GeneratedFile[] = [];
  const indexByPath = new Map<string, number>();

  FILE_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = FILE_RE.exec(text)) !== null) {
    const path = normalizePath(match[1]);
    if (!isSafePath(path)) continue;
    const content = cleanContent(match[2]);

    if (indexByPath.has(path)) {
      // A later block for the same path wins (handles regeneration).
      files[indexByPath.get(path)!] = { path, content };
    } else {
      indexByPath.set(path, files.length);
      files.push({ path, content });
    }
  }

  return {
    name: NAME_RE.exec(text)?.[1],
    description: DESC_RE.exec(text)?.[1],
    files,
  };
}

// ```lang\n…``` blocks whose first line is a path comment — the fallback shape
// a local model emits when it forgets the <file> wrapper entirely (seen live:
// an App Shell round emitted 11K chars of ```css /* app/globals.css */ …```
// blocks → parseArtifact found 0 files → the step failed with real code lost).
const FENCE_BLOCK_RE = /```[a-zA-Z0-9_-]*[ \t]*\r?\n([\s\S]*?)```/g;
const PATH_COMMENT_RE =
  /^\s*(?:\/\/|\/\*|#|<!--)?\s*(?:FILE:|File:|file:)?\s*([A-Za-z0-9_@./[\]-]+\.(?:tsx|ts|jsx|js|css|json|md|txt))\s*(?:\*\/|-->)?\s*$/;

/**
 * Fallback for step outputs with NO <file> blocks: recover files from fenced
 * code blocks that name their path in a leading comment. Only used when the
 * primary parser finds nothing, so it can't interfere with normal parsing.
 */
export function parseFencedFiles(text: string): GeneratedFile[] {
  const out: GeneratedFile[] = [];
  const seen = new Map<string, number>();
  FENCE_BLOCK_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = FENCE_BLOCK_RE.exec(text))) {
    const lines = m[1].split('\n');
    let path = '';
    let start = 0;
    for (let i = 0; i < Math.min(3, lines.length); i++) {
      if (lines[i].trim() === '') continue; // skip leading blank lines
      const pm = PATH_COMMENT_RE.exec(lines[i].trim());
      if (pm) {
        path = pm[1];
        start = i + 1;
      }
      break; // only the first non-blank line may name the path
    }
    if (!path) {
      // No path comment — recover the two UNAMBIGUOUS shell files by content
      // signature (the model sometimes fences with no path hint at all).
      const body = lines.join('\n');
      if (/^\s*@import\s+["']tailwindcss["']/.test(body)) {
        path = 'app/globals.css';
        start = 0;
      } else if (/export\s+default\s+function\s+RootLayout\b/.test(body)) {
        path = 'app/layout.tsx';
        start = 0;
      } else {
        continue;
      }
    }
    const norm = normalizePath(path);
    if (!isSafePath(norm)) continue;
    const content = cleanContent(lines.slice(start).join('\n'));
    if (!content.trim()) continue;
    if (seen.has(norm)) {
      out[seen.get(norm)!] = { path: norm, content };
    } else {
      seen.set(norm, out.length);
      out.push({ path: norm, content });
    }
  }
  return out;
}

function stripMarkdownFence(text: string): string {
  const trimmed = text.trim();
  const fence = trimmed.match(/^```(?:[a-zA-Z0-9_-]+)?\s*([\s\S]*?)\s*```$/);
  return (fence?.[1] ?? trimmed).replace(/\r?\n[ \t]*$/, '');
}

function extractLargestCodeFence(text: string): string | null {
  const matches = [...text.matchAll(/```(?:tsx|ts|jsx|js|typescript|javascript)?\s*([\s\S]*?)```/gi)];
  if (!matches.length) return null;
  return matches
    .map((m) => m[1].trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)[0] ?? null;
}

function extractJsonCommandContent(text: string): string | null {
  const firstBrace = text.indexOf('{');
  if (firstBrace === -1) return null;
  const candidate = text.slice(firstBrace).trim();
  if (!/"action"\s*:/.test(candidate) || !/"content"\s*:/.test(candidate)) return null;

  try {
    const parsed = JSON.parse(candidate) as { content?: unknown };
    return typeof parsed.content === 'string' ? parsed.content : null;
  } catch {
    const content = candidate.match(/"content"\s*:\s*"((?:\\.|[^"\\])*)"/);
    if (!content) return null;
    try {
      return JSON.parse(`"${content[1]}"`) as string;
    } catch {
      return null;
    }
  }
}

function normalizeRecoveredSource(text: string): string {
  return text
    .replace(/^(\s*)use client["']?;?(\s*(?:\r?\n|$))/, '$1"use client";$2')
    .replace(/\bArray_isArray\b/g, 'Array.isArray')
    .replace(/\bArray\.isArray\s*\(/g, 'Array.isArray(');
}

function looksLikeSourceFile(text: string): boolean {
  return /(^|\n)\s*["']use client["'];?/.test(text)
    || /(^|\n)\s*import\s+/.test(text)
    || /(^|\n)\s*export\s+default\s+/.test(text)
    || /(^|\n)\s*export\s+(async\s+)?function\s+/.test(text)
    || /return\s*\([\s\S]*<\w+/.test(text);
}

/**
 * Repair prompts target one known file. Local models sometimes obey the code
 * part but drop the XML wrapper, returning one fenced TSX block or one bare
 * component. This helper keeps that repair useful without weakening normal
 * multi-file artifact parsing.
 */
export function parseSingleFileRepair(text: string, targetPath: string): GeneratedFile | null {
  const path = normalizePath(targetPath);
  if (!isSafePath(path)) return null;

  const exact = parseArtifact(text).files.find((f) => normalizePath(f.path) === path);
  if (exact && exact.content.trim().length > 5) {
    return { path, content: normalizeRecoveredSource(exact.content) };
  }

  const jsonContent = extractJsonCommandContent(text);
  if (jsonContent) {
    const candidate = normalizeRecoveredSource(stripMarkdownFence(jsonContent));
    if (looksLikeSourceFile(candidate)) return { path, content: cleanContent(candidate) };
    return null;
  }

  const fenced = extractLargestCodeFence(text);
  if (!fenced && /"action"\s*:|"content"\s*:/.test(text)) return null;

  const candidate = normalizeRecoveredSource(stripMarkdownFence(fenced ?? text));
  if (/"action"\s*:|"content"\s*:/.test(candidate)) return null;
  if (!looksLikeSourceFile(candidate)) return null;

  return {
    path,
    content: cleanContent(candidate),
  };
}

/**
 * The file currently being written: an open <file …> whose </file> has not
 * streamed yet. Lets the UI show the file growing live, bolt-style.
 */
export function getActiveFile(text: string): GeneratedFile | null {
  const lastOpen = text.lastIndexOf('<file');
  if (lastOpen === -1) return null;

  const segment = text.slice(lastOpen);
  if (/<\/file>/i.test(segment)) return null; // already closed

  const m = segment.match(/^<file\b[^>]*?\bpath\s*=\s*["']([^"']+)["'][^>]*?>/i);
  if (!m) return null; // opening tag still streaming

  const path = normalizePath(m[1]);
  if (!isSafePath(path)) return null;

  const content = segment.slice(m[0].length).replace(/^\r?\n/, '');
  return { path, content };
}

/** True once at least one complete <file> block exists in the text. */
export function hasArtifact(text: string): boolean {
  return /<file\b[^>]*?\bpath\s*=\s*["'][^"']+["'][^>]*?>[\s\S]*?<\/file>/i.test(text);
}

/**
 * Returns the human-readable prose with all artifact markup removed, so the
 * chat bubble shows the explanation rather than a wall of file tags. Works on
 * streaming text by also cutting any dangling, not-yet-closed block.
 */
export function stripArtifactTags(text: string): string {
  let out = text.replace(FILE_RE, '');

  // Cut a dangling, unclosed <file ...> block that is still streaming.
  const danglingFile = out.lastIndexOf('<file');
  if (danglingFile !== -1 && out.indexOf('</file>', danglingFile) === -1) {
    out = out.slice(0, danglingFile);
  }

  // Remove project wrapper tags.
  out = out.replace(/<\/?project\b[^>]*>/gi, '');

  // Remove a trailing partial tag (e.g. "<proj" or "<file path=") left mid-stream.
  out = out.replace(/<[a-zA-Z/][^>]*$/, '');

  return out.trim();
}
