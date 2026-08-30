"""Render what the SRS evaluation dataset actually covers.

This turns `srs_cases.csv` into a document a reviewer can read end to end: which
claim each row is evidence for, how the domain x archetype x scale matrix is
filled in, which input scripts are paired with which output languages, and a
worked example from every category so the expectations are concrete rather than
described.

It reads the dataset only — no model is called and nothing is generated — so the
report is reproducible on any machine:

    python -m test.eval.report                 # write test/eval/results/coverage.md
    python -m test.eval.report --stdout        # print instead of writing
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .dataset import Case, DATASET_PATH, load_cases
from .validate import validate

RESULTS_DIR = Path(__file__).resolve().parent / "results"
REPORT_PATH = RESULTS_DIR / "coverage.md"

#: Scale columns, ordered smallest first rather than alphabetically.
SCALES = ("micro", "small", "medium", "large")

#: How many characters of a brief to show in a worked example.
_BRIEF_PREVIEW = 150


def _table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> list[str]:
    """A GitHub-flavoured markdown table."""
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return out


def _tier_spread(cases: Sequence[Case]) -> str:
    counts = Counter(c.tier for c in cases)
    return ", ".join(f"T{tier}x{counts[tier]}" for tier in sorted(counts))


def _preview(text: str, limit: int = _BRIEF_PREVIEW) -> str:
    """One-line, table-safe preview of a brief."""
    flat = " ".join(text.split()).replace("|", "\\|")
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _headline(cases: Sequence[Case]) -> list[str]:
    languages = {c.output_language for c in cases}
    scripts = {c.input_script for c in cases}
    matrix = [c for c in cases if c.category == "matrix"]
    cells = {(c.domain, c.archetype) for c in matrix}
    return [
        "## At a glance",
        "",
        *_table(
            ["Measure", "Value"],
            [
                ["Cases", len(cases)],
                ["Claims covered", len({c.claim for c in cases})],
                ["Categories", len({c.category for c in cases})],
                ["Tier 1 / 2 / 3", " / ".join(
                    str(sum(1 for c in cases if c.tier == t)) for t in (1, 2, 3))],
                ["Domain x archetype cells", len(cells)],
                ["Input scripts", len(scripts)],
                ["Output languages", len(languages)],
                ["Hand-written / generated / parallel-authored", " / ".join(
                    str(sum(1 for c in cases if c.origin == o))
                    for o in ("hand-written", "generated", "parallel-authored"))],
            ],
        ),
        "",
    ]


def _claims_section(cases: Sequence[Case]) -> list[str]:
    grouped: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        grouped[case.claim].append(case)

    rows = []
    for claim, members in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        rows.append([claim, members[0].category, len(members), _tier_spread(members)])

    return [
        "## Claims and their evidence",
        "",
        "Every row is evidence for exactly one claim about the SRS agent. A claim",
        "with no passing rows is a claim the project cannot make.",
        "",
        *_table(["Claim", "Category", "Cases", "Tiers"], rows),
        "",
    ]


def _matrix_section(cases: Sequence[Case]) -> list[str]:
    matrix = [c for c in cases if c.category == "matrix"]
    if not matrix:
        return []

    domains = sorted({c.domain for c in matrix})
    archetypes = sorted({c.archetype for c in matrix})
    present = {(c.domain, c.archetype, c.scale) for c in matrix}

    rows = []
    for domain in domains:
        cells = []
        for archetype in archetypes:
            filled = [s for s in SCALES if (domain, archetype, s) in present]
            if not filled:
                cells.append("—")
            elif len(filled) == len(SCALES):
                cells.append("****")
            else:
                cells.append("".join("*" if s in filled else "." for s in SCALES))
        rows.append([domain, *cells])

    covered = len({(d, a) for d, a, _ in present})
    return [
        "## Domain x archetype x scale matrix",
        "",
        f"{len(matrix)} rows over {covered} domain x archetype pairs, each at "
        f"{'/'.join(SCALES)} scale. `****` means all four scales are present, `—` "
        "means the pair is deliberately not exercised (a hospital does not run a "
        "portfolio site; a hotel has no point of sale).",
        "",
        *_table(["domain", *archetypes], rows),
        "",
    ]


def _language_section(cases: Sequence[Case]) -> list[str]:
    language_rows = [c for c in cases
                     if c.category in {"language_matrix", "language_generality",
                                       "language_drift", "language_classify", "mixed_script"}]
    if not language_rows:
        return []

    scripts = sorted({c.input_script for c in language_rows})
    languages = sorted({c.output_language for c in language_rows})
    pairs = Counter((c.input_script, c.output_language) for c in language_rows)

    rows = []
    for script in scripts:
        rows.append([script, *[pairs.get((script, lang), "·") for lang in languages]])

    return [
        "## Input script x output language",
        "",
        "The agent must produce the requested document language whatever script the",
        "customer wrote in — including romanised Sinhala and Tamil, which is how most",
        "briefs actually arrive. `·` marks a pair the dataset does not exercise.",
        "",
        *_table(["input \\ output", *languages], rows),
        "",
    ]


def _categories_section(cases: Sequence[Case]) -> list[str]:
    grouped: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        grouped[case.category].append(case)

    rows = []
    for category, members in sorted(grouped.items(), key=lambda kv: -len(kv[1])):
        keys = sorted({k for m in members for k in m.expected})
        rows.append([category, len(members), _tier_spread(members),
                     ", ".join(f"`{k}`" for k in keys) or "—"])

    return [
        "## Categories and what they assert",
        "",
        *_table(["Category", "Cases", "Tiers", "Expectation keys used"], rows),
        "",
    ]


def _examples_section(cases: Sequence[Case]) -> list[str]:
    grouped: dict[str, list[Case]] = defaultdict(list)
    for case in cases:
        grouped[case.category].append(case)

    lines = [
        "## A worked example from every category",
        "",
        "One real row per category, so the expectations above are concrete.",
        "",
    ]
    for category in sorted(grouped):
        case = grouped[category][0]
        lines.append(f"### {category} — `{case.id}`")
        lines.append("")
        lines.append(f"*{case.note}*")
        lines.append("")
        lines.append(f"> {_preview(case.brief, 400)}")
        lines.append("")
        lines.append(f"- **Claim:** {case.claim}")
        lines.append(f"- **Tier:** {case.tier} · **Origin:** {case.origin} · "
                     f"**Input script:** {case.input_script} · "
                     f"**Output language:** {case.output_language}")
        if case.expected:
            lines.append(f"- **Must hold:** `{json.dumps(case.expected, ensure_ascii=False)}`")
        if case.edit_prompt:
            lines.append(f"- **Edit applied:** {case.edit_prompt}")
            lines.append(f"- **Must hold after the edit:** "
                         f"`{json.dumps(case.expect_after, ensure_ascii=False)}`")
        lines.append("")
    return lines


def _integrity_section(cases: Sequence[Case]) -> list[str]:
    problems = validate(cases)
    lines = ["## Dataset integrity", ""]
    if not problems:
        lines += [
            f"`python -m test.eval.validate` passes: all {len(cases)} rows parse, use only "
            "known expectation keys, and state expectations that a document could actually "
            "satisfy (no floor above its own ceiling, nothing both required and forbidden).",
            "",
        ]
    else:
        lines += [f"**{len(problems)} unsound row(s):**", ""]
        for case_id, issues in sorted(problems.items()):
            for issue in issues:
                lines.append(f"- `{case_id}`: {issue}")
        lines.append("")
    return lines


def render(cases: Sequence[Case] | None = None) -> str:
    """The full coverage report as markdown."""
    rows = list(cases) if cases is not None else load_cases()
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")

    lines = [
        "# SRS evaluation dataset — coverage report",
        "",
        f"Source: `test/eval/{DATASET_PATH.name}` · "
        f"{len(rows)} cases · generated {generated}",
        "",
        "The repository suite under `test/unit` and `test/integration` asserts that the",
        "code behaves. This dataset asserts that the *document the SRS agent writes* holds",
        "the properties a customer brief implies — the part a unit test cannot reach.",
        "",
        "Rows are graded in tiers. **Tier 1** is the contract the agent must never break,",
        "**tier 2** is behaviour it is expected to get right, **tier 3** is breadth.",
        "",
    ]
    lines += _headline(rows)
    lines += _claims_section(rows)
    lines += _categories_section(rows)
    lines += _matrix_section(rows)
    lines += _language_section(rows)
    lines += _examples_section(rows)
    lines += _integrity_section(rows)
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:  # pragma: no cover - CLI
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stdout", action="store_true",
                        help="print the report instead of writing it to results/")
    parser.add_argument("--out", type=Path, default=REPORT_PATH,
                        help=f"where to write the report (default: {REPORT_PATH})")
    args = parser.parse_args(argv)

    report = render()
    if args.stdout:
        print(report)
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report, encoding="utf-8")
    print(f"wrote {args.out} ({len(report.splitlines())} lines)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
