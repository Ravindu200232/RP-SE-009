"""Public E2E agent façade composed from small purpose-specific mixins."""
from .e2e_common import *
from .e2e_context import E2EContextMixin
from .e2e_loop_guard import E2ELoopGuardMixin
from .e2e_authoring import E2EAuthoringMixin
from .e2e_execution import E2EExecutionMixin
from .e2e_evidence import E2EEvidenceMixin
from .e2e_steps import E2EStepsMixin
from .e2e_locators import E2ELocatorsMixin
from .e2e_state import E2EStateMixin


class E2EAgent(
    E2EContextMixin, E2ELoopGuardMixin, E2EAuthoringMixin, E2EExecutionMixin,
    E2EEvidenceMixin, E2EStepsMixin, E2ELocatorsMixin, E2EStateMixin,
):
    """Author a journey, run it, and report what actually broke.

    These class-level parsers/caps deliberately remain on the façade.  The
    pre-refactor E2EAgent stored them on the class and the focused mixins
    access them through ``self``.  Keeping them here preserves that contract
    without duplicating shared policy across the split modules.
    """

    _ARROW = re.compile(r"\s*(?:\u2192|-->|->|\$*\\[a-zA-Z]*(?:to|arrow)\s*\$*)\s*")
    _BULLET = re.compile(r"^\s*[-*]\s+")
    _TESTID_RE = re.compile(r"""data-testid=['"]([\w:-]+)['"]""")
    _SIGNED_OUT = ("", "signed out", "signed-out", "logged out", "logged-out",
                   "anonymous", "none", "nobody", "visitor", "public")
    _SITE_RES = (
        re.compile(r"webpack-internal:/+\([^)]*\)/\.?/?"
                   r"((?:app|components|lib)/[\w./\[\]()-]+?\.(?:jsx?|mjs))"
                   r"(?::(\d+))?"),
        re.compile(r"/_next/static/chunks/"
                   r"((?:app|components|lib)/[\w./\[\]()-]+?)\.js"
                   r"(?::(\d+))?"),
        re.compile(r"\b((?:app|components|lib)/[\w./\[\]()-]+?\.(?:jsx?|mjs))"
                   r"(?::(\d+))?"),
    )
    SWEEP_CAP = 25


__all__ = [
    "E2EAgent", "KIND_CRASH", "KIND_SELECTOR", "KIND_BEHAVIOR",
    "MAX_REAUTHOR", "MAX_FLOWS",
]

# Preserve the public surface of the pre-refactor module.
__all__ = ['ASSERT_TIMEOUT', 'CALL_BUDGET', 'E2EAgent', 'GOTO_TIMEOUT', 'HYDRATE_TIMEOUT', 'KIND_BEHAVIOR', 'KIND_CRASH', 'KIND_SELECTOR', 'MAX_FLOWS', 'MAX_REAUTHOR', 'STEP_TIMEOUT', 'SYSTEM', 'TEMPERATURE', 'log']
