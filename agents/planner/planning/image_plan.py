"""Plan image slots and translate plan routes to Next.js file paths."""
import hashlib
import re
# Source: feature_prompts.py — imported helper(s) come from this file.
from agents.features.feature_prompts import feature_image_requested
# Source: planning_helpers.py — imported helper(s) come from this file.
from agents.planner.planning.planning_helpers import _dict, _records, _slug, _text

DESIGN_ARCHETYPES = (
    "editorial magazine — type-led asymmetry, a large serif display face, hairline "
    "rules, captioned imagery, one restrained accent",
    "soft minimal — generous whitespace, rounded surfaces, a single muted accent, "
    "quiet type scale, shadow used sparingly",
    "dark technical — near-black canvas, one luminous accent, dense data surfaces, "
    "tabular numerals, precise 1px borders",
    "warm organic — earthy neutrals, humanist type, soft large radii, "
    "photography-first blocks, gentle grain",
    "high-contrast graphic — flat colour blocks, hard borders, oversized labels, "
    "no shadows, deliberate colour clashes",
    "vivid product — saturated duotone, bold geometric sans, layered cards, "
    "confident motion, bright empty states",
    "archival museum — paper-tone canvas, small caps, wide letter-spacing, "
    "framed imagery, ink-black text",
    "utility console — compact rows, monospace accents, muted greys with one "
    "signal colour, table-first composition",
)

# A stable but per-app starting direction, so builds stop looking alike.
def _design_archetype(seed: str) -> str:
    """A stable but per-app starting direction, so builds stop looking alike."""
    # From: agents/planner/planning/planning_helpers.py
    digest = hashlib.sha256(_text(seed).lower().encode("utf-8")).hexdigest()
    return DESIGN_ARCHETYPES[int(digest, 16) % len(DESIGN_ARCHETYPES)]

SHELL_FILES = (
    ("app/layout.jsx", "server",
     "Root shell: import ./globals.css, render <html>/<body>, and wrap "
     "{children} in <Chrome> so every route gets the shared frame"),
    ("components/Chrome.jsx", "client",
     "Owns which routes wear the shared frame: renders Navbar above "
     "{children} and Footer below on every route, except the planned "
     "sign-in and sign-up paths, where it returns {children} alone so the "
     "auth form stands on an empty page"),
    ("components/Navbar.jsx", "client",
     "Global navigation: brand, the planned destinations "
     "with an active state, a working mobile menu, and session-aware "
     "actions when the plan has accounts"),
    ("components/Footer.jsx", "server",
     "Global footer for every route: brand line, planned link groups and "
     "closing row"),
)

IMAGE_STYLE = ("photographic, believable materials, natural commercial lighting, "
               "clean composition, no watermark")
IMAGE_NO_TEXT = "no text, no lettering, no logos"
IMAGE_AD_STYLE = ("premium commercial advertising composition, strong visual hierarchy, "
                  "background scene with clear copy-safe space, polished campaign art")
IMAGE_FIELD_WORDS = ("image", "photo", "picture", "thumbnail", "cover",
                     "banner", "avatar", "poster")
AUTH_COLLECTIONS = {"user", "users", "session", "sessions", "account",
                    "accounts", "verification", "jwks"}
IMAGE_LIMIT = 12
SEED_IMAGE_LIMIT = 4

# The field a seeded row already keeps its picture in, when it has one.
def _image_field(model: dict) -> str:
    """The field a seeded row already keeps its picture in, when it has one."""
    # From: agents/planner/planning/planning_helpers.py
    for field in _records(model.get("fields")):
        # From: agents/planner/planning/planning_helpers.py
        name = _text(field.get("name"), 100)
        if any(word in name.lower() for word in IMAGE_FIELD_WORDS):
            return name
    return ""

# How many seeded rows of this collection deserve their own picture.
def _seed_count(model: dict) -> int:
    """How many seeded rows of this collection deserve their own picture."""
    # From: agents/planner/planning/planning_helpers.py
    digits = re.sub("[^0-9]", "", str(_dict(model.get("seed")).get("count") or ""))
    return min(int(digits or 0), SEED_IMAGE_LIMIT)

# Keep every explicit identity; synthesize only roles still unrepresented.
def _demo_accounts(accounts: list[dict], roles: list[dict]) -> list[dict]:
    """Keep every explicit identity; synthesize only roles still unrepresented."""
    out, taken_roles, taken_emails = [], set(), set()
    for account in accounts:
        # From: agents/planner/planning/planning_helpers.py
        role, email = _text(account["role"]).lower(), account["email"].lower()
        if email and email not in taken_emails:
            if role: taken_roles.add(role)
            taken_emails.add(email)
            out.append(account)
    for role in roles:
        # From: agents/planner/planning/planning_helpers.py
        name = _text(role.get("name"), 80)
        if not name or name.lower() in taken_roles:
            continue
        # From: agents/planner/planning/planning_helpers.py
        email = f"{_slug(name, 'demo')}@demo.local"
        if email in taken_emails:
            continue
        taken_roles.add(name.lower())
        taken_emails.add(email)
        out.append({"email": email, "password": "password123", "role": name,
                    "name": f"Demo {name.title()}"})
    return out

# Name one row of a collection so its picture prompt reads naturally.
def _singular(word: str) -> str:
    """Name one row of a collection so its picture prompt reads naturally."""
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    return word[:-1] if word.endswith("s") else word

# Plan pictures the model listed, plus the usual set when asked in words. The keyword test only ever reads the
# requirement prose. On an SRS build the customer answers the picture question in the interview instead, so the
# prose says nothing about images and the test came back false — throwing away a `## Images` list the model had
# already written and shipping an app with nothing to look at. What the model listed is the answer; the keyword
# only decides whether to add the standard banner/poster/auth/seed set on top.
def _plan_images(plan: dict, design: dict, source_input: str) -> list[dict]:
    """Plan pictures the model listed, plus the usual set when asked in words.

    The keyword test only ever reads the requirement prose. On an SRS build the
    customer answers the picture question in the interview instead, so the prose
    says nothing about images and the test came back false — throwing away a
    `## Images` list the model had already written and shipping an app with
    nothing to look at. What the model listed is the answer; the keyword only
    decides whether to add the standard banner/poster/auth/seed set on top.
    """
    # From: agents/planner/planning/planning_helpers.py
    listed = _records(design.get("images"))
    # From: agents/features/feature_prompts.py
    asked = feature_image_requested(source_input or plan.get("source_input_summary"))
    if not asked and not listed:
        return []
    title = plan["project"]["title"]
    out, taken = [], set()

    # Add one item to this local collection only when it is valid and not already present.
    def add_image_slot(key: str, purpose: str, subject: str, aspect: str) -> None:
        """Add one item to this local collection only when it is valid and not already present."""
        # From: agents/planner/planning/planning_helpers.py
        key = _slug(key, "")
        if not key or key in taken or len(out) >= IMAGE_LIMIT:
            return
        taken.add(key)
        # From: agents/planner/planning/planning_helpers.py
        out.append({"key": key, "purpose": _text(purpose, 300),
                    "prompt": _text(subject, 650), "aspect": aspect})

    # From: agents/planner/planning/planning_helpers.py
    context = _text(plan["project"].get("summary") or plan.get("description"), 180)
    if not asked:
        for extra in listed:
            _add_listed_image(add_image_slot, extra, title)
        return out
    add_image_slot("banner", "Hero banner across the top of the public landing page",
        f'wide premium advertisement for {title}; visually represent {context}; '
        f'background-led campaign scene, include the exact readable brand name "{title}" '
        f'as the main headline, one short relevant promotional line, {IMAGE_AD_STYLE}, {IMAGE_STYLE}',
        "banner")
    add_image_slot("poster", "Promotional poster panel on the public landing page",
        f'promotional retail advertisement for {title}; visually represent {context}; '
        f'include the exact readable brand name "{title}" with one concise offer-style headline, '
        f'product/subject as the visual focus, {IMAGE_AD_STYLE}, {IMAGE_STYLE}', "poster")
    # From: agents/planner/planning/planning_helpers.py
    access = _dict(plan.get("roles_and_access"))
    if access.get("authentication_required"):
        add_image_slot("login", "Backdrop beside the /sign-in form",
            f'calm, premium sign-in background for {title}; visually match {context}; '
            f'leave quiet negative space for the form UI, {IMAGE_STYLE}, {IMAGE_NO_TEXT}', "portrait")
        # From: agents/planner/planning/planning_helpers.py
        if _text(access.get("signup")).lower() == "open":
            add_image_slot("signup", "Backdrop beside the /sign-up form",
                f'welcoming sign-up background for {title}; visually match {context}; '
                f'warm aspirational scene with quiet negative space for the form UI, '
                f'{IMAGE_STYLE}, {IMAGE_NO_TEXT}', "portrait")

    # From: agents/planner/planning/planning_helpers.py
    models = [model for model in _records(plan.get("data_model"))
              if _text(model.get("collection")).lower() not in AUTH_COLLECTIONS
              and _seed_count(model)]
    seeded = [(model, _image_field(model)) for model in models]
    seeded = [(model, field) for model, field in seeded if field]
    if models and not seeded:
        models[0]["fields"].append({
            "name": "image", "type": "string", "required": False,
            "rules": "Path of this row's generated picture under /generated"})
        seeded = [(models[0], "image")]
    for model, field in seeded:
        # From: agents/planner/planning/planning_helpers.py
        collection = _text(model.get("collection"), 100)
        one = _singular(collection)
        for number in range(1, _seed_count(model) + 1):
            # From: agents/planner/planning/planning_helpers.py
            key = _slug(collection + "-" + str(number), "")
            # From: agents/planner/planning/planning_helpers.py
            add_image_slot(key, "Seeded `" + collection + "` row " + str(number) +
                ": set its `" + field + "` to /generated/" + key + ".png",
                one + " for " + title + ", " + _text(model.get("purpose"), 100) +
                f", authentic domain-specific subject, premium e-commerce/catalog photography, "
                f"single clear focal subject, uncluttered background, {IMAGE_STYLE}, {IMAGE_NO_TEXT}",
                "square")

    for extra in listed:
        _add_listed_image(add_image_slot, extra, title)
    return out


# Queue one picture exactly as the model described it.
def _add_listed_image(add_image_slot, extra: dict, title: str) -> None:
    """Queue one picture exactly as the model described it."""
    # From: agents/planner/planning/planning_helpers.py
    purpose = _text(extra.get("purpose"), 300)
    # From: agents/planner/planning/planning_helpers.py
    prompt = _text(extra.get("prompt"), 420) or purpose
    # From: agents/planner/planning/planning_helpers.py
    add_image_slot(extra.get("key"), purpose,
        f"{prompt}; visually consistent with {title} and its real domain; "
        f"{IMAGE_STYLE}, {IMAGE_NO_TEXT}", _text(extra.get("aspect"), 20) or "wide")

# Converts a route or plan path into the matching Next.js runtime path.
def _runtime_path(file_path: str) -> str:
    """Convert a route or plan path into the matching Next.js runtime path."""
    # From: agents/planner/planning/planning_helpers.py
    rel = _text(file_path).replace("\\", "/")
    if not rel.startswith("app/"):
        return ""
    parts = rel.split("/")
    if not parts[-1].startswith(("page.", "route.")):
        return ""
    segments = [part for part in parts[1:-1]
                if not (part.startswith("(") and part.endswith(")"))]
    return "/" + "/".join(segments) if segments else "/"

# Returns the Next.js App Router source filename for a route.
def _app_file(route_path: str, leaf: str = "page.jsx") -> str:
    """Return the Next.js App Router source filename for a route."""
    # From: agents/planner/planning/planning_helpers.py
    route = _text(route_path).split("?", 1)[0].split("#", 1)[0].strip()
    if not route.startswith("/"):
        return ""
    segments = [part for part in route.strip("/").split("/") if part]
    if any(part in {".", ".."} for part in segments):
        return ""
    return "app/" + ("/".join(segments) + "/" if segments else "") + leaf

