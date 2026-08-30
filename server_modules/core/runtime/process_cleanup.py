# Process Cleanup: one focused part of the development-server lifecycle.
# Purpose: Kill a dev server *and its children* — npm/next spawn workers.
def _kill_proc_tree(proc):
    """Kill a dev server *and its children* — npm/next spawn workers."""
    if proc is None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True, timeout=15)
            return

        try:
            pgid = os.getpgid(proc.pid)
            own_group = pgid != os.getpgid(0)
        except Exception:
            pgid, own_group = None, False

        if own_group:
            try:
                os.killpg(pgid, signal.SIGTERM)
                proc.wait(timeout=4)
            except Exception:
                pass
            try:
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                pass
            return

        try:
            proc.terminate()
            proc.wait(timeout=4)
        except Exception:
            pass
        try:
            proc.kill()
        except Exception:
            pass
    except Exception:
        pass


# Purpose: Stop an untracked `next dev` already serving this exact project.
def _kill_project_next(proj_dir: Path):
    """Stop an untracked `next dev` already serving this exact project."""
    target = str(Path(proj_dir).resolve())
    try:
        if os.name == "nt":
            q = target.replace("'", "''")
            script = (f"$p='{q}'; Get-CimInstance Win32_Process | "
                      "Where-Object {$_.Name -eq 'node.exe' -and $_.CommandLine -and "
                      "$_.CommandLine.IndexOf($p,[StringComparison]::OrdinalIgnoreCase) -ge 0 "
                      "-and $_.CommandLine -match 'next(.+)?dev'} | ForEach-Object {$_.ProcessId}")
            out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                 capture_output=True, text=True, timeout=12).stdout
            for pid in {x.strip() for x in out.splitlines() if x.strip().isdigit()}:
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                               capture_output=True, timeout=10)
        else:
            out = subprocess.run(["ps", "-eo", "pid=,args="], capture_output=True, text=True, timeout=5).stdout
            for line in out.splitlines():
                if target in line and re.search(r"next.*\bdev\b", line):
                    pid = line.strip().split(None, 1)[0]
                    if pid.isdigit() and int(pid) != os.getpid():
                        try: os.kill(int(pid), signal.SIGKILL)
                        except OSError: pass
        time.sleep(0.25)
        (Path(proj_dir) / ".next" / "dev" / "lock").unlink(missing_ok=True)
    except Exception as e:
        log.debug(f"stray next cleanup for {proj_dir}: {e}")


# Purpose: Force-kill whatever holds a port, on Windows as well as POSIX.
def _kill_port(port: int):
    """Force-kill whatever holds a port, on Windows as well as POSIX."""
    if os.name == "nt":
        try:
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                                 capture_output=True, text=True,
                                 timeout=10).stdout
            pids = set()
            for line in out.splitlines():
                parts = line.split()

                if len(parts) >= 5 and parts[1].rsplit(":", 1)[-1] == str(port):
                    pids.add(parts[-1])
            for pid in pids - {"0", "4"}:
                subprocess.run(["taskkill", "/F", "/T", "/PID", pid],
                               capture_output=True, timeout=10)
            if pids:
                time.sleep(0.5)
        except Exception:
            pass
        return

    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True, text=True, timeout=5
        )
        pids = [p.strip() for p in result.stdout.strip().split() if p.strip()]
        for pid in pids:
            try: subprocess.run(["kill", "-9", pid], timeout=3, capture_output=True)
            except: pass
        if pids:
            time.sleep(0.5)
    except Exception:
        pass


# Purpose: Terminate the tracked dev server, whatever stack it is.
def _stop_dev_proc():
    """Terminate the tracked dev server, whatever stack it is."""
    if active_vite.get("proc"):
        _kill_proc_tree(active_vite["proc"])
        active_vite["proc"] = None





