"""What this deployment actually changed, as a commit message.

Every deployment committed the same sentence with a different run id -
"chore(deploy): deploy Netlify update 4f21ab8c" - so the history of a
repository said that eleven deployments happened and nothing about what any of
them did. A person looking for the deployment that added the worker, or the one
that moved the database, had to open each commit to find out.

The diff already says. This asks the model to read it and write the subject,
falling back to the old template when it cannot - a deployment must never fail
because a sentence could not be written.
"""
from __future__ import annotations

import logging
import re
import subprocess

log = logging.getLogger("deploy.commit")

# What the model is shown. Beyond this the diff stops being informative and
# starts being expensive; the file list alone carries the shape by then.
MAX_DIFF_CHARS = 12000
MAX_SUBJECT = 72

PROMPT = """Write the git commit subject for this deployment change.

Rules:
- One line, at most 72 characters, no trailing full stop.
- Conventional Commits: `chore(deploy): ...` unless the change is plainly a
  fix, in which case `fix(deploy): ...`.
- Say what changed and why it matters to someone reading the history later.
  "deploy update" and "apply changes" say nothing; name the thing that moved.
- Describe only what the diff shows. Invent nothing.

Return the subject line and nothing else."""


def _run(args: list, cwd) -> str:
    try:
        done = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout if done.returncode == 0 else ""


def staged_change(source) -> str:
    """The staged diff, with the file list first so it survives truncation."""
    names = _run(["git", "diff", "--cached", "--stat"], source).strip()
    body = _run(["git", "diff", "--cached", "--no-color"], source)
    if not (names or body):
        return ""
    if len(body) > MAX_DIFF_CHARS:
        body = body[:MAX_DIFF_CHARS] + "\n… diff truncated …"
    return f"FILES CHANGED\n{names}\n\nDIFF\n{body}"


def _clean(text: str) -> str:
    """One subject line out of whatever the model returned."""
    line = ""
    for raw in str(text or "").splitlines():
        candidate = raw.strip().strip("`").strip()
        # Models like to answer "Here is the commit message:" first.
        if not candidate or candidate.endswith(":") and len(candidate) < 40:
            continue
        line = candidate
        break
    line = re.sub(r"^(commit\s+)?(subject|message)\s*[:\-]\s*", "", line, flags=re.I)
    # Quotes and a full stop can be in either order - `"subject".` is common -
    # so this strips until nothing more comes off rather than once each way.
    previous = None
    while line != previous:
        previous = line
        line = line.strip().strip('"').strip("'").strip("`").rstrip(".").strip()
    return line[:MAX_SUBJECT].strip()


SCHEMA = {
    "type": "object",
    "properties": {"subject": {"type": "string", "minLength": 8, "maxLength": MAX_SUBJECT}},
    "required": ["subject"],
    "additionalProperties": False,
}


def write(source, *, provider: str, redeploy: bool, fallback: str,
          client=None) -> str:
    """The subject for this commit, or `fallback` if one cannot be written."""
    change = staged_change(source)
    if not change:
        return fallback
    try:
        if client is None:
            from deploy_agent.bridge import ollama_client
            client = ollama_client()
        answer = client.chat_json(
            PROMPT,
            {
                "target": provider,
                "this_is": ("a redeployment of an app already live" if redeploy
                            else "the first deployment of this app"),
                "change": change,
            },
            SCHEMA,
        )
        subject = _clean((answer or {}).get("subject", ""))
    except Exception as exc:  # noqa: BLE001 - a sentence is never worth a failure
        log.info("commit subject fell back to the template: %s", str(exc)[:200])
        return fallback
    return subject or fallback
