"""Local GitHub design-source miner.

This module scans local, user-provided open-source template repositories and
extracts abstract component recipes. It intentionally does not store copied
source files, page layouts, images, logos, URLs, repo names, or brand text in the
recipe cache. The generated apps consume only neutral pattern summaries and
safe codegen hints.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = APP_DIR / "design_sources" / "template_repos"
DEFAULT_CACHE_PATH = APP_DIR / ".design_recipe_cache.json"


MANUAL_GITHUB_REPOS = [
    {"url": "https://github.com/ixartz/Next-JS-Landing-Page-Starter-Template", "category": "SaaS"},
    {"url": "https://github.com/nextjs/saas-starter", "category": "SaaS"},
    {"url": "https://github.com/gonzalochale/saas-landing-template", "category": "SaaS"},
    {"url": "https://github.com/launch-ui/launch-ui", "category": "SaaS"},
    {"url": "https://github.com/TailAdmin/free-nextjs-admin-dashboard", "category": "dashboard"},
    {"url": "https://github.com/Kiranism/next-shadcn-dashboard-starter", "category": "dashboard"},
    {"url": "https://github.com/reliverse/relivator", "category": "ecommerce"},
    {"url": "https://github.com/bradtraversy/property-pulse-nextjs", "category": "real estate"},
    {"url": "https://github.com/timlrx/tailwind-nextjs-starter-blog", "category": "content"},
    {"url": "https://github.com/manuelernestog/astrofy", "category": "portfolio"},
]


ALLOWED_LICENSES = {
    "MIT",
    "APACHE-2.0",
    "BSD",
    "BSD-2-CLAUSE",
    "BSD-3-CLAUSE",
    "ISC",
    "CC0",
    "UNLICENSE",
}
BLOCKED_LICENSE_MARKERS = [
    "gnu general public license",
    "affero general public license",
    "lesser general public license",
    "gpl-",
    "agpl",
    "lgpl",
]

TEXT_EXTENSIONS = {".jsx", ".tsx", ".js", ".ts", ".html", ".astro", ".css"}
SOURCE_ROOTS = [
    "src/app",
    "src/pages",
    "src/components",
    "app",
    "pages",
    "components",
    "src",
]
SKIP_DIRS = {
    ".git",
    ".next",
    ".astro",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "public",
    "assets",
    "images",
}

BRAND_OR_URL = re.compile(
    r"https?://|www\.|[a-z0-9-]+\.(?:com|app|ai|io|co|net|org|tech)\b",
    re.I,
)
ASSET_REF = re.compile(r"\.(?:png|jpe?g|gif|webp|svg|ico|mp4|webm)\b", re.I)
BANNED_BRANDS = {
    "stripe",
    "apple",
    "nike",
    "linear",
    "notion",
    "figma",
    "vercel",
    "webflow",
    "tesla",
    "amazon",
    "github",
    "openai",
    "coursera",
    "spotify",
}


SECTION_KEYWORDS = {
    "hero": ["hero", "headline", "above the fold", "jumbotron", "banner"],
    "navbar": ["nav", "navbar", "header", "navigation", "menu"],
    "footer": ["footer"],
    "feature_grid": ["feature", "benefit", "solution", "capability"],
    "pricing": ["pricing", "plans", "tier"],
    "testimonial": ["testimonial", "review", "quote", "customers"],
    "gallery": ["gallery", "showcase", "portfolio", "case study"],
    "cards": ["card", "grid", "tile", "bento"],
    "dashboard_preview": ["dashboard", "chart", "analytics", "metric", "kpi"],
    "product_grid": ["product", "collection", "cart", "shop", "inventory"],
    "cta": ["cta", "call to action", "button", "get started", "sign up"],
}

CATEGORY_KEYWORDS = {
    "SaaS": ["saas", "startup", "landing", "software", "workflow", "productivity"],
    "dashboard": ["dashboard", "admin", "analytics", "kpi", "table"],
    "ecommerce": ["ecommerce", "commerce", "shop", "store", "product", "cart"],
    "portfolio": ["portfolio", "agency", "creative", "studio", "blog", "content"],
    "real estate": ["real estate", "property", "listing", "housing", "agent"],
    "restaurant": ["restaurant", "booking", "reservation", "menu", "dining"],
    "travel": ["travel", "tour", "tourism", "destination", "itinerary"],
    "education": ["education", "course", "learning", "student", "lesson"],
    "AI/devtool": ["developer", "api", "code", "ai", "docs", "terminal"],
    "healthcare": ["healthcare", "hospital", "clinic", "patient", "doctor"],
}

VISUAL_FAMILY_BY_CATEGORY = {
    "SaaS": "service-trust",
    "dashboard": "operations-console",
    "ecommerce": "product-commerce",
    "portfolio": "creative-portfolio",
    "real estate": "real-estate-listings",
    "restaurant": "restaurant-reservation",
    "travel": "travel-destination",
    "education": "learning-editorial",
    "AI/devtool": "developer-console",
    "healthcare": "healthcare-clinical",
}


def _read_text(path: Path, limit: int = 260_000) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    return data[:limit]


def _json(path: Path) -> dict:
    try:
        return json.loads(_read_text(path, 80_000))
    except Exception:
        return {}


def _license_from_text(text: str) -> str:
    blob = str(text or "").lower()
    if any(marker in blob for marker in BLOCKED_LICENSE_MARKERS):
        if "affero" in blob or "agpl" in blob:
            return "AGPL"
        if "lesser" in blob or "lgpl" in blob:
            return "LGPL"
        return "GPL"
    if "mit license" in blob or ("permission is hereby granted" in blob and "without restriction" in blob):
        return "MIT"
    if "apache license" in blob or "apache-2.0" in blob:
        return "APACHE-2.0"
    if "bsd 3-clause" in blob:
        return "BSD-3-CLAUSE"
    if "bsd 2-clause" in blob:
        return "BSD-2-CLAUSE"
    if "redistribution and use in source and binary forms" in blob:
        return "BSD"
    if "isc license" in blob or "isc)" in blob:
        return "ISC"
    if "creative commons zero" in blob or "cc0" in blob:
        return "CC0"
    if "unlicense" in blob:
        return "UNLICENSE"
    return ""


def detect_license(repo_path: str | os.PathLike) -> dict:
    root = Path(repo_path)
    pkg = _json(root / "package.json")
    pkg_license = str(pkg.get("license") or "").strip()
    if pkg_license:
        detected = _license_from_text(pkg_license) or pkg_license.upper()
        if any(marker.upper() in detected.upper() for marker in ("GPL", "AGPL", "LGPL")):
            return {"license": detected, "allowed": False, "reason": "blocked copyleft license"}
        if detected.upper() in ALLOWED_LICENSES:
            return {"license": detected.upper(), "allowed": True, "reason": "package.json license"}

    for pattern in ("LICENSE", "LICENSE.md", "LICENSE.txt", "license.txt", "COPYING"):
        path = root / pattern
        if not path.exists():
            continue
        detected = _license_from_text(_read_text(path, 80_000))
        if not detected:
            return {"license": "UNKNOWN", "allowed": False, "reason": "license file not recognized"}
        if detected.upper() in {"GPL", "AGPL", "LGPL"}:
            return {"license": detected.upper(), "allowed": False, "reason": "blocked copyleft license"}
        return {
            "license": detected.upper(),
            "allowed": detected.upper() in ALLOWED_LICENSES,
            "reason": "license file",
        }
    return {"license": "UNKNOWN", "allowed": False, "reason": "missing clear license"}


def detect_frameworks(repo_path: str | os.PathLike) -> list[str]:
    root = Path(repo_path)
    pkg = _json(root / "package.json")
    deps = " ".join([
        " ".join((pkg.get("dependencies") or {}).keys()),
        " ".join((pkg.get("devDependencies") or {}).keys()),
        str(pkg.get("scripts") or {}),
    ]).lower()
    files = " ".join(p.suffix.lower() for p in root.rglob("*") if p.is_file())[:4000]
    frameworks = []
    if "next" in deps:
        frameworks.append("Next.js")
    if "react" in deps:
        frameworks.append("React")
    if "vite" in deps:
        frameworks.append("Vite")
    if "tailwind" in deps:
        frameworks.append("Tailwind")
    if "astro" in deps or ".astro" in files:
        frameworks.append("Astro")
    if any((root / name).exists() for name in ("index.html", "src/index.html")):
        frameworks.append("HTML/CSS")
    return sorted(set(frameworks)) or ["unknown"]


def _source_files(repo_path: Path, max_files: int = 180) -> list[Path]:
    roots = [repo_path / rel for rel in SOURCE_ROOTS if (repo_path / rel).exists()]
    if not roots:
        roots = [repo_path]
    files = []
    for root in roots:
        for path in root.rglob("*"):
            if len(files) >= max_files:
                return files
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.stat().st_size > 260_000:
                continue
            files.append(path)
    return files


def _class_values(text: str) -> list[str]:
    values = []
    for match in re.finditer(r'(?:className|class)\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|`([^`]+)`)', text):
        raw = next((g for g in match.groups() if g), "")
        if "{" in raw or "$" in raw:
            raw = re.sub(r"[{}$`'\"]", " ", raw)
        values.append(raw)
    return values


def _tokens_from_classes(class_values: list[str]) -> list[str]:
    tokens = []
    for value in class_values:
        for token in re.split(r"\s+", value.strip()):
            parts = {p for p in re.split(r"[^a-z0-9]+", token.lower()) if p}
            if token and not parts.intersection(BANNED_BRANDS) and not BRAND_OR_URL.search(token) and not ASSET_REF.search(token):
                tokens.append(token[:80])
    return tokens[:1800]


def _detect_sections(text: str, tokens: list[str]) -> list[str]:
    blob = (text[:80_000] + " " + " ".join(tokens[:900])).lower()
    found = []
    for section, keywords in SECTION_KEYWORDS.items():
        if any(k in blob for k in keywords):
            found.append(section)
    return found


def _detect_category(repo_path: Path, text: str) -> str:
    # Category detection can use local folder/package names internally, but the
    # output is a generic category label only.
    pkg = _json(repo_path / "package.json")
    blob = " ".join([
        repo_path.name,
        str(pkg.get("name") or ""),
        str(pkg.get("description") or ""),
        text[:120_000],
    ]).lower()
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = sum(1 for k in keywords if k in blob)
    category, score = max(scores.items(), key=lambda item: item[1])
    return category if score > 0 else "SaaS"


def _pattern_summary(tokens: list[str]) -> dict:
    c = Counter(tokens)
    responsive = sum(1 for t in tokens if re.match(r"(sm|md|lg|xl|2xl):", t))
    grid = sum(1 for t in tokens if "grid" in t or "grid-cols" in t)
    flex = sum(1 for t in tokens if t.startswith("flex") or t in {"items-center", "justify-between"})
    rounded = [t for t in tokens if t.startswith("rounded")]
    shadows = [t for t in tokens if t.startswith("shadow")]
    borders = [t for t in tokens if t.startswith("border")]
    text = [t for t in tokens if t.startswith("text-") or t.startswith("font-") or t.startswith("tracking")]
    spacing = [t for t in tokens if re.match(r"(p|px|py|pt|pb|m|mx|my|mt|mb|gap|space-y|space-x)-", t)]
    images = [t for t in tokens if t in {"object-cover", "aspect-video", "overflow-hidden"} or t.startswith("aspect-")]
    bg = [t for t in tokens if t.startswith("bg-")]
    return {
        "layout_pattern": "responsive grid" if grid >= flex else "split flex layout" if flex else "stacked layout",
        "spacing_pattern": "spacious rhythm" if any(t in tokens for t in ("py-24", "py-32", "gap-10", "gap-12")) else "balanced rhythm",
        "typography_pattern": "large editorial scale" if any(t in tokens for t in ("text-6xl", "text-7xl", "text-8xl")) else "clean product scale",
        "card_pattern": "bordered elevated cards" if shadows and borders else "soft rounded cards" if rounded else "flat panels",
        "image_pattern": "image mosaic or media cards" if images or "object-cover" in tokens else "minimal imagery",
        "cta_pattern": "rounded pill CTA" if any("rounded-full" in t for t in tokens) else "solid button CTA",
        "class_pattern_summary": {
            "responsive_tokens": min(responsive, 99),
            "layout_tokens": min(grid + flex, 99),
            "top_spacing": [x for x, _n in Counter(spacing).most_common(8)],
            "top_type": [x for x, _n in Counter(text).most_common(8)],
            "card_tokens": [x for x, _n in Counter(rounded + shadows + borders).most_common(8)],
            "background_tokens": [x for x, _n in Counter(bg).most_common(8)],
            "dominant": [x for x, _n in c.most_common(12) if len(x) <= 60],
        },
    }


def _quality_score(tokens: list[str], sections: list[str], frameworks: list[str], file_count: int) -> int:
    score = 42
    if "Tailwind" in frameworks:
        score += 10
    if "Next.js" in frameworks or "React" in frameworks or "Astro" in frameworks:
        score += 6
    if any(re.match(r"(sm|md|lg|xl):", t) for t in tokens):
        score += 10
    if any(t.startswith("grid-cols") or ":grid-cols" in t for t in tokens):
        score += 8
    if any(t.startswith("rounded") for t in tokens):
        score += 5
    if any(t.startswith("shadow") for t in tokens):
        score += 5
    if any(t.startswith("text-5xl") or t.startswith("text-6xl") or t.startswith("text-7xl") for t in tokens):
        score += 7
    if "hero" in sections and ("navbar" in sections or "footer" in sections):
        score += 7
    if len(set(sections)) >= 5:
        score += 6
    if file_count >= 12:
        score += 4
    return max(0, min(100, score))


def _component_types_for_sections(sections: list[str]) -> list[str]:
    preferred = ["hero", "navbar", "cards", "feature_grid", "dashboard_preview", "product_grid", "gallery", "cta", "footer"]
    out = [s for s in preferred if s in sections]
    return out or ["section"]


def _recipe_id(category: str, component_type: str, tokens: list[str], sections: list[str]) -> str:
    raw = "|".join([category, component_type, ",".join(sections), ",".join(tokens[:80])])
    digest = hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()[:12]
    return f"ghr-{component_type.replace('_', '-')}-{digest}"


def _sanitize_recipe(recipe: dict) -> dict:
    clean = json.loads(json.dumps(recipe, ensure_ascii=True))
    blob = json.dumps(clean, ensure_ascii=True).lower()
    if BRAND_OR_URL.search(blob) or ASSET_REF.search(blob):
        raise ValueError("recipe contains URL or asset-like data")
    leaked = [name for name in BANNED_BRANDS if re.search(rf"\b{re.escape(name)}\b", blob)]
    if leaked:
        raise ValueError("recipe contains banned brand vocabulary: " + ",".join(leaked[:3]))
    return clean


def scan_repository(repo_path: str | os.PathLike) -> dict:
    root = Path(repo_path)
    license_info = detect_license(root)
    frameworks = detect_frameworks(root)
    if not license_info.get("allowed"):
        return {
            "accepted": False,
            "skip_reason": license_info.get("reason", "license not allowed"),
            "license": license_info.get("license", "UNKNOWN"),
            "frameworks": frameworks,
            "recipes": [],
        }
    files = _source_files(root)
    text_parts = []
    class_values = []
    for path in files:
        text = _read_text(path)
        text_parts.append(text[:60_000])
        class_values.extend(_class_values(text))
    text = "\n".join(text_parts)
    tokens = _tokens_from_classes(class_values)
    sections = _detect_sections(text, tokens)
    category = _detect_category(root, text)
    patterns = _pattern_summary(tokens)
    quality = _quality_score(tokens, sections, frameworks, len(files))
    complexity = min(100, 15 + len(files) * 2 + len(set(tokens)) // 6 + len(sections) * 4)
    if quality < 55 or len(tokens) < 24:
        return {
            "accepted": False,
            "skip_reason": "low quality or too few reusable UI signals",
            "license": license_info.get("license", "UNKNOWN"),
            "frameworks": frameworks,
            "recipes": [],
        }
    recipes = []
    for component_type in _component_types_for_sections(sections):
        recipe = {
            "recipe_id": _recipe_id(category, component_type, tokens, sections),
            "source_license": license_info.get("license", "UNKNOWN"),
            "source_category": category,
            "component_type": component_type,
            "visual_family": VISUAL_FAMILY_BY_CATEGORY.get(category, "service-trust"),
            "layout_pattern": patterns["layout_pattern"],
            "class_pattern_summary": patterns["class_pattern_summary"],
            "spacing_pattern": patterns["spacing_pattern"],
            "typography_pattern": patterns["typography_pattern"],
            "card_pattern": patterns["card_pattern"],
            "image_pattern": patterns["image_pattern"],
            "cta_pattern": patterns["cta_pattern"],
            "complexity_score": complexity,
            "quality_score": quality,
            "reusable_abstract_recipe": _abstract_recipe(component_type, category, patterns),
        }
        recipes.append(_sanitize_recipe(recipe))
    return {
        "accepted": True,
        "license": license_info.get("license", "UNKNOWN"),
        "frameworks": frameworks,
        "source_category": category,
        "sections": sections,
        "quality_score": quality,
        "complexity_score": complexity,
        "recipes": recipes,
    }


def _abstract_recipe(component_type: str, category: str, patterns: dict) -> str:
    return "; ".join([
        f"{component_type.replace('_', ' ')} for {category}",
        patterns["layout_pattern"],
        patterns["spacing_pattern"],
        patterns["typography_pattern"],
        patterns["card_pattern"],
        patterns["image_pattern"],
        patterns["cta_pattern"],
    ])


def iter_local_repositories(source_dir: str | os.PathLike | None = None) -> list[Path]:
    root = Path(source_dir or os.environ.get("DESIGN_SOURCES_DIR") or DEFAULT_SOURCE_DIR)
    if not root.exists():
        return []
    repos = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and not child.name.startswith(".") and ((child / ".git").exists() or (child / "package.json").exists()):
            repos.append(child)
    return repos


def extract_design_recipes(
    source_dir: str | os.PathLike | None = None,
    cache_path: str | os.PathLike | None = None,
    write_cache: bool = True,
    max_repos: int | None = None,
) -> dict:
    repos = iter_local_repositories(source_dir)
    if max_repos:
        repos = repos[:max_repos]
    accepted = []
    skipped = []
    recipes = []
    for repo in repos:
        result = scan_repository(repo)
        if result.get("accepted"):
            accepted.append({
                "source_ref": _source_ref(repo),
                "license": result.get("license"),
                "category": result.get("source_category"),
                "frameworks": result.get("frameworks", []),
                "recipe_count": len(result.get("recipes", [])),
                "quality_score": result.get("quality_score"),
            })
            recipes.extend(result.get("recipes", []))
        else:
            skipped.append({
                "source_ref": _source_ref(repo),
                "license": result.get("license"),
                "reason": result.get("skip_reason"),
            })
    recipes = _dedupe_recipes(recipes)
    output = {
        "version": 1,
        "accepted_repo_count": len(accepted),
        "skipped_repo_count": len(skipped),
        "recipe_count": len(recipes),
        "accepted_repos": accepted,
        "skipped_repos": skipped,
        "recipes": recipes,
    }
    if write_cache:
        path = Path(cache_path or os.environ.get("DESIGN_RECIPE_CACHE") or DEFAULT_CACHE_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def _dedupe_recipes(recipes: list[dict]) -> list[dict]:
    seen = {}
    for recipe in recipes:
        seen[recipe["recipe_id"]] = recipe
    return sorted(seen.values(), key=lambda r: (-int(r.get("quality_score", 0)), r["recipe_id"]))


def _source_ref(path: Path) -> str:
    return hashlib.sha1(str(path.name).encode("utf-8", errors="ignore")).hexdigest()[:10]


def load_recipe_cache(cache_path: str | os.PathLike | None = None) -> dict:
    path = Path(cache_path or os.environ.get("DESIGN_RECIPE_CACHE") or DEFAULT_CACHE_PATH)
    if not path.exists():
        return {"version": 1, "recipes": [], "accepted_repo_count": 0, "skipped_repo_count": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"version": 1, "recipes": [], "accepted_repo_count": 0, "skipped_repo_count": 0}
    recipes = []
    for recipe in data.get("recipes", []):
        try:
            recipes.append(_sanitize_recipe(recipe))
        except Exception:
            continue
    data["recipes"] = recipes
    return data


def _prompt_text(genome_or_prompt) -> str:
    if isinstance(genome_or_prompt, dict):
        return " ".join(str(genome_or_prompt.get(k, "")) for k in (
            "domain", "app_category", "inspiration_family", "visual_family", "primary_dna_family"
        ))
    return str(genome_or_prompt or "")


def _score_recipe(recipe: dict, text: str, visual_family: str = "") -> int:
    score = int(recipe.get("quality_score", 0))
    category = str(recipe.get("source_category", "")).lower()
    family = str(recipe.get("visual_family", ""))
    if visual_family and family == visual_family:
        score += 40
    for key, words in CATEGORY_KEYWORDS.items():
        if category == key.lower() and any(w in text for w in words):
            score += 22
    if recipe.get("component_type") in {"hero", "cards", "feature_grid", "cta", "footer"}:
        score += 8
    if "responsive" in str(recipe.get("layout_pattern", "")):
        score += 4
    return score


def select_extracted_recipes(genome_or_prompt, visual_family: str = "", max_recipes: int = 6, cache_path=None) -> list[dict]:
    data = load_recipe_cache(cache_path)
    recipes = list(data.get("recipes") or [])
    if not recipes:
        return []
    text = _prompt_text(genome_or_prompt).lower()
    ranked = sorted(recipes, key=lambda r: _score_recipe(r, text, visual_family), reverse=True)
    selected = []
    by_type = defaultdict(int)
    for recipe in ranked:
        ctype = recipe.get("component_type", "section")
        if by_type[ctype] >= 2 and len(selected) < max_recipes - 1:
            continue
        selected.append(recipe)
        by_type[ctype] += 1
        if len(selected) >= max_recipes:
            break
    return [dict(r) for r in selected]


def summarize_recipe_influence(recipes: list[dict]) -> dict:
    recipes = list(recipes or [])
    if not recipes:
        return {}
    types = Counter(r.get("component_type", "section") for r in recipes)
    layouts = Counter(r.get("layout_pattern", "") for r in recipes)
    cards = Counter(r.get("card_pattern", "") for r in recipes)
    images = Counter(r.get("image_pattern", "") for r in recipes)
    ctas = Counter(r.get("cta_pattern", "") for r in recipes)
    families = Counter(r.get("visual_family", "") for r in recipes)
    return {
        "mode": "mined-hybrid",
        "recipe_ids": [r.get("recipe_id", "") for r in recipes[:8]],
        "component_types": [x for x, _n in types.most_common(8)],
        "visual_families": [x for x, _n in families.most_common(5)],
        "layout_pattern": layouts.most_common(1)[0][0] if layouts else "",
        "card_pattern": cards.most_common(1)[0][0] if cards else "",
        "image_pattern": images.most_common(1)[0][0] if images else "",
        "cta_pattern": ctas.most_common(1)[0][0] if ctas else "",
        "quality_score": round(sum(int(r.get("quality_score", 0)) for r in recipes) / max(1, len(recipes)), 1),
        "hero_class_add": "relative overflow-hidden shadow-sm",
        "section_class_add": "relative overflow-hidden",
        "card_class_add": "ring-1 ring-black/5 shadow-xl shadow-black/5",
        "cta_class_add": "shadow-lg",
    }


def validate_recipe_cache(cache_path: str | os.PathLike | None = None) -> dict:
    data = load_recipe_cache(cache_path)
    errors = []
    required = {
        "recipe_id",
        "source_license",
        "source_category",
        "component_type",
        "visual_family",
        "layout_pattern",
        "class_pattern_summary",
        "spacing_pattern",
        "typography_pattern",
        "card_pattern",
        "image_pattern",
        "cta_pattern",
        "complexity_score",
        "quality_score",
        "reusable_abstract_recipe",
    }
    for recipe in data.get("recipes", []):
        missing = required - set(recipe)
        if missing:
            errors.append(f"{recipe.get('recipe_id', '<missing>')} missing {sorted(missing)}")
        blob = json.dumps(recipe, ensure_ascii=True).lower()
        if BRAND_OR_URL.search(blob) or ASSET_REF.search(blob):
            errors.append(f"{recipe.get('recipe_id')} contains URL or asset-like data")
        leaked = [name for name in BANNED_BRANDS if re.search(rf"\b{re.escape(name)}\b", blob)]
        if leaked:
            errors.append(f"{recipe.get('recipe_id')} contains banned brand vocabulary {leaked[:3]}")
        if recipe.get("source_license") not in ALLOWED_LICENSES:
            errors.append(f"{recipe.get('recipe_id')} has non-permissive license {recipe.get('source_license')}")
    return {
        "ok": not errors,
        "errors": errors,
        "recipe_count": len(data.get("recipes", [])),
        "accepted_repo_count": data.get("accepted_repo_count", 0),
        "skipped_repo_count": data.get("skipped_repo_count", 0),
    }
