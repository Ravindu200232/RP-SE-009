/**
 * Kill any process listening on a given port.
 * Usage: node scripts/kill-port.js 5000
 */
const net = require('net');
const { execSync } = require('child_process');

const port = parseInt(process.argv[2] || '5000', 10);
console.log(`Killing process on port ${port}...`);

try {
  if (process.platform === 'win32') {
    const out = execSync(`netstat -a -n -o | findstr ":${port} "`, { encoding: 'utf8', stdio: ['pipe', 'pipe', 'ignore'] });
    const pids = new Set();
    for (const line of out.split('\n')) {
      const parts = line.trim().split(/\s+/);
      if (parts.length >= 5 && (parts[0] === 'TCP' || parts[3] === 'LISTENING')) {
        const pid = parts[parts.length - 1];
        if (pid && pid !== '0' && /^\d+$/.test(pid)) pids.add(pid);
      }
    }
    for (const pid of pids) {
      try {
        execSync(`taskkill /F /PID ${pid}`, { stdio: 'inherit' });
        console.log(`Killed PID ${pid}`);
      } catch(e) {
        console.log(`Failed to kill PID ${pid}: ${e.message}`);
      }
    }
  } else {
    execSync(`lsof -ti:${port} | xargs kill -9`, { stdio: 'inherit' });
  }
} catch(e) {
  console.log('Nothing to kill or already dead:', e.message.slice(0, 100));
}
console.log('Done');
