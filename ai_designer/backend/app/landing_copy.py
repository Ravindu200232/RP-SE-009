"""Landing copy-slots: the LLM writes ONLY the marketing copy (a small JSON),
and Python substitutes it into the chosen library template deterministically.

Why: asking a 7B model to echo a 12KB edited JSX file through a JSON envelope
fails regularly (escaping/truncation -> syntax errors -> fallback stub). Copy
is ~2KB of plain strings - well inside the model's reliable zone - and the
substitution can never produce invalid syntax, so a landing page can no longer
fail to generate.
"""
import json
import re

_COPY_PROMPT = """You are a senior copywriter. Write the COMPLETE landing-page copy for the app "{app_name}".
Context: {app_context}

Output ONLY raw JSON exactly in this shape (write REAL, specific, professional copy for {app_name} - never placeholders, never lorem ipsum):
{{
 "badge": "<short announcement, 4-7 words>",
 "headline_pre": "<headline words before the accent, 2-5 words>",
 "accent": "<the 1-3 accented headline words>",
 "headline_post": "<headline words after the accent, 0-4 words>",
 "subline": "<1-2 sentences, the value proposition>",
 "trust": "<short trust caption, e.g. 'Trusted by 400+ clinics'>",
 "logos": ["<COMPANY1>", "<COMPANY2>", "<COMPANY3>", "<COMPANY4>", "<COMPANY5>"],
 "features_h": "<features section heading>",
 "features_sub": "<one supporting sentence>",
 "features": [{{"title": "...", "text": "<1 sentence>"}}, ... exactly 6 items],
 "steps": [{{"t": "<step title>", "d": "<2 short sentences>"}}, ... exactly 3 items],
 "stats": [["<number>", "<label>"], ... exactly 4 pairs],
 "banner_h": "<banner headline over the photo>",
 "banner_p": "<one inviting sentence>",
 "quotes": [{{"n": "<full name>", "r": "<role, organisation>", "t": "<2-sentence testimonial>"}}, ... exactly 3 items],
 "tiers": [{{"name": "...", "price": <integer>, "items": ["...", "...", "...", "..."]}}, ... exactly 3 items, ascending price],
 "faqs": [{{"q": "<question>?", "a": "<2-sentence answer>"}}, ... exactly 5 items],
 "pillars": [{{"t": "<pillar title>", "d": "<2 warm sentences>"}}, ... exactly 3 items],
 "about_eyebrow": "<tiny uppercase label>",
 "about_h": "<heading about the people/story>",
 "about_p": "<3-sentence story>",
 "about_points": ["<selling point>", "<selling point>", "<selling point>"],
 "cta_h": "<final call-to-action headline>",
 "cta_p": "<one encouraging sentence>",
 "footer_tag": "<one-line app description>"
}}
No markdown. Only the JSON object."""

_DEFAULTS = {
    "badge": "Now available for your team",
    "headline_pre": "Run your business", "accent": "beautifully", "headline_post": "",
    "subline": "Everything you need to manage your work in one fast, friendly place.",
    "trust": "Loved by 10,000+ teams",
    "logos": ["BRANDONE", "NORTHLY", "VERTEX", "OPALCO", "LUMINA"],
    "features_h": "Everything you need", "features_sub": "Powerful tools that stay out of your way.",
    "features": [{"title": f"Capability {i}", "text": "Designed to save you time every day."} for i in range(1, 7)],
    "steps": [{"t": f"Step {i}", "d": "Quick to do. Quicker to love."} for i in range(1, 4)],
    "stats": [["10k+", "Customers"], ["99.9%", "Uptime"], ["4.9/5", "Avg rating"], ["24/7", "Support"]],
    "banner_h": "Built for the way you work", "banner_p": "See it in action today.",
    "quotes": [{"n": "Jordan Lee", "r": "Operations lead", "t": "It changed how we work. We would never go back."}] * 3,
    "tiers": [{"name": "Starter", "price": 19, "items": ["Core features", "Email support", "1 workspace", "Basic reports"]},
              {"name": "Professional", "price": 49, "items": ["Everything in Starter", "Unlimited records", "Priority support", "Advanced reports", "Integrations"]},
              {"name": "Enterprise", "price": 99, "items": ["Everything in Pro", "SSO & audit logs", "Dedicated manager", "Custom SLAs"]}],
    "faqs": [{"q": f"Common question {i}?", "a": "Short, clear answer with a concrete detail."} for i in range(1, 6)],
    "pillars": [{"t": f"Pillar {i}", "d": "A core part of the experience, done with care."} for i in range(1, 4)],
    "about_eyebrow": "Our story", "about_h": "Built by people who care",
    "about_p": "We started with a simple idea: make the everyday work effortless. Years later, that is still what drives us.",
    "about_points": ["Thoughtful design", "Fast support", "Constant improvement"],
    "cta_h": "Ready to get started?", "cta_p": "Join today - it only takes a minute.",
    "footer_tag": "The friendly way to run your operation.",
}


def _sanitize(v):
    """Copy values land in JSX TEXT positions: <,>,{,} and backticks are fatal
    there. Strip them (and collapse whitespace) from every string recursively."""
    if isinstance(v, str):
        return re.sub(r"\s+", " ", re.sub(r"[<>{}`]", "", v)).strip()
    if isinstance(v, list):
        return [_sanitize(x) for x in v]
    if isinstance(v, dict):
        return {k: _sanitize(x) for k, x in v.items()}
    return v


def _merge(raw: dict) -> dict:
    """Defaults + model output, sanitised, with list lengths normalised."""
    c = dict(_DEFAULTS)
    for k, v in (raw or {}).items():
        if k in c and v:
            c[k] = _sanitize(v)
    def pad(key, n):
        lst = list(c[key])[:max(n, 0)] or list(_DEFAULTS[key])
        while len(lst) < n:
            lst.append(_DEFAULTS[key][len(lst) % len(_DEFAULTS[key])])
        c[key] = lst
    pad("logos", 5); pad("features", 6); pad("steps", 3); pad("stats", 4)
    pad("quotes", 3); pad("tiers", 3); pad("faqs", 5); pad("pillars", 3); pad("about_points", 5)
    return c


def _sq(s) -> str:
    """Escape a value for insertion INSIDE an existing single-quoted JS literal."""
    return str(s).replace("\\", "\\\\").replace("'", "\\'")


def _js_str(s) -> str:
    return json.dumps(str(s), ensure_ascii=False)


def _arr(name: str, items_js: str, src: str) -> str:
    """Replace `const <name> = [...];` with a rebuilt literal."""
    return re.sub(r"const %s = \[.*?\];" % name, "const %s = [%s];" % (name, items_js), src, count=1, flags=re.S)


def apply(entry_name: str, src: str, copy: dict, app_name: str) -> str:
    """Substitute the copy into a landing template. Pure string work - the
    output is syntactically identical to the (validated) template."""
    c = _merge(copy)
    app_name = _sanitize(app_name or "App")
    icons = ["zap", "shield", "chart", "users", "clock", "star", "heart", "award"]

    # ---- const arrays shared across templates -------------------------------
    if "const features = [" in src:
        feats = ",\n    ".join("{ icon: '%s', title: %s, text: %s }" % (icons[i % len(icons)], _js_str(f.get("title", "")), _js_str(f.get("text", "")))
                               for i, f in enumerate(c["features"]))
        src = _arr("features", "\n    " + feats + "\n  ", src)
    if "const steps = [" in src:
        steps = ",\n    ".join("{ n: '0%d', t: %s, d: %s }" % (i + 1, _js_str(s.get("t", "")), _js_str(s.get("d", "")))
                               for i, s in enumerate(c["steps"]))
        src = _arr("steps", "\n    " + steps + "\n  ", src)
    if "const stats = [" in src:
        stats = ", ".join("[%s, %s]" % (_js_str(n), _js_str(l)) for n, l in c["stats"])
        src = _arr("stats", stats, src)
    if "const quotes = [" in src:
        n_q = 2 if entry_name == "editorial-photo" else 3
        qs = ",\n    ".join("{ n: %s, r: %s, t: %s }" % (_js_str(q.get("n", "")), _js_str(q.get("r", "")), _js_str(q.get("t", "")))
                            for q in c["quotes"][:n_q])
        src = _arr("quotes", "\n    " + qs + "\n  ", src)
    if "const tiers = [" in src:
        ts = ",\n    ".join("{ name: %s, price: %d, popular: %s, items: [%s] }"
                            % (_js_str(t.get("name", "")), int(t.get("price", 0) or 0), "true" if i == 1 else "false",
                               ", ".join(_js_str(x) for x in (t.get("items") or [])[:5]))
                            for i, t in enumerate(c["tiers"]))
        src = _arr("tiers", "\n    " + ts + "\n  ", src)
    if "const faqs = [" in src:
        fq = ",\n    ".join("{ q: %s, a: %s }" % (_js_str(f.get("q", "")), _js_str(f.get("a", ""))) for f in c["faqs"])
        src = _arr("faqs", "\n    " + fq + "\n  ", src)
    if "const numbered = [" in src:  # editorial pillars keep their images
        imgs = ["assets/gallery1.jpg", "assets/gallery2.jpg", "assets/gallery3.jpg"]
        nb = ",\n    ".join("{ n: '0%d', img: '%s', t: %s, d: %s }" % (i + 1, imgs[i % 3], _js_str(p.get("t", "")), _js_str(p.get("d", "")))
                            for i, p in enumerate(c["pillars"]))
        src = _arr("numbered", "\n    " + nb + "\n  ", src)

    # ---- inline literals (template-specific anchors I authored) -------------
    logos_js = ", ".join(_js_str(x) for x in c["logos"])
    src = src.replace("['BRANDONE', 'NORTHLY', 'VERTEX', 'OPALCO', 'LUMINA', 'KITEWORK']", "[" + logos_js + ", " + _js_str("KITEWORK") + "]")
    src = src.replace("['BRANDONE', 'NORTHLY', 'VERTEX', 'OPALCO', 'LUMINA']", "[" + logos_js + "]")
    inline_stats = {
        "[['10k+', 'Active users'], ['99.9%', 'Uptime SLA'], ['4.9/5', 'Average rating'], ['150+', 'Integrations']]",
        "[['12+', 'Years running'], ['98%', 'Happy customers'], ['40k', 'Served monthly'], ['15', 'Awards won']]",
    }
    stats_js = "[" + ", ".join("[%s, %s]" % (_js_str(n), _js_str(l)) for n, l in c["stats"]) + "]"
    for lit in inline_stats:
        src = src.replace(lit, stats_js)
    # creative-dark inline steps
    for i, word in enumerate(["one", "two", "three"]):
        src = src.replace("{ n: '%d', t: 'Step %s title', d: 'Two sentences describing the %s step of the journey.' }"
                          % (i + 1, word, ["first", "second", "third"][i]),
                          "{ n: '%d', t: %s, d: %s }" % (i + 1, _js_str(c["steps"][i].get("t", "")), _js_str(c["steps"][i].get("d", ""))))

    text_map = [
        ("Tagline category", c["badge"]), ("New: announcement text", c["badge"]), ("Eyebrow category", c["about_eyebrow"]),
        ("Headline part <", c["headline_pre"] + " <"), (">accent words</", ">" + c["accent"] + "</"), ("</span> here", "</span> " + c["headline_post"]),
        ("Headline with an <", c["headline_pre"] + " <"), (">accent phrase</", ">" + c["accent"] + "</"), ("</span> in it", "</span> " + c["headline_post"]),
        ("A huge editorial<br />headline with an<br />", c["headline_pre"] + "<br />"), (">accent word</", ">" + c["accent"] + "</"),
        ("One or two sentences describing the product value for the target user.", c["subline"]),
        ("Two sentences explaining what the product does and who it is for, in plain confident language.", c["subline"]),
        ("Two sentences setting the scene - what this place or product is, and the feeling it promises.", c["subline"]),
        ("Loved by 10,000+ teams", c["trust"]),
        ("Section heading about capabilities", c["features_h"]), ("Section heading about what you get", c["features_h"]),
        ("Section heading about the experience", c["features_h"]),
        ("One supporting sentence for this section.", c["features_sub"]),
        ("One supporting sentence inviting the visitor to explore.", c["features_sub"]),
        ("Banner headline over the photo", c["banner_h"]), ("Banner headline", c["banner_h"]),
        ("One supporting sentence over the photo.", c["banner_p"]), ("One inviting sentence.", c["banner_p"]),
        ("Benefits heading goes here", c["about_h"]), ("Heading about the people behind it", c["about_h"]),
        ("Two sentences on the overall benefit story for this audience.", c["about_p"]),
        ("Three sentences telling the story - the founding idea, the craft, and the promise to the customer.", c["about_p"]),
        ("Final call-to-action headline", c["cta_h"]),
        ("One sentence of encouragement.", c["cta_p"]), ("One sentence of encouragement to join.", c["cta_p"]),
        ("One sentence of warm encouragement.", c["cta_p"]),
        ("One sentence about pricing philosophy.", c["features_sub"]),
        ("One-line app description.", c["footer_tag"]),
        ("App Name", (app_name or "App")[:28]),
    ]
    for old, new in text_map:
        src = src.replace(old, str(new))
    # These anchors sit INSIDE single-quoted JS array literals -> values must be
    # single-quote-escaped or an apostrophe ("hospital's") breaks the file.
    words = ["one", "two", "three", "four", "five"]
    for i, pt in enumerate(c["about_points"][:5]):
        src = src.replace(f"Selling point {words[i]}", _sq(pt)) if i < 3 else src
        src = src.replace(f"Benefit point {words[i]}", _sq(pt))
    return src
