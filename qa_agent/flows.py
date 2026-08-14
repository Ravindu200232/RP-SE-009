"""
The scenario grammar: what the model is allowed to say about a user journey.

The model writes a **declarative scenario**, never code:

    FLOW :: sign in and buy a ticket
    AS   :: user
    GOTO :: /login
    FILL :: label=/email/i :: {{email}}
    FILL :: label=/password/i :: {{password}}
    CLICK :: role=button name=/sign in|log in/i
    EXPECT_URL :: /dashboard|events|\\//
    EXPECT_TEXT :: /welcome|my tickets|events/i
    DONE

Every line here maps to one fixed Python function and one fixed line of
JavaScript. An unrecognised verb is dropped rather than executed, so **code the
model wrote is never run inside AgentForge's process** — the difference between a
test harness and an arbitrary-code-execution hole. It also means the Python run
and the emitted `.spec.js` cannot drift: both are generated from the same parsed
`Scenario`, and a test asserts they agree step for step.

Three rules come from measuring generated apps rather than from taste:

* **Selectors are regexes with alternation.** The wording varies per project —
  "Sign In", "Log in", "Login" — so a literal match is a coin flip. A scenario
  that pins exact wording fails on an app that is working perfectly.
* **A clicked control is never queried again.** `Sign In` becomes
  `Signing in...` the moment it is pressed, so the second lookup finds nothing
  and reports a bug that does not exist. Rejected at parse time.
* **Never `networkidle`.** `agents/tester.py:288` already documents why: the
  HMR socket never closes, so the wait can only ever time out.
"""
import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger("qa.flows")

MAX_STEPS = 24


VERBS = {
    "GOTO": 1,
    "FILL": 2,
    "CLICK": 1,
    "WAIT_FOR": 1,
    "EXPECT_TEXT": 1,
    "EXPECT_URL": 1,
    "EXPECT_NO_ERROR": 0,
}
ASSERTIONS = {"EXPECT_TEXT", "EXPECT_URL", "EXPECT_NO_ERROR"}


SELECTOR_KINDS = ("role", "label", "placeholder", "text", "testid")


CLICKABLE_CSS = ("button, a, [role=\"button\"], [role=\"link\"], "
                 "input[type=\"submit\"], input[type=\"button\"]")

_ROLE_RE = re.compile(r"^role=([a-z]+)\s+name=(.+)$", re.I)
_KIND_RE = re.compile(r"^(label|placeholder|text|testid)=(.+)$", re.I)
_REGEX_RE = re.compile(r"^/(.*)/([a-z]*)$", re.S)
_PLACEHOLDER_RE = re.compile(r"\{\{\s*(email|password|role)\s*\}\}")


_PY_ONLY_RE = re.compile(r"\(\?P[<=]|\(\?#|\\A|\\Z|\(\?\(|\\p\{", re.I)


@dataclass
class Selector:
    """One locator, restricted to the five forms Playwright recommends."""
    kind: str
    pattern: str
    flags: str = ""
    role: str = ""
    is_regex: bool = True

    def key(self) -> str:
        """Identity, for the never-re-query rule."""
        return f"{self.kind}:{self.role}:{self.pattern}:{self.flags}".lower()

    def describe(self) -> str:
        head = f"{self.role} " if self.role else ""
        body = f"/{self.pattern}/{self.flags}" if self.is_regex else repr(self.pattern)
        return f"{head}{self.kind} {body}".strip()

    def compiled(self):
        """The Python matcher — a compiled regex, or a plain string."""
        if not self.is_regex:
            return self.pattern
        return re.compile(self.pattern, re.I if "i" in self.flags else 0)

    def js(self) -> str:
        """The JavaScript matcher, verbatim."""
        return (f"/{self.pattern}/{self.flags}" if self.is_regex
                else js_string(self.pattern))

    def js_locator(self, clickable: bool = False) -> str:
        if self.kind == "role":
            return f"getByRole({js_string(self.role)}, {{ name: {self.js()} }})"
        if self.kind == "testid":
            return f"getByTestId({self.js()})"
        if self.kind == "text" and clickable:

            return (f"locator({js_string(CLICKABLE_CSS)})"
                    f".filter({{ hasText: {self.js()} }})")
        return f"getBy{self.kind.capitalize()}({self.js()})"


@dataclass
class Step:
    verb: str
    selector: Selector = None
    value: str = ""
    line: int = 0

    def describe(self) -> str:
        bits = [self.verb]
        if self.selector:
            bits.append(self.selector.describe())
        if self.value:
            bits.append(self.value if "password" not in self.value.lower()
                        else "••••")
        return " :: ".join(bits)


@dataclass
class Scenario:
    title: str = "user flow"
    role: str = ""
    steps: list = field(default_factory=list)
    dropped: list = field(default_factory=list)

    def slug(self) -> str:
        s = re.sub(r"[^a-z0-9]+", "-", (self.title or "flow").lower()).strip("-")
        return (s or "flow")[:40]

    def spec_path(self) -> str:
        return f"tests/e2e/{self.slug()}.spec.js"

    def is_runnable(self) -> str:
        """`""` when this scenario is worth running, else why not."""
        if not self.steps:
            return "the scenario has no steps"
        if not any(s.verb == "GOTO" for s in self.steps):
            return "the scenario never navigates anywhere"
        if not any(s.verb in ASSERTIONS for s in self.steps):

            return "the scenario asserts nothing"
        return ""


def js_string(s: str) -> str:
    return "'" + (s or "").replace("\\", "\\\\").replace("'", "\\'") \
                          .replace("\n", "\\n") + "'"


def parse_selector(raw: str):
    """`(Selector, "")` or `(None, reason)`. Never raises."""
    raw = (raw or "").strip()
    if not raw:
        return None, "empty selector"

    m = _ROLE_RE.match(raw)
    if m:
        role, rest = m.group(1).lower(), m.group(2).strip()
        pat, flags, is_rx, why = _pattern(rest)
        if why:
            return None, why
        return Selector(kind="role", role=role, pattern=pat, flags=flags,
                        is_regex=is_rx), ""

    m = _KIND_RE.match(raw)
    if m:
        kind, rest = m.group(1).lower(), m.group(2).strip()
        pat, flags, is_rx, why = _pattern(rest)
        if why:
            return None, why
        if kind == "testid":

            is_rx, flags = False, ""
        return Selector(kind=kind, pattern=pat, flags=flags, is_regex=is_rx), ""

    pat, flags, is_rx, why = _pattern(raw)
    if why:
        return None, why
    return Selector(kind="text", pattern=pat, flags=flags, is_regex=is_rx), ""


def _pattern(raw: str):
    """`(pattern, flags, is_regex, reason)` — reason non-empty means refuse."""
    raw = raw.strip()
    m = _REGEX_RE.match(raw)
    if not m:
        return raw.strip("'\""), "", False, ""
    src, flags = m.group(1), m.group(2).lower()
    if not src:
        return "", "", False, "an empty regex matches everything"
    if _PY_ONLY_RE.search(src):

        return "", "", True, f"/{src}/ uses syntax JavaScript does not share"
    try:
        re.compile(src)
    except re.error as e:
        return "", "", True, f"/{src}/ is not a valid regex: {e}"
    return src, ("i" if "i" in flags else ""), True, ""


def parse_scenario(text: str, *, account: dict = None) -> Scenario:
    """
    Read the model's reply into a `Scenario`. Never raises, never executes.

    `account` supplies `{{email}}` / `{{password}}` / `{{role}}`. Those come
    from `.agentforge/plan.json`'s `demo_accounts` — the machine-readable source —
    so the model never has to invent a password, and a scenario written for one
    project cannot leak a credential into another.
    """
    sc = Scenario()
    clicked = set()

    for i, raw in enumerate((text or "").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", "//")):
            continue
        if "::" not in line:
            if line.upper() == "EXPECT_NO_ERROR":
                sc.steps.append(Step(verb="EXPECT_NO_ERROR", line=i))
            elif line.upper() not in ("DONE", "END"):
                sc.dropped.append((i, line[:80], "not a `VERB :: …` line"))
            continue

        head, _, rest = line.partition("::")
        verb = head.strip().upper()
        rest = rest.strip()

        if verb == "FLOW":
            sc.title = rest[:80]
            continue
        if verb in ("AS", "ROLE"):
            sc.role = "" if rest.lower() in ("guest", "anonymous", "none") \
                else rest.strip().lower()[:40]
            continue
        if verb not in VERBS:
            sc.dropped.append((i, line[:80], f"{verb} is not a verb"))
            continue
        if len(sc.steps) >= MAX_STEPS:
            sc.dropped.append((i, line[:80], f"over the {MAX_STEPS}-step cap"))
            continue

        arity = VERBS[verb]
        if arity == 0:
            sc.steps.append(Step(verb=verb, line=i))
            continue

        if verb == "GOTO":
            path = rest.split("::")[0].strip()
            if not path.startswith("/"):
                sc.dropped.append((i, line[:80], "GOTO needs a path like /login"))
                continue
            if path.startswith("//") or "://" in path:

                sc.dropped.append((i, line[:80], "GOTO must stay in this app"))
                continue
            if "[" in path or "]" in path:

                sc.dropped.append((i, line[:80],
                                   "a dynamic route needs a real id — reach it "
                                   "by clicking a link"))
                continue
            sc.steps.append(Step(verb=verb, value=path[:200], line=i))
            continue

        if verb in ("EXPECT_TEXT", "EXPECT_URL"):
            sel, why = parse_selector(rest)
            if why:
                sc.dropped.append((i, line[:80], why))
                continue
            sc.steps.append(Step(verb=verb, selector=sel, line=i))
            continue

        sel_raw, _, value = rest.partition("::")
        sel, why = parse_selector(sel_raw)
        if why:
            sc.dropped.append((i, line[:80], why))
            continue

        if verb == "FILL":
            value = value.strip()
            if not value:
                sc.dropped.append((i, line[:80], "FILL needs a value"))
                continue
            value = _fill_placeholders(value, account)

        if sel.key() in clicked:
            sc.dropped.append((i, line[:80],
                               "this control was already clicked — it will "
                               "have changed its label"))
            continue
        if verb == "CLICK":
            clicked.add(sel.key())

        sc.steps.append(Step(verb=verb, selector=sel, value=value.strip(),
                             line=i))

    return sc


def _fill_placeholders(value, account):
    acc = account or {}

    def sub(m):
        return str(acc.get(m.group(1), "")) or m.group(0)
    return _PLACEHOLDER_RE.sub(sub, value)[:200]


def to_playwright_js(sc: Scenario, *, base_url="http://localhost:5173") -> str:
    """
    The same scenario as a real `@playwright/test` spec, for the project.

    Generated from the parsed `Scenario`, not from the model's text, so what
    AgentForge ran and what the user can re-run cannot diverge. It is written to
    the project as a deliverable; AgentForge itself runs the Python path, which
    needs no npm install and no browser download.
    """
    body = [
        "// Written by AgentForge from a generated scenario.",
        "//   npm i -D @playwright/test && npx playwright test",
        "//",
        "// Navigation waits on 'load', never 'networkidle'. The dev server's",
        "// HMR socket never closes, so a networkidle wait can only time out.",
        "import { test, expect } from '@playwright/test'",
        "",
        f"const BASE = process.env.BASE_URL || {js_string(base_url)}",
        "",
        f"test({js_string(sc.title)}, async ({{ page }}) => {{",
        "  const problems = []",
        "  page.on('pageerror', (e) => problems.push(String(e)))",
        "  page.on('console', (m) => "
        "{ if (m.type() === 'error') problems.push(m.text()) })",
        "",
    ]
    for st in sc.steps:
        body.append("  " + _js_step(st))
    body += ["})", ""]
    return "\n".join(body)


def _js_step(st: Step) -> str:
    if st.verb == "GOTO":

        return (f"await page.goto(BASE + {js_string(st.value)}, "
                f"{{ waitUntil: 'load' }})")
    if st.verb == "FILL":
        return f"await page.{st.selector.js_locator()}.first().fill({js_string(st.value)})"
    if st.verb == "CLICK":
        return (f"await page.{st.selector.js_locator(clickable=True)}"
                f".first().click()")
    if st.verb == "WAIT_FOR":
        return (f"await expect(page.{st.selector.js_locator()}.first())"
                f".toBeVisible({{ timeout: 15000 }})")
    if st.verb == "EXPECT_TEXT":
        return (f"await expect(page.locator('body'))"
                f".toContainText({st.selector.js()}, {{ timeout: 15000 }})")
    if st.verb == "EXPECT_URL":
        return f"await expect(page).toHaveURL({st.selector.js()})"
    if st.verb == "EXPECT_NO_ERROR":
        return "expect(problems, problems.join('\\n')).toHaveLength(0)"
    return f"// unsupported: {st.verb}"


PLAYWRIGHT_CONFIG = """\
// Written by AgentForge.
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60000,
  retries: 0,
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:5173',
    // 'load', never 'networkidle': the dev server's HMR socket never closes,
    // so a networkidle wait can only ever time out.
    actionTimeout: 15000,
    trace: 'off',
  },
})
"""

GRAMMAR = """\
FLOW :: <what this journey proves, in a few words>
AS :: <role from the demo accounts, or GUEST>
GOTO :: /path
FILL :: <selector> :: <value>
CLICK :: <selector>
WAIT_FOR :: <selector>
EXPECT_TEXT :: /regex/i
EXPECT_URL :: /regex/
EXPECT_NO_ERROR
DONE

Selectors — one of these five, and nothing else:
    role=button name=/sign in|log in/i
    label=/email/i
    placeholder=/search/i
    text=/welcome back/i
    testid=submit

Values may use {{email}} and {{password}} — AgentForge substitutes the demo
account for the role you named, so never write a real password.
"""
