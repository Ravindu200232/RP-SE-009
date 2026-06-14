"""PHASE 1 - Deep Research Agent (internet-aware, runs BEFORE generation).

Local LLMs can't browse, so the pipeline is:
  1. ddgs (DuckDuckGo) web search for real sites in the requested domain,
  2. fetch + strip the top pages (their menus, headings, feature wording),
  3. Gemma 4 12B (local) synthesizes a Domain Blueprint JSON.

The blueprint drives EVERYTHING downstream so two different prompts produce
genuinely different apps (not Home/Features/About/Contact every time):
  - is_utility_tool      -> single-screen tools skip the marketing site,
  - marketing_pages      -> DOMAIN-specific public pages (school: Courses, Admissions),
  - app_modules/entities -> the authenticated workspace sections + per-module CRUD layout,
  - theme_style          -> one of 4 visual paradigms,
  - key_features / terminology / image_subjects -> research-grounded copy + photos.

No Gemini / no cloud LLM: search is a keyless API, synthesis is local Gemma.
Cached per normalized prompt in _research_cache.json.
"""
import json
import os
import re
import urllib.request

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CACHE = os.path.join(BACKEND_DIR, "_research_cache.json")

_CRUD_LAYOUTS = {"kanban", "split-pane", "spreadsheet", "timeline", "table"}
_THEME_STYLES = {"neo-brutalism", "glassmorphism", "minimal", "cyberpunk"}
_PAGE_TEMPLATES = {"features", "about", "contact", "gallery", "pricing", "content"}

_BLUEPRINT_SHAPE = """{
 "domain": "<one or two words, e.g. school, hospital, loan-calculator>",
 "is_utility_tool": <true ONLY if this is a single-screen tool/calculator/converter with no real multi-page app, else false>,
 "app_name": "<a real product-style name>",
 "tagline": "<one sentence value proposition>",
 "theme_style": "<one of: neo-brutalism | glassmorphism | minimal | cyberpunk - the look that fits this domain>",
 "roles": ["<role>", ...1-3 user roles],
 "entities": [ {"name": "<PascalCaseEntity>", "fields": ["<snake_case_field>", ...4-7], "crud_layout": "<one of: kanban|split-pane|spreadsheet|timeline|table>"} , 2-5 entities ],
 "marketing_pages": [ {"name": "<DOMAIN-SPECIFIC page like Courses, Admissions, Departments - NOT generic Features>", "slug": "<url-slug>", "template": "<features|about|contact|gallery|pricing|content>"} , 2-5 pages ],
 "landing_sections": ["<ordered subset of: hero|stats|features|gallery|whychoose|reviews|pricing|faq|banner>", 4-7],
 "key_features": ["<6-10 real capabilities such sites advertise>"],
 "terminology": ["<8-12 real domain words>"],
 "image_subjects": ["<5-8 photo subjects seen on such sites>"]
}"""

_SYNTH_PROMPT = (
    "You are a product researcher. Using the REAL website content below, design a "
    "blueprint for the app the user asked for. Output ONLY raw JSON in EXACTLY this shape:\n"
    + _BLUEPRINT_SHAPE +
    "\nRules: pick DOMAIN-SPECIFIC marketing_pages that real sites in this field actually "
    "have (a school has Courses/Admissions/Faculty - NOT 'Features'; a clinic has "
    "Departments/Doctors/Services). Choose each entity's crud_layout by its nature "
    "(workflow/status -> kanban; dense records to inspect -> split-pane; numbers/money -> "
    "spreadsheet; logs/history -> timeline; otherwise table). Set is_utility_tool=true ONLY "
    "for single-purpose tools (calculators, converters, generators). No markdown, only the JSON object."
)


# ----------------------------------------------------------------- web search
def _search(query: str, n: int = 5) -> list:
    try:
        from ddgs import DDGS
        with DDGS() as d:
            return list(d.text(query, max_results=n))
    except Exception:
        return []


def _fetch_text(url: str, limit: int = 3500) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            html = r.read(500_000).decode("utf-8", errors="ignore")
        html = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", html, flags=re.S | re.I)
        text = re.sub(r"<[^>]+>", " ", html)  # nav links + headings reveal the page set
        return re.sub(r"\s+", " ", text)[:limit]
    except Exception:
        return ""


def _gather(prompt: str) -> tuple:
    """Return (corpus_text, urls) from real sites in the domain."""
    queries = [prompt + " software features", prompt + " platform pages", prompt + " dashboard modules 2026"]
    seen, urls, snippets = set(), [], []
    for q in queries:
        for r in _search(q, 4):
            u = r.get("href") or r.get("url") or ""
            if u.startswith("http") and u not in seen:
                seen.add(u)
                urls.append(u)
                snippets.append((r.get("title", "") + " - " + (r.get("body", "") or ""))[:300])
            if len(urls) >= 6:
                break
        if len(urls) >= 6:
            break
    corpus = ["[search snippets] " + " || ".join(snippets[:8])] if snippets else []
    for u in urls[:4]:
        t = _fetch_text(u)
        if len(t) > 300:
            corpus.append(f"--- {u} ---\n{t}")
    return "\n\n".join(corpus)[:11000], urls[:6]


# --------------------------------------------------------------- synthesis (Gemma)
def _synthesize(prompt: str, corpus: str) -> dict:
    from app.agents import get_llm, extract_json  # local import avoids a cycle
    from langchain_core.messages import SystemMessage, HumanMessage
    # Invoke with direct messages (NOT ChatPromptTemplate): the prompt + corpus are
    # full of literal { } braces which langchain's f-string templating would choke on.
    user = f"The app to build: {prompt[:240]}\n\nReal website content:\n{corpus[:10000]}"
    res = get_llm(temperature=0.3, num_predict=3072).invoke(
        [SystemMessage(content=_SYNTH_PROMPT), HumanMessage(content=user)]
    )
    return extract_json(res.content)


# ----------------------------------------------------------------- sanitize
def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", str(s).lower().strip().replace(" ", "-")) or "page"


def _sanitize(b: dict) -> dict:
    pages = []
    for p in (b.get("marketing_pages") or [])[:5]:
        if not isinstance(p, dict) or not p.get("name"):
            continue
        name = re.sub(r"[^A-Za-z0-9 &]", "", str(p["name"]))[:28].strip() or "Info"
        tpl = str(p.get("template", "content")).lower()
        pages.append({"name": name, "slug": _slug(p.get("slug", name)),
                      "template": tpl if tpl in _PAGE_TEMPLATES else "content"})
    ents = []
    for e in (b.get("entities") or [])[:5]:
        if not isinstance(e, dict) or not e.get("name"):
            continue
        nm = re.sub(r"[^A-Za-z0-9]", "", str(e["name"]))[:24] or "Item"
        fields = [re.sub(r"[^a-z0-9_]", "", str(f).lower().replace(" ", "_"))[:24]
                  for f in (e.get("fields") or []) if str(f).strip()][:7] or ["name"]
        lay = str(e.get("crud_layout", "table")).lower()
        ents.append({"name": nm, "fields": fields, "crud_layout": lay if lay in _CRUD_LAYOUTS else "table"})
    theme = str(b.get("theme_style", "minimal")).lower()
    theme = next((t for t in _THEME_STYLES if t[:4] in theme), "minimal")
    sections = [s for s in (b.get("landing_sections") or [])
                if s in {"hero", "stats", "features", "gallery", "whychoose", "reviews", "pricing", "faq", "banner"}][:7]
    return {
        "domain": str(b.get("domain", ""))[:30],
        "is_utility_tool": bool(b.get("is_utility_tool", False)),
        "app_name": str(b.get("app_name", "") or "")[:40],
        "tagline": str(b.get("tagline", "") or "")[:140],
        "theme_style": theme,
        "roles": [str(r)[:20] for r in (b.get("roles") or ["Admin", "User"])[:3]] or ["Admin", "User"],
        "entities": ents,
        "marketing_pages": pages,
        "landing_sections": sections or ["hero", "features", "stats", "faq"],
        "key_features": [str(x)[:90] for x in (b.get("key_features") or [])[:10]],
        "terminology": [str(x)[:40] for x in (b.get("terminology") or [])[:12]],
        "image_subjects": [str(x)[:80] for x in (b.get("image_subjects") or [])[:8]],
        "sites_seen": [str(u)[:200] for u in (b.get("sites_seen") or [])[:6]],
        "engine": b.get("engine", "ddgs+gemma"),
    }


def _cache():
    try:
        return json.load(open(_CACHE, encoding="utf-8"))
    except Exception:
        return {}


def deep_research(prompt: str) -> dict | None:
    """Internet-grounded Domain Blueprint for the request (cached per prompt)."""
    key = re.sub(r"[^a-z0-9]+", "-", (prompt or "").lower())[:70]
    cache = _cache()
    if key in cache:
        hit = dict(cache[key])
        hit["engine"] = hit.get("engine", "?") + " (cached)"
        return hit
    corpus, urls = _gather(prompt)
    try:
        brief = _synthesize(prompt, corpus or prompt)
    except Exception:
        return None
    brief["sites_seen"] = urls
    brief = _sanitize(brief)
    cache[key] = brief
    try:
        json.dump(cache, open(_CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except OSError:
        pass
    return brief
