from __future__ import annotations

STYLE_VARIANTS = [
    {
        "id": "minimal",
        "label": "Minimal Clean",
        "guide": "Whitespace-heavy, thin 1px borders, neutral grays, sans-serif, subtle hover states. Avoid shadows, gradients, and bright colors.",
    },
    {
        "id": "bold",
        "label": "Bold Colored",
        "guide": "Vibrant saturated primary colors, thick rounded corners (rounded-2xl), bold typography, solid color backgrounds, visible shadows.",
    },
    {
        "id": "glass",
        "label": "Glassmorphism",
        "guide": "Frosted glass effect using backdrop-blur, semi-transparent white bg-white/30, soft gradient background, delicate borders, floating layout.",
    },
    {
        "id": "brutalist",
        "label": "Neo-Brutalist",
        "guide": "Hard 2px black borders, offset black box-shadows (shadow-[4px_4px_0_#000]), flat saturated accent colors, mono / display fonts, no rounded corners beyond rounded-md.",
    },
    {
        "id": "corporate",
        "label": "Corporate Enterprise",
        "guide": "Dense information layout, blue/gray palette, professional feel, serif or clean sans, conservative shadows, clear hierarchy, small accent stripes.",
    },
]

COMPONENT_SPECS = {
    "header": {
        "label": "Header",
        "role": "top-of-page site/app header with branding and primary navigation CTAs",
        "props": "{ brand, navItems, ctaLabel, onCta }",
        "example_context": "render the project name as brand and use features[] names to derive navItems",
    },
    "footer": {
        "label": "Footer",
        "role": "bottom-of-page footer with link columns, brand, copyright and social",
        "props": "{ brand, columns, social, copyright }",
        "example_context": "derive columns from SRS modules / sections; copyright uses project_name",
    },
    "nav": {
        "label": "Navigation",
        "role": "secondary navigation (sidebar, tabs, or breadcrumbs) connecting app pages",
        "props": "{ items, active, onSelect }",
        "example_context": "items correspond to the SRS page list (e.g. Dashboard, Users, Settings)",
    },
    "card": {
        "label": "Card",
        "role": "reusable content card used to display feature, entity, or list items",
        "props": "{ title, description, icon, action }",
        "example_context": "title and description illustrate one of the SRS features",
    },
}

PAGE_TEMPLATES = [
    {"id": "dashboard", "name": "Dashboard", "role": "overview page with stats, recent activity and quick actions"},
    {"id": "login", "name": "LoginPage", "role": "authentication page with form, social login and branding panel"},
    {"id": "landing", "name": "LandingPage", "role": "marketing landing with hero, feature grid, CTA, and footer"},
    {"id": "table", "name": "TablePage", "role": "data table / list page with filters, pagination and row actions"},
    {"id": "settings", "name": "SettingsPage", "role": "user/app settings with sectioned forms and toggles"},
]


COMPONENT_SYSTEM_PROMPT = """You are Agent 2, a senior React engineer. You must output a single self-contained React functional component file using JSX and Tailwind CSS utility classes only. Rules:
- Use `import React from "react";` at the top. No other imports.
- Use only Tailwind utility classes; do NOT rely on external UI libraries.
- Component must be a default export named exactly as requested.
- Accept a `props` object. If `props` fields are missing, use sensible defaults derived from the SRS.
- No placeholder TODOs. Fill content using information from the provided SRS JSON.
- The visual style MUST match the style guide exactly; do not blend styles.
- Do NOT output markdown fences. Output raw JSX only.
"""


def component_user_prompt(category: str, variant: dict, srs_json_str: str, component_name: str) -> str:
    spec = COMPONENT_SPECS[category]
    return f"""Generate a React component file for category: {spec['label']}.

Component name (default export): {component_name}
Role: {spec['role']}
Props contract: {spec['props']}
Content hint: {spec['example_context']}

Style variant: {variant['label']} ({variant['id']})
Style guide (MANDATORY): {variant['guide']}

SRS JSON (source of truth for text content, feature names, project name, pages):
```json
{srs_json_str}
```

Return ONLY the JSX file contents. Component must render correctly with zero props (use defaults from SRS)."""


PAGE_SYSTEM_PROMPT = """You are Agent 2, a senior React engineer. Produce a single self-contained React page component using JSX and Tailwind CSS.
- Use `import React from "react";` at the top.
- Use only Tailwind utility classes.
- Default export named as requested.
- Populate ALL copy, headings, stats labels, table columns, form fields from the SRS JSON — never use lorem ipsum or generic stand-ins.
- Adopt the given visual style strictly.
- Output raw JSX only; no markdown fences."""


def page_user_prompt(page: dict, variant: dict, srs_json_str: str) -> str:
    return f"""Generate a React page component.

Page name (default export): {page['name']}
Role: {page['role']}

Visual style: {variant['label']} — {variant['guide']}

SRS JSON:
```json
{srs_json_str}
```

Return ONLY the JSX file contents."""
