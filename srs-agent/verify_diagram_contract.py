"""Regression check for diagram guidance and native render coverage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.graphics import renderSVG

from srs_agent.app.generators.diagram_draw import render_native
from srs_agent.app.generators.diagram_runtime import DIAGRAM_KINDS, build_diagrams
from srs_agent.app.generators.standards import DIAGRAM_GUIDANCE, DIAGRAM_NOTATION


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--srs", type=Path, required=True)
    parser.add_argument("--render-dir", type=Path)
    args = parser.parse_args()

    raw = json.loads(args.srs.read_text(encoding="utf-8"))
    envelope = raw.get("srs", raw)
    doc = envelope.get("srs_document", envelope)
    diagrams = build_diagrams(envelope)

    assert {d["kind"] for d in diagrams} == set(DIAGRAM_KINDS)
    assert set(DIAGRAM_GUIDANCE) == set(DIAGRAM_KINDS)
    assert set(DIAGRAM_NOTATION) == set(DIAGRAM_KINDS)

    if args.render_dir:
        args.render_dir.mkdir(parents=True, exist_ok=True)
    for diagram in diagrams:
        kind = diagram["kind"]
        assert diagram["question"].startswith("What is")
        assert diagram["definition"]
        assert len(diagram["drawing_rules"]) >= 3
        assert len(diagram["notation"]) >= 3
        drawing = render_native(kind, doc, 720)
        assert drawing is not None, f"native renderer returned nothing for {kind}"
        if args.render_dir:
            renderSVG.drawToFile(drawing, str(args.render_dir / f"{kind}.svg"))

    print(f"Diagram contracts: {len(diagrams)}/{len(diagrams)} guided and rendered")


if __name__ == "__main__":
    main()
