import { spawn } from 'node:child_process';
import process from 'node:process';

/**
 * Start every service plus the gateway locally, with no Docker and no process
 * manager. One command, one public port, and one Ctrl-C that stops everything.
 */
const services = [
  { name: 'catalog', cwd: 'packages/catalog-service' },
  { name: 'gateway', cwd: 'packages/gateway' },
];

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
  // Prefixed output, so one terminal stays readable with several services in it.
  child.stdout.on('data', (chunk) => process.stdout.write('[' + service.name + '] ' + chunk));
  child.stderr.on('data', (chunk) => process.stderr.write('[' + service.name + '] ' + chunk));
  // A service that dies takes the whole run down; a half-started system that
  // looks alive is the harder failure to diagnose.
  child.on('exit', (code) => {
    if (!stopping) console.error('[' + service.name + '] exited with code ' + code);
    stopAll(code ?? 1);
  });
  children.push(child);
}

process.on('SIGINT', () => stopAll(0));
process.on('SIGTERM', () => stopAll(0));
