# SRS evaluation dataset — coverage report

Source: `test/eval/srs_cases.csv` · 471 cases · generated 2026-08-30T10:55:17+00:00

The repository suite under `test/unit` and `test/integration` asserts that the
code behaves. This dataset asserts that the *document the SRS agent writes* holds
the properties a customer brief implies — the part a unit test cannot reach.

Rows are graded in tiers. **Tier 1** is the contract the agent must never break,
**tier 2** is behaviour it is expected to get right, **tier 3** is breadth.

## At a glance

| Measure | Value |
|---|---|
| Cases | 471 |
| Claims covered | 14 |
| Categories | 14 |
| Tier 1 / 2 / 3 | 70 / 210 / 191 |
| Domain x archetype cells | 57 |
| Input scripts | 6 |
| Output languages | 13 |
| Hand-written / generated / parallel-authored | 93 / 228 / 150 |

## Claims and their evidence

Every row is evidence for exactly one claim about the SRS agent. A claim
with no passing rows is a claim the project cannot make.

| Claim | Category | Cases | Tiers |
|---|---|---|---|
| Produces a correctly sized SRS across every supported domain x archetype x scale cell | matrix | 228 | T2x57, T3x171 |
| Produces the requested document language from any input script | language_matrix | 90 | T1x18, T2x72 |
| Applies a plain-English edit without shrinking or duplicating the document | customization | 20 | T2x20 |
| The language contract holds beyond Sinhala, Tamil and English | language_generality | 20 | T3x20 |
| Machine values stay English while the customer document is localised | language_drift | 16 | T1x16 |
| Rejects unreadable input instead of specifying it (intake guard) | nonsense | 14 | T1x14 |
| Raises clarification instead of guessing (clarify agent) | ambiguous | 12 | T1x12 |
| Carries customer-stated quantities into the builder handoff | seed_volume | 12 | T2x12 |
| Renders a diagram only when the SRS carries enough semantics for it | diagram | 12 | T2x12 |
| Handles code-switched input without degrading | mixed_script | 12 | T2x12 |
| Domain classification survives non-English input, or falls back honestly | language_classify | 12 | T2x12 |
| Stays inside the approved plan under temptation (plan scope guard) | scope | 10 | T1x10 |
| Implements the account policy the customer actually described | auth_mode | 8 | T2x8 |
| Handles both terse and long-form briefs | length | 5 | T2x5 |

## Categories and what they assert

| Category | Cases | Tiers | Expectation keys used |
|---|---|---|---|
| matrix | 228 | T2x57, T3x171 | `auth`, `forbid_roles`, `forbid_tables`, `max_roles`, `max_tables`, `min_frs`, `min_roles`, `min_tables` |
| language_matrix | 90 | T1x18, T2x72 | `auth`, `builder_english`, `language`, `machine_values_ascii`, `min_roles`, `min_tables` |
| customization | 20 | T2x20 | — |
| language_generality | 20 | T3x20 | `auth`, `builder_english`, `language`, `machine_values_ascii`, `min_roles`, `min_tables` |
| language_drift | 16 | T1x16 | `builder_english`, `language`, `machine_values_ascii`, `roles_expected`, `routes_expected`, `tables_expected` |
| nonsense | 14 | T1x14 | `nonsense` |
| ambiguous | 12 | T1x12 | `clarify` |
| seed_volume | 12 | T2x12 | `seed_counts` |
| diagram | 12 | T2x12 | `diagrams_na`, `diagrams_present` |
| mixed_script | 12 | T2x12 | `auth`, `builder_english`, `machine_values_ascii`, `min_roles`, `min_tables` |
| language_classify | 12 | T2x12 | `auth`, `domain_any`, `language`, `min_roles`, `min_tables` |
| scope | 10 | T1x10 | `auth`, `forbid_roles`, `forbid_tables`, `max_roles`, `max_tables` |
| auth_mode | 8 | T2x8 | `auth`, `forbid_roles`, `forbid_tables`, `max_roles`, `min_roles` |
| length | 5 | T2x5 | `auth`, `min_frs`, `min_roles`, `min_tables` |

## Domain x archetype x scale matrix

228 rows over 57 domain x archetype pairs, each at micro/small/medium/large scale. `****` means all four scales are present, `—` means the pair is deliberately not exercised (a hospital does not run a portfolio site; a hotel has no point of sale).

| domain | blog | dashboard | ecommerce | landing | other | portfolio | pos | saas | utility |
|---|---|---|---|---|---|---|---|---|---|
| generic | **** | **** | **** | **** | **** | **** | **** | **** | **** |
| hospital | **** | **** | — | **** | **** | — | **** | **** | **** |
| hotel | **** | **** | **** | **** | **** | **** | — | **** | **** |
| restaurant | **** | **** | **** | **** | **** | **** | **** | **** | **** |
| retail | **** | **** | **** | **** | **** | **** | **** | **** | **** |
| school | **** | **** | **** | **** | **** | **** | — | **** | **** |
| vehicle | — | **** | **** | **** | **** | — | **** | **** | **** |

## Input script x output language

The agent must produce the requested document language whatever script the
customer wrote in — including romanised Sinhala and Tamil, which is how most
briefs actually arrive. `·` marks a pair the dataset does not exercise.

| input \ output | Arabic | Bengali | Chinese (Simplified) | English | French | German | Hindi | Japanese | Korean | Sinhala | Spanish | Tamil | Urdu |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| en | 2 | 2 | 2 | 6 | 2 | 2 | 2 | 2 | 2 | 14 | 2 | 14 | 2 |
| mixed | · | · | · | 12 | · | · | · | · | · | · | · | · | · |
| si | · | · | · | 6 | · | · | · | · | · | 12 | · | 6 | · |
| si-Latn | · | · | · | 6 | · | · | · | · | · | 6 | · | 6 | · |
| ta | · | · | · | 6 | · | · | · | · | · | 6 | · | 12 | · |
| ta-Latn | · | · | · | 6 | · | · | · | · | · | 6 | · | 6 | · |

## A worked example from every category

One real row per category, so the expectations above are concrete.

### ambiguous — `C01-ambiguous`

*unresolved pronouns*

> I want a system where they can manage it properly and it should be secure.

- **Claim:** Raises clarification instead of guessing (clarify agent)
- **Tier:** 1 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Must hold:** `{"clarify": true}`

### auth_mode — `A01-invite`

*invitation-only registration*

> Staff cannot sign themselves up. I create the account and email them an invitation link which they use to set a password.

- **Claim:** Implements the account policy the customer actually described
- **Tier:** 2 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Must hold:** `{"auth": true, "min_roles": 2}`

### customization — `E01-customize`

*additive edit must not shrink the document*

> A clothing shop selling online. Customers browse, add to cart and order.

- **Claim:** Applies a plain-English edit without shrinking or duplicating the document
- **Tier:** 2 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Edit applied:** Add a wishlist page where signed-in customers save items for later.
- **Must hold after the edit:** `{"min_tables": 6, "grew": true}`

### diagram — `P01-diagram`

*no persistence — ERD must be marked not applicable*

> A BMI calculator. Enter height and weight, see the result. Nothing saved.

- **Claim:** Renders a diagram only when the SRS carries enough semantics for it
- **Tier:** 2 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Must hold:** `{"diagrams_na": ["erd", "sequence", "state_machine"]}`

### language_classify — `LC01-si`

*does classify_domain() reach 'hospital' from Sinhala script, or fall back to generic?*

> මට කුඩා සායනයක් සඳහා පද්ධතියක් අවශ්‍යයි. රෝගීන්ට අන්තර්ජාලය හරහා වේලාවක් වෙන් කරගත හැකි විය යුතුයි. වෛද්‍යවරුන්ට තමන්ගේ රෝගීන් බැලිය හැකි විය යුතුයි. පිළිගැනීමේ නිලධාරියා පැමිණි අය සලකුණු කරයි.

- **Claim:** Domain classification survives non-English input, or falls back honestly
- **Tier:** 2 · **Origin:** parallel-authored · **Input script:** si · **Output language:** Sinhala
- **Must hold:** `{"auth": true, "min_roles": 3, "min_tables": 3, "language": "Sinhala", "domain_any": ["hospital", "generic"]}`

### language_drift — `LD01-sin`

*routes must stay ASCII while the document is Sinhala*

> A shop with a products page, a cart page and a checkout page.

- **Claim:** Machine values stay English while the customer document is localised
- **Tier:** 1 · **Origin:** parallel-authored · **Input script:** en · **Output language:** Sinhala
- **Must hold:** `{"machine_values_ascii": true, "routes_expected": ["/products", "/cart", "/checkout"], "language": "Sinhala", "builder_english": true}`

### language_generality — `LG011-hi`

*generality probe — Devanagari script*

> I need a system for a small clinic. Patients should be able to book an appointment online. Doctors should be able to see their own patients. Reception marks who came in.

- **Claim:** The language contract holds beyond Sinhala, Tamil and English
- **Tier:** 3 · **Origin:** parallel-authored · **Input script:** en · **Output language:** Hindi
- **Must hold:** `{"auth": true, "min_roles": 3, "min_tables": 3, "language": "Hindi", "builder_english": true, "machine_values_ascii": true}`

### language_matrix — `LM001-clini-en-en`

*input: English prose; output: English; matched pair*

> I need a system for a small clinic. Patients should be able to book an appointment online. Doctors should be able to see their own patients. Reception marks who came in.

- **Claim:** Produces the requested document language from any input script
- **Tier:** 1 · **Origin:** parallel-authored · **Input script:** en · **Output language:** English
- **Must hold:** `{"auth": true, "min_roles": 3, "min_tables": 3, "language": "English", "builder_english": true, "machine_values_ascii": true}`

### length — `X01-terse`

*3-word brief*

> Barber shop appointments.

- **Claim:** Handles both terse and long-form briefs
- **Tier:** 2 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Must hold:** `{"auth": true}`

### matrix — `G001-hosp-pos-mic`

*hospital x pos x micro*

> I have a diagnostic laboratory and the manual process is not working any more. I need to ring up a sale, apply a discount if the customer asks, print a receipt, and know my daily total at closing time. One or two users at most. It will be used by patients collecting reports and lab technicians. Keep it simple, we are not technical.

- **Claim:** Produces a correctly sized SRS across every supported domain x archetype x scale cell
- **Tier:** 3 · **Origin:** generated · **Input script:** en · **Output language:** English
- **Must hold:** `{"auth": true, "min_roles": 2, "min_tables": 4, "min_frs": 8, "max_roles": 2}`

### mixed_script — `MX01-mixed`

*Singlish, clinic*

> Mata one clinic ekakata system ekak. Patients online booking karanna one, doctors ta thama patients balanna one.

- **Claim:** Handles code-switched input without degrading
- **Tier:** 2 · **Origin:** parallel-authored · **Input script:** mixed · **Output language:** English
- **Must hold:** `{"auth": true, "min_roles": 2, "builder_english": true, "machine_values_ascii": true}`

### nonsense — `N01-nonsense`

*keyboard mash*

> asdkjh askjdh qweqwe zxczxc hjkhjk poipoi vbnvbn

- **Claim:** Rejects unreadable input instead of specifying it (intake guard)
- **Tier:** 1 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Must hold:** `{"nonsense": true}`

### scope — `S01-scope`

*invites audit/permissions*

> A simple contact directory for my 20-person office. Anyone signed in looks up a colleague's phone number and department. HR updates the entries.

- **Claim:** Stays inside the approved plan under temptation (plan scope guard)
- **Tier:** 1 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Must hold:** `{"auth": true, "max_roles": 3, "max_tables": 3, "forbid_tables": ["audit_logs", "permissions", "notifications", "invoices", "orders", "payments"]}`

### seed_volume — `V01-volume`

*two explicit counts*

> An event ticketing site. Expect around 500 tickets per event and about 20 events a year.

- **Claim:** Carries customer-stated quantities into the builder handoff
- **Tier:** 2 · **Origin:** hand-written · **Input script:** en · **Output language:** English
- **Must hold:** `{"seed_counts": ["500", "20"]}`

## Dataset integrity

`python -m test.eval.validate` passes: all 471 rows parse, use only known expectation keys, and state expectations that a document could actually satisfy (no floor above its own ceiling, nothing both required and forbidden).
