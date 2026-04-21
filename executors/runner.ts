import { spawn } from "child_process";
import path from "path";

export interface RunResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  timedOut: boolean;
  durationMs: number;
}

export async function runCommand(
  command: string,
  args: string[],
  options: {
    cwd?: string;
    env?: Record<string, string>;
    shell?: boolean;
    timeoutMs?: number;
    maxOutputBytes?: number;
  } = {}
): Promise<RunResult> {
  const start = Date.now();
  const timeout = options.timeoutMs ?? 120000;
  const maxBytes = options.maxOutputBytes ?? 5 * 1024 * 1024;

  return new Promise((resolve) => {
    let stdoutChunks: Buffer[] = [];
    let stderrChunks: Buffer[] = [];
    let stdoutBytes = 0;
    let stderrBytes = 0;
    let timedOut = false;

    const proc = spawn(command, args, {
      cwd: options.cwd,
      env: { ...process.env, ...(options.env || {}) },
      shell: options.shell ?? process.platform === "win32",
      windowsHide: true,
    });

    const timer = setTimeout(() => {
      timedOut = true;
      proc.kill("SIGTERM");
      setTimeout(() => proc.kill("SIGKILL"), 5000);
    }, timeout);

    proc.stdout?.on("data", (chunk: Buffer) => {
      stdoutBytes += chunk.length;
      if (stdoutBytes <= maxBytes) stdoutChunks.push(chunk);
    });

    proc.stderr?.on("data", (chunk: Buffer) => {
      stderrBytes += chunk.length;
      if (stderrBytes <= maxBytes) stderrChunks.push(chunk);
    });

    proc.on("close", (exitCode) => {
      clearTimeout(timer);
      resolve({
        stdout: Buffer.concat(stdoutChunks).toString("utf-8"),
        stderr: Buffer.concat(stderrChunks).toString("utf-8"),
        exitCode: exitCode ?? -1,
        timedOut,
        durationMs: Date.now() - start,
      });
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      resolve({
        stdout: "",
        stderr: err.message,
        exitCode: -1,
        timedOut: false,
        durationMs: Date.now() - start,
      });
    });
  });
}

export async function checkCommandAvailable(cmd: string): Promise<boolean> {
  const checkCmd = process.platform === "win32" ? "where" : "which";
  const result = await runCommand(checkCmd, [cmd], { timeoutMs: 5000 });
  return result.exitCode === 0;
}
