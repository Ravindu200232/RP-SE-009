import ts from 'typescript';
import { promises as fs } from 'fs';
import path from 'path';
import { projectDir, isProtectedPath } from '../workspace/fs';

/**
 * Lightweight, dependency-free syntax verification of generated source files.
 *
 * The deterministic autofix repairs MECHANICAL bugs (imports, simple syntax),
 * but a 12B/14B model also produces STRUCTURAL parse errors it can't safely fix
 * — mismatched/miscased JSX tags, a `</div>` too many, a stray `</query>`, a
 * function written with an arrow body, etc. Those are exactly the errors the
 * TypeScript PARSER reports, and the parser needs no installed deps and no
 * tsconfig — so we can flag them at build time and hand each broken file to the
 * local model for an LLM repair pass.
 */

const SRC_EXT = ['.tsx', '.ts', '.jsx', '.js'];

export interface BrokenFile {
  rel: string;
  content: string;
  errors: string[];
}

/** Syntax-only diagnostics for one file (parse errors only — no type-checking). */
export function syntaxErrors(rel: string, content: string): string[] {
  const kind = /\.tsx$|\.jsx$/.test(rel) ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(rel, content, ts.ScriptTarget.Latest, false, kind);
  const diags =
    (sf as unknown as { parseDiagnostics?: ts.Diagnostic[] }).parseDiagnostics ?? [];
  return diags.map((d) => {
    const msg = ts.flattenDiagnosticMessageText(d.messageText, ' ');
    if (d.start == null) return msg;
    const { line, character } = sf.getLineAndCharacterOfPosition(d.start);
    return `line ${line + 1}:${character + 1} — ${msg}`;
  });
}

/** Walk app/, components/, lib/ and return the files that fail to parse. */
export async function findBrokenFiles(id: string): Promise<BrokenFile[]> {
  const root = projectDir(id);
  const out: BrokenFile[] = [];

  async function walk(dir: string): Promise<void> {
    let entries;
    try {
      entries = await fs.readdir(dir, { withFileTypes: true });
    } catch {
      return;
    }
    for (const e of entries) {
      if (e.name === 'node_modules' || e.name === '.next' || e.name === '_plans') continue;
      const full = path.join(dir, e.name);
      if (e.isDirectory()) {
        await walk(full);
        continue;
      }
      if (!SRC_EXT.some((x) => e.name.endsWith(x))) continue;
      const rel = path.relative(root, full).replace(/\\/g, '/');
      // Protected (scaffold-owned) files can't be repaired — writeProjectFiles
      // drops writes to them — so flagging one loops the repair pass forever.
      if (isProtectedPath(rel)) continue;
      let content: string;
      try {
        content = await fs.readFile(full, 'utf8');
      } catch {
        continue;
      }
      const errors = syntaxErrors(rel, content);
      if (errors.length) out.push({ rel, content, errors });
    }
  }

  for (const d of ['app', 'components', 'lib']) await walk(path.join(root, d));
  return out;
}
