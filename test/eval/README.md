# SRS evaluation dataset

`test/unit` and `test/integration` assert that the **code behaves**. This dataset
asserts that the **document the SRS agent writes** holds the properties a customer
brief implies — the part a unit test cannot reach, because the output is prose,
diagrams and a builder handoff rather than a return value.

One row is one customer brief plus the properties the resulting SRS must hold.

## Files

| File | What it is |
|---|---|
| `srs_cases.csv` | The dataset: 471 briefs and their expected properties. |
| `dataset.py` | Reads the CSV into typed `Case` objects; fails loudly on a malformed row. |
| `validate.py` | Checks the dataset against *itself* — no model, no network. |
| `report.py` | Renders the coverage report a reviewer reads. |
| `results/coverage.md` | The generated report. |

## Commands

```bash
python -m test.eval.validate          # is the dataset sound?
python -m test.eval.report            # write results/coverage.md
python -m test.eval.report --stdout   # print it instead
python -m unittest test.unit.eval.test_dataset   # the dataset's own tests
```

The dataset's tests also run as part of `python test/run_suite.py`, so a broken
dataset fails the ordinary suite rather than waiting to surface as a mystery
during a scored run.

## Columns

| Column | Meaning |
|---|---|
| `id` | Stable case identifier, e.g. `G005-hosp-saas-mic`. |
| `tier` | 1 = contract that must never break, 2 = expected behaviour, 3 = breadth. |
| `category` | The behaviour under test; maps 1:1 to `claim_supported`. |
| `origin` | `hand-written`, `generated` (matrix cells) or `parallel-authored` (language pairs). |
| `domain`, `archetype`, `scale` | The matrix cell, for generated rows. |
| `input_script` | Script the customer wrote in: `en`, `si`, `ta`, `si-Latn`, `ta-Latn`, `mixed`. |
| `output_language` | Language the finished document must be written in. |
| `brief_word_count` | Word count of the brief, kept in step with the text. |
| `note` | What this particular row probes. |
| `brief` | The customer's words, verbatim. |
| `expected_properties` | JSON object of properties the SRS must hold. |
| `customization` | JSON object holding an `edit_prompt` and its `expect_after` block. |
| `claim_supported` | The claim this row is evidence for. |

### Expectation vocabulary

`validate.py` holds the authoritative list in `KNOWN_EXPECTATION_KEYS`; a key
outside it is rejected, because an unrecognised key would be silently skipped at
grading time and score as a free pass.

| Key | Meaning |
|---|---|
| `nonsense` | The intake guard must (or must not) reject the brief as unreadable. |
| `clarify` | The agent must (or must not) raise a clarifying question. |
| `auth` | The system does or does not have sign-in. |
| `min_roles` / `max_roles` | Floor and ceiling on the role taxonomy. |
| `min_tables` / `max_tables` | Floor and ceiling on the data model. |
| `min_frs` | Minimum functional requirements. |
| `forbid_tables` / `forbid_roles` | Names the SRS must not invent. |
| `seed_counts` | Customer-stated quantities that must reach the builder handoff. |
| `routes_expected` / `tables_expected` / `roles_expected` | Exact machine values expected. |
| `language` | Language the document must be written in. |
| `builder_english` | The builder prompt stays English even when the document is not. |
| `machine_values_ascii` | Routes, table names, roles and enums stay ASCII. |
| `diagrams_present` / `diagrams_na` | Diagrams the SRS must render, or mark not applicable. |
| `domain_any` | Acceptable domain classifications, including an honest `generic` fallback. |

## What the dataset covers

14 claims over 471 cases. The full breakdown, including the matrix grid and the
input-script/output-language grid, is in [`results/coverage.md`](results/coverage.md).

- **Intake guards** — nonsense rejection and clarification, each with controls that
  must *not* fire. A guard that always fires is worth nothing, so roughly a third
  of those rows are negative controls.
- **Scope discipline** — briefs that tempt the planner into audit logs, payments and
  admin roles nobody asked for.
- **The matrix** — 57 domain x archetype pairs at four scales each, so an SRS is
  sized to the business rather than to a template.
- **Language** — 13 output languages from 6 input scripts, including romanised
  Sinhala and Tamil, which is how most briefs actually arrive. Separate rows pin
  the drift contract: the document localises, the machine values do not.
- **Customization** — a plain-English edit must extend the document, not shrink or
  duplicate it. Two rows are deliberate shrink cases (an explicit removal and a
  pure value change) so "always grew" cannot pass.

## Soundness

`validate.py` rejects a row that states an expectation no document could satisfy —
a floor above its own ceiling, a table both required and forbidden, a diagram both
required and not-applicable, or a role taxonomy demanded of a system with no
sign-in. This matters because an unsatisfiable row fails every run regardless of
how good the agent is, and reads as an agent defect.

Seven `saas x micro` rows previously carried `min_roles: 3` alongside `max_roles: 2`:
the SaaS archetype mandates owner, member and tenant-admin, while the micro scale
cap had been applied to the role taxonomy when it describes headcount. The cap was
removed, making SaaS consistent across all four scales, and
`ValidatorTests.test_catches_floor_above_ceiling` keeps the class of defect out.
