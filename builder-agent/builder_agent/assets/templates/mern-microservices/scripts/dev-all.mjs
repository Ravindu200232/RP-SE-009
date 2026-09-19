import { spawn } from 'node:child_process';
import { readdirSync, existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import process from 'node:process';

// Studio's allocated ports win. Also support running the downloaded project
// directly, where no parent has loaded its environment yet.
const inherited = new Set(Object.keys(process.env));
for (const file of ['.env', '.env.local']) {
  if (!existsSync(file)) continue;
  for (const line of readFileSync(file, 'utf8').split(/\r?\n/)) {
    const match = line.match(/^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/);
    if (match && !inherited.has(match[1])) {
      process.env[match[1]] = match[2].replace(/^(['"])(.*)\1$/, '$2');
    }
  }
}

/**
 * Start every service plus the gateway locally, with no Docker and no process
 * manager. One command, one public port, one Ctrl-C that stops everything.
 *
 * The service list is read from the workspace rather than written here, so
 * adding a package is the only step needed to run it.
 */
const packagesDir = 'packages';
const services = readdirSync(packagesDir, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && existsSync(path.join(packagesDir, entry.name, 'src/server.js')))
  // The gateway starts last: it is the front door, and a client that reaches
  // it before the services are listening sees avoidable 503s.
  .sort((a, b) => Number(a.name.includes('gateway')) - Number(b.name.includes('gateway')))
  .map((entry) => ({ name: entry.name, cwd: path.join(packagesDir, entry.name) }));

if (!services.length) {
  console.error('No service found. A service is packages/<name>/src/server.js');
  process.exit(1);
}

const children = [];
let stopping = false;

function stopAll(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) { try { child.kill(); } catch { /* already gone */ } }
  process.exit(code);
}

for (const service of services) {
  const child = spawn(process.execPath, ['src/server.js'], {
    cwd: service.cwd,
    env: process.env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  child.stdout.on('data', (chunk) => process.stdout.write('[' + service.name + '] ' + chunk));
  child.stderr.on('data', (chunk) => process.stderr.write('[' + service.name + '] ' + chunk));
  // A service that dies takes the whole run down. A half-started system that
  // still looks alive is the harder failure to diagnose.
  child.on('exit', (code) => {
    if (!stopping) console.error('[' + service.name + '] exited with code ' + code);
    stopAll(code ?? 1);
  });
  children.push(child);
}

process.on('SIGINT', () => stopAll(0));
process.on('SIGTERM', () => stopAll(0));
