# Server modules

`server.py` is the stable backend entrypoint. `server_runtime.py` assembles the runtime in an explicit order so shared server state is initialized once.

- `core/` — process, job and dev-server lifecycle.
- `srs/` — SRS bridge and API.
- `deploy/` — deployment bridge and jobs.
- `ui/` — backend HTTP handling.

Builder-owned server workflows live in `agents/server/`. QA-owned server workflows live in `qa_agent/server/`; they are not duplicated here.

Keep runtime fragments focused, below 1000 lines where practical, and preserve the public server contract.
