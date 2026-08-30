"""Gives agents safe, read-only access to the current project."""
from __future__ import annotations

import json
import re
from pathlib import Path

TOOL_HELP = r"""
AGENTIC WORKSPACE TOOLS — use them only when current context is insufficient.
Ask for at most four read-only tools in one turn, one tag per line.  AgentForge
will return the observations and you continue the SAME task.  Do not repeat an
identical request.

<read_file path="app/cart/page.jsx"/>
<search_code query="stock_quantity"/>
<list_files prefix="components/"/>
<route_source path="/products/123"/>
<importers path="components/ProductCard.jsx"/>
<dependency_closure path="app/checkout/page.jsx"/>
<dependency_neighborhood path="app/checkout/page.jsx"/>
<tests_for path="components/ProductCard.jsx"/>
<route_map prefix="/"/>
<plan_query query="checkout"/>

After the observations, make the smallest complete change.  Never ask the user
to copy a file that these tools can inspect.
"""

_TAGS = {
    "read_file": re.compile(r"<read_file\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "search_code": re.compile(r"<search_code\s+query=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "list_files": re.compile(r"<list_files\s+prefix=[\"']([^\"']*)[\"']\s*/?>", re.I),
    "route_source": re.compile(r"<route_source\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "importers": re.compile(r"<importers\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "dependency_closure": re.compile(r"<dependency_closure\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "dependency_neighborhood": re.compile(r"<dependency_neighborhood\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "tests_for": re.compile(r"<tests_for\s+path=[\"']([^\"']+)[\"']\s*/?>", re.I),
    "route_map": re.compile(r"<route_map\s+prefix=[\"']([^\"']*)[\"']\s*/?>", re.I),
    "plan_query": re.compile(r"<plan_query\s+query=[\"']([^\"']+)[\"']\s*/?>", re.I),
}

_IMPORT_RE = re.compile(r"(?:from\s+|import\s*\(\s*)['\"]([^'\"]+)['\"]")
_SIDE_EFFECT_IMPORT_RE = re.compile(
    r"(?:^|[;\n])\s*import\s*['\"]([^'\"]+)['\"]", re.M)


# Extracts local import specifications from one source file.
def _import_specs(body: str) -> list[str]:
    """Extract local import specifications from one source file."""
    specs = list(_IMPORT_RE.findall(str(body or "")))
    specs.extend(_SIDE_EFFECT_IMPORT_RE.findall(str(body or "")))
    return list(dict.fromkeys(specs))



# Normalize one user/tool path into the workspace path format.
def _clean(value: str) -> str:
    """Normalize one user/tool path into the workspace path format."""
    value = str(value or "").strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


