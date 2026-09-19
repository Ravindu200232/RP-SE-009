"""Keep validated artifact hashes and optimistic source baselines after an agent repair."""
from __future__ import annotations

import json
from pathlib import Path

from .security import sha256_file


def record_repairs(store, run_id, agent, applied=False):
    run = store.get_run(run_id)
    root, source = Path(run["staged_path"]), Path(run["project_path"])
    records = {record["path"]: record for record in store.get_artifacts(run_id)}
    for relative in agent.changed:
        path = root / relative
        original = records.get(relative)
        source_path = source / relative
        records[relative] = {
            "path": relative, "kind": original["kind"] if original else "source-patch",
            "sha256": sha256_file(path), "size": path.stat().st_size,
            "original_exists": bool(agent.baselines[relative]) if applied else (original["original_exists"] if original else source_path.exists()),
            "original_sha256": agent.baselines[relative] if applied else (original.get("original_sha256", "") if original else agent.baselines[relative]),
        }
    manifest_path = root / "deployment-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["agent_owned_files"] = manifest["artifacts"] = sorted(records)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    original = records["deployment-manifest.json"]
    if applied:
        original.update(original_exists=True, original_sha256=original["sha256"])
    original.update(sha256=sha256_file(manifest_path), size=manifest_path.stat().st_size)
    store.set_artifacts(run_id, list(records.values()))
    return list(records.values())
