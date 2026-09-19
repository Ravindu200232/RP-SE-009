# Starts the HTTP, WebSocket and sidecar services.
def start_http():
    try:

        httpd = _UIServer((bind_host(), UI_PORT), UIHandler)
        print(f"HTTP server listening on 127.0.0.1:{UI_PORT}")
        httpd.serve_forever()
    except Exception as e:
        print(f"HTTP server failed: {e}")


def _runs_the_last_server_left() -> dict:
    """{(project, agent): status} as the last server wrote it, read before anything else writes.

    Stored status, not the read one: a read turns `running` and `queued` alike
    into `interrupted`, and the difference is the whole question here. It has to
    be taken in one pass up front, because saving any agent rewrites its whole
    project file and settles that difference away.
    """
    from server_modules.services.project_state import SERVER_ID, read_json
    stored = {}
    for path in PROD_DIR.glob("*/.agentforge/workflow.json"):
        for role, agent in (read_json(path).get("agents") or {}).items():
            if agent.get("server_id") != SERVER_ID:
                stored[(path.parent.parent.name, role)] = str(agent.get("status") or "")
    return stored


def _settle(project: str, role: str, status: str, error: str = "") -> None:
    """Write down where a run stopped, so the studio can offer it rather than run it."""
    try:
        ProjectState(PROD_DIR / project).agent(role, status=status, error=error)
    except (OSError, ValueError) as problem:
        log.warning("Cannot settle %s %s: %s", project, role, problem)


def settle_interrupted_runs():
    """Settle what the last server left behind. Only an unfinished change transaction runs on its own.

    A build that was interrupted comes back as something to press Resume on,
    not as a build that takes the machine before anyone asks for it. Starting
    them here spent the one machine there is on work nobody had just asked for:
    every restart handed the queue to an old build, and whatever the person at
    the studio asked for next sat behind it. A change transaction part-way
    through is the exception - until it finishes, a project's documents
    disagree with its code.
    """
    if not PROD_DIR.is_dir():
        return
    stored = _runs_the_last_server_left()
    for (project, role), status in stored.items():
        if status in ("running", "finishing"):
            _settle(project, role, "interrupted",
                    "The server stopped during this run. Resume it when you want it.")
        elif status == "queued":
            _settle(project, role, "paused",
                    "The server restarted before this run started. Start it again when you want it.")
    transactions = []
    for path in sorted(PROD_DIR.glob("*/.agentforge/requests/*.json"), key=lambda item: item.name):
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            if request.get("sync_error"):
                continue
            project, owner, kind = request["project"], request["owner"], request["target"]
            if kind not in _DURABLE_TARGETS or not owner or auth_db.owner_of("project", project) != owner:
                continue
            if request.get("stage"):
                transactions.append((path, request, project, owner, kind))
                continue
            # Where its run stopped is written down above; the studio offers it
            # from there, so nothing is left to replay.
            log.info("%s %s: saved for Resume, not restarted", project, request["agent"])
            path.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError) as error:
            log.warning("Cannot settle request %s: %s", path.name, error)
    if transactions and not wait_for_srs_startup():
        log.warning("Saved changes remain available; the SRS service could not start")
        return
    for path, request, project, owner, kind in transactions:
        start_run(globals()[kind], tuple(request["args"]), project=project,
                  user={"id": owner}, replay_path=path)


async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    RUNTIMES.start_watcher()

    threading.Thread(target=MONGO.ensure_running, daemon=True).start()
    threading.Thread(target=start_srs_api, daemon=True).start()
    threading.Thread(target=start_deploy_api, daemon=True).start()
    threading.Thread(target=start_http, daemon=True).start()
    threading.Thread(target=settle_interrupted_runs, daemon=True).start()
    print(f"\n{'━'*46}")
    print(f"  ⚡ AgentForge v1.0.0 Starting...")
    print(f"  ⚡ UI Server   →  http://127.0.0.1:{UI_PORT}")
    print(f"  🔌 WebSocket   →  ws://127.0.0.1:{WS_PORT}")
    print(f"  📄 SRS agent   →  http://127.0.0.1:{SRS_PORT}")
    print(f"  🚀 Deploy      →  http://127.0.0.1:{DEPLOY_PORT}")
    print(f"  🧠 Refine      :  {DEFAULT_REFINE}")
    print(f"  🏗️  Build       :  {DEFAULT_BUILD}")
    print(f"  📝 Local development mode")
    print(f"{'━'*46}\n")
    # Send periodic keep-alive pings over SSE tunnels to prevent connection timeouts.
    async with websockets.serve(ws_handler, bind_host(), WS_PORT,
                                ping_interval=20, ping_timeout=60):
        await asyncio.Future()


def shutdown_all():
    global SERVER_STOPPING
    SERVER_STOPPING = True
    try:
        print("\n🛑 Shutting down AgentForge backend...")
    except UnicodeEncodeError:
        print("\n[!] Shutting down AgentForge backend...")

    RUNTIMES.close()
    with _SESSIONS_LOCK:
        sessions = list(_SESSIONS.values())
    for session in sessions:
        try:
            session["agent"].processes.stop_all()
        except Exception as error:
            print(f"   Could not stop build processes: {error}")

    try:
        # Every published preview address stops answering with this server.
        PREVIEW_LINKS.close_all()
    except Exception:                                                # noqa: BLE001
        pass

    try:
        MONGO.stop()
    except:
        pass

    try:
        stop_model(DEFAULT_REFINE)
        stop_model(DEFAULT_BUILD)
        print("   ✅ Ollama models unloaded")
    except:
        pass

atexit.register(shutdown_all)

def handle_signal(sig, frame):
    shutdown_all()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⛔ Stopped.")
        RUNTIMES.close()
