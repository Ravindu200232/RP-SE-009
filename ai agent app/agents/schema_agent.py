"""
agents/schema_agent.py — Data/Schema agent.

Writes the data layer deterministically from the spec's data_model:
  • lib/mongodb.ts  — cached connection + in-memory fallback
  • lib/api.ts      — JSON response helpers
  • models/*.ts     — Mongoose schemas with the overwrite guard

No LLM involvement for standard schemas — these are exactly the files a small
model breaks, so they are generated as fixed strings.
"""
import logging

from agents import scaffold

log = logging.getLogger("schema")


class SchemaAgent:
    def __init__(self, write):
        # write(relpath: str, content: str) — provided by the pipeline so files
        # are tracked in built_files and streamed to the UI.
        self.write = write

    def generate(self, spec: dict) -> list:
        files = scaffold.data_layer_files(spec)
        models = [scaffold.pascal(m.get("name", "Item")) for m in (spec.get("data_model") or [])]
        log.info("   Data layer: %d model(s) %s", len(models), models)
        for rel, content in files.items():
            self.write(rel, content)
        return list(files.keys())
