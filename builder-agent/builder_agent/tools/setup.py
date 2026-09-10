"""Asking the person watching, while the work is still going on.

Two things a build cannot work out on its own, and used to guess at.

The first is an account setting — a Stripe secret, a Cloudinary cloud name. No
amount of reading the project produces one. Most are settled before planning,
because the plan should know which provider it is for; `askForSetup` is for the
one discovered later, and it never returns the value to the model: it goes from
the browser to the run to `.env.local` and stops there, so a key cannot be
echoed into a transcript, compacted into a summary, or sent to whichever
provider is answering.

The second is a decision that was always the user's. A request says "members
can cancel a booking" and does not say whether that is allowed an hour before
it starts. Something has to decide, and a model deciding quietly is how an
application ends up not being the one somebody asked for. `askUser` puts it to
them.

Neither blocks. Both carry a deadline, and when it passes the run continues on
the assumption it declared — a closed browser costs a choice, never a build.
"""
from __future__ import annotations

from ..errors import ToolError
from ..policy import MODERATE, SAFE
from ..setup import ASK_TIMEOUT, apply_answer, read_choices, read_fields
from .base import Tool


def ask_for_setup(args, ctx):
    purpose = str(args.get("purpose") or "").strip()
    if len(purpose) < 8:
        raise ToolError("Say what these settings are for, in a sentence the user will "
                        "recognise - 'Stripe payments', 'Email notifications through Resend'.")
    question = {
        "skill": "",
        "purpose": purpose[:200],
        "question": str(args.get("question") or "").strip()[:200],
        "choices": read_choices(args.get("choices")),
        "fields": read_fields(args.get("fields")),
    }

    approvals = getattr(ctx, "approvals", None)
    answer = {}
    if approvals is not None:
        answer = approvals.ask(
            "setup",
            {key: question[key] for key in ("purpose", "question", "choices", "fields")},
            default={"decision": "later"}, timeout=ASK_TIMEOUT,
            cancel=getattr(ctx, "cancel", None))

    applied = apply_answer(ctx.sandbox.root, question, answer)
    # Names only. A value that reaches an event reaches the log, the saved
    # stream and the transcript, which is every place a secret must not be.
    ctx.events.emit("setup", purpose=question["purpose"], choice=applied["label"],
                    saved=applied["saved"], missing=applied["missing"])

    lines = [applied["note"]]
    if applied["saved"]:
        lines.append("The values were not returned to you and must never be written into "
                     "source, a test, a commit or a message.")
    if applied["missing"]:
        lines.append("Do not ask for these again in this run.")
    return {"ok": True, "content": " ".join(lines)}


# What a question may offer before it stops being a question and starts being
# a form.
MAX_OPTIONS = 6


def _options(raw) -> list[dict]:
    out = []
    for item in (raw or [])[:MAX_OPTIONS]:
        if isinstance(item, str) and item.strip():
            out.append({"id": item.strip()[:60], "label": item.strip()[:60], "hint": ""})
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("id") or "").strip()
            if label:
                out.append({"id": str(item.get("id") or label)[:60], "label": label[:60],
                            "hint": str(item.get("hint") or "").strip()[:200]})
    return out


def ask_user(args, ctx):
    """Put a decision to the person watching instead of taking it alone."""
    question = str(args.get("question") or "").strip()
    if len(question) < 10:
        raise ToolError("Ask a whole question, in the words the user would use.")
    assumption = str(args.get("assumption") or "").strip()

    approvals = getattr(ctx, "approvals", None)
    answer = {}
    if approvals is not None:
        answer = approvals.ask(
            "question",
            {"question": question[:400], "why": str(args.get("why") or "").strip()[:300],
             "options": _options(args.get("options")), "assumption": assumption[:200]},
            default={"decision": "default"}, timeout=ASK_TIMEOUT,
            cancel=getattr(ctx, "cancel", None))

    reply = str(answer.get("reply") or "").strip()
    if answer.get("decision") == "answer" and reply:
        ctx.events.emit("answered", question=question[:200], reply=reply[:300])
        return {"ok": True, "content": f"They answered: {reply}\n"
                                       "Build that. It is now part of the requirement."}

    return {"ok": True, "content":
            "Nobody answered in time, so this one is yours. "
            + (f"Proceed with what you proposed: {assumption}. " if assumption else
               "Take the most conservative reading of the request. ")
            + "Say what you assumed in the final report, and do not ask this again."}


def register(registry):
    registry.add(Tool(
        name="askUser", risk=SAFE, review_safe=True, handler=ask_user,
        summarize=lambda args: str(args.get("question") or "")[:60],
        description=(
            "Put a question to the person watching this build and use their answer. For a "
            "decision that is genuinely theirs and expensive to get wrong: an ambiguity in "
            "the request that changes what gets built, two reasonable readings of a "
            "requirement, a product choice the request never settled, a piece of information "
            "only they have. Offer `options` when the sensible answers are known, and always "
            "give `assumption` — what you will do if nobody replies — because the run carries "
            "on either way. Do not ask what the request, the plan or the code already "
            "answers; do not ask permission to do the work you were asked to do; do not ask "
            "the same thing twice."),
        parameters={
            "type": "object",
            "properties": {
                "question": {"type": "string",
                             "description": "The question, in the user's own terms."},
                "why": {"type": "string",
                        "description": "What in the request or the code raised it."},
                "options": {"type": "array",
                            "description": "The answers you can see: strings, or "
                                           "{id, label, hint} objects.",
                            "items": {"type": "any"}},
                "assumption": {"type": "string",
                               "description": "What you will do if nobody answers."},
            },
            "required": ["question"],
        }))

    registry.add(Tool(
        name="askForSetup", risk=MODERATE, mutates=True, handler=ask_for_setup,
        summarize=lambda args: str(args.get("purpose") or "settings"),
        description=(
            "Ask the user for an account setting only they can supply — an API key, a "
            "publishable key, an account identifier — and write it into this project's "
            ".env.local. Most are settled before the build starts; use this for one you "
            "discover you need. Give every field a real example value, because someone who "
            "has never seen the setting cannot tell a secret key from an account id without "
            "one. Offer `choices` when there is a decision first, such as test credentials "
            "against live ones, and hang each option's own fields off it. The values are "
            "never returned to you: read them with process.env at run time and never write "
            "one into source. If nobody answers, the names are recorded in .env.example and "
            "you build the feature against the environment anyway."),
        parameters={
            "type": "object",
            "properties": {
                "purpose": {"type": "string",
                            "description": "What these settings are for, in the user's words."},
                "question": {"type": "string",
                             "description": "The choice to put to them, when there is one."},
                "choices": {"type": "array",
                            "description": "Options for that choice: {id, label, hint, fields}.",
                            "items": {"type": "object"}},
                "fields": {"type": "array",
                           "description": "Settings asked for whichever option is taken: "
                                          "{key, label, hint, example, secret, required}. "
                                          "`key` is the environment variable name.",
                           "items": {"type": "object"}},
            },
            "required": ["purpose", "fields"],
        }))
