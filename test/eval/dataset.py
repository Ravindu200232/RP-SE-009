"""Read `srs_cases.csv` into typed cases.

One row is one customer brief plus the properties the resulting SRS must hold.
The two JSON columns (`expected_properties`, `customization`) are parsed here so
that a malformed row fails at load time rather than half way through a run.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


DATASET_PATH = Path(__file__).resolve().parent / "srs_cases.csv"

#: Rows are graded in tiers. Tier 1 is the contract the agent must never break,
#: tier 2 is the behaviour it is expected to get right, tier 3 is breadth.
TIERS = (1, 2, 3)


class DatasetError(RuntimeError):
    """The dataset file is missing, unreadable, or a row is malformed."""


@dataclass(frozen=True)
class Case:
    """One evaluation row."""

    id: str
    tier: int
    category: str
    origin: str
    domain: str
    archetype: str
    scale: str
    input_script: str
    output_language: str
    note: str
    brief: str
    expected: dict[str, Any] = field(default_factory=dict)
    customization: dict[str, Any] = field(default_factory=dict)
    claim: str = ""

    @property
    def edit_prompt(self) -> str:
        """The plain-English edit for a customization row, if it has one."""
        return str(self.customization.get("edit_prompt") or "")

    @property
    def expect_after(self) -> dict[str, Any]:
        """Properties the document must hold *after* the edit is applied."""
        value = self.customization.get("expect_after")
        return value if isinstance(value, dict) else {}

    def __str__(self) -> str:  # pragma: no cover - display only
        return f"{self.id} [{self.category}/tier {self.tier}]"


def _json_column(raw: str, *, case_id: str, column: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise DatasetError(f"{case_id}: column `{column}` is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise DatasetError(f"{case_id}: column `{column}` must be a JSON object")
    return value


def _tier(raw: str, *, case_id: str) -> int:
    try:
        tier = int(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise DatasetError(f"{case_id}: tier `{raw}` is not a number") from exc
    if tier not in TIERS:
        raise DatasetError(f"{case_id}: tier {tier} is outside {TIERS}")
    return tier


def load_cases(path: Path | str | None = None) -> list[Case]:
    """Load every row. Raises `DatasetError` on a malformed file."""
    source = Path(path or DATASET_PATH)
    if not source.exists():
        raise DatasetError(f"dataset not found: {source}")

    cases: list[Case] = []
    seen: set[str] = set()
    # The briefs carry Sinhala, Tamil, Devanagari and romanised text, so the
    # encoding is pinned rather than left to the platform default.
    with source.open("r", encoding="utf-8", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=2):
            case_id = (row.get("id") or "").strip()
            if not case_id:
                raise DatasetError(f"{source}:{index}: row has no id")
            if case_id in seen:
                raise DatasetError(f"{source}:{index}: duplicate id `{case_id}`")
            seen.add(case_id)

            brief = (row.get("brief") or "").strip()
            if not brief:
                raise DatasetError(f"{case_id}: row has no brief")

            cases.append(Case(
                id=case_id,
                tier=_tier(row.get("tier", ""), case_id=case_id),
                category=(row.get("category") or "").strip(),
                origin=(row.get("origin") or "").strip(),
                domain=(row.get("domain") or "").strip(),
                archetype=(row.get("archetype") or "").strip(),
                scale=(row.get("scale") or "").strip(),
                input_script=(row.get("input_script") or "").strip(),
                output_language=(row.get("output_language") or "English").strip(),
                note=(row.get("note") or "").strip(),
                brief=brief,
                expected=_json_column(row.get("expected_properties", ""),
                                      case_id=case_id, column="expected_properties"),
                customization=_json_column(row.get("customization", ""),
                                           case_id=case_id, column="customization"),
                claim=(row.get("claim_supported") or "").strip(),
            ))

    if not cases:
        raise DatasetError(f"{source}: dataset is empty")
    return cases


def select(cases: Iterable[Case], *, tiers: Iterable[int] | None = None,
           categories: Iterable[str] | None = None,
           ids: Iterable[str] | None = None,
           limit: int | None = None) -> list[Case]:
    """Filter cases the way the runner's command line describes them."""
    tier_set = {int(t) for t in tiers} if tiers else None
    category_set = {c.strip().lower() for c in categories} if categories else None
    id_set = {i.strip() for i in ids} if ids else None

    def keep(case: Case) -> bool:
        if tier_set is not None and case.tier not in tier_set:
            return False
        if category_set is not None and case.category.lower() not in category_set:
            return False
        if id_set is not None and case.id not in id_set:
            return False
        return True

    kept = [c for c in cases if keep(c)]
    return kept[:limit] if limit else kept


def categories(cases: Iterable[Case]) -> list[str]:
    """Every category present, in first-seen order."""
    out: list[str] = []
    for case in cases:
        if case.category not in out:
            out.append(case.category)
    return out


def iter_claims(cases: Iterable[Case]) -> Iterator[tuple[str, list[Case]]]:
    """Group cases by the claim they are evidence for."""
    grouped: dict[str, list[Case]] = {}
    for case in cases:
        grouped.setdefault(case.claim, []).append(case)
    yield from grouped.items()


__all__ = [
    "Case", "DATASET_PATH", "DatasetError", "TIERS", "categories",
    "iter_claims", "load_cases", "select",
]
