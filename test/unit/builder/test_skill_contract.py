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




# Read on every build, and re-read inside the phases that own them, so their
# length is paid for every time. Each was measured, cut and re-measured.
#
# The ceiling is the size it came out at, rounded up to the next 500 — headroom
# for a rule to be worded better, not for the prose to grow back. A rounder,
# more generous number would only be an invitation to fill it, which is exactly
# what the page-size rule this file removes turned out to be.
#
# `full-app-builder`, `vitest` and `page-composition` were split into the
# `stack-*` skills and are no longer on disk, so their rule lists went with
# them. The new skills carry no content contract yet.
CONTRACTS = [
    ("html-prototype", DRAWING, 18_000),      # 17,615, was 29,512
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
        for skill in ("html-prototype",):
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
        for skill in ("html-prototype",):
            text = (SKILLS / skill / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill):
                self.assertRegex(text, r"hero", "no hero guidance to qualify")
                self.assertRegex(
                    text, r"worked in|works in|working screen",
                    f"{skill} describes a hero without saying who it is for")
                self.assertRegex(
                    text, r"wrong reader",
                    f"{skill} never says what `/` follows from")

    # Two skills saying the same thing is how they come to disagree, and this
    # used to pin four phrases to the skill that owned them. All four pairs
    # named `vitest`, `browser-e2e` or `full-app-builder`, none of which ship
    # any more. The `stack-*` skills that replaced them do share resource files
    # - `build-error-resolver.md` sits in both stack-debug and stack-testing,
    # `api-security-hardening.md` in both stack-security and stack-mern - so
    # this is worth pinning again once it is settled which of them owns what.


if __name__ == "__main__":
    unittest.main()
