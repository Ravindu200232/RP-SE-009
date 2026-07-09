/**
 * SEARCH/REPLACE edit blocks — surgical, line-level repairs instead of
 * regenerating a whole 400-line file to fix one bad line. The model returns:
 *
 *   <<<<<<< SEARCH
 *   the exact current lines
 *   =======
 *   the fixed lines
 *   >>>>>>> REPLACE
 *
 * We apply each block by an exact substring match (with a whitespace-tolerant
 * fallback), leaving the rest of the file byte-for-byte untouched. This is far
 * faster (the model emits only the changed lines) and never loses the working
 * parts of the file — the recurring risk of full-file regeneration.
 */

export interface EditBlock {
  search: string;
  replace: string;
}

const BLOCK_RE =
  /<{5,}\s*SEARCH[^\n]*\r?\n([\s\S]*?)\r?\n={5,}[^\n]*\r?\n([\s\S]*?)\r?\n>{5,}\s*REPLACE/g;

export function parseEditBlocks(text: string): EditBlock[] {
  const blocks: EditBlock[] = [];
  BLOCK_RE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = BLOCK_RE.exec(text))) {
    // The SEARCH body may legitimately be empty (pure insertion is rare; we
    // require a non-empty search so we never blindly prepend).
    if (m[1].length > 0) blocks.push({ search: m[1], replace: m[2] });
  }
  return blocks;
}

/** Collapse runs of whitespace so indentation drift doesn't defeat a match. */
function normalizeWs(s: string): string {
  return s.replace(/[ \t]+/g, ' ').replace(/[ \t]*\r?\n[ \t]*/g, '\n').trim();
}

/**
 * Apply edit blocks to source. Exact match first; if that fails, try to locate
 * the block by whitespace-normalized comparison over a sliding line window and
 * replace that span. Blocks that can't be located are skipped (safe no-op).
 */
export function applyEditBlocks(
  source: string,
  blocks: EditBlock[],
): { content: string; applied: number } {
  let content = source;
  let applied = 0;

  for (const block of blocks) {
    const search = block.search.replace(/\r\n/g, '\n');
    const replace = block.replace.replace(/\r\n/g, '\n');
    if (!search.trim()) continue;

    // 1. Exact substring.
    const idx = content.indexOf(search);
    if (idx !== -1) {
      content = content.slice(0, idx) + replace + content.slice(idx + search.length);
      applied++;
      continue;
    }

    // 2. Whitespace-tolerant line-window match.
    const srcLines = content.split('\n');
    const searchNorm = normalizeWs(search);
    const searchLineCount = search.split('\n').length;
    let matched = false;
    for (let i = 0; i + searchLineCount <= srcLines.length; i++) {
      const window = srcLines.slice(i, i + searchLineCount).join('\n');
      if (normalizeWs(window) === searchNorm) {
        srcLines.splice(i, searchLineCount, ...replace.split('\n'));
        content = srcLines.join('\n');
        applied++;
        matched = true;
        break;
      }
    }
    if (matched) continue;
    // 3. Not found — skip this block, leave the file intact.
  }

  return { content, applied };
}
