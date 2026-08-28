#!/usr/bin/env python3
"""Load the server modules into the legacy shared runtime namespace."""
from __future__ import annotations

from pathlib import Path

# Order matters because these files share one runtime namespace.
_RUNTIME_PARTS = (
    'server_modules/core/bootstrap.py',
    'server_modules/core/dev_runtime.py',
    'agents/server/build_repair.py',
    'qa_agent/server/unit_support.py',
    'server_modules/srs/srs_runtime.py',
    'server_modules/deploy/deploy_runtime.py',
    'qa_agent/server/unit_stage.py',
    'qa_agent/server/e2e_stage.py',
    'qa_agent/server/e2e_final.py',
    'qa_agent/server/runtime_repair.py',
    'agents/server/images.py',
    'qa_agent/server/verification.py',
    'agents/server/chat_bugfix.py',
    'agents/server/agent_pipeline.py',
    'agents/server/feature_actions.py',
    'agents/server/scope_map.py',
    'agents/server/pencil_page.py',
    'agents/server/project_ops.py',
    'server_modules/ui/http_base.py',
    'server_modules/ui/http_handler.py',
    'server_modules/srs/srs_api.py',
    'server_modules/deploy/deploy_api.py',
    'server_modules/core/jobs.py',
    'server_modules/deploy/jobs.py',
    'server_modules/core/main.py',
)


def _load_runtime_parts() -> None:
    root = Path(__file__).resolve().parent
    namespace = globals()
    for relative_path in _RUNTIME_PARTS:
        path = root / relative_path
        source = path.read_text(encoding="utf-8")
        exec(compile(source, str(path), "exec"), namespace, namespace)


_load_runtime_parts()
