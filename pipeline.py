#!/usr/bin/env python3
"""Stable entrypoint for the modular AgentForge idea-file pipeline."""
from agents.server.pipeline.config import log
from agents.server.pipeline.dev_server import (
    active_proc,
    handle_signal,
    shutdown_backend,
    start_vite,
    stop_vite,
)
from agents.server.pipeline.runner import run_pipeline, write_readme
from agents.server.pipeline.watcher import IdeaFileHandler, main

__all__ = [
    "IdeaFileHandler",
    "active_proc",
    "handle_signal",
    "log",
    "main",
    "run_pipeline",
    "shutdown_backend",
    "start_vite",
    "stop_vite",
    "write_readme",
]

if __name__ == "__main__":
    main()
