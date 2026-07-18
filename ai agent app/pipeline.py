#!/usr/bin/env python3
"""
pipeline.py — legacy folder-watcher entrypoint.

The Vite/React single-page pipeline that used to live here has been retired.
Locode now builds full-stack Next.js + MongoDB apps through the 6-agent pipeline
in server.py. This script is kept as a headless convenience: drop a .txt idea
file into ideas/ and it runs the exact same pipeline server.py uses (just without
the web UI / WebSocket streaming).

For the full experience (live preview, streaming code, reprompt) run:

    python server.py      →  http://localhost:7824
"""
import sys
import time
import logging
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import server            # reuse the real Next.js pipeline + Ollama/model config
from agents import llm

BASE_DIR  = Path(__file__).parent
IDEAS_DIR = BASE_DIR / "ideas"

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pipeline")


class IdeaFileHandler(FileSystemEventHandler):
    def __init__(self):
        self.processing = set()

    def on_created(self, event):  self._handle(event.src_path)
    def on_modified(self, event): self._handle(event.src_path)

    def _handle(self, path):
        p = Path(path)
        if p.suffix != ".txt" or p in self.processing:
            return
        time.sleep(0.5)
        self.processing.add(p)
        try:
            idea = p.read_text(encoding="utf-8").strip()
            if not idea:
                log.warning("Idea file is empty. Skipping.")
                return
            log.info("=" * 60)
            log.info("🚀 Building: %s", idea[:120])
            log.info("=" * 60)
            # Every stage is pinned to local Gemma 4 with the verified 98K context.
            server.run_pipeline(idea, llm.GEN_MODEL, llm.GEN_MODEL)
        finally:
            self.processing.discard(p)


if __name__ == "__main__":
    IDEAS_DIR.mkdir(parents=True, exist_ok=True)
    log.info("🤖 Locode headless pipeline — Next.js + MongoDB edition")
    log.info("   👁️  Watching : %s", IDEAS_DIR)
    log.info("   🧠 Model    : %s (98K local GPU context, thinking %s)", llm.LOCAL_MODEL, llm.THINK)
    log.info("   Drop a .txt file into ideas/ to build. Ctrl-C to stop.\n")

    observer = Observer()
    observer.schedule(IdeaFileHandler(), str(IDEAS_DIR), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("\n⛔ Stopping…")
        observer.stop()
    observer.join()
