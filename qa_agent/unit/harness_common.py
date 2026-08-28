"""
Everything a generated test needs in order to run, written by Python.

The split is deliberate and it is the difference between this feature helping
and hurting. **AgentForge writes the config and the mocks; the model writes only the
test bodies.** Every hazard below is a configuration problem, and a
configuration problem produces a failure that reads exactly like an application
bug — at which point the bug fixer goes after correct code:

* `jsconfig.json`'s `@/*` alias **is not read by Vitest**. Without an explicit
  `resolve.alias`, every single test dies on `Failed to resolve import
  "@/lib/mongodb"` — which looks like a missing module in the app.
* `postcss.config.js` is auto-discovered by Vite and would drag Tailwind and
  autoprefixer into every run.
* These projects have no `"type": "module"`, so a `vitest.config.js` containing
  `import` is ambiguous. `.mjs` is not.
* `vi.mock` is hoisted above the imports. A mock expressed as anything other
  than a module the test points at will silently not apply.
* `new ObjectId('123')` throws. A model that hardcodes a short id produces a
  crash inside the driver, three frames from anything it wrote.

So the model gets one copyable line per mock and never has to know any of it.
"""
import logging
import re
import textwrap
import threading
from pathlib import Path

log = logging.getLogger("qa.harness")


NPM_LOCK = threading.RLock()
NPM_FAILED_SPEC = {}


def npm_busy() -> bool:
    """True when something is installing right now. For logging only."""
    if NPM_LOCK.acquire(blocking=False):
        NPM_LOCK.release()
        return False
    return True


DEV_DEPS = ["vitest@3", "jsdom@25",
            "@testing-library/react@16", "@testing-library/jest-dom@6",

            "@testing-library/user-event@14"]

CONFIG = "vitest.config.mjs"
SETUP = "tests/setup.js"
HELPERS = "tests/helpers"

__all__ = [name for name in globals() if not name.startswith("__")]
