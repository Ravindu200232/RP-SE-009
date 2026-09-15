# Starts the HTTP, WebSocket and sidecar services.
def start_http():
    try:

        httpd = _UIServer((bind_host(), UI_PORT), UIHandler)
        print(f"HTTP server listening on 127.0.0.1:{UI_PORT}")
        httpd.serve_forever()
    except Exception as e:
        print(f"HTTP server failed: {e}")


def resume_interrupted_projects():
    """Resume only crash-interrupted work once; failed and explicitly paused work waits."""
    if not PROD_DIR.is_dir():
        return
    recovered = set()
    pending = sorted(PROD_DIR.glob("*/.agentforge/requests/*.json"), key=lambda item: item.name)
    if pending and not wait_for_srs_startup():
        log.warning("Saved requests remain available; the SRS service could not start")
        return
    for path in pending:
        try:
            request = json.loads(path.read_text(encoding="utf-8"))
            if request.get("sync_error"):
                continue
            project, owner, kind = request["project"], request["owner"], request["target"]
            if kind not in _DURABLE_TARGETS or not owner or auth_db.owner_of("project", project) != owner:
                continue
            recovered.add((project, request["agent"]))
            start_run(globals()[kind], tuple(request["args"]), project=project, user={"id": owner}, replay_path=path)
        except (OSError, ValueError, KeyError) as error:
            log.warning("Cannot recover request %s: %s", path.name, error)
    for directory in PROD_DIR.iterdir():
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        try:
            state = ProjectState(directory).read()
            for role, agent in state.get("agents", {}).items():
                if (directory.name, role) in recovered:
                    continue
                if agent.get("status") != "interrupted":
                    continue
                request = agent.get("request", {})
                owner = agent.get("owner")
                if not request or not owner or auth_db.owner_of("project", directory.name) != owner:
                    continue
                start_run(run_agent_pipeline, ("", request.get("model", ""), request.get("think"), "",
                    directory.name, "", "", request.get("stack", ""), "", role == "designer"),
                    project=directory.name, user={"id": owner})
        except (OSError, ValueError) as error:
            log.warning("Cannot recover %s: %s", directory.name, error)


async def main():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    RUNTIMES.start_watcher()

    threading.Thread(target=MONGO.ensure_running, daemon=True).start()
    threading.Thread(target=start_srs_api, daemon=True).start()
    threading.Thread(target=start_deploy_api, daemon=True).start()
    threading.Thread(target=start_http, daemon=True).start()
    threading.Thread(target=resume_interrupted_projects, daemon=True).start()
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
    # Kept alive on purpose. Reached through a tunnel, a socket with nothing on
    # it is closed by whatever is in the middle after a minute or two, and the
    # studio then reconnects every time the build it is watching goes quiet.
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
