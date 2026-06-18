"""Freeze / concurrency tests for the FastAPI backend.

Starts the REAL app in an in-process uvicorn thread and monkeypatches
editor.edit_component into a deterministic slow/failing blocking call (no Ollama
needed). Proves the event loop never freezes: /health and /openapi.json must
answer instantly while a heavy edit is blocking a worker thread, two heavy
requests must not deadlock, and worker failures must not crash the server.

Run:  python _test_freeze.py   (exit 1 on any failure)
"""
import os, sys, json, time, threading, urllib.request, urllib.error
import concurrent.futures as cf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
import app.editor as editor_mod
import app.server as server_mod

PORT = 8137
BASE = f"http://127.0.0.1:{PORT}"
SLOW = 2.5
RESULTS = []


def rec(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  -> {detail}" if detail else ""), flush=True)


def http(path, method="GET", body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data else {})
    t = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, time.time() - t, r.read()
    except urllib.error.HTTPError as e:               # 4xx/5xx still proves the server answered
        return e.code, time.time() - t, e.read()


def edit(body=None, timeout=20):
    return http("/api/edit-element", "POST",
                body or {"project_id": "t", "component_id": "home", "prompt": "x"}, timeout)


def main():
    # --- deterministic slow blocking edit (no Ollama) ---
    def slow_edit(*a, **k):
        time.sleep(SLOW)
        return {"ok": True, "mode": "TEST_SLOW"}
    editor_mod.edit_component = slow_edit

    # --- start the real app in a background thread ---
    config = uvicorn.Config(server_mod.app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    up = False
    for _ in range(60):
        try:
            if http("/health", timeout=1)[0] == 200:
                up = True; break
        except Exception:
            time.sleep(0.25)
    if not up:
        rec("server started", False, "did not come up"); return _finish(server)

    print("=" * 66)
    print(f"FREEZE SUITE  (slow blocking edit = {SLOW}s, in-process uvicorn :{PORT})")
    print("=" * 66)

    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        # 1) /health answers FAST while a slow blocking edit is mid-flight
        fut = ex.submit(edit)
        time.sleep(0.4)                      # ensure the edit is blocking a worker thread
        hcode, hlat, _ = http("/health", timeout=3)
        rec("/health responds while a slow edit blocks a worker", hcode == 200 and hlat < 1.0, f"{hlat:.2f}s")
        # 2) /openapi.json answers while the same edit is still blocking
        ocode, olat, _ = http("/openapi.json", timeout=3)
        rec("/openapi.json responds while a slow edit blocks a worker", ocode == 200 and olat < 2.0, f"{olat:.2f}s")
        scode, slat, _ = fut.result()
        rec("the slow edit still completed (was threadpooled, not dropped)", scode == 200 and slat >= SLOW - 0.5, f"{slat:.1f}s")

    # 3) two heavy requests concurrently -> both finish ~in parallel, server responsive
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        t0 = time.time()
        f1, f2 = ex.submit(edit), ex.submit(edit)
        time.sleep(0.4)
        h2 = http("/health", timeout=3)
        both = f1.result()[0] == 200 and f2.result()[0] == 200
        wall = time.time() - t0
        rec("two heavy edits both complete + /health stays responsive", both and h2[0] == 200 and h2[1] < 1.0,
            f"wall={wall:.1f}s (parallel < {2 * SLOW:.0f}s serial), /health={h2[1]:.2f}s")
        rec("the two heavy edits ran in PARALLEL (threadpool), not serialized", wall < 2 * SLOW - 0.3, f"{wall:.1f}s")

    # 4) a worker that RETURNS a readable error -> client gets it, server stays alive
    editor_mod.edit_component = lambda *a, **k: {"ok": False, "error": "simulated readable failure"}
    code, _, body = edit()
    data = json.loads(body or b"{}")
    rec("failed edit returns a readable string error (not object/crash)",
        code == 200 and not data.get("ok") and isinstance(data.get("error"), str), data.get("error"))

    # 5) a worker that RAISES (e.g. a timeout) -> 5xx readable, server NOT crashed
    def boom(*a, **k):
        raise TimeoutError("ollama timed out")
    editor_mod.edit_component = boom
    code, _, _ = edit()
    rec("worker exception -> error response, no crash", code in (500, 502, 503), f"HTTP {code}")
    alive = http("/health", timeout=3)
    rec("server still ALIVE after a worker exception", alive[0] == 200, f"/health HTTP {alive[0]}")

    _finish(server)


def _finish(server):
    server.should_exit = True
    time.sleep(0.4)
    ok = all(RESULTS)
    print("=" * 66)
    print((f"FREEZE SUITE GREEN  ({sum(RESULTS)}/{len(RESULTS)})" if ok
           else f"FREEZE FAILURES  ({sum(RESULTS)}/{len(RESULTS)} passed)"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
