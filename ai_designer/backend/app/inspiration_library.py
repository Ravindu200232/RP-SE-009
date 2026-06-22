"""Local-first design inspiration library.

The references in this file are metadata only. They are never copied into
generated pages as layouts, text, colors, assets, logos, or imagery. The
generator consumes abstract design DNA such as "dashboard proof hero" or
"editorial rhythm" and then maps those labels into our own build-safe component
grammar.
"""
from __future__ import annotations

from collections import Counter
import os
import random
import re


CATEGORY_SAAS = "SaaS / Productivity"
CATEGORY_BUSINESS = "POS / ERP / Business Software"
CATEGORY_CREATIVE = "Portfolio / Agency / Creative"
CATEGORY_ECOMMERCE = "Ecommerce / Product"
CATEGORY_MARKETING = "Marketing / Landing / Brand"
CATEGORY_SOCIAL = "Social / Community / Creator"
CATEGORY_AI = "AI / Developer Tools"
CATEGORY_FINANCE = "Finance / FinTech"
CATEGORY_EDUCATION = "Education / Media / Content"


_CATEGORY_DNA = {
    CATEGORY_SAAS: {
        "design_family": "saas-productivity",
        "hero_patterns": ["split product story", "dashboard proof", "workflow preview"],
        "navigation_patterns": ["centered topnav", "action topnav", "utility bar"],
        "section_patterns": ["feature cards", "portal preview", "stats band", "FAQ"],
        "card_patterns": ["bordered", "shadow", "stat-card"],
        "typography_style": "precise sans",
        "spacing_style": "spacious",
        "color_palette_family": "calm trust",
        "image_strategy": "dashboard mockup",
        "CTA_patterns": ["hero-primary", "nav-cta", "floating"],
        "footer_patterns": ["product footer", "utility footer"],
        "best_for_domains": ["saas", "productivity", "business", "healthcare", "operations", "crm"],
    },
    CATEGORY_BUSINESS: {
        "design_family": "operational-business",
        "hero_patterns": ["dashboard proof", "metrics first", "workflow preview"],
        "navigation_patterns": ["sidebar", "utility bar", "action topnav"],
        "section_patterns": ["stats band", "portal preview", "timeline", "feature cards"],
        "card_patterns": ["stat-card", "bordered", "flat"],
        "typography_style": "dense sans",
        "spacing_style": "compact",
        "color_palette_family": "operational blue",
        "image_strategy": "dashboard mockup",
        "CTA_patterns": ["after-stats", "nav-cta", "hero-primary"],
        "footer_patterns": ["enterprise footer", "utility footer"],
        "best_for_domains": ["pos", "erp", "inventory", "warehouse", "operations", "dashboard", "business"],
    },
    CATEGORY_CREATIVE: {
        "design_family": "creative-agency",
        "hero_patterns": ["editorial lead", "immersive brand image", "card stack"],
        "navigation_patterns": ["floating nav", "centered topnav", "action topnav"],
        "section_patterns": ["gallery", "split image/text", "timeline", "feature cards"],
        "card_patterns": ["image-card", "glass", "shadow"],
        "typography_style": "editorial display",
        "spacing_style": "editorial",
        "color_palette_family": "creative contrast",
        "image_strategy": "gallery",
        "CTA_patterns": ["hero-split", "section-end", "floating"],
        "footer_patterns": ["minimal footer", "studio footer"],
        "best_for_domains": ["portfolio", "agency", "creative", "studio", "designer", "brand"],
    },
    CATEGORY_ECOMMERCE: {
        "design_family": "ecommerce-product",
        "hero_patterns": ["immersive brand image", "product spotlight", "card stack"],
        "navigation_patterns": ["action topnav", "centered topnav", "floating nav"],
        "section_patterns": ["gallery", "feature cards", "split image/text", "CTA"],
        "card_patterns": ["image-card", "shadow", "flat"],
        "typography_style": "premium sans",
        "spacing_style": "image-heavy",
        "color_palette_family": "premium product",
        "image_strategy": "gallery",
        "CTA_patterns": ["hero-primary", "nav-cta", "section-end"],
        "footer_patterns": ["commerce footer", "brand footer"],
        "best_for_domains": ["ecommerce", "product", "vehicle", "car", "sales", "shop", "marketplace", "retail"],
    },
    CATEGORY_MARKETING: {
        "design_family": "marketing-brand",
        "hero_patterns": ["split product story", "card stack", "editorial lead"],
        "navigation_patterns": ["action topnav", "floating nav", "centered topnav"],
        "section_patterns": ["feature cards", "timeline", "FAQ", "CTA"],
        "card_patterns": ["shadow", "glass", "bordered"],
        "typography_style": "friendly sans",
        "spacing_style": "spacious",
        "color_palette_family": "warm brand",
        "image_strategy": "section images",
        "CTA_patterns": ["hero-primary", "floating", "section-end"],
        "footer_patterns": ["brand footer", "newsletter footer"],
        "best_for_domains": ["landing", "brand", "marketing", "startup", "service", "creator"],
    },
    CATEGORY_SOCIAL: {
        "design_family": "social-community",
        "hero_patterns": ["community cards", "card stack", "immersive brand image"],
        "navigation_patterns": ["floating nav", "centered topnav", "utility bar"],
        "section_patterns": ["gallery", "feature cards", "timeline", "portal preview"],
        "card_patterns": ["glass", "shadow", "image-card"],
        "typography_style": "friendly sans",
        "spacing_style": "spacious",
        "color_palette_family": "community bright",
        "image_strategy": "gallery",
        "CTA_patterns": ["hero-split", "floating", "nav-cta"],
        "footer_patterns": ["community footer", "minimal footer"],
        "best_for_domains": ["social", "community", "creator", "forum", "network", "content"],
    },
    CATEGORY_AI: {
        "design_family": "ai-devtools",
        "hero_patterns": ["dashboard proof", "editorial lead", "code workspace"],
        "navigation_patterns": ["utility bar", "floating nav", "sidebar"],
        "section_patterns": ["portal preview", "stats band", "timeline", "FAQ"],
        "card_patterns": ["glass", "bordered", "stat-card"],
        "typography_style": "technical sans",
        "spacing_style": "data-heavy",
        "color_palette_family": "developer dark",
        "image_strategy": "dashboard mockup",
        "CTA_patterns": ["hero-split", "nav-cta", "after-stats"],
        "footer_patterns": ["developer footer", "docs footer"],
        "best_for_domains": ["ai", "developer", "devtool", "code", "api", "cloud", "docs"],
    },
    CATEGORY_FINANCE: {
        "design_family": "fintech-trust",
        "hero_patterns": ["metrics first", "dashboard proof", "split product story"],
        "navigation_patterns": ["utility bar", "action topnav", "centered topnav"],
        "section_patterns": ["stats band", "portal preview", "feature cards", "FAQ"],
        "card_patterns": ["stat-card", "bordered", "flat"],
        "typography_style": "precise sans",
        "spacing_style": "data-heavy",
        "color_palette_family": "fintech trust",
        "image_strategy": "dashboard mockup",
        "CTA_patterns": ["after-stats", "hero-primary", "nav-cta"],
        "footer_patterns": ["trust footer", "enterprise footer"],
        "best_for_domains": ["finance", "fintech", "bank", "payments", "invoice", "wallet", "trust", "security"],
    },
    CATEGORY_EDUCATION: {
        "design_family": "education-media",
        "hero_patterns": ["editorial lead", "course preview", "immersive brand image"],
        "navigation_patterns": ["centered topnav", "action topnav", "floating nav"],
        "section_patterns": ["split image/text", "gallery", "timeline", "feature cards"],
        "card_patterns": ["image-card", "bordered", "shadow"],
        "typography_style": "readable editorial",
        "spacing_style": "editorial",
        "color_palette_family": "learning editorial",
        "image_strategy": "section images",
        "CTA_patterns": ["hero-primary", "hero-split", "section-end"],
        "footer_patterns": ["content footer", "catalog footer"],
        "best_for_domains": ["education", "course", "learning", "media", "content", "news", "school"],
    },
}


_ROWS = [
    ("Stripe", "https://stripe.com", CATEGORY_SAAS),
    ("Linear", "https://linear.app", CATEGORY_SAAS),
    ("Notion", "https://www.notion.com", CATEGORY_SAAS),
    ("Figma", "https://www.figma.com", CATEGORY_SAAS),
    ("Vercel", "https://vercel.com", CATEGORY_SAAS),
    ("Framer", "https://www.framer.com", CATEGORY_SAAS),
    ("Webflow", "https://webflow.com", CATEGORY_SAAS),
    ("Slack", "https://slack.com", CATEGORY_SAAS),
    ("Dropbox", "https://www.dropbox.com", CATEGORY_SAAS),
    ("Airtable", "https://www.airtable.com", CATEGORY_SAAS),
    ("Miro", "https://miro.com", CATEGORY_SAAS),
    ("Asana", "https://asana.com", CATEGORY_SAAS),
    ("Monday", "https://monday.com", CATEGORY_SAAS),
    ("ClickUp", "https://clickup.com", CATEGORY_SAAS),
    ("Calendly", "https://calendly.com", CATEGORY_SAAS),
    ("Square POS", "https://squareup.com", CATEGORY_BUSINESS),
    ("Shopify POS", "https://www.shopify.com/pos", CATEGORY_BUSINESS),
    ("Toast POS", "https://pos.toasttab.com", CATEGORY_BUSINESS),
    ("Lightspeed", "https://www.lightspeedhq.com", CATEGORY_BUSINESS),
    ("Clover", "https://www.clover.com", CATEGORY_BUSINESS),
    ("Revel Systems", "https://revelsystems.com", CATEGORY_BUSINESS),
    ("Odoo", "https://www.odoo.com", CATEGORY_BUSINESS),
    ("Zoho", "https://www.zoho.com", CATEGORY_BUSINESS),
    ("QuickBooks", "https://quickbooks.intuit.com", CATEGORY_BUSINESS),
    ("Xero", "https://www.xero.com", CATEGORY_BUSINESS),
    ("Bruno Simon", "https://bruno-simon.com", CATEGORY_CREATIVE),
    ("Brittany Chiang", "https://brittanychiang.com", CATEGORY_CREATIVE),
    ("Tobias van Schneider", "https://vanschneider.com", CATEGORY_CREATIVE),
    ("Adham Dannaway", "https://www.adhamdannaway.com", CATEGORY_CREATIVE),
    ("Locomotive", "https://locomotive.ca", CATEGORY_CREATIVE),
    ("Huge", "https://www.hugeinc.com", CATEGORY_CREATIVE),
    ("Instrument", "https://www.instrument.com", CATEGORY_CREATIVE),
    ("Pentagram", "https://www.pentagram.com", CATEGORY_CREATIVE),
    ("Work & Co", "https://work.co", CATEGORY_CREATIVE),
    ("Active Theory", "https://activetheory.net", CATEGORY_CREATIVE),
    ("Apple", "https://www.apple.com", CATEGORY_ECOMMERCE),
    ("Nike", "https://www.nike.com", CATEGORY_ECOMMERCE),
    ("Adidas", "https://www.adidas.com", CATEGORY_ECOMMERCE),
    ("Tesla", "https://www.tesla.com", CATEGORY_ECOMMERCE),
    ("IKEA", "https://www.ikea.com", CATEGORY_ECOMMERCE),
    ("Amazon", "https://www.amazon.com", CATEGORY_ECOMMERCE),
    ("Best Buy", "https://www.bestbuy.com", CATEGORY_ECOMMERCE),
    ("Etsy", "https://www.etsy.com", CATEGORY_ECOMMERCE),
    ("Glossier", "https://www.glossier.com", CATEGORY_ECOMMERCE),
    ("Allbirds", "https://www.allbirds.com", CATEGORY_ECOMMERCE),
    ("Warby Parker", "https://www.warbyparker.com", CATEGORY_ECOMMERCE),
    ("Patagonia", "https://www.patagonia.com", CATEGORY_ECOMMERCE),
    ("Huckberry", "https://huckberry.com", CATEGORY_ECOMMERCE),
    ("Gymshark", "https://www.gymshark.com", CATEGORY_ECOMMERCE),
    ("Nothing", "https://nothing.tech", CATEGORY_ECOMMERCE),
    ("Mailchimp", "https://mailchimp.com", CATEGORY_MARKETING),
    ("HubSpot", "https://www.hubspot.com", CATEGORY_MARKETING),
    ("Intercom", "https://www.intercom.com", CATEGORY_MARKETING),
    ("Typeform", "https://www.typeform.com", CATEGORY_MARKETING),
    ("Canva", "https://www.canva.com", CATEGORY_MARKETING),
    ("MOO", "https://www.moo.com", CATEGORY_MARKETING),
    ("Headspace", "https://www.headspace.com", CATEGORY_MARKETING),
    ("Duolingo", "https://www.duolingo.com", CATEGORY_MARKETING),
    ("Grammarly", "https://www.grammarly.com", CATEGORY_MARKETING),
    ("Ahrefs", "https://ahrefs.com", CATEGORY_MARKETING),
    ("Discord", "https://discord.com", CATEGORY_SOCIAL),
    ("Reddit", "https://www.reddit.com", CATEGORY_SOCIAL),
    ("Product Hunt", "https://www.producthunt.com", CATEGORY_SOCIAL),
    ("Behance", "https://www.behance.net", CATEGORY_SOCIAL),
    ("Dribbble", "https://dribbble.com", CATEGORY_SOCIAL),
    ("GitHub", "https://github.com", CATEGORY_SOCIAL),
    ("Stack Overflow", "https://stackoverflow.com", CATEGORY_SOCIAL),
    ("LinkedIn", "https://www.linkedin.com", CATEGORY_SOCIAL),
    ("Medium", "https://medium.com", CATEGORY_SOCIAL),
    ("Pinterest", "https://www.pinterest.com", CATEGORY_SOCIAL),
    ("OpenAI", "https://openai.com", CATEGORY_AI),
    ("Anthropic", "https://www.anthropic.com", CATEGORY_AI),
    ("Perplexity", "https://www.perplexity.ai", CATEGORY_AI),
    ("Cursor", "https://cursor.com", CATEGORY_AI),
    ("Replit", "https://replit.com", CATEGORY_AI),
    ("GitLab", "https://about.gitlab.com", CATEGORY_AI),
    ("Supabase", "https://supabase.com", CATEGORY_AI),
    ("Railway", "https://railway.com", CATEGORY_AI),
    ("Cloudflare", "https://www.cloudflare.com", CATEGORY_AI),
    ("GitBook", "https://www.gitbook.com", CATEGORY_AI),
    ("Wise", "https://wise.com", CATEGORY_FINANCE),
    ("Revolut", "https://www.revolut.com", CATEGORY_FINANCE),
    ("Monzo", "https://monzo.com", CATEGORY_FINANCE),
    ("Mercury", "https://mercury.com", CATEGORY_FINANCE),
    ("Ramp", "https://ramp.com", CATEGORY_FINANCE),
    ("Brex", "https://www.brex.com", CATEGORY_FINANCE),
    ("PayPal", "https://www.paypal.com", CATEGORY_FINANCE),
    ("Coinbase", "https://www.coinbase.com", CATEGORY_FINANCE),
    ("Robinhood", "https://robinhood.com", CATEGORY_FINANCE),
    ("Nubank", "https://nubank.com.br", CATEGORY_FINANCE),
    ("Coursera", "https://www.coursera.org", CATEGORY_EDUCATION),
    ("edX", "https://www.edx.org", CATEGORY_EDUCATION),
    ("Khan Academy", "https://www.khanacademy.org", CATEGORY_EDUCATION),
    ("Udemy", "https://www.udemy.com", CATEGORY_EDUCATION),
    ("MasterClass", "https://www.masterclass.com", CATEGORY_EDUCATION),
    ("TED", "https://www.ted.com", CATEGORY_EDUCATION),
    ("The Verge", "https://www.theverge.com", CATEGORY_EDUCATION),
    ("The New York Times", "https://www.nytimes.com", CATEGORY_EDUCATION),
    ("National Geographic", "https://www.nationalgeographic.com", CATEGORY_EDUCATION),
    ("Spotify", "https://www.spotify.com", CATEGORY_EDUCATION),
]


def _ref(name: str, url: str, category: str) -> dict:
    dna = _CATEGORY_DNA[category]
    return {
        "name": name,
        "url": url,
        "category": category,
        "design_family": dna["design_family"],
        "hero_patterns": list(dna["hero_patterns"]),
        "navigation_patterns": list(dna["navigation_patterns"]),
        "section_patterns": list(dna["section_patterns"]),
        "card_patterns": list(dna["card_patterns"]),
        "typography_style": dna["typography_style"],
        "spacing_style": dna["spacing_style"],
        "color_palette_family": dna["color_palette_family"],
        "image_strategy": dna["image_strategy"],
        "CTA_patterns": list(dna["CTA_patterns"]),
        "footer_patterns": list(dna["footer_patterns"]),
        "best_for_domains": list(dna["best_for_domains"]),
    }


CURATED_REFERENCES = [_ref(*row) for row in _ROWS]


_FAMILY_CATEGORY_WEIGHTS = {
    "healthcare-trust-saas": [CATEGORY_SAAS, CATEGORY_FINANCE, CATEGORY_BUSINESS, CATEGORY_MARKETING],
    "ecommerce-product": [CATEGORY_ECOMMERCE, CATEGORY_MARKETING, CATEGORY_SOCIAL],
    "operational-business": [CATEGORY_BUSINESS, CATEGORY_SAAS, CATEGORY_FINANCE],
    "creative-agency": [CATEGORY_CREATIVE, CATEGORY_MARKETING, CATEGORY_SOCIAL],
    "ai-devtools": [CATEGORY_AI, CATEGORY_SAAS, CATEGORY_SOCIAL],
    "fintech-trust": [CATEGORY_FINANCE, CATEGORY_SAAS, CATEGORY_BUSINESS],
    "education-media": [CATEGORY_EDUCATION, CATEGORY_MARKETING, CATEGORY_SOCIAL],
    "saas-productivity": [CATEGORY_SAAS, CATEGORY_MARKETING, CATEGORY_BUSINESS],
    "social-community": [CATEGORY_SOCIAL, CATEGORY_CREATIVE, CATEGORY_EDUCATION],
    "marketing-brand": [CATEGORY_MARKETING, CATEGORY_SAAS, CATEGORY_CREATIVE],
}


_FAMILY_KEYWORDS = {
    "healthcare-trust-saas": ["hospital", "clinic", "patient", "doctor", "medical", "health", "lab", "telehealth", "care"],
    "ecommerce-product": ["vehicle", "car", "sales", "dealer", "ecommerce", "store", "shop", "product", "retail", "marketplace"],
    "operational-business": ["pos", "erp", "inventory", "stock", "warehouse", "supplier", "order", "operations", "booking", "payment"],
    "creative-agency": ["portfolio", "agency", "creative", "studio", "designer", "artist", "brand"],
    "ai-devtools": ["ai", "developer", "devtool", "code", "api", "cloud", "agent", "llm", "automation"],
    "fintech-trust": ["finance", "fintech", "bank", "loan", "wallet", "invoice", "accounting", "payment", "trading"],
    "education-media": ["education", "course", "learning", "lms", "student", "teacher", "media", "content", "news"],
    "saas-productivity": ["saas", "productivity", "crm", "project", "team", "collaboration", "workflow"],
    "social-community": ["social", "community", "creator", "forum", "network", "member", "chat"],
    "marketing-brand": ["landing", "marketing", "brand", "campaign", "startup", "service"],
}


_GENOME_BIAS_BY_FAMILY = {
    "healthcare-trust-saas": {
        "hero_variant": ["search-booking", "stats-first", "split"],
        "nav_variant": ["utility bar", "action topnav"],
        "section_variants": ["portal preview", "stats band", "feature cards", "FAQ"],
        "card_style": ["bordered", "stat-card"],
        "layout_rhythm": ["spacious", "data-heavy"],
        "image_strategy": ["hero image", "dashboard mockup", "section images"],
        "cta_placement": ["floating", "hero-primary"],
        "section_strategy": ["productized-service", "conversion"],
        "dashboard_style": ["kpi-cards", "activity-feed"],
        "crud_style": ["split-pane", "table-dense"],
        "visual_style": ["enterprise", "minimal"],
    },
    "ecommerce-product": {
        "hero_variant": ["full-image", "card-stack", "editorial"],
        "nav_variant": ["action topnav", "centered topnav"],
        "section_variants": ["gallery", "feature cards", "split image/text", "CTA"],
        "card_style": ["image-card", "shadow"],
        "layout_rhythm": ["image-heavy", "spacious"],
        "image_strategy": ["gallery", "hero image", "section images"],
        "cta_placement": ["hero-primary", "nav-cta"],
        "section_strategy": ["directory", "conversion"],
        "dashboard_style": ["kanban", "kpi-cards"],
        "crud_style": ["card-grid", "kanban"],
        "visual_style": ["clean", "editorial"],
    },
    "operational-business": {
        "hero_variant": ["dashboard-preview", "stats-first"],
        "nav_variant": ["sidebar", "utility bar"],
        "section_variants": ["stats band", "portal preview", "timeline", "feature cards"],
        "card_style": ["stat-card", "bordered"],
        "layout_rhythm": ["compact", "data-heavy"],
        "image_strategy": ["dashboard mockup", "no-image fallback"],
        "cta_placement": ["after-stats", "nav-cta"],
        "section_strategy": ["operations", "analytics"],
        "dashboard_style": ["table-first", "analytics"],
        "crud_style": ["table-dense", "split-pane"],
        "visual_style": ["dense-admin", "enterprise"],
    },
    "creative-agency": {
        "hero_variant": ["editorial", "full-image", "card-stack"],
        "nav_variant": ["floating nav", "centered topnav"],
        "section_variants": ["gallery", "split image/text", "timeline", "feature cards"],
        "card_style": ["image-card", "glass", "shadow"],
        "layout_rhythm": ["editorial", "image-heavy"],
        "image_strategy": ["gallery", "section images"],
        "cta_placement": ["hero-split", "section-end"],
        "section_strategy": ["storytelling", "community"],
        "dashboard_style": ["activity-feed", "kanban"],
        "crud_style": ["timeline", "card-grid"],
        "visual_style": ["editorial", "glass"],
    },
    "ai-devtools": {
        "hero_variant": ["dashboard-preview", "editorial", "stats-first"],
        "nav_variant": ["utility bar", "floating nav", "sidebar"],
        "section_variants": ["portal preview", "stats band", "timeline", "FAQ"],
        "card_style": ["glass", "bordered", "stat-card"],
        "layout_rhythm": ["data-heavy", "compact"],
        "image_strategy": ["dashboard mockup", "no-image fallback"],
        "cta_placement": ["hero-split", "nav-cta"],
        "section_strategy": ["analytics", "productized-service"],
        "dashboard_style": ["analytics", "split-pane"],
        "crud_style": ["split-pane", "table-dense"],
        "visual_style": ["premium-dark", "enterprise"],
    },
    "fintech-trust": {
        "hero_variant": ["stats-first", "dashboard-preview"],
        "nav_variant": ["utility bar", "action topnav"],
        "section_variants": ["stats band", "portal preview", "feature cards", "FAQ"],
        "card_style": ["stat-card", "bordered"],
        "layout_rhythm": ["data-heavy", "compact"],
        "image_strategy": ["dashboard mockup"],
        "cta_placement": ["after-stats", "hero-primary"],
        "section_strategy": ["analytics", "conversion"],
        "dashboard_style": ["analytics", "kpi-cards"],
        "crud_style": ["table-dense", "spreadsheet"],
        "visual_style": ["enterprise", "premium-dark"],
    },
    "education-media": {
        "hero_variant": ["editorial", "full-image", "dashboard-preview"],
        "nav_variant": ["centered topnav", "action topnav"],
        "section_variants": ["split image/text", "gallery", "timeline", "feature cards"],
        "card_style": ["image-card", "bordered"],
        "layout_rhythm": ["editorial", "spacious"],
        "image_strategy": ["section images", "gallery"],
        "cta_placement": ["hero-primary", "section-end"],
        "section_strategy": ["storytelling", "community"],
        "dashboard_style": ["activity-feed", "kpi-cards"],
        "crud_style": ["card-grid", "timeline"],
        "visual_style": ["editorial", "playful"],
    },
    "saas-productivity": {},
    "social-community": {},
    "marketing-brand": {},
}

_GENOME_BIAS_BY_FAMILY["saas-productivity"] = dict(_GENOME_BIAS_BY_FAMILY["healthcare-trust-saas"])
_GENOME_BIAS_BY_FAMILY["social-community"] = dict(_GENOME_BIAS_BY_FAMILY["creative-agency"])
_GENOME_BIAS_BY_FAMILY["marketing-brand"] = dict(_GENOME_BIAS_BY_FAMILY["creative-agency"])


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _family_scores(prompt: str) -> Counter:
    words = _words(prompt)
    scores = Counter()
    for family, kws in _FAMILY_KEYWORDS.items():
        scores[family] = sum(1 for kw in kws if kw in words or kw in (prompt or "").lower())
    if not any(scores.values()):
        scores["saas-productivity"] = 1
        scores["marketing-brand"] = 1
    return scores


def classify_inspiration_family(prompt: str, history=None, rng=None) -> str:
    rng = rng or random.Random()
    scores = _family_scores(prompt)
    ranked = sorted(scores, key=lambda f: (scores[f], rng.random()), reverse=True)
    recent = [h.get("inspiration_family") for h in (history or [])[-3:] if isinstance(h, dict)]
    if len(recent) == 3 and len(set(recent)) == 1:
        ranked = [f for f in ranked if f != recent[0]] or ranked
    top = [f for f in ranked if scores[f] == scores[ranked[0]]]
    return rng.choice(top or ranked or ["saas-productivity"])


def _reference_score(ref: dict, prompt_words: set[str], family: str, rng) -> float:
    cats = _FAMILY_CATEGORY_WEIGHTS.get(family, [ref["category"]])
    score = 0.0
    if ref["category"] in cats:
        score += 8 - cats.index(ref["category"])
    if ref["design_family"] == family:
        score += 4
    score += sum(1.5 for d in ref.get("best_for_domains", []) if d in prompt_words)
    score += rng.random()
    return score


def _safe_selected(ref: dict) -> dict:
    return {
        "name": ref["name"],
        "category": ref["category"],
        "design_family": ref["design_family"],
    }


def _merge_dna(refs: list[dict], family: str) -> dict:
    def top_list(field, limit=5):
        c = Counter()
        for r in refs:
            vals = r.get(field, [])
            if not isinstance(vals, list):
                vals = [vals]
            c.update(vals)
        return [x for x, _n in c.most_common(limit)]

    def top_value(field):
        vals = []
        for r in refs:
            v = r.get(field)
            if v:
                vals.append(v)
        return Counter(vals).most_common(1)[0][0] if vals else ""

    cats = list(dict.fromkeys(r["category"] for r in refs))
    return {
        "source": "curated",
        "inspiration_family": family,
        "reference_categories": cats,
        "hero_patterns": top_list("hero_patterns"),
        "navigation_patterns": top_list("navigation_patterns"),
        "section_patterns": top_list("section_patterns", 6),
        "card_patterns": top_list("card_patterns"),
        "typography_style": top_value("typography_style"),
        "spacing_style": top_value("spacing_style"),
        "color_palette_family": top_value("color_palette_family"),
        "image_strategy": top_value("image_strategy"),
        "CTA_patterns": top_list("CTA_patterns"),
        "footer_patterns": top_list("footer_patterns"),
    }


def select_curated_inspiration(prompt: str, history=None, max_refs: int = 8, rng=None) -> dict:
    rng = rng or random.Random()
    family = classify_inspiration_family(prompt, history=history, rng=rng)
    prompt_words = _words(prompt)
    ranked = sorted(
        CURATED_REFERENCES,
        key=lambda r: _reference_score(r, prompt_words, family, rng),
        reverse=True,
    )
    span = max(1, min(5, max_refs - 2))
    count = max(3, min(max_refs, 3 + rng.randrange(0, span)))
    selected = ranked[:count]
    dna = _merge_dna(selected, family)
    return {
        "mode": "curated",
        "inspiration_family": family,
        "selected_inspirations": [_safe_selected(r) for r in selected],
        "inspiration_dna": dna,
        "online_research": {"ok": False, "reason": "disabled"},
    }


def _merge_online(curated: dict, online: dict, requested_mode: str = "hybrid") -> dict:
    if not online or not online.get("ok"):
        out = dict(curated)
        if requested_mode in {"hybrid", "online"}:
            out["mode"] = f"{requested_mode}-fallback"
        if online:
            out["online_research"] = online
        return out
    merged = dict(curated)
    dna = dict(curated.get("inspiration_dna") or {})
    online_dna = online.get("design_dna") or {}
    for key in ("hero_patterns", "navigation_patterns", "section_patterns", "card_patterns", "CTA_patterns", "footer_patterns"):
        vals = []
        for v in list(dna.get(key) or []) + list(online_dna.get(key) or []):
            if v and v not in vals:
                vals.append(v)
        dna[key] = vals[:6]
    for key in ("typography_style", "spacing_style", "color_palette_family", "image_strategy"):
        if online_dna.get(key):
            dna[key] = online_dna[key]
    dna["source"] = "hybrid"
    merged["mode"] = "hybrid"
    merged["inspiration_dna"] = dna
    merged["online_research"] = online
    return merged


def select_inspiration(prompt: str, history=None, max_refs: int = 8, rng=None) -> dict:
    """Select local inspiration, optionally merging online abstract design DNA.

    This is safe to call in the hot generation path: online research is skipped
    by default and failures fall back to the local curated library.
    """
    rng = rng or random.Random()
    curated = select_curated_inspiration(prompt, history=history, max_refs=max_refs, rng=rng)
    mode = (os.getenv("DESIGN_INSPIRATION_MODE") or "curated").strip().lower()
    enabled = (os.getenv("DESIGN_RESEARCH_ENABLED") or "false").strip().lower() in {"1", "true", "yes", "on"}
    if mode == "curated" or not enabled:
        return curated
    try:
        from app import design_research
        online = design_research.fetch_online_design_dna(prompt)
    except Exception as exc:
        online = {"ok": False, "reason": str(exc)[:120]}
    if mode == "online" and online.get("ok"):
        out = dict(curated)
        out["mode"] = "online"
        out["online_research"] = online
        out["inspiration_dna"] = online.get("design_dna") or curated["inspiration_dna"]
        return out
    return _merge_online(curated, online, requested_mode=mode)


def apply_inspiration_to_genome(genome: dict, inspiration: dict, rng=None) -> dict:
    rng = rng or random.Random()
    genome = dict(genome or {})
    inspiration = inspiration or {}
    family = inspiration.get("inspiration_family") or "saas-productivity"
    dna = inspiration.get("inspiration_dna") or {}
    bias = _GENOME_BIAS_BY_FAMILY.get(family) or _GENOME_BIAS_BY_FAMILY["saas-productivity"]

    def choose(axis, fallback=None):
        vals = list(bias.get(axis) or [])
        if not vals:
            return fallback
        return rng.choice(vals)

    for axis in ("hero_variant", "nav_variant", "card_style", "layout_rhythm",
                 "image_strategy", "cta_placement", "section_strategy",
                 "dashboard_style", "crud_style", "visual_style"):
        val = choose(axis)
        if val:
            genome[axis] = val

    seq = list(bias.get("section_variants") or dna.get("section_patterns") or [])
    if seq:
        allowed = {"feature cards", "icon grid", "split image/text", "stats band", "timeline", "portal preview", "gallery", "FAQ", "CTA"}
        seq = [x for x in seq if x in allowed]
        if seq:
            genome["section_variants"] = seq[:5]
            genome["section_variant"] = seq[0]

    genome["inspiration_family"] = family
    genome["selected_inspirations"] = list(inspiration.get("selected_inspirations") or [])
    genome["inspiration_dna"] = dna
    genome["color_palette_family"] = dna.get("color_palette_family", "")
    genome["typography_style"] = dna.get("typography_style", "")
    genome["spacing_style"] = dna.get("spacing_style", "")
    genome["footer_style"] = (dna.get("footer_patterns") or ["product footer"])[0]
    genome["inspiration_mode"] = inspiration.get("mode", "curated")
    genome["online_research"] = inspiration.get("online_research", {"ok": False})
    return genome
