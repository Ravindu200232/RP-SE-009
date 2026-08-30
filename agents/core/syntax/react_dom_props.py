"""Keeps common React DOM attribute names in the JSX form React expects."""
from __future__ import annotations

import re


REACT_DOM_PROP_ALIASES = {
    "accept-charset": "acceptCharset",
    "allowfullscreen": "allowFullScreen",
    "autocomplete": "autoComplete",
    "autofocus": "autoFocus",
    "cellpadding": "cellPadding",
    "cellspacing": "cellSpacing",
    "charset": "charSet",
    "class": "className",
    "colspan": "colSpan",
    "contenteditable": "contentEditable",
    "crossorigin": "crossOrigin",
    "datetime": "dateTime",
    "enctype": "encType",
    "for": "htmlFor",
    "formaction": "formAction",
    "formenctype": "formEncType",
    "formmethod": "formMethod",
    "formnovalidate": "formNoValidate",
    "formtarget": "formTarget",
    "frameborder": "frameBorder",
    "http-equiv": "httpEquiv",
    "maxlength": "maxLength",
    "minlength": "minLength",
    "novalidate": "noValidate",
    "playsinline": "playsInline",
    "readonly": "readOnly",
    "referrerpolicy": "referrerPolicy",
    "rowspan": "rowSpan",
    "spellcheck": "spellCheck",
    "srcset": "srcSet",
    "tabindex": "tabIndex",
    "usemap": "useMap",
}


# Fixes invalid HTML-style property names only inside lowercase JSX DOM tags.
def normalize_react_dom_props(rel: str, body: str) -> str:
    """Fix invalid React DOM property casing without touching normal JavaScript variables."""
    if not rel.endswith((".js", ".jsx", ".ts", ".tsx")) or "<" not in body:
        return body
    fixed = body
    for bad, good in REACT_DOM_PROP_ALIASES.items():
        pattern = rf"(<[a-z][\w.-]*\b[^<>]*?\s){re.escape(bad)}(\s*=)"
        fixed = re.sub(pattern, rf"\1{good}\2", fixed, flags=re.S)
    return fixed


# Finds HTML-style property names that would make React print an Invalid DOM property warning.
def find_invalid_react_dom_props(body: str) -> list[tuple[str, str]]:
    """Return each invalid DOM property and the React property name that should replace it."""
    found = []
    for bad, good in REACT_DOM_PROP_ALIASES.items():
        pattern = rf"<[a-z][\w.-]*\b[^<>]*?\s{re.escape(bad)}\s*="
        if re.search(pattern, body, flags=re.S):
            found.append((bad, good))
    return found
