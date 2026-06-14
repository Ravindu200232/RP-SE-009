"""
Design Token Theme Engine for the standalone prototype generator.

ONE theme is picked per generation (random) and applied uniformly:
  - the HTML shell uses its background + fonts,
  - the page/sidebar coder prompts are told to use these EXACT Tailwind classes.

Only standard Tailwind palette classes are used, so everything works with the
Tailwind CDN with no extra config. This is what makes each project come out in a
different design instead of the same navy/glass look every time.
"""

import random

DESIGN_THEMES = [
    {
        "name": "Glassmorphism Aurora",
        "mode": "dark",
        "font_display": "Sora",
        "font_body": "Inter",
        "page_background": "bg-gradient-to-br from-slate-950 via-indigo-950 to-purple-950 text-slate-100",
        "card": "backdrop-blur-xl bg-white/5 border border-white/10 rounded-2xl shadow-2xl",
        "primary_button": "bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg shadow-cyan-500/20",
        "secondary_button": "bg-white/5 border border-white/10 hover:bg-white/10 text-slate-100",
        "input": "bg-white/5 border border-white/10 rounded-xl text-white placeholder-slate-400 focus:ring-2 focus:ring-cyan-500 focus:outline-none",
        "text_primary": "text-white",
        "text_muted": "text-slate-400",
        "accent": "text-cyan-400",
        "sidebar": "bg-white/5 backdrop-blur-xl border-r border-white/10 text-slate-100",
    },
    {
        "name": "Cyberpunk Neon",
        "mode": "dark",
        "font_display": "Orbitron",
        "font_body": "Rajdhani",
        "page_background": "bg-black text-zinc-100",
        "card": "bg-zinc-900/80 border border-fuchsia-500/30 rounded-lg shadow-[0_0_25px_-5px_rgba(217,70,239,0.4)]",
        "primary_button": "bg-fuchsia-600 hover:bg-fuchsia-500 text-white shadow-[0_0_18px_-2px_rgba(217,70,239,0.7)]",
        "secondary_button": "bg-transparent border border-lime-400/50 text-lime-300 hover:bg-lime-400/10",
        "input": "bg-zinc-950 border border-fuchsia-500/30 rounded-md text-lime-200 placeholder-zinc-500 focus:ring-2 focus:ring-fuchsia-500 focus:outline-none",
        "text_primary": "text-zinc-50",
        "text_muted": "text-zinc-500",
        "accent": "text-lime-400",
        "sidebar": "bg-zinc-950 border-r border-fuchsia-500/20 text-zinc-200",
    },
    {
        "name": "Nordic Minimalist",
        "mode": "light",
        "font_display": "Poppins",
        "font_body": "Inter",
        "page_background": "bg-slate-50 text-slate-800",
        "card": "bg-white border border-slate-200 rounded-2xl shadow-sm",
        "primary_button": "bg-blue-600 hover:bg-blue-700 text-white shadow-sm",
        "secondary_button": "bg-white border border-slate-200 hover:bg-slate-50 text-slate-700",
        "input": "bg-white border border-slate-300 rounded-lg text-slate-800 placeholder-slate-400 focus:ring-2 focus:ring-blue-500 focus:outline-none",
        "text_primary": "text-slate-900",
        "text_muted": "text-slate-500",
        "accent": "text-blue-600",
        "sidebar": "bg-white border-r border-slate-200 text-slate-700",
    },
    {
        "name": "Slate Corporate",
        "mode": "light",
        "font_display": "IBM Plex Sans",
        "font_body": "IBM Plex Sans",
        "page_background": "bg-slate-100 text-slate-800",
        "card": "bg-white border border-slate-200 rounded-xl shadow-md",
        "primary_button": "bg-slate-800 hover:bg-slate-900 text-white shadow",
        "secondary_button": "bg-slate-100 border border-slate-300 hover:bg-slate-200 text-slate-700",
        "input": "bg-slate-50 border border-slate-300 rounded-md text-slate-800 placeholder-slate-400 focus:ring-2 focus:ring-slate-500 focus:outline-none",
        "text_primary": "text-slate-900",
        "text_muted": "text-slate-500",
        "accent": "text-indigo-600",
        "sidebar": "bg-slate-900 border-r border-slate-800 text-slate-200",
    },
    {
        "name": "Emerald Eco",
        "mode": "light",
        "font_display": "Quicksand",
        "font_body": "Nunito",
        "page_background": "bg-emerald-50 text-stone-800",
        "card": "bg-white border border-emerald-100 rounded-3xl shadow-sm",
        "primary_button": "bg-emerald-600 hover:bg-emerald-700 text-white shadow",
        "secondary_button": "bg-white border border-emerald-200 hover:bg-emerald-50 text-emerald-700",
        "input": "bg-white border border-emerald-200 rounded-xl text-stone-800 placeholder-stone-400 focus:ring-2 focus:ring-emerald-500 focus:outline-none",
        "text_primary": "text-stone-900",
        "text_muted": "text-stone-500",
        "accent": "text-emerald-600",
        "sidebar": "bg-emerald-700 border-r border-emerald-600 text-emerald-50",
    },
    {
        "name": "Sunset Coral",
        "mode": "light",
        "font_display": "Fraunces",
        "font_body": "Inter",
        "page_background": "bg-gradient-to-br from-orange-50 to-rose-50 text-stone-800",
        "card": "bg-white/80 backdrop-blur border border-rose-100 rounded-3xl shadow-lg shadow-rose-200/40",
        "primary_button": "bg-gradient-to-r from-rose-500 to-orange-500 hover:from-rose-600 hover:to-orange-600 text-white shadow",
        "secondary_button": "bg-white border border-rose-200 hover:bg-rose-50 text-rose-600",
        "input": "bg-white border border-rose-200 rounded-xl text-stone-800 placeholder-stone-400 focus:ring-2 focus:ring-rose-400 focus:outline-none",
        "text_primary": "text-stone-900",
        "text_muted": "text-stone-500",
        "accent": "text-rose-500",
        "sidebar": "bg-white/70 backdrop-blur border-r border-rose-100 text-stone-700",
    },
]


# =========================================================================
# LAYOUT VARIANTS — randomly combined per project so no two prototypes share
# the same page architecture. Landing layouts distilled from the Figma
# community file "50 Landing page designs"; auth layouts from "50 Web Sign
# up/log in designs"; dashboard layouts from the local React admin templates
# (Mantis, Tabler, Argon/Star, Paper). Dashboard briefs contain __TILES__/
# __FIRST_NAME__/__FIRST_KEY__ tokens that planner.kind_brief fills in.
# =========================================================================
LANDING_LAYOUTS = [
    {"name": "editorial-center",
     "brief": ("HERO (editorial, centered): an eyebrow badge, then a HUGE centered display headline (text-5xl md:text-7xl font-bold "
               "tracking-tight, 2 lines, ONE key word in the accent color), a centered muted subline (max-w-2xl mx-auto), two CTAs "
               "(primary Link '/register' 'Get Started', secondary text-link '/login' with arrow). BELOW, full-width: "
               "<img src=\"assets/hero.jpg\" alt=\"\" className=\"rounded-3xl shadow-xl w-full max-h-[480px] object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />. "
               "Then sections in this order: numbered 01/02/03 feature trio (big muted number, bold title, 2-line text) -> stats strip (4 big numbers) "
               "-> pricing (3 tiers, middle highlighted) -> FAQ accordion (4 items, state) -> testimonials (2-3 quote cards, initials avatars) -> CTA band -> footer.")},
    {"name": "split-right-photo",
     "brief": ("HERO (split): grid lg:grid-cols-2 gap-10 items-center - LEFT: eyebrow, big display headline (accent word), muted paragraph, two CTAs, "
               "and a small 'Trusted by 2,000+ teams' caption row; RIGHT: relative container with a blurred accent-color circle div BEHIND (-z-10) and "
               "<img src=\"assets/hero.jpg\" alt=\"\" className=\"rounded-3xl shadow-2xl w-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />. "
               "Then: 6-card feature grid (icon tiles) -> full-width image band assets/feature.jpg (rounded-3xl h-72 object-cover, onError hide) -> "
               "stats strip -> pricing (3 tiers) -> FAQ accordion -> CTA band -> footer.")},
    {"name": "numbered-editorial",
     "brief": ("HERO (editorial 2-col): LEFT a giant 2-line display headline (accent word), RIGHT (self-end) a short muted paragraph + a text-link CTA to '/register'. "
               "BELOW: three numbered columns 01/02/03, EACH with a small photo on top "
               "(<img src=\"assets/hero.jpg\"/'assets/feature.jpg'/'assets/about.jpg' className=\"rounded-2xl h-40 w-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} alt=\"\" /> - a DIFFERENT one each), "
               "a bold title and 2 lines of text. Then: stats strip -> testimonials -> pricing (3 tiers) -> FAQ accordion -> CTA band -> footer.")},
    {"name": "color-block",
     "brief": ("HERO (color block): a full-width rounded-3xl band in the accent color/gradient (p-10 md:p-16, contrasting text) - grid lg:grid-cols-2: "
               "LEFT the display headline + subline + a WHITE/contrast primary button to '/register'; RIGHT "
               "<img src=\"assets/hero.jpg\" alt=\"\" className=\"rounded-2xl shadow-xl w-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} />. "
               "Then: 'How it works' 3 steps with numbered badges -> 6-card feature grid -> stats strip -> pricing -> FAQ accordion -> CTA band -> footer.")},
    {"name": "dark-product",
     "brief": ("HERO (dark product panel): a rounded-3xl bg-slate-900 text-white p-10 md:p-16 section (works on any theme) - grid lg:grid-cols-2 items-center: "
               "LEFT eyebrow in the accent color, big display headline, muted slate-300 subline, primary CTA + ghost CTA; RIGHT a relative container with "
               "<img src=\"assets/hero.jpg\" alt=\"\" className=\"rounded-2xl w-full object-cover opacity-90\" onError={(e)=>{e.currentTarget.style.display='none'}} /> "
               "and TWO small floating stat chips (absolute, top-right and bottom-left, bg-white/10 backdrop-blur rounded-xl px-4 py-2 - decorative, inside the relative box, NOT over text). "
               "Then: logos/social-proof row -> 6-card feature grid -> stats strip -> pricing -> FAQ accordion -> testimonials -> CTA band -> footer.")},
]

AUTH_LAYOUTS = [
    {"name": "brand-left",
     "brief": ("SPLIT-SCREEN, root <div className=\"min-h-screen flex\">: LEFT (hidden md:flex md:w-1/2 relative) brand panel - "
               "<img src=\"assets/auth.jpg\" alt=\"\" className=\"absolute inset-0 w-full h-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} /> "
               "+ overlay div (absolute inset-0 bg-gradient-to-t from-black/70 to-black/20) + bottom content (relative z-10 self-end p-10): app name in display font, "
               "one-line value proposition, a small quote card (quote + initials avatar + name). RIGHT (flex-1 flex items-center justify-center p-6) the form (max-w-sm w-full).")},
    {"name": "brand-right",
     "brief": ("SPLIT-SCREEN MIRRORED, root <div className=\"min-h-screen flex\">: LEFT (flex-1 flex items-center justify-center p-6) the form (max-w-sm w-full); "
               "RIGHT (hidden md:flex md:w-1/2 relative) brand panel - <img src=\"assets/auth.jpg\" alt=\"\" className=\"absolute inset-0 w-full h-full object-cover\" "
               "onError={(e)=>{e.currentTarget.style.display='none'}} /> + dark gradient overlay + (relative z-10 self-end p-10) app name, value line, and a 3-item benefits checklist with check icons.")},
    {"name": "cover-center",
     "brief": ("FULL-BLEED COVER, root <div className=\"min-h-screen relative flex items-center justify-center p-6\">: "
               "<img src=\"assets/auth.jpg\" alt=\"\" className=\"absolute inset-0 w-full h-full object-cover\" onError={(e)=>{e.currentTarget.style.display='none'}} /> "
               "+ overlay div (absolute inset-0 bg-black/60). The form card sits ON TOP (relative z-10, max-w-sm w-full, bg-white/95 backdrop-blur rounded-2xl shadow-2xl p-8). "
               "IMPORTANT - the card is WHITE, so EVERYTHING inside it must use EXPLICIT dark-on-white classes and NOT the theme's input/text classes: "
               "headings `text-slate-900`, labels/subtext `text-slate-600`, inputs `bg-white border border-slate-300 rounded-lg text-slate-900 placeholder-slate-400 focus:ring-2`, "
               "links in the theme accent. Only the primary button keeps the theme's primary classes. App name centered on top (with assets/logo.jpg h-10 w-10 rounded-xl, onError hide), then the form.")},
    {"name": "minimal-center",
     "brief": ("MINIMAL CENTERED, root <div className=\"min-h-screen flex items-center justify-center p-6\"> (theme page background, NO photo): "
               "a max-w-sm w-full themed card with a thin accent gradient bar across the top (h-1.5 rounded-t), the app name as a centered wordmark, "
               "a muted welcome line, then the form. Below the card a centered muted switch-link line.")},
]

DASHBOARD_LAYOUTS = [
    {"name": "mantis",
     "brief": ("LAYOUT (Mantis admin): (a) 'Dashboard' title row + subtitle with the user's name and today's date; "
               "(b) grid sm:grid-cols-2 lg:grid-cols-4 gap-6 of analytics stat cards - ONE PER REAL ENTITY: __TILES__. Each card: muted label, LIVE count as a big bold number, "
               "a small trend pill (rounded-full px-2 py-0.5 text-xs accent-tinted, varied fake % - one negative), muted caption; whole card = Link to its list route, hover shadow; "
               "(c) grid lg:grid-cols-3 gap-6: an 'Overview' card (lg:col-span-2) containing EXACTLY this bar-chart pattern with 12 varied values: "
               "const chart=[{m:'Jan',v:45},{m:'Feb',v:62},...12 months, values 20-95...]; then "
               "<div className=\"flex items-end gap-2 h-40\">{chart.map(c => <div key={c.m} className=\"flex-1 flex flex-col items-center justify-end h-full\">"
               "<div className=\"w-full rounded-t ..accent bg..\" style={{height: c.v + '%'}} title={c.m + ': ' + c.v}></div>"
               "<span className=\"text-[10px] mt-1 ..muted..\">{c.m}</span></div>)}</div> "
               "- and a 'This week' card with one big number, a trend pill and 5 mini bars using the same pattern (h-16, 5 days); "
               "(d) grid lg:grid-cols-3 gap-6: 'Recent __FIRST_NAME__' TABLE card (lg:col-span-2) - 5 rows from (window.AppDB.getRecords('__FIRST_KEY__')||[]).slice(0,5), "
               "3-4 columns using the entity's REAL seeded field names (guarded row?.field), a status pill column, 'View all' Link in the header; "
               "and a 'Quick actions' card with working navigate buttons + a small static activity feed.")},
    {"name": "tinted-tiles",
     "brief": ("LAYOUT (tinted tiles): (a) welcome header with the user's name + date + a working notification-bell button (toggles a dropdown panel of 3 items via state); "
               "(b) grid sm:grid-cols-2 lg:grid-cols-4 gap-6 of stat tiles - ONE PER REAL ENTITY: __TILES__ - each tile uses a SOFT TINTED background (bg-<accent>-50 style consistent with the theme), "
               "a colored icon tile on the right, the live count big and bold, and a muted caption; each tile is a Link to its list; "
               "(c) ONE full-width 'Activity Overview' card containing EXACTLY this pattern with 12 varied values: const chart=[{m:'Jan',v:45},...]; "
               "<div className=\"flex items-end gap-2 h-40\">{chart.map(c => <div key={c.m} className=\"flex-1 flex flex-col items-center justify-end h-full\">"
               "<div className=\"w-full rounded-t ..accent bg..\" style={{height: c.v + '%'}} title={c.m + ': ' + c.v}></div><span className=\"text-[10px] mt-1\">{c.m}</span></div>)}</div> "
               "+ a 3-stat mini-row under it; "
               "(d) grid lg:grid-cols-3 gap-6: 'Recent __FIRST_NAME__' table card (lg:col-span-2, 5 guarded rows using the entity's REAL seeded field names + status pills) and a vertical activity TIMELINE card "
               "(a left border line with dot markers, 4 events: icon, text, time).")},
    {"name": "kpi-strip",
     "brief": ("LAYOUT (KPI strip): (a) compact header row: title + date + a 'New' primary button navigating to the first create route; "
               "(b) ONE wide card containing a KPI STRIP - a grid divided by vertical borders (divide-x), one column PER REAL ENTITY: __TILES__ - each column: muted label, big count, "
               "and a 5-bar mini sparkline (tiny divs of varying heights in the accent color); "
               "(c) grid lg:grid-cols-3 gap-6: a BIG 'Recent __FIRST_NAME__' table card (lg:col-span-2) with 6 guarded rows using the entity's REAL seeded field names, status pills and per-row View buttons that work "
               "(set localStorage selection + navigate like the list page); RIGHT column: an SVG DONUT card ('Storage used' - two <circle> elements with strokeDasharray, accent stroke, % in the middle) "
               "stacked above a 'Quick actions' card with working buttons.")},
    {"name": "header-band",
     "brief": ("LAYOUT (gradient header band): (a) a full-width rounded-3xl accent-gradient band card (p-8, contrasting text): 'Welcome back, <name>', today's date, a one-line summary, "
               "and TWO inline glass chips (bg-white/15 rounded-xl px-4 py-2) showing the two biggest entity counts; "
               "(b) BELOW the band (separate row, no overlap): grid sm:grid-cols-2 lg:grid-cols-4 gap-6 stat cards - ONE PER REAL ENTITY: __TILES__ (label, big count, small icon, Link); "
               "(c) grid lg:grid-cols-3 gap-6: an 'Overview' card (lg:col-span-2) containing EXACTLY: const chart=[{m:'Jan',v:45},...12 varied values...]; "
               "<div className=\"flex items-end gap-2 h-40\">{chart.map(c => <div key={c.m} className=\"flex-1 flex flex-col items-center justify-end h-full\">"
               "<div className=\"w-full rounded-t ..accent bg..\" style={{height: c.v + '%'}} title={c.m + ': ' + c.v}></div><span className=\"text-[10px] mt-1\">{c.m}</span></div>)}</div> "
               "+ a tasks card with 4 checkbox to-dos that really toggle in state; "
               "(d) a 'Recent __FIRST_NAME__' table card full-width (5 guarded rows using the entity's REAL seeded field names, status pills, 'View all' Link).")},
]


def pick_layouts() -> dict:
    """Randomly choose one layout per page family for a generation run."""
    return {
        "landing": random.choice(LANDING_LAYOUTS),
        "auth": random.choice(AUTH_LAYOUTS),
        "dashboard": random.choice(DASHBOARD_LAYOUTS),
    }


def pick_theme() -> dict:
    """Choose ONE theme for a generation run (different design each project)."""
    return random.choice(DESIGN_THEMES)


def fonts_url(theme: dict) -> str:
    """Build the Google Fonts stylesheet URL for the theme's two fonts."""
    display = theme["font_display"].replace(" ", "+")
    body = theme["font_body"].replace(" ", "+")
    families = f"family={display}:wght@400;500;600;700"
    if body != display:
        families += f"&family={body}:wght@300;400;500;600;700"
    return f"https://fonts.googleapis.com/css2?{families}&display=swap"


def design_brief(theme: dict) -> str:
    """A compact instruction block injected into the coder prompts so generated
    pages use the chosen theme's exact Tailwind classes (uniform look)."""
    return (
        f"DESIGN SYSTEM (theme: {theme['name']}, {theme['mode']} mode). "
        f"Use THESE exact Tailwind classes for the matching elements; do NOT invent other color families:\n"
        f"- Page/root container background: {theme['page_background']}\n"
        f"- Cards / panels / modals: {theme['card']}\n"
        f"- Primary buttons: {theme['primary_button']}\n"
        f"- Secondary buttons: {theme['secondary_button']}\n"
        f"- Inputs / selects / textareas: {theme['input']}\n"
        f"- Headings / primary text: {theme['text_primary']}\n"
        f"- Muted / secondary text: {theme['text_muted']}\n"
        f"- Accent (links, active icons, highlights): {theme['accent']}\n"
        f"- Sidebar surface: {theme['sidebar']}\n"
        f"Typography: display font '{theme['font_display']}', body font '{theme['font_body']}'.\n\n"
        "BLOCK STYLE (shadcn/ui-inspired - clean, modern, generous whitespace):\n"
        "- Build the page as clear horizontal SECTIONS. Center content in `max-w-7xl mx-auto px-4 sm:px-6`; vertical rhythm `py-12` to `py-24` per marketing section, `p-6 md:p-8` for app pages.\n"
        "- Cards use the theme card classes + `p-6`; grids use `grid gap-6`. Keep one consistent corner radius and subtle borders/shadows throughout.\n"
        "- Section header pattern: a small UPPERCASE eyebrow label or a rounded-full badge, then a large bold display-font heading, then a muted one-line subheading - usually `max-w-2xl mx-auto text-center`.\n"
        "- Badges/pills: `inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium` tinted with the accent color.\n"
        "- Buttons: the primary/secondary classes above with `rounded-lg px-5 py-2.5 font-medium` and a hover transition.\n"
        "- Data tables: a muted header row, `divide-y` body rows, comfortable `px-4 py-3` cells, and a subtle row hover.\n"
        "- IMAGES: locally generated images exist ONLY at these exact paths: assets/logo.jpg (square brand mark), assets/hero.jpg, assets/feature.jpg, "
        "assets/about.jpg, assets/auth.jpg, assets/contact.jpg, assets/gallery1.jpg, assets/gallery2.jpg, assets/gallery3.jpg, assets/banner.jpg (wide panoramic). "
        "Use them ONLY where the page brief says to, always with `alt=\"\"`, an explicit object-cover + rounded class, and "
        "`onError={(e)=>{e.currentTarget.style.display='none'}}` so a missing file never breaks the layout. NEVER invent other image URLs "
        "(no picsum/unsplash/placeholder.com). For people, use initials-in-a-circle avatars, not photos."
    )
