"""
The SRS agent — the step before a build.

It interviews the user about what they want, writes a plan, generates a full
SRS document, and ends with a handoff prompt. AgentForge takes that prompt and
builds the app; the SRS, the app and the QA results then all live together in
the same project folder.

`app/` is a verbatim copy of the standalone srs-generator at
D:\\GITHUB\\srs-generator (apps/api/app). Only `app/config.py` differs. Keep it
that way: everything AgentForge-specific belongs in `bridge.py`.
"""
from .bridge import SRS_PORT, SRS_STAGING  # noqa: F401
