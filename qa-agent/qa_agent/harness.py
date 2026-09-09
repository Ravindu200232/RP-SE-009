"""Making sure a test suite can actually run before asking a model to write one.

The most common way a unit stage wastes an hour is authoring twenty good test
files into a project whose runner was never installed, then spending every
repair round on the same "vitest: not found". So the harness is checked and
repaired first, deterministically, with no model involved.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

VITEST_CONFIG = """import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  // App Router files are `.js` and contain JSX. Vite only applies the JSX
  // transform to `.jsx` unless told otherwise, so a test that imports a page
  // fails to parse at the first `<`.
  plugins: [react({ include: /\\.(js|jsx)$/ })],
  resolve: { alias: { '@': path.resolve(process.cwd()) } },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['vitest.setup.js'],
    include: ['test/**/*.test.{js,jsx}'],
    testTimeout: 15000,
    hookTimeout: 15000,
    coverage: { provider: 'v8', reporter: ['json-summary', 'text'],
                reportsDirectory: 'coverage',
                include: ['app/**', 'lib/**', 'models/**', 'components/**'],
                exclude: ['**/*.test.*', 'test/**', '.next/**'] },
  },
});
"""

VITEST_SETUP = """// The runner-specific entry brings its own `expect`; importing the plain
// '@testing-library/jest-dom' would need a global one to exist already.
import '@testing-library/jest-dom/vitest';
"""

DEV_DEPENDENCIES = {
    "vitest": "^2.1.8",
    "@vitest/coverage-v8": "^2.1.8",
    "@vitejs/plugin-react": "^4.3.4",
    "@testing-library/react": "^16.1.0",
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/user-event": "^14.5.2",
    "jsdom": "^25.0.1",
}


def package_manager(root: Path) -> str:
    for lockfile, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                           ("bun.lockb", "bun"), ("package-lock.json", "npm")):
        if (root / lockfile).is_file():
            return name
    return "npm"


def _load(root: Path) -> dict:
    try:
        return json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def prepare(root: Path, run) -> dict:
    """Make the project runnable by Vitest with coverage. Returns what it did.

    `run(command)` executes a shell command in the project and returns the
    engine's result dict, so this stays testable without spawning npm.
    """
    root = Path(root)
    actions: list[str] = []
    manifest = _load(root)
    if not manifest:
        return {"ok": False, "actions": [], "reason": "No readable package.json in this project."}

    dev = dict(manifest.get("devDependencies") or {})
    missing = {name: version for name, version in DEV_DEPENDENCIES.items() if name not in dev}
    if missing:
        manifest.setdefault("devDependencies", {}).update(missing)
        actions.append("added " + ", ".join(sorted(missing)))

    scripts = manifest.setdefault("scripts", {})
    if "test" not in scripts:
        scripts["test"] = "vitest run"
        actions.append("added the test script")

    if missing or "test" in actions:
        (root / "package.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    config = root / "vitest.config.js"
    if not config.is_file():
        config.write_text(VITEST_CONFIG, encoding="utf-8")
        actions.append("wrote vitest.config.js")
    elif "coverage" not in config.read_text(encoding="utf-8", errors="replace"):
        # A config without a coverage reporter cannot produce the machine
        # report the floor is measured from, and the stage would fail on a
        # missing file rather than on the code.
        config.write_text(VITEST_CONFIG, encoding="utf-8")
        actions.append("added coverage reporting to vitest.config.js")

    setup = root / "vitest.setup.js"
    if not setup.is_file():
        setup.write_text(VITEST_SETUP, encoding="utf-8")
        actions.append("wrote vitest.setup.js")

    (root / "test").mkdir(exist_ok=True)

    if not (root / "node_modules" / "vitest").is_dir() or missing:
        manager = package_manager(root)
        result = run(f"{manager} install")
        if result.get("exitCode") not in (0, None):
            return {"ok": False, "actions": actions,
                    "reason": f"{manager} install failed: "
                              f"{(result.get('stderr') or result.get('stdout') or '')[-800:]}"}
        actions.append(f"{manager} install")

    return {"ok": True, "actions": actions, "reason": ""}


def run_command(root: Path, files: list[str] | None = None) -> str:
    """The command that produces both a JSON report and a coverage summary."""
    manager = package_manager(root)
    runner = {"npm": "npx", "pnpm": "pnpm exec", "yarn": "yarn", "bun": "bunx"}[manager]
    target = " " + " ".join(files) if files else ""
    return (f"{runner} vitest run{target} --coverage "
            "--reporter=json --outputFile=.agentforge/qa/vitest.json")


def read_report(root: Path) -> dict | None:
    try:
        return json.loads((root / ".agentforge" / "qa" / "vitest.json")
                          .read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def read_coverage(root: Path) -> dict | None:
    for candidate in ("coverage/coverage-summary.json", "coverage/coverage-final.json"):
        try:
            data = json.loads((root / candidate).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        total = data.get("total")
        if isinstance(total, dict):
            return total
    return None


# The engine's own machinery inside a project, which ships example tests that
# the project does not run. Guarded suffixes mark the same thing at file level.
ENGINE_DIRS = frozenset({".agents", ".agent", ".agentforge", ".git", "node_modules"})
GUARDED = (".txt", ".tpl")


def test_files(root: Path, limit: int = 60) -> list[Path]:
    """Every test file this project actually runs, wherever it keeps them.

    One project puts them in `test/` at the root; a workspaces project puts
    them in `packages/<service>/test/` and `client/test/`, and looking only at
    the root found none of them - the Coder view said a repository with five
    suites had no test files on disk.

    A skill's example test and a scaffold skeleton are not this project's
    tests: both carry a guard suffix so no runner picks them up, and neither
    does this.
    """
    from .security import ignored_dirs

    skip = ENGINE_DIRS | ignored_dirs(root)
    found = []
    for path in sorted(Path(root).rglob("*.test.*")):
        if path.name.endswith(GUARDED) or not path.is_file():
            continue
        if any(part in skip for part in path.relative_to(root).parts):
            continue
        found.append(path)
        if len(found) >= limit:
            break
    return found


def collect_test_sources(root: Path, limit: int = 60) -> dict[str, str]:
    """Every test file on disk, for the studio's Coder view."""
    out = {}
    for path in test_files(Path(root), limit):
        try:
            out[path.relative_to(root).as_posix()] = path.read_text(
                encoding="utf-8", errors="replace")[:40_000]
        except OSError:
            continue
    return out


def has_runner(root: Path) -> bool:
    return (Path(root) / "node_modules" / "vitest").is_dir() or bool(shutil.which("vitest"))
