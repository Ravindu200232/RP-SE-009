"""The deployment commit never carries an environment value file.

The builder writes saved keys to `.env.local` at the project root. The commit
used to stage it, because its exclude patterns only matched below a directory,
and the last check then refused the whole deployment.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test import _support

# The deployment agent imports its own packages by their top-level names.
_AGENT = str(_support.ROOT / "deployment-agent" / "deploy_agent")
if _AGENT not in sys.path:
    sys.path.insert(0, _AGENT)

from dfagents.deployer_git import DeploymentGitMixin  # noqa: E402


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class EnvironmentFilesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        for relative, text in {
            ".env.local": "AUTH_SECRET=not-for-github\n",
            "packages/orders-service/.env": "MONGODB_URI=mongodb://127.0.0.1/app\n",
            ".env.example": "MONGODB_URI=\n",
            "packages/orders-service/src/server.js": "console.log('up')\n",
            "node_modules/left-pad/index.js": "module.exports = 1\n",
        }.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)

    def stage(self):
        return DeploymentGitMixin._stage_reviewed_tree(self.repo, [".env.example"])

    def test_env_files_at_the_root_and_below_are_left_out(self):
        names = self.stage()
        self.assertNotIn(".env.local", names)
        self.assertNotIn("packages/orders-service/.env", names)
        # The generated example has no values, and it is the one kept.
        self.assertIn(".env.example", names)
        self.assertIn("packages/orders-service/src/server.js", names)
        self.assertFalse(any(name.startswith("node_modules/") for name in names))

    def test_a_retry_takes_out_what_an_earlier_attempt_left_staged(self):
        subprocess.run(["git", "add", "-A", "-f", "--", "."], cwd=self.repo, check=True)
        names = self.stage()
        self.assertNotIn(".env.local", names)
        self.assertNotIn("packages/orders-service/.env", names)
        self.assertIn(".env.example", names)


if __name__ == "__main__":
    unittest.main()
