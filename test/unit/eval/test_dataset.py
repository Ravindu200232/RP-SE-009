"""The evaluation dataset must be loadable and internally sound.

These run in the ordinary suite because a broken dataset is indistinguishable
from a broken agent once a scored run is under way: the run fails either way,
and only these tests say which. Nothing here calls a model or touches a network.
"""
from __future__ import annotations

import unittest
from collections import Counter, defaultdict

from test.eval.dataset import Case, DatasetError, categories, load_cases, select
from test.eval.report import render
from test.eval.validate import (
    KNOWN_EXPECTATION_KEYS,
    ValidationError,
    assert_valid,
    validate,
    validate_case,
)


class DatasetLoadTests(unittest.TestCase):
    """The CSV parses into typed cases."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()

    def test_dataset_is_not_empty(self) -> None:
        self.assertGreater(len(self.cases), 400,
                           "the dataset should carry the full case matrix")

    def test_every_case_has_an_id_a_brief_and_a_claim(self) -> None:
        for case in self.cases:
            with self.subTest(case=case.id):
                self.assertTrue(case.id)
                self.assertTrue(case.brief.strip())
                self.assertTrue(case.claim, "a row must say what it is evidence for")

    def test_ids_are_unique(self) -> None:
        duplicates = [i for i, n in Counter(c.id for c in self.cases).items() if n > 1]
        self.assertEqual(duplicates, [], "case ids address rows and must be unique")

    def test_tiers_are_within_range(self) -> None:
        self.assertEqual({c.tier for c in self.cases} - {1, 2, 3}, set())

    def test_non_english_briefs_survive_decoding(self) -> None:
        """Sinhala and Tamil rows must load as script, not as mojibake."""
        sinhala = [c for c in self.cases if c.input_script == "si"]
        tamil = [c for c in self.cases if c.input_script == "ta"]
        self.assertTrue(sinhala and tamil, "the language matrix should be present")

        # U+0D80-U+0DFF is Sinhala, U+0B80-U+0BFF is Tamil. A file decoded with the
        # wrong codec would show Latin-1 lookalikes here instead.
        self.assertTrue(any("඀" <= ch <= "෿" for ch in sinhala[0].brief),
                        "Sinhala brief did not decode to Sinhala script")
        self.assertTrue(any("஀" <= ch <= "௿" for ch in tamil[0].brief),
                        "Tamil brief did not decode to Tamil script")

    def test_malformed_json_column_is_rejected_at_load(self) -> None:
        import tempfile
        from pathlib import Path

        header = ("id,tier,category,origin,domain,archetype,scale,input_script,"
                  "output_language,brief_word_count,note,brief,expected_properties,"
                  "customization,claim_supported\n")
        row = "X1,1,nonsense,hand-written,,,,en,English,1,note,brief,{not json},{},claim\n"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.csv"
            path.write_text(header + row, encoding="utf-8")
            with self.assertRaises(DatasetError):
                load_cases(path)


class DatasetSelectionTests(unittest.TestCase):
    """The runner's filters behave."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()

    def test_select_by_tier(self) -> None:
        tier_one = select(self.cases, tiers=[1])
        self.assertTrue(tier_one)
        self.assertEqual({c.tier for c in tier_one}, {1})

    def test_select_by_category_is_case_insensitive(self) -> None:
        picked = select(self.cases, categories=["NONSENSE"])
        self.assertTrue(picked)
        self.assertEqual({c.category for c in picked}, {"nonsense"})

    def test_select_by_id_and_limit(self) -> None:
        wanted = self.cases[3].id
        self.assertEqual([c.id for c in select(self.cases, ids=[wanted])], [wanted])
        self.assertEqual(len(select(self.cases, limit=5)), 5)

    def test_categories_are_reported_in_first_seen_order(self) -> None:
        found = categories(self.cases)
        self.assertEqual(len(found), len(set(found)))
        self.assertEqual(found[0], self.cases[0].category)


class DatasetSoundnessTests(unittest.TestCase):
    """No row may state an expectation a document could never satisfy."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()

    def test_dataset_validates(self) -> None:
        problems = validate(self.cases)
        self.assertEqual(
            problems, {},
            "dataset is unsound:\n" + "\n".join(
                f"  {k}: {v}" for k, v in sorted(problems.items())),
        )

    def test_assert_valid_passes(self) -> None:
        assert_valid(self.cases)

    def test_expectation_keys_are_all_known(self) -> None:
        """An unknown key would be ignored at grading time and score a free pass."""
        used = {k for c in self.cases for k in c.expected}
        self.assertEqual(used - KNOWN_EXPECTATION_KEYS, set())

    def test_role_and_table_bounds_do_not_contradict(self) -> None:
        for case in self.cases:
            with self.subTest(case=case.id):
                for floor, ceiling in (("min_roles", "max_roles"), ("min_tables", "max_tables")):
                    if floor in case.expected and ceiling in case.expected:
                        self.assertLessEqual(
                            case.expected[floor], case.expected[ceiling],
                            f"{case.id}: {floor} exceeds {ceiling}",
                        )

    def test_public_cases_do_not_demand_a_role_taxonomy(self) -> None:
        for case in self.cases:
            if case.expected.get("auth") is False:
                with self.subTest(case=case.id):
                    self.assertLessEqual(case.expected.get("min_roles", 1), 1)

    def test_each_category_maps_to_one_claim(self) -> None:
        claims: dict[str, set[str]] = defaultdict(set)
        for case in self.cases:
            claims[case.category].add(case.claim)
        for category, found in claims.items():
            with self.subTest(category=category):
                self.assertEqual(len(found), 1, f"{category} spans {len(found)} claims")

    def test_non_english_rows_declare_their_language(self) -> None:
        for case in self.cases:
            if case.output_language != "English":
                with self.subTest(case=case.id):
                    self.assertEqual(case.expected.get("language"), case.output_language)

    def test_customization_rows_carry_an_edit_and_an_expectation(self) -> None:
        rows = [c for c in self.cases if c.category == "customization"]
        self.assertTrue(rows)
        for case in rows:
            with self.subTest(case=case.id):
                self.assertTrue(case.edit_prompt)
                self.assertTrue(case.expect_after)

    def test_matrix_rows_name_a_complete_cell(self) -> None:
        rows = [c for c in self.cases if c.category == "matrix"]
        self.assertTrue(rows)
        for case in rows:
            with self.subTest(case=case.id):
                self.assertTrue(case.domain and case.archetype and case.scale)

    def test_matrix_covers_every_scale_of_each_pair(self) -> None:
        """A pair present at one scale must be present at all four."""
        rows = [c for c in self.cases if c.category == "matrix"]
        by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
        for case in rows:
            by_pair[(case.domain, case.archetype)].add(case.scale)
        for pair, scales in by_pair.items():
            with self.subTest(pair=pair):
                self.assertEqual(scales, {"micro", "small", "medium", "large"})


class ValidatorTests(unittest.TestCase):
    """The validator must actually catch the defects it claims to catch."""

    @staticmethod
    def _case(**expected) -> Case:
        return Case(
            id="T1", tier=1, category="matrix", origin="hand-written",
            domain="retail", archetype="pos", scale="micro", input_script="en",
            output_language="English", note="probe", brief="A shop.",
            expected=expected, customization={}, claim="a claim",
        )

    def test_catches_floor_above_ceiling(self) -> None:
        problems = validate_case(self._case(min_roles=3, max_roles=2))
        self.assertTrue(any("unsatisfiable" in p for p in problems), problems)

    def test_catches_public_case_demanding_roles(self) -> None:
        problems = validate_case(self._case(auth=False, min_roles=3))
        self.assertTrue(any("auth=false" in p for p in problems), problems)

    def test_catches_unknown_expectation_key(self) -> None:
        problems = validate_case(self._case(min_rolls=2))
        self.assertTrue(any("unknown expectation key" in p for p in problems), problems)

    def test_catches_table_both_required_and_forbidden(self) -> None:
        problems = validate_case(
            self._case(tables_expected=["orders"], forbid_tables=["orders"]))
        self.assertTrue(any("required and forbidden" in p for p in problems), problems)

    def test_catches_diagram_both_required_and_not_applicable(self) -> None:
        problems = validate_case(
            self._case(diagrams_present=["erd"], diagrams_na=["erd"]))
        self.assertTrue(any("not-applicable" in p for p in problems), problems)

    def test_catches_wrong_value_type(self) -> None:
        problems = validate_case(self._case(min_roles="three"))
        self.assertTrue(any("whole number" in p for p in problems), problems)

    def test_accepts_a_sound_case(self) -> None:
        self.assertEqual(validate_case(self._case(auth=True, min_roles=2, max_roles=3)), [])

    def test_assert_valid_raises_on_an_unsound_case(self) -> None:
        with self.assertRaises(ValidationError):
            assert_valid([self._case(min_roles=3, max_roles=2)])


class ReportTests(unittest.TestCase):
    """The coverage report renders from the dataset alone."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = load_cases()
        cls.report = render(cls.cases)

    def test_report_names_every_claim(self) -> None:
        for claim in {c.claim for c in self.cases}:
            with self.subTest(claim=claim):
                self.assertIn(claim, self.report)

    def test_report_names_every_category(self) -> None:
        for category in {c.category for c in self.cases}:
            with self.subTest(category=category):
                self.assertIn(category, self.report)

    def test_report_states_the_case_count(self) -> None:
        self.assertIn(str(len(self.cases)), self.report)

    def test_report_records_a_clean_integrity_check(self) -> None:
        self.assertIn("## Dataset integrity", self.report)
        self.assertNotIn("unsound row(s)", self.report)


if __name__ == "__main__":  # pragma: no cover - CLI
    unittest.main()
