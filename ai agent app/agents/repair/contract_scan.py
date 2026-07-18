"""agents/repair/contract_scan.py — ContractUsageScanner (P2).

Static check that a frontend file uses ONLY the field names the Canonical Contract Registry declares
for the entity it is typed with — catching model↔frontend field-name drift BEFORE the (slow) build.
TypeScript is the final authority (pages type rows as the entity DTO from `@/types`); this scanner is
the fast pre-build gate.

Deliberately CONSERVATIVE — it only inspects property accesses on variables that are *provably* typed
as an entity DTO (`useState<Entity[]>`, `x: Entity`, an `Entity` map callback param). It never guesses,
so it does not false-positive on untyped/generic records. Regex-based (no TS parser); good enough
because the generation contract makes the typing patterns predictable.
"""
from __future__ import annotations

import re
from pathlib import Path

_META = {"_id", "__v", "createdAt", "updatedAt"}
# array/string/object members that are never entity fields.
_MEMBERS = {
    "map", "filter", "forEach", "find", "findIndex", "some", "every", "reduce", "sort", "slice",
    "splice", "join", "includes", "indexOf", "length", "push", "pop", "shift", "concat", "flat",
    "toFixed", "toString", "toLocaleString", "toLocaleDateString", "toLocaleTimeString", "toISOString",
    "padStart", "padEnd", "trim", "split", "replace", "replaceAll", "match", "charAt", "keys", "values",
    "entries", "hasOwnProperty", "then", "catch", "finally", "json", "text", "ok", "status", "data",
    # DOM/React event + input members (a form var is often typed as its entity but reads e.target.value).
    # NOTE: keep `name`/`id`/`type` OUT — they are real entity fields (and `record.id` should be `_id`).
    "value", "checked", "target", "currentTarget", "preventDefault", "stopPropagation", "FormEvent",
    "ChangeEvent", "MouseEvent", "KeyboardEvent", "files", "valueAsNumber",
    "selectedOptions", "dataset", "closest", "querySelector", "focus", "blur",
}
_SKIP_DIRS = {"node_modules", ".next", ".locode", ".git"}


def _allowed(contract: dict) -> set[str]:
    return set(contract.get("fieldNames") or []) | _META


def _entity_vars(text: str, entity: str) -> set[str]:
    """Variable names provably typed as `entity` or `entity[]` in this file."""
    e = re.escape(entity)
    vs: set[str] = set()
    # const [x, setX] = useState<Entity[]>()
    for m in re.finditer(r"const\s*\[\s*(\w+)\s*,\s*\w+\s*\]\s*=\s*useState\s*<\s*" + e + r"\s*\[?\]?\s*>", text):
        vs.add(m.group(1))
    # const x: Entity[] =  /  let x: Entity =
    for m in re.finditer(r"\b(?:const|let|var)\s+(\w+)\s*:\s*" + e + r"(?:\[\])?\b", text):
        vs.add(m.group(1))
    # (x: Entity) / (x: Entity[]) callback or function param
    for m in re.finditer(r"\(\s*(\w+)\s*:\s*" + e + r"(?:\[\])?\s*[),]", text):
        vs.add(m.group(1))
    # x as Entity
    for m in re.finditer(r"\b(\w+)\s+as\s+" + e + r"\b", text):
        vs.add(m.group(1))
    # any Entity var that is .map()'d binds its callback param to Entity too
    for base in list(vs):
        for m in re.finditer(r"(?<![\w$])" + re.escape(base) +
                             r"\.(?:map|filter|find|forEach|some|every)\(\s*\(?\s*(\w+)", text):
            vs.add(m.group(1))
    return vs


def scan_text(rel: str, text: str, registry: dict) -> list[dict]:
    """[{file, line, entity, field}] for field accesses not in the entity contract."""
    imported: set[str] = set()
    for m in re.finditer(r"import\s+type\s*\{([^}]*)\}\s*from\s*['\"]@/types(?:/index)?['\"]", text):
        for nm in m.group(1).split(","):
            nm = nm.strip()
            if nm in registry:
                imported.add(nm)
    findings: list[dict] = []
    seen: set[tuple] = set()
    for entity in imported:
        allowed = _allowed(registry[entity])
        for v in _entity_vars(text, entity):
            # `t` is a common map parameter. Without the identifier boundary below it matched the
            # tail of unrelated names (`result.success`, `React.useEffect`) and reported their
            # members as Tea fields.
            for m in re.finditer(r"(?<![\w$])" + re.escape(v) + r"(?:\?\.|\.)(\w+)", text):
                prop = m.group(1)
                if prop in allowed or prop in _MEMBERS:
                    continue
                key = (v, prop)
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "file": rel, "line": text[:m.start()].count("\n") + 1,
                    "entity": entity, "field": prop,
                })
    return findings


def scan_project(project_dir: Path, registry: dict) -> dict[str, list[dict]]:
    """{rel: [findings]} for every frontend file. Empty == no contract drift detected."""
    project_dir = Path(project_dir)
    report: dict[str, list[dict]] = {}
    if not registry:
        return report
    for base in ("app", "components"):
        root = project_dir / base
        if not root.exists():
            continue
        for fp in root.rglob("*.tsx"):
            if any(p in _SKIP_DIRS for p in fp.parts):
                continue
            try:
                text = fp.read_text(encoding="utf-8")
            except Exception:
                continue
            found = scan_text(fp.relative_to(project_dir).as_posix(), text, registry)
            if found:
                report[fp.relative_to(project_dir).as_posix()] = found
    return report
