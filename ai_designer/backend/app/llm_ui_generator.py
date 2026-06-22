"""LLM-driven page generator for public landing pages.

Generates build-safe React/Next.js JSX guided by design_blueprint.json.
Template pages are written first as a safe baseline; this module overwrites
them on validation success. On LLM failure or validation error the template
stays and the build proceeds normally — no breakage.

Scope: PUBLIC marketing/landing pages only.
CRUD/admin/app pages remain template-based.
"""
import os
import re
from typing import Optional

# ── Import allowlist ──────────────────────────────────────────────────────────

_ALLOWED_PREFIXES = (
    "react",
    "next/link",
    "next/image",
    "next/navigation",
    "lucide-react",
    "@/components/ui/",
    "@/lib/",
)

# ── System contract ───────────────────────────────────────────────────────────

_CONTRACT = """\
You are generating a build-safe React/Next.js JSX file for a production web app.

STRICT RULES — violating any rule makes the output unusable:
1. Output ONLY the file content — no markdown, no explanation, no triple backticks.
2. First line must be: 'use client';
3. Imports MUST come from ONLY these sources:
   react | next/link | next/image | next/navigation | lucide-react
   @/components/ui/* | @/lib/site | @/lib/api | @/lib/utils | @/lib/access
4. Tailwind CSS classes ONLY — no inline style attributes, no CSS modules.
5. All JSX tags must be closed. Adjacent elements need a Fragment wrapper.
6. Use className= (not class=). Use htmlFor= (not for=).
7. All images must use <img> with onError fallback or next/image.
8. Export ONE default function. No named exports.
9. No useEffect, no fetch, no async — use static placeholder data from SRS.
10. Every string containing domain copy must match the SRS domain — no lorem ipsum.
11. Make the page visually unique per the design blueprint colours and style.
"""

_PAGE_TEMPLATE = """\
Generate a {page_type} page for {app_name}.

Route: {route}
Page name: {page_name}
Sections to render (in order): {sections}
Domain keywords from SRS: {keywords}

Design blueprint:
  mood: {mood}
  feel: {feel}
  layout: {layout}
  hero: {hero}
  card style: {card}
  button classes: {btn}
  card classes: {card_cls}
  hero classes: {hero_cls}
  nav classes: {nav_cls}
  primary color: {color_primary}
  accent color: {color_accent}
  background style: {bg_style}
  page visual notes: {page_notes}
  section order: {section_order}

STRUCTURAL LAYOUT VARIANT: {layout_variant}
{layout_directive}

LISTING VARIANT: {listing_variant}
{listing_directive}

FILTER PLACEMENT: {filter_placement}
{filter_directive}

Allowed roles for this page: {roles}

Produce a beautiful, production-ready {page_type} page that:
- Renders ALL listed sections in the specified order
- Uses the blueprint colours and style classes above
- STRICTLY follows the structural layout variant above — do NOT use a centered heading + plain card grid if the variant says otherwise
- Contains real domain copy from the SRS keywords (no lorem ipsum)
- Has no imports from unallowed packages
"""

# ── Layout directives — explicit structural instructions per variant ───────────

_LAYOUT_DIRECTIVES = {
    "booking-catalog": "MUST render hero with date-picker inputs (check-in/check-out/guests) at the bottom of a full-bleed background image. Listings MUST use horizontal cards with large left-side image, price-per-night badge, and Book Now CTA on the right.",
    "schedule-catalog": "MUST render a class/event schedule grid with TIME shown prominently on each card, instructor name, duration, and intensity badge. Do NOT use a plain image grid — this is a timetable layout.",
    "product-catalog": "MUST render a featured product showcase with one large featured item taking 60% width, surrounded by a smaller product grid. Include price, rating, and Add to Cart CTA.",
    "editorial-split": "MUST use alternating LEFT-RIGHT section layout — odd sections: image left + text right; even sections: text left + image right. No centered headings above a card grid.",
    "centered-catalog": "Use a centered text layout with a prominent search/filter bar below the headline. Cards arranged in a clean responsive grid with clear category labels.",
    "full-bleed-hero": "MUST render a full-viewport-height hero with a background image, strong overlay, and text positioned at vertical center-left. No floating booking widget.",
    "magazine-sections": "Use editorial-style wide sections: alternating between full-width feature imagery and text columns. Think newspaper / editorial magazine layout, not a simple card grid.",
    "dashboard-landing": "Show a hero with a dashboard-preview mockup (stats cards, mini chart placeholder) on the right side. Left side: headline, subtext, CTA. Think SaaS landing page.",
}

_LISTING_DIRECTIVES = {
    "horizontal-media-cards": "Each listing card MUST be a horizontal flex container: left 30% wide image, right 70% content with title, description, price, and CTA button. NOT a vertical card with image on top.",
    "schedule-grid": "Each card shows CLASS NAME, TIME in large bold text, TRAINER NAME, DURATION, and an INTENSITY badge. Cards have left-border accent color. NOT an image-top card.",
    "large-featured-grid": "First item is a large featured card spanning full width with a prominent image. Below it: 3-column smaller cards. NOT uniform-size grid.",
    "compact-catalog": "Compact table-like list: each row has name, category tag, brief description, and a View button. Dense, text-focused, NOT card-based.",
    "table-catalog": "Render as a proper HTML table or table-style flex list with sortable headers: Name, Category, Price, Status, Action.",
    "standard-card-grid": "3-column responsive card grid. Each card: top image, title, short description, CTA link.",
}

_FILTER_DIRECTIVES = {
    "top-search-bar": "MUST render a full-width search bar ABOVE the listings, with Location, Date, and Guest count inputs side by side, and a Search button. NOT chip filters.",
    "left-sidebar": "MUST render a 2-column layout: left sidebar (250px) with checkbox filter groups, right main content area with results grid.",
    "inline-chips": "Render a row of pill/chip buttons for category filtering. Chips are small (px-4 py-1.5), rounded-full, highlighted on active.",
    "compact-toolbar": "A compact horizontal toolbar with dropdowns for Sort By, Category, and Price Range filters. Positioned directly above the results grid.",
    "dark-panel": "A dark-background filter panel (bg-slate-800 or similar) with white text labels and toggle/checkbox controls.",
}


def _get_layout_directive(layout_variant: str, listing_variant: str, filter_placement: str) -> tuple[str, str, str]:
    """Return (layout_dir, listing_dir, filter_dir) for the given variants."""
    lv = layout_variant.lower().replace("_", "-") if layout_variant else ""
    li = listing_variant.lower().replace("_", "-") if listing_variant else ""
    fi = filter_placement.lower().replace("_", "-") if filter_placement else ""

    layout_dir = _LAYOUT_DIRECTIVES.get(lv, "Use a well-structured layout appropriate for this domain.")
    listing_dir = _LISTING_DIRECTIVES.get(li, "Render a responsive card grid with domain-appropriate content.")
    filter_dir = _FILTER_DIRECTIVES.get(fi, "Add simple inline category chip filters above the content.")

    return layout_dir, listing_dir, filter_dir


# ── Validation ────────────────────────────────────────────────────────────────

def _validate(code: str) -> tuple[bool, str]:
    """Return (ok, reason). reason is '' when ok."""
    if not code or len(code.strip()) < 120:
        return False, "Output too short"

    stripped = code.strip()

    if "```" in stripped:
        return False, "Contains markdown fences"

    if "export default" not in stripped:
        return False, "Missing export default"

    for pkg in re.findall(r"^import\s+.*?from\s+['\"](.+?)['\"]", stripped, re.MULTILINE):
        if not any(pkg.startswith(p) for p in _ALLOWED_PREFIXES):
            return False, f"Disallowed import: {pkg}"

    if re.search(r"\bclass=", stripped):
        return False, "Use className= not class="

    return True, ""


def _strip_fences(code: str) -> str:
    """Remove markdown code fences and leading non-code preamble from LLM output."""
    code = code.strip()
    code = re.sub(r"^```(?:jsx?|tsx?|javascript|typescript)?\s*\n?", "", code, flags=re.IGNORECASE)
    code = re.sub(r"\n?```\s*$", "", code)

    # Find the first line that looks like actual code
    lines = code.split("\n")
    start = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if (s.startswith("'use client'") or s.startswith('"use client"')
                or s.startswith("import ") or s.startswith("//")
                or s.startswith("export")):
            start = i
            break
    return "\n".join(lines[start:]).strip()


def _domain_keywords(srs_data: dict, page: dict) -> list[str]:
    """Extract domain-relevant words from SRS for this page."""
    keywords: list[str] = []
    doc = (srs_data.get("srs_document") or srs_data) if isinstance(srs_data, dict) else {}

    cat = doc.get("system_category", "")
    if cat:
        keywords.append(cat)

    summary = str(doc.get("app_summary") or "")
    keywords.extend(w for w in re.findall(r"\b[A-Za-z]{4,}\b", summary)[:12])

    for s in page.get("sections", [])[:5]:
        keywords.extend(re.findall(r"\b[A-Za-z]{4,}\b", str(s))[:3])

    stop = {"with", "that", "this", "have", "from", "will", "been", "page",
            "section", "feature", "about", "their", "would", "should"}
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        kl = kw.lower()
        if kl not in seen and kl not in stop:
            seen.add(kl)
            result.append(kw)
    return result[:15]


# ── Public API ────────────────────────────────────────────────────────────────

def generate_page(
    page: dict,
    srs_data: dict,
    blueprint: dict,
    app_name: str,
    roles: list,
    page_type: str = "home",
) -> Optional[str]:
    """Generate JSX for one public page.

    Returns clean JSX string on success, None on failure.
    The caller keeps the template baseline and overwrites only on success.
    """
    from app.agents import get_llm, ensure_ollama
    from langchain_core.prompts import ChatPromptTemplate

    if not ensure_ollama():
        return None

    tc = blueprint.get("tailwind_classes", {})
    palette = blueprint.get("color_palette", {})
    sections = page.get("sections", [])
    keywords = _domain_keywords(srs_data, page)

    lv = blueprint.get("page_layout_variant", "")
    li = blueprint.get("listing_variant", "")
    fp = blueprint.get("filter_placement", "")
    layout_dir, listing_dir, filter_dir = _get_layout_directive(lv, li, fp)

    user_prompt = _PAGE_TEMPLATE.format(
        page_type=page_type,
        app_name=app_name,
        route=page.get("route", "/"),
        page_name=page.get("page_name", page.get("name", "Page")),
        sections=", ".join(str(s) for s in sections[:12]) or "hero, features, cta",
        keywords=", ".join(keywords),
        mood=blueprint.get("domain_mood", "professional"),
        feel=blueprint.get("target_feel", "Modern and efficient"),
        layout=blueprint.get("layout_style", "split-hero"),
        hero=blueprint.get("hero_composition", "split-image-text"),
        card=blueprint.get("card_style", "elevated-shadow"),
        btn=tc.get("primary_button", "bg-blue-600 text-white px-6 py-3 rounded-lg font-semibold"),
        card_cls=tc.get("card", "bg-white rounded-xl border shadow-sm p-6"),
        hero_cls=tc.get("hero_section", "bg-slate-900 text-white py-20 px-6"),
        nav_cls=tc.get("nav", "bg-white border-b px-6 py-4"),
        color_primary=palette.get("primary", "#3b82f6"),
        color_accent=palette.get("accent", "#06b6d4"),
        bg_style=blueprint.get("background_style", "flat-color"),
        page_notes=(blueprint.get("page_designs") or {}).get(page_type, ""),
        section_order=", ".join(blueprint.get("section_order", ["hero", "features", "cta"])),
        layout_variant=lv or "centered-catalog",
        layout_directive=layout_dir,
        listing_variant=li or "standard-card-grid",
        listing_directive=listing_dir,
        filter_placement=fp or "inline-chips",
        filter_directive=filter_dir,
        roles=", ".join(str(r) for r in roles[:5]) or "All",
    )

    try:
        chain = ChatPromptTemplate.from_messages([
            ("system", _CONTRACT),
            ("user", "{prompt}"),
        ]) | get_llm(temperature=0.65, num_predict=3500, json_mode=False)

        result = chain.invoke({"prompt": user_prompt})
        raw = result.content if hasattr(result, "content") else str(result)
        code = _strip_fences(raw)

        ok, reason = _validate(code)
        if not ok:
            return None

        return code
    except Exception:
        return None


def augment_public_pages(
    output_dir: str,
    srs_data: dict,
    blueprint: dict,
    app_name: str,
    roles: list,
    logs: list,
    fast: bool = False,
) -> int:
    """Augment up to 3 public landing pages with LLM-generated JSX.

    Template files are written before this call; we only overwrite on
    successful validation. Returns number of pages successfully augmented.
    """
    if fast:
        return 0

    doc = (srs_data.get("srs_document") or srs_data) if isinstance(srs_data, dict) else {}
    pub_pages = (doc.get("public_landing_website") or {}).get("pages") or []

    augmented = 0

    # Augment first 3 non-home public pages (home is the most important one)
    home_done = False
    for page in pub_pages[:5]:
        route = page.get("route", "")
        page_name = page.get("page_name", "")
        is_home = route in ("/", "") or "home" in page_name.lower()
        page_type = "home" if is_home else "listing"

        if is_home and home_done:
            continue
        if is_home:
            home_done = True

        # Locate the file the template wrote
        from app.srs_public_page_generator import _slug_for_page
        slug = _slug_for_page(page_name, route)
        dest = os.path.join(output_dir, "src", "app", "(marketing)", slug, "page.jsx")
        if not os.path.exists(dest):
            continue

        code = generate_page(page, srs_data, blueprint, app_name, roles, page_type)
        if code:
            try:
                with open(dest, "w", encoding="utf-8") as f:
                    f.write(code)
                augmented += 1
                logs.append(
                    f"--- [AGENT: LLM UI] generated {page_type} page "
                    f"'{page_name}' ({slug}) with blueprint style ---"
                )
            except Exception as e:
                logs.append(f"--- [AGENT: LLM UI] write failed for {slug}: {str(e)[:60]} ---")
        else:
            logs.append(f"--- [AGENT: LLM UI] {slug} — LLM output invalid; template kept ---")

        if augmented >= 3:
            break

    return augmented
