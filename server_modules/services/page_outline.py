"""A page's shape, small enough to put in a prompt.

A prototype page is twelve kilobytes of markup, most of it presentation: class
lists, inline styles, the script that fills a table, the font link in the head.
A wireframe is not interested in any of that. It is interested in what sections
the page has, in what order, and what sits in them - which is perhaps a
fiftieth of the file.

So a page travels as its outline. The elements that carry structure keep their
tag, their id, a little of their class list and their own text; wrappers that
say nothing collapse; a row repeated nine times is recorded once and counted.
What comes out is a couple of kilobytes that a model with an eight-thousand
token window can read beside the specification, which the file itself is not.

Read-only and stdlib-only on purpose: this runs on markup an agent wrote
moments ago, in the middle of a change transaction, and it must never be the
reason one fails.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

# Elements that say something about a page's structure. Everything else is a
# wrapper: its children are kept, it is not.
STRUCTURAL = {
    "header", "nav", "main", "footer", "aside", "section", "article", "form",
    "table", "thead", "tbody", "tr", "th", "td", "ul", "ol", "li", "dialog",
    "h1", "h2", "h3", "h4", "h5", "h6", "p", "a", "button", "input", "select",
    "textarea", "label", "img", "video", "audio", "iframe", "canvas", "svg",
    "figure", "blockquote", "summary", "details",
}
IGNORED = {"script", "style", "noscript", "head", "meta", "link", "title", "base"}
VOID = {"img", "input", "br", "hr", "source", "meta", "link"}

MAX_NODES = 400
MAX_DEPTH = 9
MAX_TEXT = 60
MAX_CLASSES = 3
MAX_CHARS = 6000
TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _tidy(text: str) -> str:
    """One line of visible text, short enough to be a label."""
    flat = " ".join(str(text or "").split())
    return flat[:MAX_TEXT].rstrip() + ("…" if len(flat) > MAX_TEXT else "")


class _Node:
    __slots__ = ("tag", "ident", "classes", "text", "children", "attrs")

    def __init__(self, tag: str, attrs: dict):
        self.tag = tag
        self.ident = str(attrs.get("id") or "").strip()
        self.classes = [c for c in str(attrs.get("class") or "").split() if c][:MAX_CLASSES]
        self.attrs = attrs
        self.text = ""
        self.children: list["_Node"] = []

    def signature(self) -> str:
        """What this element is, ignoring its text. Repeats are counted by it."""
        return (f"{self.tag}#{self.ident}." + ".".join(self.classes)
                + "|" + "|".join(child.signature() for child in self.children))

    def line(self) -> str:
        parts = [self.tag]
        if self.ident:
            parts.append(f"#{self.ident}")
        for name in self.classes:
            parts.append(f".{name}")
        head = "".join(parts)
        if self.tag in ("input", "textarea", "select"):
            kind = str(self.attrs.get("type") or "").strip()
            placeholder = _tidy(self.attrs.get("placeholder") or "")
            if kind:
                head += f" [{kind}]"
            if placeholder:
                head += f' "{placeholder}"'
            return head
        if self.tag == "img":
            return head + f' "{_tidy(self.attrs.get("alt") or "image")}"'
        return head + (f' "{self.text}"' if self.text else "")


class _Reader(HTMLParser):
    """The document as a tree of the elements that matter."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("body", {})
        self.stack = [self.root]
        self.skipping = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in IGNORED:
            if tag not in ("meta", "link", "base"):
                self.skipping += 1
            return
        if self.skipping:
            return
        node = _Node(tag, {k.lower(): (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        if tag.lower() in IGNORED or self.skipping:
            return
        self.stack[-1].children.append(_Node(tag.lower(), {k.lower(): (v or "") for k, v in attrs}))

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in IGNORED:
            if self.skipping and tag not in ("meta", "link", "base"):
                self.skipping -= 1
            return
        if self.skipping or tag in VOID:
            return
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return

    def handle_data(self, data):
        if self.skipping:
            return
        said = _tidy(data)
        if said and not self.stack[-1].text:
            self.stack[-1].text = said


def _keep(node: _Node) -> list[_Node]:
    """This element if it carries structure, otherwise whatever it holds.

    A page is four wrapper divs deep before it says anything, and an outline
    that spends its depth budget on them runs out before the content. A div
    survives only when it is named - an id or a class is how the page itself
    says the section is a thing - or when it holds text of its own.
    """
    kept: list[_Node] = []
    for child in node.children:
        kept.extend(_keep(child))
    node.children = kept
    if node.tag in STRUCTURAL or node.ident or node.classes or node.text:
        return [node]
    return kept


def _render(node: _Node, depth: int, out: list[str], budget: list[int]) -> None:
    if depth > MAX_DEPTH or budget[0] <= 0:
        return
    out.append("  " * depth + node.line())
    budget[0] -= 1
    previous, repeats = "", 0
    for child in node.children:
        if budget[0] <= 0:
            out.append("  " * (depth + 1) + "…")
            return
        signature = child.signature()
        if signature == previous:
            repeats += 1
            continue
        if repeats:
            out[-1] += f"   (x{repeats + 1})"
            repeats = 0
        previous = signature
        _render(child, depth + 1, out, budget)
    if repeats:
        out[-1] += f"   (x{repeats + 1})"


def outline(html: str) -> str:
    """The structure of one HTML page, as indented text.

    Never raises: malformed markup yields whatever was parsed before it, which
    is still a better description of the page than its first kilobyte.
    """
    reader = _Reader()
    try:
        reader.feed(str(html or ""))
        reader.close()
    except Exception:                                            # noqa: BLE001
        pass
    lines: list[str] = []
    for node in _keep(reader.root):
        _render(node, 0, lines, [MAX_NODES])
    text = "\n".join(lines)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS].rsplit("\n", 1)[0] + "\n…"
    return text


def title_of(html: str) -> str:
    found = TITLE.search(str(html or ""))
    return _tidy(found.group(1)) if found else ""


# ---------------------------------------------------------------------------
# JSX / TSX outline — reads the actual UI structure from React source files
# ---------------------------------------------------------------------------

# JSX attribute patterns to strip so the HTML parser can read the tags.
_JSX_ATTR_STRIP = re.compile(
    r"""
    className\s*=\s*(?:\{[^}]*\}|"[^"]*"|'[^']*')   # className={…} or "…"
    | style\s*=\s*\{[^}]*\}                           # style={{…}}
    | on[A-Z]\w*\s*=\s*\{[^}]*\}                     # onClick={…}
    | ref\s*=\s*\{[^}]*\}                             # ref={…}
    | key\s*=\s*\{[^}]*\}                             # key={…}
    | \w[\w.]*\s*=\s*\{[^}]*\}                        # any other ={…} prop
    """,
    re.VERBOSE,
)


# Self-closing JSX components (PascalCase) — map to semantic equivalents
_COMPONENT_MAP = {
    "header": "header", "navbar": "nav", "nav": "nav", "sidebar": "aside",
    "footer": "footer", "main": "main", "hero": "section", "banner": "section",
    "form": "form", "modal": "dialog", "table": "table", "card": "article",
    "button": "button", "input": "input", "select": "select", "textarea": "textarea",
    "section": "section", "article": "article",
}

_PASCAL_COMPONENT = re.compile(r"<([A-Z][a-zA-Z0-9]*)(\s[^>]*)?>", re.MULTILINE)


def _extract_jsx_markup(jsx: str) -> str:
    """Pull just the JSX/HTML markup out of a React component source file.

    Strategy:
    1. Strip import/export/hook lines that clearly contain no markup.
    2. Find every `return (` block and collect its content.
    3. If no explicit return block found, fall back to scanning the whole text.

    Returns the extracted markup text, which may still contain JS expressions
    that the subsequent cleanup strips.
    """
    text = str(jsx or "")

    # --- Step 1: Remove non-markup lines safely (line-by-line, not greedy) ---
    clean_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        # Skip imports, simple hook-only lines, exports, comments
        if (stripped.startswith("import ") or
                stripped.startswith("//") or
                stripped.startswith("* ") or
                stripped.startswith("/*") or
                stripped.startswith("*/") or
                stripped.startswith("'use ") or
                stripped.startswith('"use ') or
                re.match(r"^export\s+(?:default\s+)?(?:function|class|const|let|var)\s+\w", stripped) or
                re.match(r"^(?:const|let|var)\s+\w+\s*=\s*use\w+", stripped) or
                re.match(r"^console\.\w+\(", stripped)):
            continue
        clean_lines.append(line)
    text = "\n".join(clean_lines)

    # --- Step 2: Extract return (...) blocks ---
    # Find "return (" and collect balanced parentheses content
    collected: list[str] = []
    i = 0
    while i < len(text):
        m = re.search(r"\breturn\s*\(", text[i:])
        if not m:
            break
        start = i + m.end()
        depth = 1
        j = start
        while j < len(text) and depth > 0:
            if text[j] == "(":
                depth += 1
            elif text[j] == ")":
                depth -= 1
            j += 1
        collected.append(text[start:j - 1])
        i = j

    return "\n".join(collected) if collected else text


def _jsx_to_html(jsx: str) -> str:
    """Convert JSX source to pseudo-HTML the standard parser can read.

    Not a correct JSX parser — it does not handle all edge cases. It strips
    JS expressions and attribute syntax that would confuse the HTML parser and
    turns PascalCase component names into their nearest semantic equivalent.
    The result is structurally representative enough for an outline.
    """
    text = _extract_jsx_markup(str(jsx or ""))

    # Strip JSX attribute syntax that would confuse the HTML parser
    text = _JSX_ATTR_STRIP.sub("", text)

    # Map PascalCase components to semantic HTML equivalents
    def _map_component(m: re.Match) -> str:
        name = m.group(1).lower()
        for key, tag in _COMPONENT_MAP.items():
            if key in name:
                return f"<{tag}>"
        return "<div>"

    text = _PASCAL_COMPONENT.sub(_map_component, text)

    # Closing PascalCase tags: </ComponentName> → </div>
    text = re.sub(r"</[A-Z][a-zA-Z0-9]*>", "</div>", text)

    # Self-closing tags: <input /> → <input>
    text = re.sub(r"\s*/\s*>", ">", text)

    # Strip JSX expression blocks {…} — these are JS values inside markup
    text = re.sub(r"\{[^}]*\}", " ", text)

    # Collapse excessive whitespace
    text = re.sub(r"\s{3,}", " ", text)
    return text



def outline_jsx(jsx: str) -> str:
    """The structure of one JSX / TSX component, as indented text.

    Converts the JSX markup to pseudo-HTML and feeds it through the same
    structural outline pipeline as a real HTML page. This means the wireframe
    generator sees the same kind of outline regardless of whether the page
    comes from a `.html` prototype file or a `.jsx` build file.

    Never raises: a file that cannot be parsed yields an empty string, and
    the caller treats that as 'nothing to redraw'.
    """
    try:
        pseudo_html = _jsx_to_html(jsx)
    except Exception:                                            # noqa: BLE001
        return ""
    return outline(pseudo_html)


def title_of_jsx(jsx: str) -> str:
    """Best-effort page title from a JSX file.

    Looks for <title>, a string inside <h1>, or a metadata title= prop.
    """
    text = str(jsx or "")
    # Next.js metadata export: export const metadata = { title: "..." }
    meta_title = re.search(r"title\s*:\s*['\"]([^'\"]+)['\"]", text)
    if meta_title:
        return _tidy(meta_title.group(1))
    # <title>…</title>
    html_title = TITLE.search(text)
    if html_title:
        return _tidy(html_title.group(1))
    # First h1 text
    h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", text, re.IGNORECASE)
    if h1:
        return _tidy(h1.group(1))
    return ""

