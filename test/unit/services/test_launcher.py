"""The Windows launcher, and the console it must not leave behind.

`start "" /b` sounds like the quiet option and is the opposite of one: `/b`
means "no new window", so the child shares the batch file's console — and a
console is destroyed only once every process attached to it has exited. The
launcher therefore held a command window open for as long as AgentForge ran,
and closing that window took the application with it.

Electron is a GUI binary and opens no console of its own, so launching it as
its own process lets the batch file exit and its console close.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / "start.bat"
QUIET = ROOT / "AgentForge.vbs"


class StartBatTests(unittest.TestCase):
    def setUp(self):
        self.body = LAUNCHER.read_text(encoding="utf-8")

    def tail(self):
        """Everything after the checks: the part that actually launches."""
        return self.body.split("set \"ELECTRON=")[1]

    def test_electron_is_launched_as_its_own_process(self):
        self.assertIn('start "" "%ELECTRON%"', self.tail())

    def test_the_launch_does_not_hold_this_console(self):
        """The `/b` that caused it survives only in the npm fallback."""
        launches = re.findall(r"^\s*start\s+\"\"\s*(/b)?", self.body, re.M)
        self.assertTrue(launches, "the launcher starts nothing at all")
        self.assertEqual(launches[0], "", "the first launch still uses /b")

    def test_there_is_a_fallback_when_the_binary_is_not_where_it_should_be(self):
        """Lingering console beats not starting."""
        self.assertIn("npm --prefix desktop start", self.tail())

    def test_no_pause_can_strand_a_hidden_launcher(self):
        """A `pause` in a hidden window waits forever for a keypress.

        Every one of them is guarded, or the windowless launcher never returns
        and the person sees nothing at all.
        """
        for line in self.body.splitlines():
            stripped = line.strip()
            if re.fullmatch(r"(if not defined AGENTFORGE_QUIET )?pause", stripped):
                with self.subTest(stripped):
                    self.assertTrue(stripped.startswith("if not defined AGENTFORGE_QUIET"),
                                    "an unguarded pause strands the hidden launcher")

    def test_the_launcher_still_refuses_without_its_runtimes(self):
        for needed in ("where node", "where python"):
            with self.subTest(needed):
                self.assertIn(needed, self.body)


class QuietLauncherTests(unittest.TestCase):
    def setUp(self):
        self.body = QUIET.read_text(encoding="utf-8")

    def test_it_runs_the_batch_with_the_window_hidden(self):
        """0 is hidden; True waits, so a refusal can be reported."""
        self.assertRegex(self.body, r"shell\.Run\(command,\s*0,\s*True\)")

    def test_it_tells_the_batch_not_to_wait_on_a_keypress(self):
        self.assertIn('AGENTFORGE_QUIET', self.body)

    def test_a_failure_is_shown_rather_than_swallowed(self):
        self.assertIn("If code <> 0 Then", self.body)
        self.assertIn("MsgBox", self.body)

    def test_what_went_wrong_is_written_down(self):
        """There is no console to have read it from."""
        self.assertIn("start.log", self.body)

    def test_it_runs_from_the_folder_it_lives_in(self):
        """A shortcut's working directory is not this one."""
        self.assertIn("shell.CurrentDirectory = here", self.body)


if __name__ == "__main__":
    unittest.main()
