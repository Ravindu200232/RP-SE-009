"""
The end-to-end pass: sign in as a real seeded account and use the app.

This is the only gate in AgentForge that exercises a page. Unit tests cannot:
Next's own bundled documentation says Vitest does not support async Server
Components, which is every page that reads data. The route probe proves a page
returns 200; nothing until here proves that filling the login form and pressing
the button actually signs you in.

Two decisions shape the whole file.

**The model writes a scenario, not code.** `flows.py` maps each line to one
fixed Python call, so nothing the model produced is ever executed in AgentForge's
process. The same parsed scenario is also emitted as a real
`tests/e2e/<flow>.spec.js`, which the user can run and export — generated from
the parsed form, so what AgentForge ran and what ships cannot diverge.

**AgentForge runs it through the Python Playwright it already has.** Measured on
this machine: `playwright==1.60.0` wants chromium **1223**, which is already in
`~/AppData/Local/ms-playwright`. So the run costs no npm install and no browser
download, while `npx playwright test` would cost ~50 MB per project and might
want a revision that is not cached. The `.spec.js` is the deliverable; the
Python path is the runner.

Failures are split before anyone is asked to fix anything, because the two
kinds mean opposite things:

* **the scenario is wrong** — a control it named does not exist. That is the
  model's description being off, not the app being broken, and it costs one
  re-author, never a code edit.
* **the app is broken** — a 500, an uncaught exception, an assertion about
  content that is genuinely absent. Only these reach the bug fixer.
"""
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from agents.planner.architecture import FileStreamParser
from agents.build.tester_common import overlay_error

from qa_agent.e2e.flows import (CLICKABLE_CSS, FIELD_CSS, GRAMMAR, PLAYWRIGHT_CONFIG,
                    Scenario, Selector, field_css, is_auth_submit_step,
                    parse_scenario, to_playwright_js)
from qa_agent.core.session_files import QASession
from qa_agent.unit.spec import TestFailure

log = logging.getLogger("qa.e2e")

TEMPERATURE = 0.3

# One scenario is a few dozen lines.
CALL_BUDGET = 180

STEP_TIMEOUT = 7_000
ASSERT_TIMEOUT = 8_000
GOTO_TIMEOUT = 30_000
HYDRATE_TIMEOUT = 8_000
# How many journeys the E2E stage walks.
MAX_FLOWS = 6
MAX_REAUTHOR = 3


KIND_CRASH = "CRASH"
KIND_SELECTOR = "SELECTOR"
KIND_BEHAVIOR = "BEHAVIOR"

SYSTEM = """\
You describe ONE end-to-end user journey through a Next.js app, as a scenario.

You are NOT writing code. You emit only the lines below, and AgentForge runs them
with a real browser. Anything that is not one of these verbs is discarded.

""" + GRAMMAR + """
RULES THAT DECIDE WHETHER THIS WORKS
  • Selectors must be REGEXES WITH ALTERNATION, because the exact wording
    varies per app: use /sign in|log in|login/i, never 'Sign In'. A scenario
    that pins exact wording fails on an app that is working perfectly.
  • For login/auth fields use `field=email` and `field=password`. They bind to
    input type/name/autocomplete, so `placeholder="name@example.com"` is still
    an email field. For other text inputs use the REAL placeholder shown in the
    markup, then `role=textbox name=…`. Do NOT invent `/email/i` merely because
    the field contains an email address.
  • Do NOT use `label=` unless the markup ties the label to the input with
    htmlFor/id. A visible `<label>` beside an input is not automatically a
    Playwright label.
  • RUNTIME DOM EVIDENCE IS AUTHORITATIVE. If it exposes a `data-testid`,
    accessible name, field name or href for the action, COPY that observed
    locator instead of paraphrasing it. Prefer an observed `testid=` for icon
    controls and mutation buttons because it survives copy changes. Never
    invent a glyph, record id, or button wording that the evidence does
    not show. If a workflow requires an action but the evidence has no usable
    control, keep the business action in the scenario using its natural
    accessible name so the run exposes an APP defect; do not replace it with an
    unrelated control merely to make the test green.
  • CLICK must name a control: `role=button name=/…/i` or
    `role=link name=/…/i`. A bare text match is ambiguous with prose — a login
    page whose heading reads "Sign in to manage your tickets" puts that
    sentence before the button, so `text=/sign in/i` matches the paragraph.
  • NEVER click a control and then refer to it again. A submit button becomes
    "Signing in..." the moment it is pressed, so the second lookup finds
    nothing and reports a bug that does not exist.
  • Page identity is a URL fact, not a copywriting fact. Prefer EXPECT_URL for
    reaching a workspace/list/detail page. Do NOT assert a marketing
    slogan or section heading unless the runtime DOM evidence below contains it.
  • Use `field=<name-or-id>` only when RUNTIME DOM EVIDENCE literally shows
    that input/select `name=` or `id=`. Standard HTML email/password fields may
    use field=email and field=password. Product field names come from this app,
    never from a global sample vocabulary. When the
    runtime evidence says the element is a <select>, use SELECT, not FILL.
  • If a journey needs another role page after login, GOTO that exact served
    route observed for that actor. Do not assume the auth landing page is
    the page where the rest of the workflow happens.
  • Assert something the seeded data guarantees. Do not assert a number, a
    date, or a name you are guessing at. Prefer EXPECT_VALUE after editing a
    field and EXPECT_URL after navigation.
  • FILL/SELECT values are evidence too. Copy a value from the accepted
    requirement, seed/demo data, current DOM/source, option list or explicit
    input constraint. Do not invent app-specific identifiers, option values,
    prices or test ids just because that would make a
    plausible scenario. If the workflow only requires changing a free-form
    value, choose a simple valid value that satisfies the observed input type
    and then prove that SAME value with EXPECT_VALUE/text/state.
  • Registration has no universal redirect. Never assert the credential-entry
    route after signup unless the accepted flow or observed runtime/source explicitly
    says signup lands there. Some apps auto-sign-in and route by role; prove the
    actual planned outcome instead of forcing the app to fit a generic auth
    script.
  • Prefer the shortest journey that proves the feature works end to end:
    sign in, reach the page that needs the session, see the thing that only
    a signed-in user sees.
  • Between 4 and 12 steps. Finish with DONE.

Emit the scenario and nothing else — no explanation, no code fences.
"""



_NOISE = ("[Fast Refresh]", "webpack-hmr", "Download the React DevTools",
          "[browser]", "hydrat", "favicon.ico", "DevTools",
          "destination stream closed early")


def _is_noise(text: str) -> bool:
    return any(n.lower() in (text or "").lower() for n in _NOISE)


def _landed_on(current: str, route: str) -> bool:
    """
    Whether the browser is on `route` — the whole path, not the tail of it.

    `current.rstrip("/").endswith(route)` was close enough to pass and wrong
    in a way that matters: `http://x` ends with `/x`, so a short route matched
    the bare origin the guard had just redirected to, and a page that
    correctly bounced somebody was recorded as having let them in. Whether a
    guard fired is the entire question this file answers.
    """
    try:
        path = urlparse(current or "").path or "/"
    except Exception:
        return False
    return path.rstrip("/") == (route or "/").rstrip("/")

__all__ = [name for name in globals() if not name.startswith("__")]
