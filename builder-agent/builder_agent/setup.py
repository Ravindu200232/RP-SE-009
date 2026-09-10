"""The account settings a build needs, asked before it plans anything.

Some of what an application needs cannot be read out of a repository: a Stripe
secret, a Cloudinary cloud name, whether the payments being built are real ones
or test ones. Asking during the build is late — by then the plan has already
been written, and it was written without knowing which provider it was for.

So the questions come first. A skill that needs settings ships a `setup.json`
beside its SKILL.md declaring what to ask; the questions belong to the skill
because the skill is what knows the answer's shape, and because adding a new
integration should be a new directory rather than a new branch in here.

A question is only asked when its skill was selected, and a skill is only
selected when the request asks for it. A todo list is never asked about Stripe.

The value never enters the model's context. It goes from the browser to the
run to `.env.local` and stops there; what the plan and the build are told is
which provider was chosen and which names were set, never what they were set
to.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import ToolError
from .skills import SKILL_ROOT

# An environment variable name, which is what every one of these becomes.
ENV_NAME = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
MAX_FIELDS = 12

# Long enough to go and find a key in someone else's dashboard, which is what
# this is actually asking for, and short enough that a closed browser does not
# hold a build open for the afternoon.
ASK_TIMEOUT = 900.0

# A question about the product is not that. It is answered in seconds by
# somebody watching, or it is not going to be answered at all, so waiting a
# quarter of an hour on one only stalls a run nobody is in front of.
QUESTION_TIMEOUT = 240.0


def read_fields(raw, *, source: str = "") -> list[dict]:
    """Read requested fields, refusing anything that cannot honestly be asked."""
    where = f" in {source}" if source else ""
    if not isinstance(raw, list) or not raw:
        raise ToolError(f"Name at least one setting to ask for{where}.")
    if len(raw) > MAX_FIELDS:
        raise ToolError(f"Ask for at most {MAX_FIELDS} settings at a time{where}.")

    out, seen = [], set()
    for item in raw:
        if not isinstance(item, dict):
            raise ToolError(f"Each field{where} is an object with key, label and example.")
        key = str(item.get("key") or "").strip().upper()
        if not ENV_NAME.match(key):
            raise ToolError(f"{key or '(empty)'} is not an environment variable name{where}. "
                            "Use upper case with underscores, such as STRIPE_SECRET_KEY.")
        if key in seen:
            raise ToolError(f"{key} was asked for twice{where}.")
        seen.add(key)
        example = str(item.get("example") or "").strip()
        if not example:
            # Told only "API key", people paste an account id, or a publishable
            # key where a secret belongs, or the whole line they copied out of
            # a dashboard. An example is the difference.
            raise ToolError(f"{key} needs an example value{where}. Someone who has never seen "
                            "this setting cannot tell a key from an account id without one.")
        out.append({
            "key": key,
            "label": str(item.get("label") or key).strip()[:80],
            "hint": str(item.get("hint") or "").strip()[:240],
            "example": example[:120],
            "secret": bool(item.get("secret", True)),
            "required": bool(item.get("required", True)),
        })
    return out


def read_choices(raw, *, source: str = "") -> list[dict]:
    """The options for a question, each able to carry its own fields.

    Stripe and PayHere do not ask for the same things, so the fields belong to
    the option rather than to the question: choose one and you are asked for
    what that one needs, and never for the other's.
    """
    if not isinstance(raw, list):
        return []
    out = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "").strip()[:40]
        if not ident:
            continue
        option = {"id": ident, "label": str(item.get("label") or ident).strip()[:60],
                  "hint": str(item.get("hint") or "").strip()[:200]}
        if item.get("fields"):
            option["fields"] = read_fields(item["fields"], source=source)
        out.append(option)
    return out


def merge_env(path: Path, values: dict) -> None:
    """Set these names in an env file, leaving every other line alone."""
    try:
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    except OSError:
        existing = ""

    lines = existing.splitlines()
    for key, value in values.items():
        # A value with a newline in it would silently become two settings.
        clean = str(value).replace("\n", " ").replace("\r", " ")
        line = f"{key}={clean}"
        for index, current in enumerate(lines):
            if current.strip().startswith(f"{key}="):
                lines[index] = line
                break
        else:
            lines.append(line)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def questions_for(skills) -> list[dict]:
    """What the selected skills need asked, in the order they were selected."""
    out = []
    for name in skills or []:
        declaration = SKILL_ROOT / str(name) / "setup.json"
        if not declaration.is_file():
            continue
        try:
            body = json.loads(declaration.read_text(encoding="utf-8"))
            purpose = str(body.get("purpose") or "").strip()
            if len(purpose) < 4:
                raise ToolError("a setup declaration needs a purpose")
            question = {
                "skill": str(name),
                "purpose": purpose[:200],
                "question": str(body.get("question") or "").strip()[:200],
                "choices": read_choices(body.get("choices"), source=f"{name}/setup.json"),
                "fields": (read_fields(body["fields"], source=f"{name}/setup.json")
                           if body.get("fields") else []),
            }
        except (OSError, ValueError, ToolError) as error:
            # A broken declaration must not stop a build; it stops its question.
            out.append({"skill": str(name), "error": f"{error}"})
            continue
        if question["choices"] or question["fields"]:
            out.append(question)
    return out


def fields_of(question: dict, choice: str) -> list[dict]:
    """Everything the answer to this question could have filled in."""
    fields = list(question.get("fields") or [])
    for option in question.get("choices") or []:
        if option.get("id") == choice:
            fields += list(option.get("fields") or [])
    return fields


def all_fields(question: dict) -> list[dict]:
    """Every field the question mentions, whichever option is taken."""
    fields = list(question.get("fields") or [])
    for option in question.get("choices") or []:
        fields += list(option.get("fields") or [])
    return fields


def apply_answer(root: Path, question: dict, answer: dict) -> dict:
    """Write what was supplied, record what was not, and say so in one line.

    The example file is always written, whether or not anybody answered: it is
    the list of what this project needs, it is safe to commit, and it is what
    someone reads when the app says a setting is missing.
    """
    root = Path(root)
    answer = answer or {}
    choice = str(answer.get("choice") or "").strip()[:40]
    # An option that needs nothing needs nothing. Falling back to every option's
    # fields when the chosen one had none put Resend's and Twilio's keys into
    # the example file of a project whose author had just said "send nothing".
    # The fallback is for a question nobody answered at all.
    chosen = fields_of(question, choice) if choice else all_fields(question)

    merge_env(root / ".env.example",
              {field["key"]: field["example"] for field in chosen})

    values = answer.get("values") if answer.get("decision") == "save" else None
    wanted = {field["key"]: field for field in chosen}
    saved = ({key: str(value) for key, value in values.items()
              if key in wanted and str(value).strip()}
             if isinstance(values, dict) else {})
    if saved:
        merge_env(root / ".env.local", saved)

    missing = sorted(key for key, field in wanted.items()
                     if key not in saved and field["required"])
    label = next((option["label"] for option in question.get("choices") or []
                  if option["id"] == choice), choice)

    note = question["purpose"]
    if label:
        note += f": {label}"
    if saved:
        note += f". Configured: {', '.join(sorted(saved))} (read from process.env)"
    if missing:
        note += (f". Not supplied: {', '.join(missing)} — build against process.env and fail "
                 f"loudly when one is absent")
    return {"skill": question.get("skill", ""), "choice": choice, "label": label,
            "saved": sorted(saved), "missing": missing, "note": note + "."}
