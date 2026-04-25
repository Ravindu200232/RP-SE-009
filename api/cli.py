"""Agent 2 Developer terminal CLI.

Reads SRS JSON from stdin or a file path and runs the LangGraph generation
pipeline (LangChain + Ollama + Qwen 2.5-Coder-14B) to produce 5 styled React
variants for each component category and 5 styled variants for each page
template.

Usage examples:
    python cli.py --srs path/to/srs.json
    python cli.py --srs - < srs.json
    python cli.py --srs srs.json --model qwen2.5-coder:14b --out runs/myapp
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

from app.graph import run_build
from app.llm import DEFAULT_MODEL


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agent 2 Developer CLI")
    parser.add_argument("--srs", required=True, help="Path to SRS JSON file, or '-' for stdin")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model tag (default: {DEFAULT_MODEL})")
    parser.add_argument("--out", default=None, help="Output directory (default: runs/<uuid>)")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-step log lines")
    return parser.parse_args()


def load_srs(path: str) -> dict:
    if path == "-":
        return json.loads(sys.stdin.read())
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> int:
    args = parse_args()
    try:
        srs_json = load_srs(args.srs)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[error] failed to read SRS JSON: {exc}", file=sys.stderr)
        return 2

    base = Path(__file__).resolve().parent
    out_dir = Path(args.out) if args.out else base / "runs" / str(uuid4())

    project = (
        srs_json.get("project_name")
        or srs_json.get("name")
        or (srs_json.get("metadata") or {}).get("project")
        or "GeneratedApp"
    )

    print(f"Agent 2 Developer")
    print(f"  project : {project}")
    print(f"  model   : {args.model}")
    print(f"  output  : {out_dir}")
    print("-" * 60)

    started = time.time()

    def on_log(message: str) -> None:
        if not args.quiet:
            elapsed = time.time() - started
            print(f"[{elapsed:6.1f}s] {message}", flush=True)

    try:
        state = run_build(
            srs_json=srs_json,
            output_dir=str(out_dir),
            model=args.model,
            on_log=on_log,
        )
    except Exception as exc:
        print(f"[error] generation failed: {exc}", file=sys.stderr)
        return 1

    files = state.get("files", [])
    print("-" * 60)
    print(f"Done. Generated {len(files)} files in {time.time() - started:.1f}s.")
    print(f"Manifest: {out_dir / 'build.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
