"""V2 pipeline core: each generation produces a COMPLETE Next.js app.

- `create_project` copies the pre-installed `next_scaffold/` (node_modules is
  shared into the project via a Windows junction - instant, no npm install).
- `write_status` drives the studio's gated preview: the UI shows ONLY these
  phases and never the prototype itself until phase == "done".
- `write_site` / `write_theme` / `write_db` parametrize the deterministic
  scaffold (shells read src/lib/site.js; shadcn tokens in src/theme.css;
  data/db.json is the local database the built-in API serves).
- `run_build` runs `next build` and returns (ok, error_excerpt).
"""
import json
import os
import re
import shutil
import subprocess
import time

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAFFOLD = os.path.join(BACKEND_DIR, "next_scaffold")

# Phases the studio is allowed to show the user (hidden QA reports as "qa").
PHASES = ("planning", "pages", "images", "qa", "building", "done", "error")


def write_status(out_dir: str, phase: str, detail: str = "") -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "status.json"), "w", encoding="utf-8") as f:
        json.dump({"phase": phase, "detail": detail, "ts": time.time()}, f)


def read_status(out_dir: str) -> dict:
    try:
        with open(os.path.join(out_dir, "status.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"phase": "planning", "detail": ""}


def create_project(out_dir: str) -> None:
    """Copy the scaffold (sans node_modules/.next) and junction node_modules."""
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir, ignore_errors=True)
    shutil.copytree(SCAFFOLD, out_dir, ignore=shutil.ignore_patterns("node_modules", ".next", "out"))
    link = os.path.join(out_dir, "node_modules")
    target = os.path.join(SCAFFOLD, "node_modules")
    subprocess.run(["cmd", "/c", "mklink", "/J", link, target], capture_output=True, shell=False)
    if not os.path.exists(link):  # junction failed -> fall back to a copy (slow but works)
        shutil.copytree(target, link)


def _js(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def write_site(out_dir: str, app_name: str, tagline: str, marketing_links, sidebar_links, entities_meta, roles, styles=None, auth=True) -> None:
    src = (
        "// Site configuration - generated per project. The deterministic shells\n"
        "// (Navbar/Sidebar/layouts) read everything from here.\n"
        "export const site = {\n"
        f"  appName: {json.dumps(str(app_name)[:40])},\n"
        f"  tagline: {json.dumps(str(tagline)[:120])},\n"
        f"  auth: {json.dumps(bool(auth))},\n"
        f"  marketingLinks: {_js(marketing_links)},\n"
        f"  sidebarLinks: {_js(sidebar_links)},\n"
        f"  entities: {_js(entities_meta)},\n"
        f"  roles: {_js(list(roles))},\n"
        f"  styles: {_js(styles or {})},\n"
        "};\n"
    )
    with open(os.path.join(out_dir, "src", "lib", "site.js"), "w", encoding="utf-8") as f:
        f.write(src)


# Accent family -> shadcn-style HSL token sets (primary + ring).
ACCENT_HSL = {
    "cyan":    ("192 91% 36%", "192 91% 36%"),
    "blue":    ("221 83% 53%", "221 83% 53%"),
    "indigo":  ("239 84% 67%", "239 84% 67%"),
    "violet":  ("258 90% 66%", "258 90% 66%"),
    "fuchsia": ("293 69% 49%", "293 69% 49%"),
    "rose":    ("347 77% 50%", "347 77% 50%"),
    "emerald": ("160 84% 39%", "160 84% 39%"),
    "lime":    ("84 81% 44%", "84 81% 44%"),
    "amber":   ("38 92% 50%", "38 92% 50%"),
    "slate":   ("215 25% 27%", "215 25% 27%"),
}


# --- PHASE 3: Theme & UX Architect ---------------------------------------
# Each of the 4 paradigms re-skins the WHOLE app from one file: a surface
# palette (overrides the shadcn :root tokens) PLUS a scoped "texture" block
# that retrofits the look onto the deterministic shells (borders, radius,
# shadow, blur, glow). The accent family is independent, so paradigm x accent
# x fonts gives a genuinely different design every run.
PARADIGMS = {
    "minimal": {
        "class": "paradigm-minimal",
        "tokens": {
            "--background": "0 0% 100%", "--foreground": "240 10% 6%",
            "--card": "0 0% 100%", "--card-foreground": "240 10% 6%",
            "--popover": "0 0% 100%", "--popover-foreground": "240 10% 6%",
            "--secondary": "240 5% 96%", "--secondary-foreground": "240 6% 10%",
            "--muted": "240 5% 96%", "--muted-foreground": "240 4% 46%",
            "--accent": "240 5% 96%", "--accent-foreground": "240 6% 10%",
            "--border": "240 6% 90%", "--input": "240 6% 90%", "--radius": "0.5rem",
        },
        "texture": (
            ".paradigm-minimal [class*='shadow']{box-shadow:0 1px 2px hsl(240 6% 10% / .04),0 1px 3px hsl(240 6% 10% / .06) !important}\n"
            ".paradigm-minimal h1,.paradigm-minimal h2{letter-spacing:-.02em}\n"
        ),
    },
    "neo-brutalism": {
        "class": "paradigm-neo",
        "tokens": {
            "--background": "47 92% 95%", "--foreground": "0 0% 7%",
            "--card": "0 0% 100%", "--card-foreground": "0 0% 7%",
            "--popover": "0 0% 100%", "--popover-foreground": "0 0% 7%",
            "--secondary": "47 70% 88%", "--secondary-foreground": "0 0% 7%",
            "--muted": "47 60% 90%", "--muted-foreground": "0 0% 30%",
            "--accent": "47 70% 88%", "--accent-foreground": "0 0% 7%",
            "--border": "0 0% 7%", "--input": "0 0% 7%", "--ring": "0 0% 7%", "--radius": "0rem",
        },
        "texture": (
            ".paradigm-neo [class*='rounded']{border-radius:3px !important}\n"
            ".paradigm-neo button,.paradigm-neo input,.paradigm-neo select,.paradigm-neo textarea,"
            ".paradigm-neo [class*='rounded-xl'],.paradigm-neo [class*='rounded-2xl'],.paradigm-neo [class*='rounded-3xl'],"
            ".paradigm-neo [class*='border']{border:2.5px solid hsl(var(--foreground)) !important}\n"
            ".paradigm-neo button,.paradigm-neo [class*='rounded-xl'],.paradigm-neo [class*='rounded-2xl'],"
            ".paradigm-neo [class*='rounded-3xl']{box-shadow:5px 5px 0 0 hsl(var(--foreground)) !important}\n"
            ".paradigm-neo h1,.paradigm-neo h2,.paradigm-neo h3{font-weight:800 !important;letter-spacing:-.01em}\n"
            ".paradigm-neo input:focus,.paradigm-neo select:focus{outline:none;box-shadow:5px 5px 0 0 hsl(var(--primary)) !important}\n"
        ),
    },
    "glassmorphism": {
        "class": "paradigm-glass",
        "tokens": {
            "--background": "222 32% 96%", "--foreground": "230 28% 14%",
            "--card": "0 0% 100%", "--card-foreground": "230 28% 14%",
            "--popover": "0 0% 100%", "--popover-foreground": "230 28% 14%",
            "--secondary": "222 30% 92%", "--secondary-foreground": "230 28% 14%",
            "--muted": "222 26% 92%", "--muted-foreground": "230 12% 42%",
            "--accent": "222 30% 92%", "--accent-foreground": "230 28% 14%",
            "--border": "230 30% 88%", "--input": "230 30% 88%", "--radius": "1rem",
        },
        "texture": (
            "body.paradigm-glass{background-image:"
            "radial-gradient(at 0% 0%, hsl(var(--primary) / .20), transparent 45%),"
            "radial-gradient(at 100% 0%, hsl(285 85% 70% / .18), transparent 45%),"
            "radial-gradient(at 50% 100%, hsl(190 85% 60% / .16), transparent 45%) !important;background-attachment:fixed}\n"
            ".paradigm-glass [class*='rounded-xl']:not(a):not(button),.paradigm-glass [class*='rounded-2xl']:not(a):not(button),.paradigm-glass [class*='rounded-3xl']:not(a):not(button){"
            "background:hsla(0,0%,100%,.55) !important;backdrop-filter:blur(14px) saturate(150%);"
            "-webkit-backdrop-filter:blur(14px) saturate(150%);border:1px solid hsla(0,0%,100%,.7) !important;"
            "box-shadow:0 8px 32px hsla(230,45%,28%,.12) !important}\n"
        ),
    },
    "cyberpunk": {
        "class": "paradigm-cyber",
        "tokens": {
            "--background": "240 30% 7%", "--foreground": "180 90% 92%",
            "--card": "245 34% 11%", "--card-foreground": "180 70% 92%",
            "--popover": "245 34% 11%", "--popover-foreground": "180 70% 92%",
            "--secondary": "245 30% 16%", "--secondary-foreground": "180 70% 92%",
            "--muted": "245 26% 17%", "--muted-foreground": "220 25% 68%",
            "--accent": "245 30% 18%", "--accent-foreground": "180 90% 92%",
            "--border": "280 60% 50%", "--input": "245 30% 22%", "--radius": "0.4rem",
        },
        "texture": (
            "body.paradigm-cyber{background-image:"
            "radial-gradient(at 15% 0%, hsl(var(--primary) / .14), transparent 45%),"
            "radial-gradient(at 90% 100%, hsl(300 90% 60% / .12), transparent 45%) !important}\n"
            ".paradigm-cyber [class*='rounded-xl']:not(a):not(button),.paradigm-cyber [class*='rounded-2xl']:not(a):not(button),.paradigm-cyber [class*='rounded-3xl']:not(a):not(button){"
            "background:hsl(245 34% 11% / .82) !important;border:1px solid hsl(var(--primary) / .45) !important;"
            "box-shadow:0 0 0 1px hsl(var(--primary) / .12),0 0 20px hsl(var(--primary) / .22) !important}\n"
            ".paradigm-cyber h1,.paradigm-cyber h2{text-shadow:0 0 20px hsl(var(--primary) / .5)}\n"
            ".paradigm-cyber [class*='border']{border-color:hsl(var(--primary) / .35) !important}\n"
        ),
    },
}


def paradigm_class(theme_style: str) -> str:
    return PARADIGMS.get(theme_style, PARADIGMS["minimal"])["class"]


def write_theme(out_dir: str, accent_family: str, font_display: str, font_body: str,
                theme_style: str = "minimal") -> None:
    primary, ring = ACCENT_HSL.get(accent_family, ACCENT_HSL["indigo"])
    para = PARADIGMS.get(theme_style, PARADIGMS["minimal"])
    toks = dict(para["tokens"])
    toks["--primary"] = primary
    toks["--primary-foreground"] = "0 0% 100%"
    toks.setdefault("--ring", ring)
    toks["--font-display"] = f"'{font_display}'"
    toks["--font-body"] = f"'{font_body}'"
    root = "".join(f"  {k}: {v};\n" for k, v in toks.items())
    css = (
        f"/* Per-project theme - paradigm '{theme_style}', accent '{accent_family}' */\n"
        ":root {\n" + root + "}\n\n"
        "/* paradigm texture (scoped to the body class set in layout.jsx) */\n"
        + para["texture"]
    )
    with open(os.path.join(out_dir, "src", "theme.css"), "w", encoding="utf-8") as f:
        f.write(css)


def _meta_safe(s: str, limit: int) -> str:
    """Value lands inside a single-quoted JS string literal: straight quotes
    become typographic ones (U+2018/U+2019 - looks better AND can't break the
    string), backslashes/newlines dropped."""
    s = str(s).replace("\\", "").replace("\n", " ")
    s = s.replace("'", "’").replace('"', "”")
    return s[:limit]


def write_layout_meta(out_dir: str, app_title: str, description: str, fonts_url: str,
                      theme_style: str = "minimal") -> None:
    path = os.path.join(out_dir, "src", "app", "layout.jsx")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    src = (src.replace("__APP_TITLE__", _meta_safe(app_title, 60))
              .replace("__APP_DESCRIPTION__", _meta_safe(description, 140))
              .replace("__FONTS_URL__", fonts_url)
              .replace("__PARADIGM_CLASS__", paradigm_class(theme_style)))
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)


def seed_placeholder_images(out_dir: str) -> int:
    """100% image guarantee: copy the bundled gradient placeholder into EVERY
    image slot before build, so the preview never shows an empty card. The
    background AI photos overwrite them; any slot whose AI image fails simply
    keeps the tasteful placeholder instead of rendering blank."""
    from app.fooocus_images import V2_NAMES
    assets = os.path.join(out_dir, "public", "assets")
    os.makedirs(assets, exist_ok=True)
    ph = os.path.join(assets, "placeholder.jpg")
    if not os.path.exists(ph):   # not copied with the scaffold? pull it from the source
        src_ph = os.path.join(SCAFFOLD, "public", "assets", "placeholder.jpg")
        if os.path.exists(src_ph):
            try:
                shutil.copyfile(src_ph, ph)
            except OSError:
                pass
    if not os.path.exists(ph):
        return 0
    n = 0
    for name in V2_NAMES:
        dst = os.path.join(assets, name)
        if not os.path.exists(dst):
            try:
                shutil.copyfile(ph, dst)
                n += 1
            except OSError:
                pass
    return n


def write_db(out_dir: str, db: dict) -> None:
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    with open(os.path.join(out_dir, "data", "db.json"), "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def write_page(out_dir: str, route_dir: str, code: str) -> str:
    """Write src/app/<route_dir>/page.jsx (route_dir like '(marketing)/features')."""
    folder = os.path.join(out_dir, "src", "app", *route_dir.split("/"))
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "page.jsx")
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    return path


# --- PHASE 1-2: domain marketing pages -----------------------------------
# The Deep Research blueprint decides the secondary public pages (a school gets
# Admissions / Curriculum / Faculty - NOT Features / About / Contact). These
# deterministic, build-safe templates render the page named by the blueprint.
def _txt(s, limit=120):
    s = str(s).replace("{", "").replace("}", "").replace("<", "").replace(">", "")
    return s[:limit]


def _img_block(asset, h, extra=""):
    """A bg-image tile that degrades to a tinted block when the asset is absent
    (FAST runs / partial image sets) - never a broken-image icon."""
    return (
        f'<div className="{h} w-full overflow-hidden rounded-2xl bg-gradient-to-br '
        f'from-primary/15 to-primary/5 {extra}" '
        f'style={{{{ backgroundImage: "url(/assets/{asset})", backgroundSize: "cover", '
        f'backgroundPosition: "center" }}}} />'
    )


def _mk_hero(title, sub, app_name):
    return (
        '      <section data-component-id="hero" data-component-label="Page hero" className="border-b bg-muted/30">\n'
        '        <div className="mx-auto max-w-6xl px-6 py-20 md:py-28">\n'
        '          <p className="mb-3 text-sm font-semibold uppercase tracking-wider text-primary">'
        + _txt(app_name, 40) + '</p>\n'
        '          <h1 className="font-display text-4xl font-bold tracking-tight md:text-6xl">'
        + _txt(title, 50) + '</h1>\n'
        '          <p className="mt-5 max-w-2xl text-lg text-muted-foreground">' + _txt(sub, 180) + '</p>\n'
        '        </div>\n'
        '      </section>\n'
    )


def _features_section(features):
    feats = (features or [])[:6] or ["Fast and reliable", "Secure by design", "Built for teams"]
    cards = ""
    for i, f in enumerate(feats):
        cards += (
            '          <div className="rounded-2xl border bg-card p-6 shadow-sm">\n'
            '            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10 text-primary">'
            '<CheckCircle2 className="h-5 w-5" /></div>\n'
            '            <h3 className="font-display text-lg font-semibold">' + _txt(f, 40) + '</h3>\n'
            '            <p className="mt-2 text-sm text-muted-foreground">'
            + _txt("Everything you need for " + str(f).lower() + ", built in from day one.", 140) + '</p>\n'
            '          </div>\n'
        )
    return (
        '      <section className="mx-auto max-w-6xl px-6 py-20">\n'
        '        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">\n'
        + cards +
        '        </div>\n'
        '      </section>\n'
    )


def _stats_section():
    return (
        '      <section className="border-y bg-muted/30">\n'
        '        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-8 px-6 py-14 md:grid-cols-4">\n'
        + "".join(
            '          <div><p className="font-display text-4xl font-bold text-primary">' + n +
            '</p><p className="mt-1 text-sm text-muted-foreground">' + l + '</p></div>\n'
            for n, l in (("12k+", "Active users"), ("99.9%", "Uptime"), ("4.9/5", "Rating"), ("24/7", "Support"))
        ) +
        '        </div>\n      </section>\n'
    )


def _gallery_section():
    tiles = ["gallery1.jpg", "feature1.jpg", "gallery2.jpg", "about1.jpg", "gallery3.jpg", "feature2.jpg"]
    body = "".join('          ' + _img_block(t, "h-56") + "\n" for t in tiles)
    return (
        '      <section className="mx-auto max-w-6xl px-6 py-20">\n'
        '        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">\n'
        + body +
        '        </div>\n      </section>\n'
    )


def _pricing_section(app_name):
    tiers = [("Starter", "$0", ["Up to 3 users", "Core features", "Community support"]),
             ("Pro", "$29", ["Unlimited users", "Advanced analytics", "Priority support"]),
             ("Enterprise", "Custom", ["SSO & audit logs", "Dedicated manager", "Custom SLAs"])]
    cols = ""
    for name, price, feats in tiers:
        pop = name == "Pro"
        items = "".join(
            '              <li className="flex items-center gap-2 text-sm"><CheckCircle2 className="h-4 w-4 text-primary" />'
            + _txt(x, 40) + '</li>\n' for x in feats)
        cols += (
            '          <div className="rounded-2xl border ' + ('border-primary shadow-lg' if pop else 'bg-card') + ' p-7">\n'
            '            <h3 className="font-display text-lg font-semibold">' + name + '</h3>\n'
            '            <p className="mt-3"><span className="font-display text-4xl font-bold">' + price +
            '</span><span className="text-muted-foreground">/mo</span></p>\n'
            '            <ul className="mt-6 space-y-3">\n' + items + '            </ul>\n'
            '            <a href="/register" className="mt-7 block rounded-xl '
            + ('bg-primary text-primary-foreground' if pop else 'border') +
            ' px-4 py-2.5 text-center text-sm font-semibold">Get started</a>\n'
            '          </div>\n'
        )
    return (
        '      <section className="mx-auto max-w-6xl px-6 py-20">\n'
        '        <div className="grid gap-6 md:grid-cols-3">\n' + cols + '        </div>\n      </section>\n'
    )


def _cta_section(app_name):
    return (
        '      <section className="mx-auto max-w-6xl px-6 pb-24">\n'
        '        <div className="rounded-3xl bg-primary px-8 py-14 text-center text-primary-foreground">\n'
        '          <h2 className="font-display text-3xl font-bold">Ready to get started?</h2>\n'
        '          <p className="mx-auto mt-3 max-w-xl opacity-90">Join ' + _txt(app_name, 40) +
        ' today and see the difference.</p>\n'
        '          <a href="/register" className="mt-7 inline-block rounded-xl bg-background px-6 py-3 '
        'font-semibold text-foreground">Create your account</a>\n'
        '        </div>\n      </section>\n'
    )


def _contact_page_jsx(title, app_name):
    return (
        "'use client';\n"
        "import * as React from 'react';\n"
        "import { Mail, MapPin, Phone } from 'lucide-react';\n\n"
        "export default function Page() {\n"
        "  const [sent, setSent] = React.useState(false);\n"
        "  return (\n"
        '    <div>\n'
        + _mk_hero(title, "We would love to hear from you. Reach out and our team will respond shortly.", app_name) +
        '      <section className="mx-auto grid max-w-6xl gap-10 px-6 py-20 md:grid-cols-2">\n'
        '        <div className="space-y-6">\n'
        + "".join(
            '          <div className="flex items-start gap-4"><span className="flex h-11 w-11 items-center justify-center '
            'rounded-xl bg-primary/10 text-primary"><' + ic + ' className="h-5 w-5" /></span>'
            '<div><p className="font-semibold">' + lab + '</p>'
            '<p className="text-sm text-muted-foreground">' + val + '</p></div></div>\n'
            for ic, lab, val in (("Mail", "Email", "hello@example.com"),
                                  ("Phone", "Phone", "+1 (555) 012-3456"),
                                  ("MapPin", "Office", "100 Market St, Suite 200"))
        ) +
        '        </div>\n'
        '        <form onSubmit={(e) => { e.preventDefault(); setSent(true); }} className="rounded-2xl border bg-card p-6 shadow-sm">\n'
        '          {sent ? (\n'
        '            <div className="py-10 text-center"><p className="font-display text-xl font-semibold">Thank you!</p>'
        '<p className="mt-2 text-sm text-muted-foreground">Your message has been sent.</p></div>\n'
        '          ) : (<>\n'
        '            <div className="space-y-4">\n'
        '              <input required placeholder="Your name" className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm" />\n'
        '              <input required type="email" placeholder="Email address" className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm" />\n'
        '              <textarea required rows={5} placeholder="How can we help?" className="w-full rounded-xl border bg-background px-4 py-2.5 text-sm" />\n'
        '              <button className="w-full rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground">Send message</button>\n'
        '            </div>\n'
        '          </>)}\n'
        '        </form>\n'
        '      </section>\n'
        '    </div>\n'
        '  );\n}\n'
    )


def _marketing_page_jsx(page, app_name, key_features, tagline):
    """Static server-component page for one blueprint marketing page."""
    title = page.get("name", "Info")
    tpl = page.get("template", "content")
    if tpl == "contact":
        return _contact_page_jsx(title, app_name)
    sub = tagline or f"Discover what makes {app_name} different."
    body = _mk_hero(title, sub, app_name)
    if tpl == "pricing":
        body += _pricing_section(app_name)
    elif tpl == "gallery":
        body += _gallery_section() + _stats_section()
    else:  # features / about / content
        body += _features_section(key_features) + _stats_section()
    body += _cta_section(app_name)
    return (
        "import { CheckCircle2 } from 'lucide-react';\n\n"
        "export default function Page() {\n"
        "  return (\n"
        "    <div>\n" + body + "    </div>\n"
        "  );\n}\n"
    )


_RESERVED_MK = {"", "home", "index", "dashboard", "login", "register", "logout", "e", "entity",
                "workspace", "notifications", "profile", "settings", "api", "assets", "auth", "admin"}


def write_marketing_pages(out_dir, pages, app_name, blueprint, ai_sections=False, section_order=None):
    """Write each blueprint marketing page under (marketing)/<slug>/page.jsx.
    Each page is composed from a domain-driven, VARIED section pack (see
    page_sections) so no two domains - or two pages - look alike. With
    ai_sections, Gemma writes each section's JSX (validated, else fallback).
    `section_order` (from the genome's section_strategy) reorders the default pack.
    Returns the list of written file paths."""
    from app import page_sections
    written, seen = [], set()
    for idx, p in enumerate(pages):
        slug = re.sub(r"[^a-z0-9-]+", "-", str(p.get("slug") or "").lower()).strip("-")[:32]
        if not slug or slug in _RESERVED_MK or slug in seen:   # never collide with app routes / landing
            continue
        seen.add(slug)
        if p.get("template") == "contact":
            src = _contact_page_jsx(p.get("name", "Contact"), app_name)
        else:
            src = page_sections.compose_marketing_page({**p, "slug": slug}, blueprint or {}, idx, app_name,
                                                       ai_sections, section_order)
        written.append(write_page(out_dir, f"(marketing)/{slug}", src))
    return written


def run_build(out_dir: str, timeout: int = 600):
    """`next build`; returns (ok, tail_of_output)."""
    p = subprocess.run(
        ["npm", "run", "build"],
        cwd=out_dir, capture_output=True, text=True, shell=True, timeout=timeout,
    )
    out = (p.stdout or "") + "\n" + (p.stderr or "")
    return p.returncode == 0, out[-4000:]


_ERR_FILE = re.compile(r"([./\\\w()\[\]-]+?[/\\](?:page|layout)\.jsx)")

def failing_page(build_output: str):
    """Best-effort extraction of the failing page path from next build output."""
    m = _ERR_FILE.search(build_output or "")
    return m.group(1).replace("\\", "/") if m else None


# ---------------------------------------------------------------- seeds (LLM)
_SEED_PROMPT = """You create realistic seed data for a {app_name} application.
Entities and their fields:
{entities_brief}

Output ONLY raw JSON in exactly this shape:
{{
  "users": [ {{ "name": "...", "email": "...", "password": "password123", "role": "<one of {roles}>" }} , ... one per role ],
  "<EntityName>": [ {{ "<field>": "<value>", ... }} , ... 12 to 15 rows ],
  ... one key per entity, EXACT entity names as given ...
}}
RULES: hand-written, realistic, domain-specific values (real-sounding names, titles,
prices, phone numbers, emails, ISO dates like 2026-03-14, varied statuses). Every row
unique. Status-like select fields use their given options. No placeholders, no
"Item 1", no lorem ipsum, no markdown - ONLY the JSON object."""


def generate_seeds(state) -> dict:
    """One small LLM call -> the local database. Deterministic fallback seeds on
    any failure, and ids/admin user are always enforced in Python."""
    from app.agents import get_llm, extract_json  # local import avoids cycles
    from langchain_core.prompts import ChatPromptTemplate

    entities = state.get("entities", [])
    roles = state.get("roles", ["Admin", "User"])
    brief = "\n".join(
        "- %s: fields %s" % (
            e.get("name"),
            ", ".join(
                f["name"] + (" (select: %s)" % "/".join(f.get("options", [])) if f.get("type") == "select" and f.get("options") else "")
                for f in e.get("fields", [])
            ) or "name",
        )
        for e in entities
    ) or "- Item: fields name, status"

    raw = {}
    try:
        chain = ChatPromptTemplate.from_messages([
            ("system", _SEED_PROMPT),
            ("user", "Generate the seed data now."),
        ]) | get_llm(temperature=0.4, num_predict=6144)
        raw = extract_json(chain.invoke({
            "app_name": state.get("app_name", "App"),
            "entities_brief": brief,
            "roles": ", ".join(roles),
        }).content)
    except Exception:
        raw = {}

    db = {}
    # users: always include the demo admin the login page advertises
    users = [u for u in (raw.get("users") or []) if isinstance(u, dict) and u.get("email")]
    have_roles = {u.get("role") for u in users}
    for r in roles:
        if r not in have_roles:
            users.append({"name": f"{r} User", "email": f"{r.lower()}@example.com", "password": "password123", "role": r})
    if not any(u.get("email") == "admin@example.com" for u in users):
        users.insert(0, {"name": "Admin", "email": "admin@example.com", "password": "password123", "role": roles[0] if roles else "Admin"})
    for i, u in enumerate(users):
        u.setdefault("id", f"u{i + 1}")
    db["users"] = users

    for e in entities:
        name = e.get("name", "Item")
        rows = raw.get(name)
        if not isinstance(rows, list):
            rows = []
        rows = [r for r in rows if isinstance(r, dict)]
        # Thin seed sets make lists/dashboards look empty - top up with
        # deterministic rows so every entity has at least 8.
        if len(rows) < 8:
            rows += _fallback_rows(e)[: 8 - len(rows) + 4]
        clean = []
        for i, r in enumerate(rows[:18]):
            r.setdefault("id", f"{name[:2].lower()}{i + 1}")
            clean.append(r)
        db[name] = clean
    return db


def _fallback_rows(entity) -> list:
    """Generic-but-presentable rows when the seed call fails."""
    fields = entity.get("fields", []) or [{"name": "name", "type": "text"}]
    out = []
    samples = ["Aurora", "Beacon", "Cedar", "Delta", "Ember", "Fable", "Garnet", "Harbor", "Iris", "Juniper", "Koa", "Luna"]
    for i in range(12):
        row = {}
        for f in fields:
            n, t = f.get("name", "name"), f.get("type", "text")
            if t == "number":
                row[n] = (i + 1) * 7
            elif t in ("date", "datetime-local"):
                row[n] = f"2026-0{(i % 9) + 1}-1{i % 3}"
            elif t == "select" and f.get("options"):
                row[n] = f["options"][i % len(f["options"])]
            elif n == "email":
                row[n] = f"{samples[i].lower()}@example.com"
            else:
                row[n] = f"{samples[i]} {n.replace('_', ' ').title()}"
        out.append(row)
    return out


def write_env(out_dir: str, project_id: str) -> bool:
    """Per-project .env.local: MongoDB URI from the backend's gitignored .env,
    database name = project id. Returns True when Mongo mode is configured."""
    uri = ""
    env_path = os.path.join(BACKEND_DIR, ".env")
    if os.path.exists(env_path):
        for line in open(env_path, encoding="utf-8"):
            if line.startswith("MONGODB_URI_TEMPLATE="):
                uri = line.split("=", 1)[1].strip()
    if not uri:
        return False
    with open(os.path.join(out_dir, ".env.local"), "w", encoding="utf-8") as f:
        f.write(f"MONGODB_URI={uri}\nMONGODB_DB={project_id}\n")
    return True


def run_seed(out_dir: str, timeout: int = 60) -> str:
    p = subprocess.run(["node", "scripts/seed.mjs"], cwd=out_dir,
                       capture_output=True, text=True, shell=True, timeout=timeout)
    return ((p.stdout or "") + (p.stderr or "")).strip()[-300:]
