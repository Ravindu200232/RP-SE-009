"""Check the dataset itself, before any agent is asked to satisfy it.

`dataset.py` fails on a row that cannot be *parsed*. This module fails on a row
that cannot be *satisfied* — an expectation no SRS could ever meet, such as a
floor above its own ceiling — plus the structural conventions the dataset keeps
so that a reader can trust the coverage tables in `report.py`.

Running this needs no model, no network and no generated document, so it is the
cheapest evidence that a failing evaluation run is the agent's fault and not the
dataset's.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from typing import Iterable

from .dataset import Case, load_cases

#: Every key the grader understands. A key outside this set is a typo that would
#: otherwise be silently ignored at grading time and score as a free pass.
KNOWN_EXPECTATION_KEYS = frozenset({
    # intake guards
    "nonsense", "clarify",
    # shape of the specified system
    "auth", "min_roles", "max_roles", "min_tables", "max_tables", "min_frs",
    "forbid_tables", "forbid_roles",
    # handoff to the builder
    "seed_counts", "routes_expected", "tables_expected", "roles_expected",
    # document language contract
    "language", "builder_english", "machine_values_ascii",
    # diagrams and classification
    "diagrams_present", "diagrams_na", "domain_any",
})

#: Keys allowed inside a customization row's `expect_after` block.
KNOWN_AFTER_KEYS = frozenset({"grew", "min_roles", "max_roles", "min_tables", "max_tables"})

#: Pairs where the first key is a floor and the second the matching ceiling.
_BOUND_PAIRS = (("min_roles", "max_roles"), ("min_tables", "max_tables"))

#: Keys whose value must be a list of strings.
_STRING_LIST_KEYS = (
    "forbid_tables", "forbid_roles", "seed_counts", "routes_expected",
    "tables_expected", "roles_expected", "diagrams_present", "diagrams_na",
    "domain_any",
)

_NUMBER_KEYS = ("min_roles", "max_roles", "min_tables", "max_tables", "min_frs")
_FLAG_KEYS = ("auth", "nonsense", "clarify", "builder_english", "machine_values_ascii")


class ValidationError(RuntimeError):
    """The dataset is internally inconsistent."""


def _check_vocabulary(case: Case) -> list[str]:
    problems = []
    for key in case.expected:
        if key not in KNOWN_EXPECTATION_KEYS:
            problems.append(f"unknown expectation key `{key}`")
    for key in case.expect_after:
        if key not in KNOWN_AFTER_KEYS:
            problems.append(f"unknown expect_after key `{key}`")
    return problems


def _check_types(case: Case) -> list[str]:
    problems = []
    expected = case.expected

    for key in _STRING_LIST_KEYS:
        if key in expected:
            value = expected[key]
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                problems.append(f"`{key}` must be a list of strings, got {value!r}")

    for key in _NUMBER_KEYS:
        # bool is a subclass of int, so it has to be excluded explicitly.
        if key in expected and (isinstance(expected[key], bool) or not isinstance(expected[key], int)):
            problems.append(f"`{key}` must be a whole number, got {expected[key]!r}")

    for key in _FLAG_KEYS:
        if key in expected and not isinstance(expected[key], bool):
            problems.append(f"`{key}` must be true or false, got {expected[key]!r}")

    counts = expected.get("seed_counts")
    if isinstance(counts, list):
        for count in counts:
            if isinstance(count, str) and not count.isdigit():
                problems.append(f"`seed_counts` entry `{count}` is not a plain number")

    return problems


def _check_satisfiable(case: Case) -> list[str]:
    """A row must describe a document that could actually exist."""
    problems = []
    expected = case.expected

    for floor, ceiling in _BOUND_PAIRS:
        if floor in expected and ceiling in expected and expected[floor] > expected[ceiling]:
            problems.append(
                f"unsatisfiable: {floor}={expected[floor]} exceeds {ceiling}={expected[ceiling]}"
            )

    # A document with no sign-in cannot carry a role taxonomy beyond the visitor.
    if expected.get("auth") is False and expected.get("min_roles", 1) > 1:
        problems.append(f"unsatisfiable: auth=false but min_roles={expected['min_roles']}")

    # The same name cannot be both demanded and banned.
    for demanded, banned, noun in (
        ("tables_expected", "forbid_tables", "table"),
        ("roles_expected", "forbid_roles", "role"),
    ):
        clash = set(expected.get(demanded, [])) & set(expected.get(banned, []))
        if clash:
            problems.append(f"unsatisfiable: {noun}(s) {sorted(clash)} both required and forbidden")

    # A diagram cannot be required and marked not-applicable at once.
    clash = set(expected.get("diagrams_present", [])) & set(expected.get("diagrams_na", []))
    if clash:
        problems.append(f"unsatisfiable: diagram(s) {sorted(clash)} both required and not-applicable")

    after = case.expect_after
    for floor, ceiling in _BOUND_PAIRS:
        if floor in after and ceiling in after and after[floor] > after[ceiling]:
            problems.append(f"unsatisfiable expect_after: {floor} exceeds {ceiling}")

    return problems


def _check_conventions(case: Case) -> list[str]:
    """Conventions the coverage tables rely on."""
    problems = []

    if not case.claim:
        problems.append("row states no claim it is evidence for")
    if not case.note:
        problems.append("row has no note explaining what it probes")

    # A row that asks for a non-English document must say so in machine-readable
    # form, otherwise the language grader has nothing to check against.
    declared = case.expected.get("language")
    if case.output_language != "English" and not declared:
        problems.append(f"output_language is `{case.output_language}` but no `language` expectation")
    if declared and declared != case.output_language:
        problems.append(
            f"`language` expectation `{declared}` disagrees with "
            f"output_language `{case.output_language}`"
        )

    # Customization rows are graded on the edit, not on a static shape.
    if case.category == "customization":
        if not case.edit_prompt:
            problems.append("customization row has no edit_prompt")
        if not case.expect_after:
            problems.append("customization row has no expect_after block")
    elif not case.expected:
        problems.append("row states no expectations")

    # A matrix row is addressed by its cell, so the cell must be complete.
    if case.category == "matrix":
        for field in ("domain", "archetype", "scale"):
            if not getattr(case, field):
                problems.append(f"matrix row has no {field}")

    return problems


def validate_case(case: Case) -> list[str]:
    """Every problem with one row. An empty list means the row is sound."""
    return (
        _check_vocabulary(case)
        + _check_types(case)
        + _check_satisfiable(case)
        + _check_conventions(case)
    )


def validate(cases: Iterable[Case] | None = None) -> dict[str, list[str]]:
    """Validate the whole dataset. Returns `{case id: [problems]}` for bad rows."""
    rows = list(cases) if cases is not None else load_cases()
    report: dict[str, list[str]] = {}

    for case in rows:
        problems = validate_case(case)
        if problems:
            report[case.id] = problems

    # Cross-row conventions: one claim per category, so the claim table in the
    # coverage report is a faithful summary rather than an arbitrary pick.
    claims: dict[str, set[str]] = defaultdict(set)
    for case in rows:
        claims[case.category].add(case.claim)
    for category, found in sorted(claims.items()):
        if len(found) > 1:
            report[f"<category {category}>"] = [
                f"category maps to {len(found)} different claims: {sorted(found)}"
            ]

    duplicates = sorted(i for i, n in Counter(c.id for c in rows).items() if n > 1)
    if duplicates:
        report["<dataset>"] = [f"duplicate ids: {duplicates}"]

    return report


def assert_valid(cases: Iterable[Case] | None = None) -> None:
    """Raise `ValidationError` describing every bad row, or return quietly."""
    problems = validate(cases)
    if not problems:
        return
    lines = [f"{len(problems)} row(s) in the dataset are unsound:"]
    for case_id, issues in sorted(problems.items()):
        for issue in issues:
            lines.append(f"  {case_id}: {issue}")
    raise ValidationError("\n".join(lines))


def main() -> int:  # pragma: no cover - CLI
    cases = load_cases()
    problems = validate(cases)
    if problems:
        print(f"FAIL  {len(problems)} unsound row(s) of {len(cases)}")
        for case_id, issues in sorted(problems.items()):
            for issue in issues:
                print(f"  {case_id}: {issue}")
        return 1
    print(f"OK    {len(cases)} rows, every expectation is satisfiable")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI
    raise SystemExit(main())
