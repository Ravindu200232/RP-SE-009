const spawn = require('cross-spawn');
const path = require('path');
const fs = require('fs-extra');
const treeKill = require('tree-kill');

/**
 * AppRunnerService — Runs terminal commands exactly like a human developer would.
 * Every command + every output line is emitted to the execution log in real-time.
 *
 * Vite+React frontend workflow:
 *   npm create vite@latest frontend -- --template react
 *   cd frontend && npm install
 *   npm install -D tailwindcss @tailwindcss/vite
 *   (AI generates source files)
 *   npm run build
 *   npm run preview -- --port 3001
 */
class AppRunnerService {
  constructor(io) {
    this.io = io;
    this.runningProcesses = new Map(); // name -> { process, pid, port }
    this.commandTimeoutMs = Number.parseInt(process.env.APP_COMMAND_TIMEOUT_MS || '900000', 10);
  }

  configureRun({ timeoutMs } = {}) {
    if (Number.isFinite(timeoutMs) && timeoutMs > 0) {
      this.commandTimeoutMs = timeoutMs;
    }
  }

  withMinimumTimeout(minimumMs) {
    return Math.max(this.commandTimeoutMs, minimumMs);
  }

  /**
   * Emit a terminal command to the log (so users see exactly what's being run).
   */
  _emitCmd(jobId, cmd, cwd = '') {
    const line = cwd ? `$ cd ${path.basename(cwd)} && ${cmd}` : `$ ${cmd}`;
    this.io.to(jobId).emit('log', {
      level: 'command',
      agent: 'Terminal',
      message: line,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Emit a single output line to the execution log.
   */
  _emitLine(jobId, line, level = 'terminal') {
    if (!line.trim()) return;
    this.io.to(jobId).emit('log', {
      level,
      agent: 'Terminal',
      message: line,
      timestamp: new Date().toISOString()
    });
  }

  /**
   * Core command runner — streams every output line to execution log.
   * @returns { success, output, error }
   */
  async runCommand(cmd, args, cwd, jobId, { timeout = this.commandTimeoutMs, env = {} } = {}) {
    this._emitCmd(jobId, `${cmd} ${args.join(' ')}`, cwd);

    return new Promise((resolve) => {
      const proc = spawn(cmd, args, {
        cwd,
        shell: true,
        env: { ...process.env, ...env }
      });

      let output = '';
      let errorOutput = '';
      let lineBuffer = '';

      const flushLine = (buf, isErr) => {
        const lines = (lineBuffer + buf).split('\n');
        lineBuffer = lines.pop(); // keep incomplete
        for (const line of lines) {
          const txt = line.replace(/\x1B\[[0-9;]*m/g, ''); // strip ANSI colors
          if (!txt.trim()) continue;
          const isWarn = txt.toLowerCase().includes('warn');
          const isErrLine = txt.toLowerCase().includes('error') || txt.toLowerCase().includes('failed');
          const level = isErr && isErrLine ? 'error' : isWarn ? 'warning' : 'terminal';
          this._emitLine(jobId, txt, level);
          if (isErr) errorOutput += txt + '\n';
          else output += txt + '\n';
        }
      };

      proc.stdout?.on('data', (d) => flushLine(d.toString(), false));
      proc.stderr?.on('data', (d) => flushLine(d.toString(), true));

      proc.on('close', (code) => {
        // Flush remaining buffer
        if (lineBuffer.trim()) this._emitLine(jobId, lineBuffer, 'terminal');
        resolve({ success: code === 0, output, error: errorOutput, code });
      });

      proc.on('error', (err) => {
        this._emitLine(jobId, `Command error: ${err.message}`, 'error');
        resolve({ success: false, output, error: err.message, code: -1 });
      });

      setTimeout(() => {
        if (!proc.killed) {
          proc.kill();
          this._emitLine(jobId, `Command timed out after ${timeout / 1000}s`, 'error');
          resolve({ success: false, output, error: 'Timeout', code: -1 });
        }
      }, timeout);
    });
  }

  /**
   * npm install <packages...>
   * Shows each line as it installs — just like watching a terminal.
   */
  async npmInstall(serviceDir, serviceName, jobId, packages = []) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Runner',
      message: `Installing packages for ${serviceName}...`
    });

    const args = packages.length > 0
      ? ['install', ...packages]
      : ['install', '--prefer-offline', '--no-audit'];

    return this.runCommand('npm', args, serviceDir, jobId, { timeout: this.withMinimumTimeout(300000) });
  }

  /**
   * Create a Vite + React app using the official create command.
   * Mirrors exactly what a human developer would type.
   */
  async createViteApp(parentDir, appName, jobId) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Runner',
      message: `Creating Vite + React app: ${appName}...`
    });

    // Step 1: npm create vite@latest appName -- --template react
    const create = await this.runCommand(
      'npm', ['create', 'vite@latest', appName, '--', '--template', 'react'],
      parentDir, jobId, { timeout: this.withMinimumTimeout(120000) }
    );

    const appDir = path.join(parentDir, appName);

    if (!await fs.pathExists(appDir)) {
      // Sometimes create vite uses different casing — just ensure dir
      this._emitLine(jobId, `Creating ${appDir} manually...`, 'warning');
      await fs.ensureDir(appDir);
    }

    return { success: create.success || await fs.pathExists(appDir), appDir };
  }

  /**
   * Install Tailwind CSS v3 with PostCSS (team template pattern).
   *
   * Pattern from MICROSERVICE_PATTERN_README.md:
   *   npm install -D tailwindcss@3 postcss autoprefixer
   *   npx tailwindcss init -p   (generates tailwind.config.js + postcss.config.js)
   *
   * This is the standard v3 PostCSS pattern — NOT @tailwindcss/vite (v4).
   * src/index.css uses: @tailwind base; @tailwind components; @tailwind utilities;
   */
  async installTailwindPostCSS(appDir, jobId) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Runner',
      message: 'Installing Tailwind CSS v3 (PostCSS pattern)...'
    });

    // Step 1: install tailwindcss v3 + postcss + autoprefixer
    await this.runCommand(
      'npm', ['install', '-D', 'tailwindcss@3', 'postcss', 'autoprefixer'],
      appDir, jobId, { timeout: this.withMinimumTimeout(120000) }
    );

    // Step 2: init — generates tailwind.config.js + postcss.config.js
    const init = await this.runCommand(
      'npx', ['tailwindcss', 'init', '-p'],
      appDir, jobId, { timeout: this.withMinimumTimeout(30000) }
    );

    return init;
  }

  /**
   * Install React Router, axios, react-hot-toast, react-icons for the frontend.
   */
  async installFrontendLibs(appDir, jobId) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Runner',
      message: 'Installing frontend libraries...'
    });

    return this.runCommand(
      'npm', ['install', 'react-router-dom', 'axios', 'react-hot-toast', 'react-icons', 'lucide-react'],
      appDir, jobId, { timeout: this.withMinimumTimeout(120000) }
    );
  }

  /**
   * @deprecated Use installTailwindPostCSS() instead.
   * Kept for compatibility — redirects to PostCSS method.
   */
  async installTailwindVite(appDir, jobId) {
    return this.installTailwindPostCSS(appDir, jobId);
  }

  /**
   * npm run build
   */
  async npmBuild(serviceDir, serviceName, jobId) {
    this.io.to(jobId).emit('agent:working', {
      agent: 'Runner',
      message: `Building ${serviceName}...`
    });
    return this.runCommand('npm', ['run', 'build'], serviceDir, jobId, { timeout: this.withMinimumTimeout(300000) });
  }

  /**
   * Start a service with npm start (or npm run dev for Vite).
   * Streams every output line. Detects "ready" messages to know when started.
   */
  async startService(serviceDir, serviceName, port, jobId, { useDevMode = false } = {}) {
    return new Promise((resolve) => {
      this.io.to(jobId).emit('agent:working', {
        agent: 'Runner',
        message: `Starting ${serviceName} on port ${port}...`
      });

      const args = useDevMode ? ['run', 'dev'] : ['start'];
      this._emitCmd(jobId, `npm ${args.join(' ')}`, serviceDir);

      const proc = spawn('npm', args, {
        cwd: serviceDir,
        shell: true,
        env: { ...process.env, PORT: String(port), NODE_ENV: useDevMode ? 'development' : 'production' }
      });

      let resolved = false;
      let output = '';
      let errorOutput = '';
      let startTimeout;

      const tryResolve = (success, extra = {}) => {
        if (!resolved) {
          resolved = true;
          clearTimeout(startTimeout);
          resolve({ success, pid: proc.pid, output, error: errorOutput, ...extra });
        }
      };

      const onLine = (txt, isErr) => {
        const clean = txt.replace(/\x1B\[[0-9;]*m/g, '').trim();
        if (!clean) return;

        const isErrLine = clean.toLowerCase().includes('error') || clean.toLowerCase().includes('failed') || clean.toLowerCase().includes('cannot');
        const level = isErr && isErrLine ? 'error' : isErr ? 'warning' : 'terminal';

        this.io.to(jobId).emit('log', {
          level,
          agent: serviceName,
          message: clean,
          timestamp: new Date().toISOString()
        });

        if (isErr) errorOutput += clean + '\n';
        else output += clean + '\n';

        // Detect successful startup signals
        const lower = clean.toLowerCase();
        const isReady = lower.includes('listening') || lower.includes('running on') ||
          lower.includes('started') || lower.includes('ready') ||
          lower.includes(`:${port}`) || lower.includes('local:') ||
          lower.includes('network:') || lower.includes('server is running');

        if (isReady && !resolved) {
          this.runningProcesses.set(serviceName, { process: proc, pid: proc.pid, port });
          this.io.to(jobId).emit('service:running', {
            service: serviceName, port, url: `http://localhost:${port}`
          });
          tryResolve(true, { url: `http://localhost:${port}` });
        }
      };

      let stdoutBuf = '', stderrBuf = '';
      proc.stdout?.on('data', (d) => {
        (stdoutBuf + d.toString()).split('\n').forEach((l, i, arr) => {
          if (i < arr.length - 1) onLine(l, false);
          else stdoutBuf = l;
        });
      });
      proc.stderr?.on('data', (d) => {
        (stderrBuf + d.toString()).split('\n').forEach((l, i, arr) => {
          if (i < arr.length - 1) onLine(l, true);
          else stderrBuf = l;
        });
      });

      proc.on('close', (code) => {
        this.runningProcesses.delete(serviceName);
        if (stderrBuf.trim()) onLine(stderrBuf, true);
        if (!resolved) {
          this.io.to(jobId).emit('service:error', { service: serviceName, error: errorOutput });
          tryResolve(false);
        }
      });

      proc.on('error', (err) => {
        tryResolve(false, { error: err.message });
      });

      // Assume running after 30s if process is alive
      startTimeout = setTimeout(() => {
        if (!resolved && proc.pid && !proc.killed) {
          this.runningProcesses.set(serviceName, { process: proc, pid: proc.pid, port });
          this.io.to(jobId).emit('service:running', {
            service: serviceName, port, url: `http://localhost:${port}`
          });
          tryResolve(true, { url: `http://localhost:${port}` });
        } else if (!resolved) {
          tryResolve(false, { error: errorOutput || 'Service did not start' });
        }
      }, 30000);
    });
  }

  /**
   * Kill whatever process is using a port before we start something new there.
   * Fixes EADDRINUSE from leftover gateway/service processes between runs.
   */
  async killPort(port, jobId) {
    return new Promise((resolve) => {
      if (jobId) {
        this.io.to(jobId).emit('log', {
          level: 'info', agent: 'Runner',
          message: `Checking port ${port} — killing any existing process...`,
          timestamp: new Date().toISOString()
        });
      }

      let cmd, args;
      if (process.platform === 'win32') {
        cmd = 'cmd';
        args = ['/c', `FOR /F "tokens=5" %P IN ('netstat -a -n -o ^| findstr ":${port} "') DO (taskkill /F /PID %P 2>NUL)`];
      } else {
        cmd = 'sh';
        args = ['-c', `lsof -ti:${port} | xargs -r kill -9 2>/dev/null; true`];
      }

      const proc = spawn(cmd, args, { shell: false, stdio: 'pipe' });
      const done = () => { clearTimeout(t); resolve(); };
      proc.on('close', done);
      proc.on('error', done);
      const t = setTimeout(done, 3000);
    });
  }

  async stopAll() {
    for (const [name, info] of this.runningProcesses.entries()) {
      try { treeKill(info.pid, 'SIGTERM'); } catch {}
    }
    this.runningProcesses.clear();
  }

  async stop(serviceName) {
    const info = this.runningProcesses.get(serviceName);
    if (info) { try { treeKill(info.pid, 'SIGTERM'); } catch {} this.runningProcesses.delete(serviceName); }
  }

  getRunning() {
    const result = {};
    for (const [name, info] of this.runningProcesses.entries()) {
      result[name] = { port: info.port, pid: info.pid, url: `http://localhost:${info.port}` };
    }
    return result;
  }

  async hasPackageJson(dir) {
    return fs.pathExists(path.join(dir, 'package.json'));
  }
}

module.exports = AppRunnerService;
