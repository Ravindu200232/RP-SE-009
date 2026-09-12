"""Every class the drawing uses, declared — or the page has no styling at all.

A drawing is styled by Tailwind's browser build, which reads the classes off
the page and compiles them there and then. Asked for one it does not know —
`shadow-overlay`, when the page's own theme declared only `shadow-raised` —
it does not skip that one rule and carry on. It throws, and the page is left
with no styling whatsoever: one invented name takes the whole drawing down,
and the reviewer is shown bare HTML.

Measured on a hotel drawing of seven pages: one `hover:shadow-overlay`, and
every page came out unstyled.

So before the drawing is shown, each custom name it uses is declared beside
the ones that were, in the same theme block, on every page. A name the design
system already has a variable for gets that variable; the rest get a plain
value that matches what the name is for.

Only names that are unmistakably the theme's own are touched: no digits (which
are Tailwind's own scales — `text-2xl`, `border-2`), nothing bracketed, nothing
that is one of Tailwind's own words for that family. What cannot be placed is
left alone and reported, because a wrong declaration is worse than none: it
would quietly take over a class the page meant to come from Tailwind.
"""
from __future__ import annotations

import re
from pathlib import Path

# Where a family's names are declared in the theme, and what an undeclared one
# is worth when the design system has no variable for it.
FAMILIES = {
    "boxShadow": {"prefixes": ("shadow",), "fallback": "0 10px 30px rgba(0, 0, 0, 0.18)",
                  "variable": "shadow"},
    "borderRadius": {"prefixes": ("rounded",), "fallback": "12px", "variable": "radius"},
    "fontFamily": {"prefixes": ("font",), "fallback": "var(--font-body, inherit)",
                   "variable": "font"},
    "colors": {"prefixes": ("bg", "text", "border", "ring", "from", "via", "to",
                            "fill", "stroke", "divide", "outline", "decoration",
                            "caret", "accent", "shadow"),
               "fallback": "currentColor", "variable": ""},
}

# Tailwind's own words, which are never redeclared.
OWN = {
    "shadow": {"sm", "md", "lg", "xl", "inner", "none"},
    "rounded": {"none", "sm", "md", "lg", "xl", "full"},
    "font": {"sans", "serif", "mono", "thin", "extralight", "light", "normal", "medium",
             "semibold", "bold", "extrabold", "black", "italic", "not-italic"},
    "bg": {"fixed", "local", "scroll", "clip", "origin", "bottom", "center", "left",
           "right", "top", "repeat", "no-repeat", "round", "space", "auto", "cover",
           "contain", "none", "gradient-to-t", "gradient-to-b", "gradient-to-l",
           "gradient-to-r", "gradient-to-tl", "gradient-to-tr", "gradient-to-bl",
           "gradient-to-br", "blend-normal", "blend-multiply", "blend-screen",
           "blend-overlay", "blend-darken", "blend-lighten", "transparent", "current",
           "inherit", "clip-border", "clip-padding", "clip-content", "clip-text"},
    "text": {"left", "center", "right", "justify", "start", "end", "wrap", "nowrap",
             "balance", "pretty", "ellipsis", "clip", "xs", "sm", "base", "lg", "xl",
             "transparent", "current", "inherit"},
    "border": {"solid", "dashed", "dotted", "double", "hidden", "none", "collapse",
               "separate", "spacing", "x", "y", "t", "b", "l", "r", "s", "e",
               "transparent", "current", "inherit"},
    "ring": {"inset", "offset", "none", "transparent", "current", "inherit"},
    "divide": {"solid", "dashed", "dotted", "double", "none", "x", "y", "reverse",
               "transparent", "current", "inherit"},
    "outline": {"none", "dashed", "dotted", "double", "hidden", "offset",
                "transparent", "current", "inherit"},
    "decoration": {"solid", "double", "dotted", "dashed", "wavy", "auto", "from-font",
                   "slice", "clone", "transparent", "current", "inherit"},
    "fill": {"none", "transparent", "current", "inherit"},
    "stroke": {"none", "transparent", "current", "inherit"},
    "caret": {"transparent", "current", "inherit"},
    "accent": {"auto", "transparent", "current", "inherit"},
    "from": {"transparent", "current", "inherit"},
    "via": {"transparent", "current", "inherit"},
    "to": {"transparent", "current", "inherit"},
}

# Tailwind's palette: every shade of these is its own.
PALETTE = {"slate", "gray", "zinc", "neutral", "stone", "red", "orange", "amber",
           "yellow", "lime", "green", "emerald", "teal", "cyan", "sky", "blue",
           "indigo", "violet", "purple", "fuchsia", "pink", "rose", "black", "white",
           "transparent", "current", "inherit"}

# The sides a radius or a border can be given, between the prefix and the name.
SIDES = {"t", "b", "l", "r", "s", "e", "tl", "tr", "bl", "br", "ss", "se", "es", "ee",
         "x", "y"}

CLASS_ATTRIBUTE = re.compile(r"""class(?:Name)?\s*=\s*["']([^"']*)["']""")
CLASS_IN_SCRIPT = re.compile(r"""(?:classList\.(?:add|remove|toggle)|className\s*=)\s*\(?["'`]([^"'`]*)["'`]""")
# A page's own CSS asks for classes too, and this is where Tailwind reports the
# failure from: `<css input>` was the .card rule, not the markup.
CLASS_IN_APPLY = re.compile(r"@apply\s+([^;{}]*)[;}]")
VAR_COLOUR = re.compile(r"""(['"]?[\w-]+['"]?)\s*:\s*(['"])([^'"]*var\([^'"]*)\2""")
LOCAL_ENGINE = re.compile(r"""<script[^>]*\ssrc=["']tailwind\.js["']""")
CDN_ENGINE = re.compile(
    r"""(?P<indent>[ \t]*)<script[^>]*\ssrc=["']https://cdn\.tailwindcss\.com[^"']*["'][^>]*>"""
    r"""\s*</script>""")
THEME_BLOCK = re.compile(r"(extend\s*:\s*\{)", re.S)
PAGES = (".html",)
SCRIPTS = (".js",)


def _stylesheets(root: Path) -> list:
    return _files(root, (".css",))


def restore_engine(root: Path) -> bool:
    """Put the drawing's own copy of Tailwind back, and the pages' use of it.

    The pages load `tailwind.js` from beside them and fall back to the public
    CDN only if that did not define anything. Asked why a page had no styling,
    a build once decided the local copy must be truncated: it replaced all
    407KB of it with a three-line comment and pointed every page straight at
    the CDN. The copy was whole, and the real fault was a class the theme
    never declared - see `repair`.

    A drawing that renders only with the internet is not the drawing that was
    checked in, so both halves are put back: the file when what is there is
    not Tailwind, and the local script tag when a page has dropped it.
    """
    pages = _files(root, PAGES)
    bundled = Path(__file__).resolve().parent / "assets" / "static" / "tailwind.js"
    if not pages or not bundled.is_file():
        return False
    changed = False
    for page in pages:
        try:
            text = page.read_text("utf-8")
        except OSError:
            continue
        if LOCAL_ENGINE.search(text):
            continue
        replaced = CDN_ENGINE.sub(_local_engine, text, count=1)
        if replaced != text:
            page.write_text(replaced, "utf-8")
            changed = True
    if not any(LOCAL_ENGINE.search(page.read_text("utf-8", errors="ignore"))
               for page in pages):
        return changed
    engine = _prototype(root) / "tailwind.js"
    try:
        present = engine.read_bytes() if engine.is_file() else b""
    except OSError:
        present = b""
    # The real build is hundreds of kilobytes and defines the global the pages
    # look for; anything that does neither is not it.
    if len(present) > 50_000 and b"tailwind" in present[:200_000].lower():
        return changed
    try:
        engine.write_bytes(bundled.read_bytes())
    except OSError:
        return changed
    return True


def alpha_colors(root: Path) -> list:
    """Let a colour taken from a variable also be used at part strength.

    The theme's colours are `var(--primary)`, and Tailwind cannot fade a value
    it cannot see inside: `ring-primary/20` comes back as a class that does not
    exist, and - as with any class it does not know - the page then loses all
    of its styling, not just that ring. Written as a mix, the variable still
    does its work and the fraction does too.
    """
    touched: list = []
    for page in _files(root, PAGES):
        try:
            text = page.read_text("utf-8")
        except OSError:
            continue
        block = _family_block(text, "colors")
        if block is None:
            continue
        changed = block
        for name, quote, value in VAR_COLOUR.findall(block):
            if "<alpha-value>" in value:
                continue
            mixed = f"color-mix(in srgb, {value} calc(<alpha-value> * 100%), transparent)"
            changed = changed.replace(f"{quote}{value}{quote}", f"{quote}{mixed}{quote}")
            touched.append(name.strip("'\""))
        if changed != block:
            page.write_text(text.replace(block, changed, 1), "utf-8")
    return sorted(set(touched))


def _local_engine(match) -> str:
    """The template's own way of loading Tailwind: beside the page, then the CDN."""
    indent = match.group("indent") or ""
    return (f'{indent}<script src="tailwind.js"></script>\n'
            f"{indent}<script>\n"
            f"{indent}  if (!window.tailwind) {{\n"
            f"{indent}    document.write('<script src=\"https://cdn.tailwindcss.com\">"
            f"<\\/script>');\n"
            f"{indent}  }}\n"
            f"{indent}</script>")


def _prototype(root: Path) -> Path:
    folder = Path(root) / ".agentforge" / "prototype"
    return folder if folder.is_dir() else Path(root)


def _files(root: Path, suffixes) -> list:
    folder = _prototype(root)
    return sorted(path for path in folder.glob("*")
                  if path.is_file() and path.suffix.lower() in suffixes)


def used_classes(root: Path) -> set:
    """Every class name the drawing puts on an element, markup and script alike."""
    names: set = set()
    for path in _files(root, PAGES + SCRIPTS + (".css",)):
        try:
            text = path.read_text("utf-8")
        except OSError:
            continue
        for pattern in (CLASS_ATTRIBUTE, CLASS_IN_SCRIPT, CLASS_IN_APPLY):
            for match in pattern.finditer(text):
                names.update(match.group(1).split())
    return names


def declared(text: str) -> dict:
    """The names the page's own theme declares, per family."""
    out = {family: set() for family in FAMILIES}
    for family in FAMILIES:
        block = _family_block(text, family)
        if block is None:
            continue
        for line in block.splitlines():
            key = re.match(r"\s*'?\"?([A-Za-z][A-Za-z0-9_-]*)'?\"?\s*:", line)
            if key:
                out[family].add(key.group(1))
    return out


def _family_block(text: str, family: str):
    """The text between `family: {` and its closing brace, or None."""
    start = re.search(rf"\b{family}\s*:\s*\{{", text)
    if not start:
        return None
    depth, index = 0, start.end() - 1
    for position in range(index, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return text[index + 1:position]
    return None


def _plain(name: str) -> bool:
    """A theme's own name: letters and dashes. Never a scale, never arbitrary."""
    return bool(re.fullmatch(r"[a-z][a-z-]*[a-z]", name))


def _wanted(classes: set) -> dict:
    """The custom name each family is asked for, with the utility it came from."""
    asked = {family: {} for family in FAMILIES}
    for raw in classes:
        # A variant says when, not what: hover:, md:, dark:, group-hover:.
        name = raw.split(":")[-1].split("/")[0].lstrip("!-")
        parts = name.split("-")
        if len(parts) < 2:
            continue
        prefix, rest = parts[0], parts[1:]
        if rest and rest[0] in SIDES and prefix in ("rounded", "border", "divide"):
            rest = rest[1:]
        suffix = "-".join(rest)
        if not suffix or not _plain(suffix) or suffix in OWN.get(prefix, set()):
            continue
        # One family per name, in the order above: `shadow-` is a shadow before
        # it is a colour, and declaring it twice would fight with itself.
        for family, spec in FAMILIES.items():
            if prefix not in spec["prefixes"]:
                continue
            if not (family == "colors" and suffix in PALETTE):
                asked[family].setdefault(suffix, raw)
            break
    return asked


def _value(family: str, name: str, variables: set) -> str:
    """What an undeclared name is worth: the design system's, or a plain one."""
    spec = FAMILIES[family]
    for candidate in ([f"--{spec['variable']}-{name}"] if spec["variable"] else []) + [f"--{name}"]:
        if candidate in variables:
            return f"var({candidate}, {spec['fallback']})"
    return spec["fallback"]


def _variables(root: Path) -> set:
    """The custom properties the design system defined, to be preferred."""
    found: set = set()
    for path in _files(root, PAGES + SCRIPTS + (".css",)):
        try:
            found.update(re.findall(r"(--[a-z][a-z0-9-]*)\s*:", path.read_text("utf-8")))
        except OSError:
            continue
    return found


def repair(root: Path) -> list:
    """Declare every custom class the drawing uses. Returns what was declared."""
    pages = _files(root, PAGES)
    if not pages:
        return []
    asked = _wanted(used_classes(root))
    variables = _variables(root)
    added: list = []
    for path in pages:
        try:
            text = path.read_text("utf-8")
        except OSError:
            continue
        known = declared(text)
        changed = text
        for family, names in asked.items():
            missing = sorted(name for name in names if name not in known.get(family, set()))
            if not missing:
                continue
            for name in missing:
                value = _value(family, name, variables)
                changed = _declare(changed, family, name, value)
                added.append({"page": path.name, "family": family, "name": name,
                              "class": names[name], "value": value})
        if changed != text:
            path.write_text(changed, "utf-8")
    return added


def _declare(text: str, family: str, name: str, value: str) -> str:
    """Put one name into the page's theme, making the family if it has none."""
    key = name if re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) else f"'{name}'"
    block = re.search(rf"\b{family}\s*:\s*\{{", text)
    if block:
        return text[:block.end()] + f"\n            {key}: '{value}'," + text[block.end():]
    extend = THEME_BLOCK.search(text)
    if not extend:
        return text
    return (text[:extend.end()]
            + f"\n          {family}: {{\n            {key}: '{value}',\n          }},"
            + text[extend.end():])
