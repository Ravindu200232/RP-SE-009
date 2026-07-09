const DEFAULT_DIGEST_CAP = Number(process.env.SRS_DIGEST_CHAR_CAP || 70000);

const IMPORTANT_KEY =
  /(app|summary|goal|user|role|permission|module|feature|requirement|functional|workflow|page|screen|dashboard|portal|api|endpoint|data|entity|table|schema|model|auth|security|report|payment|booking|order|inventory|attendance|course|student|teacher|vehicle|hotel|room|pos|sale|invoice|supplier|customer)/i;

function stripFence(input: string): string {
  const s = (input || '').trim();
  const fenced = s.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return fenced ? fenced[1].trim() : s;
}

function safeString(v: unknown): string {
  if (v == null) return '';
  if (typeof v === 'string') return v.replace(/\s+/g, ' ').trim();
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  return '';
}

function compactLine(path: string, value: unknown): string | null {
  const text = safeString(value);
  if (!text) return null;
  return `- ${path}: ${text.slice(0, 700)}`;
}

function walkJson(
  value: unknown,
  path: string,
  out: string[],
  depth = 0,
  inheritedImportant = false,
): void {
  if (out.length > 1800 || depth > 7) return;
  const important = inheritedImportant || IMPORTANT_KEY.test(path);

  if (Array.isArray(value)) {
    const take = important ? 80 : 18;
    value.slice(0, take).forEach((item, i) => {
      walkJson(item, `${path}[${i}]`, out, depth + 1, important);
    });
    if (value.length > take) out.push(`- ${path}: ...${value.length - take} more items`);
    return;
  }

  if (value && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>);
    for (const [key, child] of entries) {
      const childPath = path ? `${path}.${key}` : key;
      const childImportant = important || IMPORTANT_KEY.test(key);
      if (childImportant || depth < 2) {
        walkJson(child, childPath, out, depth + 1, childImportant);
      }
      if (out.length > 1800) break;
    }
    return;
  }

  if (important) {
    const line = compactLine(path, value);
    if (line) out.push(line);
  }
}

function keywordDigest(raw: string): string[] {
  const lines = stripFence(raw)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  const out: string[] = [];
  for (const line of lines) {
    if (IMPORTANT_KEY.test(line) || /^#{1,4}\s/.test(line) || /^\d+[\.)]\s/.test(line)) {
      out.push(`- ${line.slice(0, 700)}`);
    }
    if (out.length > 1200) break;
  }
  return out;
}

export function buildSrsDigest(srs: string, cap = DEFAULT_DIGEST_CAP): string {
  const raw = stripFence(srs);
  if (!raw) return '';

  let lines: string[] = [];
  try {
    const parsed = JSON.parse(raw) as unknown;
    walkJson(parsed, '', lines);
  } catch {
    lines = keywordDigest(raw);
  }

  const digest = [
    'SRS DIGEST (compact requirement-focused extraction for the local model):',
    ...lines,
  ].join('\n');

  if (digest.length <= cap) return digest;
  return digest.slice(0, cap) + '\n...(SRS digest truncated for VRAM-safe context)...';
}
