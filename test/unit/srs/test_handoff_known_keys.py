"""Every SRS field is either rendered by a handoff section, or deliberately not.

`_build_app_md` turns any top-level key it does not recognise into a
`## Title Cased` section built by `_generic_markdown`. That escape hatch is
useful once - it stops a new field from being invisible - but it means the
handoff's shape changes the moment anyone adds a field, and the agents read
that handoff as a contract.

This caught `effective_plan`: written by `parent_sync` after every accepted
change, absent from `_KNOWN_KEYS`, so `app.md` grew an `## Effective Plan`
section after the first sync and not before. A freshly generated project and a
synced one handed the agents different documents.

Adding a key here is a decision, not a formality. A key belongs in
`_KNOWN_KEYS` when a section builder already renders it, or when the agents
genuinely do not need it; if neither is true, write the section instead.
"""
import unittest

from test import _support  # noqa: F401 - puts the agent packages on the path
from srs_agent.app.generators.agent_handoff import _KNOWN_KEYS
from srs_agent.app.schemas.srs import SrsDocument

# Dynamic schema keys added at runtime that map to specific document sections.
RUNTIME_KEYS = {
    # A projection of the SRS the studio reads; the agents get the same content
    # through `approved_plan` and `approved_plan_markdown`, which are rendered.
    "effective_plan",
}


class HandoffKnownKeys(unittest.TestCase):
    def test_every_schema_field_is_accounted_for(self):
        missing = sorted(set(SrsDocument.model_fields) - _KNOWN_KEYS)
        self.assertEqual(missing, [], (
            "These SRS fields are not in _KNOWN_KEYS, so each one becomes a new "
            "'## Title Cased' section in app.md and changes the handoff the "
            "agents read. Render them in a section builder, or add them to "
            f"_KNOWN_KEYS deliberately: {missing}"))

    def test_runtime_keys_are_declared(self):
        undeclared = sorted(RUNTIME_KEYS - _KNOWN_KEYS)
        self.assertEqual(undeclared, [], (
            "Keys written onto the document at run time must be in _KNOWN_KEYS "
            f"for the same reason: {undeclared}"))


if __name__ == "__main__":
    unittest.main()
