"""InterviewAgent — the per-question LLM call.

Before every question the model is given the raw idea, all answers so far, and
the app-type pack — so question N is genuinely conditioned on answers 1..N-1
rather than read off a fixed script.

The model only supplies *wording and options*. The queue, the conditions and the
answer storage are deterministic (knowledge/topics.py), so a bad response costs
a clumsy question, never a broken interview.
"""
from __future__ import annotations

import json
import logging
import re

from ..knowledge import app_types as catalog
from ..knowledge import topics
from ..llm import LLMRepairFailed, LLMUnavailable, get_llm
from ..services.events import bus
from .customer_context import customer_context

log = logging.getLogger("agentforge.interview")

SYSTEM = """You are Agent 1 in an app-building studio, gathering requirements \
from a NON-TECHNICAL customer.

Ask ONE short question at a time, in plain language. No jargon: say "records" \
not "entities", "log in" not "authentication", "pages" not "routes".

Return ONLY a JSON object:
{
  "question": "the question, one sentence",
  "options":  [{"label": "short answer", "value": "machine_value", "hint": "optional 3-5 words"}],
  "recommended": "machine_value of the best default, or null",
  "known": ["the answer the customer's own words already give you"],
  "known_quote": "the words of theirs that say so, quoted back"
}

Rules:
- 3 to 5 options. Concrete and specific to THIS customer's idea, never generic.
- "value" is a lowercase machine value; "label" is what the customer reads.
- NEVER skip a question because they already answered it. Ask it back as a \
confirmation instead: put every value their own words already give you in \
"known", quote those words in "known_quote", and word the question so they are \
confirming rather than starting over — "You mentioned X — shall I take it that …?"
- On a question with options, every "known" entry must be one of the option \
values you just listed. On a typed question ("Answer style: text" or "number") \
there are no options and no machine values: write the answer the way the \
customer would type it into the box — "Pubudu Tire Shop", not "pubudu_tire_shop".
- Leave "known" empty and "known_quote" blank when they have not touched this yet.
- For yes/no questions use exactly two options with values true and false.
- NEVER ask about the LOOK or the LAYOUT — no navbar, no sidebar, no menu \
placement, no colours, no theme, no fonts, no light-or-dark. The app type \
fixes the chrome and the palette, so asking hands the customer a choice that \
is not theirs to make, and a landing page that answers "yes, a sidebar" comes \
out specified as an admin app. If the topic you are given is about something \
else, do not drift into appearance while wording it."""


ANSWER_TYPE = {
    "single": "single_choice",
    "multi": "multi_choice",
    "yes_no": "yes_no",
    "number": "number",
    "text": "free_text",
    "upload": "single_choice",
}


ATTACHMENT_STORE_LIMIT = 4000
ATTACHMENT_DIGEST_LIMIT = 700


# "yes" is not an app name.
#
# The model is told above to ask a value back rather than ask for it twice, and
# to carry the candidate in `known` — which reaches the question as `prefill`.
# On a chip question that prefill is a ticked option, so a bare yes cannot
# happen. On a TYPED question there is nothing to tick: the box is empty, the
# question reads "You mentioned 'pubudu tireshop' — is that the exact name you
# want shown at the top of your app?", and the honest reply is "yes".
#
# It was stored verbatim as the answer. Measured on three real interviews, all
# three named the app "yes" — `app_summary.app_name`, `project_name`, the plan
# heading, `package.json`, the browser tab, the project folder
# (`production-ready/yes`, then `yes-2`) and the Mongo database
# (`agentforge_yes`). Nothing downstream could tell: "yes" is a perfectly valid
# string, so every layer passed it on.
#
# A bare yes on a typed question therefore means the candidate it was asked
# about, and a bare no means "not that" — which is not a name either, so it is
# stored as nothing and the later fallbacks decide.
AFFIRMATIONS = {
    "y", "ya", "yah", "yeah", "yep", "yes", "yup", "yes please", "yes thanks",
    "ok", "okay", "oky", "k", "sure", "fine", "good", "great", "perfect",
    "correct", "right", "thats right", "that is right", "exactly", "exact",
    "true", "confirm", "confirmed", "agreed", "agree", "keep it", "use that",
    "thats it", "that is it", "same", "as it is",
}
NEGATIONS = {
    "n", "no", "nope", "nah", "no thanks", "not", "not really", "not exactly",
    "not that", "wrong", "incorrect", "negative", "false", "change it",
}

_BARE_RE = re.compile(r"[^a-z0-9 ]+")


def _bare_word(text) -> str:
    """An answer reduced to plain lowercase words, for matching against the sets."""
    return _BARE_RE.sub("", str(text or "").lower()).strip()


def _confirmable(session: dict, key: str, topic_key: str) -> str:
    """
    The candidate the question on screen quoted back, or "".

    Only for typed topics: elsewhere the prefill is an option and the customer
    ticks it. `session["current"]` is the question this answer is answering —
    the orchestrator records before it asks the next one — and the key check
    keeps a stale `current` from lending its prefill to a different question.
    """
    topic = topics.TOPICS_BY_KEY.get(topic_key)
    if not topic or topic.kind not in ("text", "number"):
        return ""
    current = session.get("current") or {}
    if str(current.get("key") or current.get("id") or "") != key:
        return ""
    prefill = current.get("prefill") or []
    return str(prefill[0]).strip() if prefill else ""


def _attachment_entries(attachments) -> list[dict]:
    """Uploaded sources, trimmed to what an answer needs to carry."""
    out = []
    for src in attachments or []:
        if not isinstance(src, dict):
            continue
        text = str(src.get("text") or "").strip()
        out.append({
            "id": str(src.get("id") or ""),
            "filename": str(src.get("filename") or "attachment"),
            "mode": str(src.get("mode") or ""),
            "text": text[:ATTACHMENT_STORE_LIMIT],
        })
    return out


def attachment_texts(entry: dict) -> list[str]:
    """`filename: extracted text` for every attachment on one answer."""
    return [f"{a['filename']}: {a['text']}"
            for a in (entry.get("attachments") or []) if a.get("text")]


def _answers_digest(session: dict) -> str:
    """Compact transcript of what we already know.

    The chips they ticked, the words they typed *and* whatever they attached.
    Showing only the stored value loses the typed half on every mixed answer —
    and that half is the part they bothered to write out.
    """
    lines = []
    for key, entry in (session.get("answers") or {}).items():
        val = entry.get("value")
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        line = f"- {key}: {val}"
        typed = str(entry.get("custom_text") or entry.get("text") or "").strip()
        if typed and typed not in str(val):
            line += f"  (they typed: {typed})"
        lines.append(line)
        for att in attachment_texts(entry):
            lines.append(f"    (they attached {att[:ATTACHMENT_DIGEST_LIMIT]})")
    return "\n".join(lines) or "(nothing yet)"


def _suggested_options(topic: topics.Topic, item: dict, session: dict) -> list:
    """The topic's own deterministic options, if it has any."""
    if not topic.options_from:
        return []
    try:
        return topic.options_from(session, item) or []
    except Exception:  # noqa: BLE001 - a template gap must not break the interview
        log.warning("options_from failed for %s", topic.key, exc_info=True)
        return []


def _topic_brief(topic: topics.Topic, item: dict, session: dict) -> str:
    subject = item.get("subject")
    lines = [
        f"Topic: {topic.key}",
        f"What we need: {topic.intent}",
        f"Answer style: {topic.kind}",
    ]
    if subject:
        lines.append(f"This question is specifically about: {subject}")
    suggested = _suggested_options(topic, item, session)
    if suggested:
        labels = [str(o.get("label", o)) for o in suggested][:12]
        lines.append(f"Reasonable options to draw from: {', '.join(labels)}")
    return "\n".join(lines)


async def ask(session: dict) -> dict | None:
    """Build the next question. Returns None when the backbone is exhausted."""
    queue = topics.build_queue(session)
    if not queue:
        return None

    item = queue[0]
    topic = topics.TOPICS_BY_KEY[item["topic"]]
    total = topics.total_estimate(session)
    index = len([k for k in session.get("asked", [])
                 if not topics.is_clarification(k)]) + 1
    pid = session.get("project_id", "")

    if topic.key == "app_type":
        return _question(item, topic, index, total,
                         question="What kind of application is this?",
                         options=(_suggested_options(topic, item, session)
                                  or catalog.app_type_options()),
                         recommended=session.get("guessed_app_type"))

    if topic.fixed:
        return _question(item, topic, index, total,
                         question=topic.fixed,
                         options=list(topic.fallback_options))

    pack = session.get("pack") or {}
    user_msg = f"""{customer_context(session=session)}

Detected app type: {pack.get('app_label', 'unknown')} ({pack.get('archetype', '')})
Detected business domain: {pack.get('domain_label', 'general')}

What the customer has told us so far:
{_answers_digest(session)}

{_topic_brief(topic, item, session)}

Ask the next question now. Every option you offer must read as though you had
their idea in front of you — name their trade, their goods, their people. If
their own words above already answer this, ask it back for confirmation and
fill in "known" — never make them tell you something twice."""

    data: dict | None = None
    try:
        data = await get_llm().complete_json(
            system=SYSTEM, user=user_msg,
            label=f"interview:{topic.key}",
            trace_sink=(lambda p: bus.trace(pid, p)) if pid else None,
        )
    except (LLMUnavailable, LLMRepairFailed) as exc:
        log.info("interview: LLM unusable for %s (%s)", topic.key, exc)
    except Exception:  # noqa: BLE001
        log.warning("interview: LLM error for %s", topic.key, exc_info=True)

    suggested = _suggested_options(topic, item, session)
    default_options = suggested or topic.fallback_options

    if not isinstance(data, dict) or not data.get("question"):
        return _question(item, topic, index, total,
                         question=_fallback_question(topic, item),
                         options=default_options)

    if topic.options_locked:
        options = default_options
    else:
        options = [o for o in (data.get("options") or [])
                   if isinstance(o, dict) and o.get("label")]
        if not options and topic.kind in ("single", "multi", "yes_no"):
            options = default_options

    return _question(
        item, topic, index, total,
        question=str(data["question"]),
        options=options,
        recommended=data.get("recommended"),
        prefill=_known_values(data.get("known"), options, topic),
        prefill_note=str(data.get("known_quote") or "").strip()[:240],
    )


def _known_values(known, options: list, topic: topics.Topic) -> list:
    """The answer their own words already gave, ready to be confirmed.

    A prefill the customer cannot trace back to something they said is worse
    than none — it ticks a box they never ticked. So on a chip question a value
    only survives if it matches an option actually on screen; on a typed one it
    has to be something that could plausibly go in the box.
    """
    if not isinstance(known, list) or not known:
        return []

    if topic.kind in ("text", "number"):
        first = str(known[0]).strip()[:200]
        if topic.kind == "number":
            try:
                float(first)
            except ValueError:
                return []
        elif "_" in first and " " not in first:

            first = first.replace("_", " ")
        return [first] if first else []

    allowed = {str(o.get("value")): o.get("value") for o in options
               if isinstance(o, dict)}
    out: list = []
    for value in known:
        real = allowed.get(str(value))
        if real is not None and real not in out:
            out.append(real)
    return out if topic.kind == "multi" else out[:1]


def _question(item, topic, index, total, question, options,
              recommended=None, prefill=None, prefill_note=""):
    """One question, in both shapes at once.

    The first block is the `Question` contract the rest of the API already
    speaks (coverage scoring, the SRS answer digest); the second is what the
    interview UI needs to render chips, recommendations and repeat subjects.
    """
    options = options or []
    return {

        "id": item["key"],
        "question": question,
        "why_needed": topic.intent[:200],
        "answer_type": ANSWER_TYPE.get(topic.kind, "single_choice"),
        "suggested_options": [str(o.get("label", o)) for o in options],
        "maps_to_srs_fields": list(topic.srs_fields),
        "coverage_areas": list(topic.coverage),
        "required": not topic.optional,

        "key": item["key"],
        "topic": topic.key,
        "subject": item.get("subject"),
        "kind": topic.kind,
        "index": index,
        "total": max(total, index),
        "options": options,
        "recommended": recommended,
        "placeholder": topic.placeholder,

        "optional": topic.optional,
        "multiline": topic.multiline,

        "prefill": prefill or [],
        "prefill_note": prefill_note,
    }


def _fallback_question(topic: topics.Topic, item: dict) -> str:
    subject = item.get("subject")
    base = {
        "app_type": "What kind of application is this?",
        "app_name": "What should we call it?",
        "logo": "Do you have a logo?",
        "auth_roles": "What kinds of user will there be?",
        "auth_identity": "What should people sign in with?",
        "role_functions": (f"What should a {subject} be able to do?" if subject
                           else "What should this role do?"),
        "page_functions": "What should each page let visitors do?",
        "data_tables": "What information should the system store?",
        "table_entities": (f"What details do you keep for each {subject}?" if subject
                           else "What details do you keep?"),
        "pos_payments": "How can a customer pay at the counter?",
        "pos_receipt": "What happens at the end of a sale?",
        "pos_stock_rules": "How should stock behave as things are sold?",
        "saas_plans": "What subscription plans will there be?",
        "saas_signup": "Can anyone sign up, or does the team invite people?",
        "saas_workspace": "Do people work alone, or share a workspace?",
        "store_checkout": "Must a shopper have an account to buy?",
        "store_payments": "How does a shopper pay?",
        "store_fulfilment": "How does an order reach the customer?",
        "dash_metrics": "Which numbers should be on the front page?",
        "dash_exports": "How should the data leave the tool?",
        "blog_workflow": "What steps does a post go through before readers see it?",
        "blog_organisation": "How should readers find their way around the posts?",
        "blog_engagement": "What can readers do besides read?",

        "sections": "What should the page show, from top to bottom?",
        "offerings": "What do you offer?",
        "cta": "What do you most want a visitor to do?",
        "lead_capture": "Do you want to collect enquiries you can read later?",
        "lead_fields": "What should the enquiry form ask for?",
        "contact_channels": "How else can people reach you?",
        "social_proof": "What helps people trust you?",

        "tool_job": "In one sentence, what does this tool do?",
        "tool_inputs": "What does someone type in?",
        "tool_outputs": "What does it give back?",
        "save_history": "Should past results be saved?",
        "images": "Should we create artwork for it?",
        "image_kinds": "What artwork do you need?",
        "theme_type": "Light or dark?",
        "color_palette": "Which colours suit your brand?",
        "responsive_pwa": "Which devices should it work on?",
        "extra_notes": "Anything else the site should show, or anything we missed?",
    }
    return base.get(topic.key, f"Tell us about {topic.label.lower()}.")


def record(session: dict, key: str, value=None, text: str = "", images=None,
           selected=None, custom: str = "", attachments=None) -> dict:
    """Store an answer and re-derive anything that depends on it.

    Two shapes are kept side by side. `value` is what every caller reads through
    `topics.ans`. `selected_values` / `custom_text` keep the two halves apart,
    because "which of these, plus this thing I typed" is a distinction the
    merged list destroys — and the typed half is the part the customer cared
    enough to write out.

    `attachments` is the third shape: a customer who finds it easier to send a
    photo of their price list, or say it out loud, is still answering. The
    extracted text is kept on the answer so it reads back exactly like typing.
    """
    topic_key = key.split(":", 1)[0]

    if selected is None and custom == "":

        selected = value if isinstance(value, list) else (
            [] if value is None else [value])
        custom = text or ""

    entry = {
        "topic": topic_key,
        "value": value if value is not None else text,
        "text": text,
        "images": images or [],
        "question_id": key,
        "selected_values": list(selected or []),
        "custom_text": str(custom or "").strip(),
        "attachments": _attachment_entries(attachments),
        "details": {},
    }

    candidate = _confirmable(session, key, topic_key)
    if candidate and not isinstance(entry["value"], (list, dict)):
        said = _bare_word(entry["value"])
        if said in AFFIRMATIONS:
            # What they typed is kept in `details` — it is the record of what
            # happened — but it must not stay in `value`, `text` or
            # `custom_text`, because those three are what `_answers_digest`
            # and `flat_answers` hand to the SRS generator. Leaving "yes"
            # anywhere in that digest invites the same name back.
            entry["details"]["confirmed"] = said
            entry["value"] = candidate
            entry["text"] = candidate
            entry["custom_text"] = candidate
            entry["selected_values"] = [candidate]
        elif said in NEGATIONS:
            entry["details"]["declined"] = said
            entry["value"] = ""
            entry["text"] = ""
            entry["custom_text"] = ""
            entry["selected_values"] = []

    picked = [s for s in entry["selected_values"] if str(s).strip()]
    if (entry["attachments"] and not picked
            and not str(entry["value"] or "").strip()):
        read = " ".join(a["text"] for a in entry["attachments"] if a["text"]).strip()
        names = ", ".join(a["filename"] for a in entry["attachments"])
        summary = read[:ATTACHMENT_STORE_LIMIT] or f"(attached {names}; no text could be read)"
        kind = getattr(topics.TOPICS_BY_KEY.get(topic_key), "kind", "text")
        entry["value"] = [summary] if kind == "multi" else summary

    session.setdefault("answers", {})[key] = entry
    if key not in session.setdefault("asked", []):
        session["asked"].append(key)

    if topic_key == "app_type":
        chosen = entry["value"]
        if isinstance(chosen, list):
            chosen = chosen[0] if chosen else catalog.DEFAULT_APP_TYPE
        chosen = str(chosen)
        if chosen not in catalog.APP_TYPES:
            # Typed rather than picked, so it has to be matched to a category.
            #
            # The confidence is what decides, and it used to be thrown away:
            # `guess_app_type` answers ("other", 0.0) when no keyword matched
            # at all, and taking the first half of that pair recorded a real
            # category for an answer nothing in it was recognised. Measured on
            # a labelled set of 49 ordinary ideas, 35 of them matched nothing
            # and every one was filed as "saas".
            #
            # Below the floor the honest answer is "other". It is also the only
            # safe one: this single answer sets `auth_policy` for the whole
            # application, and three categories switch the login off.
            guess, confidence = catalog.guess_app_type(
                f"{chosen} {session.get('raw_idea', '')}")
            chosen = guess if confidence >= catalog.GUESS_FLOOR else "other"
        session["app_type"] = chosen
        session["pack"] = catalog.build_pack(chosen, session.get("raw_idea", ""))
        session["answers"][key]["value"] = chosen

    return session


def flat_answers(session: dict) -> list[dict]:
    """The keyed interview answers as the flat list the rest of the API reads.

    `offline_srs._answer_texts`, `srs_generator._answers_digest` and
    `coverage_auditor.compute_coverage` all speak this shape, so rebuilding it
    after every answer is what keeps the generation half untouched.
    """
    out: list[dict] = []
    for key, entry in (session.get("answers") or {}).items():
        raw = entry.get("custom_text") or entry.get("text") or None

        attached = " ".join(attachment_texts(entry)).strip()
        if attached:
            raw = f"{raw} {attached}".strip() if raw else attached
        out.append({
            "question_id": key,
            "value": entry.get("value"),
            "raw_text": raw,
        })
    return out
