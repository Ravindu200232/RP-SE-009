#!/usr/bin/env python3
"""Load the server's runtime parts into one shared namespace.

These files were split for readability, not for isolation: they are one
program, and each one expects the names the previous ones defined. Executing
them in order into a single namespace keeps that honest, and keeps `__file__`
pointing at the repository root for every one of them.

The agents themselves are ordinary importable packages beside this file
(`builder-agent/`, `qa-agent/`, `srs-agent/`, `deployment-agent/`). Only the
server's own glue lives here.
"""
from __future__ import annotations

from pathlib import Path

# Order matters: each part uses what the ones before it defined.
_RUNTIME_PARTS = (
    'server_modules/core/bootstrap.py',
    'server_modules/core/dev_runtime.py',
    'server_modules/srs/srs_runtime.py',
    'server_modules/deploy/deploy_runtime.py',
    'server_modules/builder/media.py',
    'server_modules/builder/qa.py',
    'server_modules/builder/bridge.py',
    'server_modules/builder/pipeline.py',
    'server_modules/builder/edits.py',
    'server_modules/builder/projects.py',
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
