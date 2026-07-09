import { spawn } from 'child_process';
import { existsSync } from 'fs';
import path from 'path';

export interface TscResult {
  total: number;
  byFile: Map<string, string[]>;
}

export function ensureInstalled(dir: string, force = false): Promise<boolean> {
  if (!force && existsSync(path.join(dir, 'node_modules'))) return Promise.resolve(true);
  return new Promise((resolve) => {
    const proc = spawn('npm install --legacy-peer-deps --no-audit --no-fund', {
      cwd: dir,
      shell: true,
      env: { ...process.env },
    });
    proc.on('error', () => resolve(false));
    proc.on('exit', (code) => resolve(code === 0));
  });
}

export function runTsc(dir: string): Promise<TscResult> {
  return new Promise((resolve) => {
    const proc = spawn('npx tsc --noEmit --pretty false', {
      cwd: dir,
      shell: true,
      env: { ...process.env },
    });
    let out = '';
    proc.stdout?.on('data', (d) => (out += d.toString()));
    proc.stderr?.on('data', (d) => (out += d.toString()));
    proc.on('error', () => resolve({ total: 0, byFile: new Map() }));
    proc.on('exit', () => {
      const byFile = new Map<string, string[]>();
      let total = 0;
      const re = /^(.+?)\((\d+),(\d+)\):\s+error\s+TS\d+:\s+(.+)$/;
      for (const line of out.split(/\r?\n/)) {
        const m = line.match(re);
        if (!m) continue;
        const file = m[1].replace(/\\/g, '/').replace(/^\.\//, '');
        if (file.includes('node_modules') || file.startsWith('.next/')) continue;
        if (!byFile.has(file)) byFile.set(file, []);
        byFile.get(file)!.push(`Line ${m[2]}: ${m[4]}`);
        total++;
      }
      resolve({ total, byFile });
    });
  });
}
