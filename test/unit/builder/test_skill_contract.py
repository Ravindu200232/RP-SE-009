"""What each skill has to say, however short it gets.

A skill is read at the start of the phase that owns it and re-read while that
phase runs, so its length is paid for on every build. Shortening one is worth
doing and easy to do badly: a rule that quietly falls out comes back as work
nobody notices is wrong until the build has copied it.

So every rule each skill carries is listed here, with a phrase that only
appears while it is still being said. Cut the prose, keep this passing.

A rule belongs to exactly one skill. When two skills said the same thing, the
duplicate was cut from the one that does not own the phase, and the reader was
pointed at the owner instead — which is why some rows here read as "it says
whose rule it is" rather than as the rule itself.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from test import _support                                            # noqa: F401

SKILLS = Path("builder-agent/builder_agent/assets/skills")


# Each rule, and a phrase that only appears when it is still being said.
DRAWING = [
    ("a file per screen, not one page", r"multi-page"),
    ("the files link to each other", r"<a href="),
    ("no backend, no fetch", r"No fetch"),
    ("styles.css is written first", r"styles\.css.*first|first.*styles\.css"),
    ("demo.js makes the flow work", r"demo\.js"),
    ("the tokens live on :root", r":root"),
    ("no hex outside the token block", r"hex"),
    ("no CSS framework at all", r"No CSS framework"),
    ("a class says what the thing is", r"what the thing is"),
    ("transitions on what responds", r"transition"),
    ("the sections arrive", r"@keyframes"),
    ("reduced motion is honoured", r"prefers-reduced-motion"),
    ("the hero carries a photograph", r"hero"),
    ("depth from the palette", r"shadow"),
    ("one thing that is yours", r"One thing that is yours|memorable"),
    ("thirty links across the shell", r"30 or more"),
    # The checklist is the last thing read, so a count only stated in the prose
    # is a count that gets rounded down: one drawing built a 7-link header while
    # clearing the 30 total, because 30 was the only number in the table.
    ("the header carries its own twelve", r"links in the header \| \*\*12 or more"),
    ("so does the footer", r"links in the footer \| \*\*12 or more"),
    ("every link is a real anchor", r"real `<a href"),
    ("state survives the walk", r"localStorage"),
    ("the script never supplies the content", r"never supplies the content"),
    ("professional app of long quality with natural composition",
     r"professional app.*long quality|natural"),
    ("what `/` is follows the reader", r"wrong reader"),
    ("a working screen has its own six", r"empty state"),
    ("real content, no lorem ipsum", r"lorem ipsum"),
    ("photographs of the subject", r"loremflickr"),
    ("every address carries /any", r"/any"),
    ("every address carries a lock", r"\?lock="),
    ("width, height and alt on a picture", r"alt="),
    ("the phone at ~390px", r"390px"),
    ("the tablet at ~820px", r"820px"),
    ("a change starts at the token", r"token in `styles\.css`|one property changes"),
    ("it never says it is a drawing", r"coming soon"),
    ("the sign-in page does not confess", r"sign-in"),
    ("the stylesheet's own counts", r"120 or more"),
    ("eight rows in a list", r"8 or more|[Ee]ight or ten"),
]

BUILDER = [
    # Discover
    ("read only the skills that resolve an uncertainty", r"concrete\s+uncertainty"),
    ("a follow-up message continues the same project", r"follow-up"),
    ("search before an uncertain path", r"`search`"),
    ("never probe guessed path variants", r"guessed"),
    ("detect the real operating system and shell", r"shell"),
    ("current documentation beats model memory", r"documentation"),
    ("reuse what earlier runs proved", r"recallKnowledge"),
    # Greenfield root
    ("one canonical application root", r"canonical"),
    ("no second parallel source tree", r"parallel"),
    ("re-inspect after a structural move", r"inspectProject"),
    ("a clean staging directory when the generator refuses", r"staging"),
    ("promote an explicit inventory, not the whole tree", r"inventory"),
    ("dependency trees and caches stay behind", r"stay behind"),
    ("install dependencies once, in the final root", r"[Ii]nstall dependencies once"),
    # Scope
    ("an assigned pass runs only its own part", r"handed one verification pass|assigned"),
    ("authentication comes from the requirements", r"authorization"),
    ("prove both the allowed and the denied case", r"denied"),
    ("do not invent a login the product never asked for", r"invent login"),
    # The order
    ("complete vertical flows, not a scaffold", r"vertical"),
    ("the screens' skills are read when the screens start", r"page-composition"),
    ("one screen finished before the next begins", r"one screen before"),
    ("the application is finished before any verification", r"before running any\s+verification"),
    ("the saved design blocks are read before the first screen", r"blocks\.json"),
    ("adapt the whole block; no hand-made lookalike", r"lookalike"),
    ("the repository's own package manager and scripts", r"package manager"),
    ("the README is written with the implementation", r"README"),
    ("wait for observable readiness", r"readiness"),
    ("a long-lived service belongs in background management", r"background"),
    ("re-read the unit-test skill at its phase", r"Vitest skill"),
    ("requirement ids travel with every run", r"requirement ID"),
    ("read the failures together and repair by shared cause", r"shared cause"),
    ("look at the screens at desktop and mobile", r"mobile"),
    ("re-read the browser skill at its phase", r"browser-e2e"),
    ("journeys run through the harness", r"browserRunJourney"),
    ("finish after E2E; no second QA pass", r"second QA"),
    ("the handover records versions, commands, ports, omissions",
     r"deliberately left out"),
    # First-pass reliability
    ("slices order the work; they do not pull a later step in", r"slice"),
    ("write the whole suite, run it once", r"[Bb]atch"),
    ("the sketch for the selected stack is read first", r"nextjs-sketch"),
    ("open the sketch's own file before writing yours", r"listDir"),
    ("a revision dies at the next write to that file", r"stale"),
    ("never two patches to one file in a turn", r"two patches"),
    ("a JSON manifest is repaired with path operations", r"patchJson"),
    ("read a file once, not a window at a time", r"aroundLine"),
    ("inspect the contract before writing its consumer", r"selectors"),
    ("prove durability against a real restart", r"restart"),
    ("the lockfile and its version lines are preserved", r"lockfile"),
    ("no overlapping package-manager operations", r"overlapping"),
    ("repair the implementation, never weaken the test", r"weakening tests"),
    ("rerun the affected check, not the whole regression", r"affected check"),
    ("re-read a testing skill after compaction", r"compaction"),
    ("never claim verified from generated code alone", r"bug-free"),
    # Finish
    ("stop the services the task started", r"[Ss]top the task-owned|[Ss]top task-owned"),
    ("reports and screenshots stay out of source control", r"source control"),
    ("the quality profile is the evidence budget", r"Ultra"),
    ("a failed done-condition is a hard barrier", r"barrier"),
    ("completion needs evidence after the last edit", r"last relevant code edit"),
    ("one hypothesis, the smallest edit, then the check", r"hypothesis"),
]

UNIT_TESTS = [
    # What the runner is
    ("Vitest is the runner; never substitute another", r"do not substitute"),
    ("the project's own versions and conventions are preserved", r"pinned versions"),
    ("re-read at the phase, not between unchanged retries", r"unchanged retries"),
    # Evidence
    ("run through runTests from the first execution", r"suite ID"),
    ("write the JSON report from that same command", r"reportPath"),
    ("never rerun a suite merely to register evidence", r"register evidence"),
    ("reading the report again is not a reason to rerun", r"output-reading task"),
    ("coverage is a diagnostic, not a gate", r"[Cc]overage is optional"),
    ("a machine-readable coverage report", r"LCOV"),
    ("report the percentages honestly", r"honestly"),
    # Choosing the tests
    ("inspect the source, config, setup and aliases first", r"path aliases"),
    ("in Planner, installs go in the blueprint", r"blueprint"),
    ("choose tests from behaviour and risk", r"behavior and risk"),
    ("a regression test for every repaired bug", r"regression for every repaired bug"),
    ("match the existing conventions", r"import\s+conventions"),
    ("assert observable output, not existence", r"existence-only"),
    ("mock only the nondeterministic boundary, and restore it", r"restore spies"),
    ("every test runs on its own", r"independently runnable"),
    ("Vitest APIs, never Jest globals", r"Jest globals"),
    ("await, resolves and rejects used correctly", r"resolves`/`rejects"),
    ("table-driven where it expresses one rule", r"[Tt]able-driven"),
    # Passing first time
    ("read the module before testing it", r"Read the module before"),
    ("import the way the application imports", r"public entry point"),
    ("assert the shape you actually produce", r"cents"),
    ("every test creates its own rows", r"unique keys"),
    ("reset shared state between tests", r"module-level singletons"),
    ("await everything", r"floating promise"),
    ("never assert on wall-clock time or the local timezone", r"timezone"),
    ("write the failing edge case last", r"edge case"),
    ("the setup file and globals are one decision", r"globals"),
    ("the runner-specific matcher entry", r"jest-dom"),
    ("read every failure and group by cause", r"group them by cause"),
    # DOM and network
    ("query by role and accessible name", r"accessible name"),
    ("the query whose timing contract matches", r"findBy"),
    ("a fresh userEvent per test", r"userEvent"),
    ("a request interceptor is optional", r"MSW"),
    ("a third party's API is never called from a unit test",
     r"third\s+party's API is never called"),
    # Running it
    ("finite commands, never the watch loop", r"watch loop"),
    ("a file filter is runner input, not shell expansion", r"shell expansion"),
    ("the positional filter is a substring", r"contains that string"),
    ("discover the real test root; never guess it", r"[Nn]ever guess"),
    ("the typechecker runs separately", r"type checker"),
    # Dependencies
    ("the coverage provider matches the runner's version line", r"coverage-v8"),
    ("one package-manager mutation at a time", r"one package-manager mutation"),
    ("install the smallest test surface", r"smallest test surface"),
    ("align the conflicting declaration, not force/legacy peers", r"legacy peer"),
    ("install a peer-complete set in one operation", r"peer-complete"),
    ("one install checklist before the first run", r"checklist"),
    ("the config filename matches the ESM/CommonJS contract", r"CommonJS"),
    ("a dedicated vitest config takes precedence; merge explicitly",
     r"takes precedence"),
    ("keep the runners' discovery boundaries disjoint", r"disjoint"),
    # Repairs
    ("fake timers only for clock-dependent code", r"[Ff]ake timers"),
    ("unhandled rejections are failures, not noise", r"noise to suppress"),
    ("never delete the lockfile as a first repair", r"first repair"),
    ("the official documentation", r"vitest\.dev"),
    ("never weaken an assertion to make it pass", r"weaken assertions"),
]

COMPOSITION = [
    ("the palette and personality belong to other skills", r"Do not re-open"),
    ("answer what this product is before composing", r"What is this\?"),
    ("the tells of a generated page", r"tells"),
    ("professional app of long quality with natural composition",
     r"professional app.*long quality|natural"),
    ("never pad to reach a number", r"Never pad"),
    ("the page argues in an order", r"Orient"),
    ("a dashboard argues differently", r"needs attention now"),
    ("consecutive sections do not share a shape", r"share a shape"),
    ("compose for the product type", r"Booking / scheduling|Commerce"),
    ("write the words, never lorem ipsum", r"lorem ipsum"),
    ("loading, empty, error and success", r"Empty"),
    ("one shell in the root layout", r"root layout"),
    ("thirty-odd links, not three", r"thirty"),
    ("a footer of three or four columns", r"3[-–]4 categorized|three or four columns"),
    ("no dead ends", r"dead-end"),
    ("the current route is marked", r"current route"),
    ("the narrow layout is a real layout", r"squeezed"),
    ("the same three widths the drawing was checked at", r"390px"),
    ("the tablet width", r"820px"),
    ("count before calling a page done", r"Count these first"),
    ("what `/` is follows the reader", r"wrong reader"),
    ("eight rows and the empty state", r"8 or more"),
    ("a heading, a paragraph and a button is not a page", r"not a\s+page"),
]

# Read on every build, and re-read inside the phases that own them, so their
# length is paid for every time. Each was measured, cut and re-measured.
#
# The ceiling is the size it came out at, rounded up to the next 500 — headroom
# for a rule to be worded better, not for the prose to grow back. A rounder,
# more generous number would only be an invitation to fill it, which is exactly
# what the page-size rule this file removes turned out to be.
CONTRACTS = [
    ("html-prototype", DRAWING, 18_000),      # 17,615, was 29,512
    ("full-app-builder", BUILDER, 14_500),    # 14,441, was 18,021
    ("vitest", UNIT_TESTS, 14_000),           # 13,704, was 15,639
    ("page-composition", COMPOSITION, 10_500),  # 10,244
]


class TheSkillContractTests(unittest.TestCase):
    def test_every_rule_is_still_said(self):
        for skill, rules, _ in CONTRACTS:
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            for name, pattern in rules:
                with self.subTest(skill=skill, rule=name):
                    self.assertRegex(text, pattern)

    def test_they_stay_short_enough_to_be_read(self):
        for skill, _, ceiling in CONTRACTS:
            path = SKILLS / skill / "SKILL.md"
            size = len(path.read_text(encoding="utf-8"))
            with self.subTest(skill=skill):
                self.assertLess(size, ceiling, f"{skill} is {size} characters")

    def test_no_skill_asks_for_a_fixed_page_size(self):
        """A page is as long as its content, not as long as a number.

        A byte count is the one rule that can be met without writing anything
        worth reading, and it was: pages padded to clear 9,000 while the six
        sections they were supposed to carry were three.
        """
        for skill, _, _ in CONTRACTS:
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertNotIn("9,000", text)
                self.assertNotIn("15,000", text)

    def test_no_skill_forces_rigid_sections(self):
        """Skills must not prescribe rigid section formulas or arbitrary counts."""
        for skill in ("html-prototype", "page-composition"):
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertIn("professional app", text.lower())
                self.assertIn("natural", text.lower())

    def test_no_skill_hardcodes_one_kind_of_product(self):
        """A hero belongs to a page someone is sold, not to every page.

        Both skills branched on this — a public page opens on a hero, a working
        screen opens on the work — but both stated the hero first and
        unconditionally, and stated the branch much later. The unconditional
        sentence is the one that won: the tyre-shop till was drawn with a hero
        photograph, an overlay, and a "How a sale flows" explainer, on the
        screen its own cashier opens all day.

        So wherever a skill tells a hero to be built, the same passage says who
        it is for. A skill that names one without the other is back to
        designing every product as a landing page.
        """
        for skill in ("html-prototype", "frontend-design"):
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertRegex(text, r"hero", "no hero guidance to qualify")
                self.assertRegex(
                    text, r"worked in|works in|working screen",
                    f"{skill} describes a hero without saying who it is for")
                self.assertRegex(
                    text, r"wrong reader",
                    f"{skill} never says what `/` follows from")

    def test_a_rule_is_not_stated_twice_in_two_skills(self):
        """Two skills saying the same thing is how they come to disagree.

        Every phrase below was being said by both of a pair, and the reader had
        no way to tell which copy was current. The duplicate was cut from the
        skill that does not own the phase.
        """
        moved = [
            # (phrase, the skill that owns it, the skill that must not repeat it)
            ("Coverage", "vitest", "full-app-builder"),
            ("browser downloads", "browser-e2e", "full-app-builder"),
            ("browserSnapshot", "browser-e2e", "full-app-builder"),
            ("vi.mock", "vitest", "full-app-builder"),
        ]
        for phrase, owner, borrower in moved:
            with self.subTest(phrase=phrase):
                self.assertIn(
                    phrase,
                    (SKILLS / owner / "SKILL.md").read_text(encoding="utf-8"),
                    f"{owner} was supposed to own '{phrase}'")
                self.assertNotIn(
                    phrase,
                    (SKILLS / borrower / "SKILL.md").read_text(encoding="utf-8"),
                    f"{borrower} repeats '{phrase}', which {owner} owns")


if __name__ == "__main__":
    unittest.main()
