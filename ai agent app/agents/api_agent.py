"""
agents/api_agent.py — API agent.

Writes Next.js App Router route handlers (app/api/<resource>/route.ts and
[id]/route.ts) as standard CRUD templates derived from the spec's data_model.
Deterministic for standard CRUD — the LLM never writes these, which removes a
whole class of backend bugs and gives the frontend a fixed, known contract.
"""
import logging

from agents import scaffold

log = logging.getLogger("api")


class ApiAgent:
    def __init__(self, write):
        self.write = write

    def generate(self, spec: dict) -> list:
        files = scaffold.api_files(spec)
        if not files:
            log.info("   No data model — skipping API routes (client-only app)")
            return []
        log.info("   API routes: %d handler file(s)", len(files))
        for rel, content in files.items():
            self.write(rel, content)
        return list(files.keys())
