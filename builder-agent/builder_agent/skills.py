"""Skills: the guidance a build reads before it writes anything.

A skill is a Markdown file with front matter, shipped with the engine and
copied into the project it is about to be used on. Copying rather than
injecting matters: the model reads a skill once, on demand, instead of carrying
every skill in every prompt; the guidance stays visible in the workspace; and a
project can override a bundled skill by simply having its own file of that name.

Selection is evidence-driven. The stack's core skills always apply. Beyond
those, a skill is selected when the task text or the project's own manifest
mentions one of its terms - and explicitly de-selected when the request negates
that term, in English or in the Sinhala the studio's users actually type.
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .config import stack_for

ASSET_ROOT = Path(__file__).parent / "assets"
SKILL_ROOT = ASSET_ROOT / "skills"
MANIFEST = SKILL_ROOT / "skill-pack.json"
SKILL_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$", re.I)
VERIFICATION_PHASES = frozenset({"unit", "e2e", "runtime"})
MAX_SKILL_BYTES = 96 * 1024
# Suffixes that keep an example file inert inside a skill or template.
GUARD_SUFFIXES = (".txt", ".tpl")


def _normalise(value) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _contains(corpus: str, term: str) -> bool:
    needle = _normalise(term)
    if not needle:
        return False
    if re.fullmatch(r"[a-z0-9]+", needle):
        return needle in corpus.split(" ")
    return f" {needle} " in f" {corpus} "


def _negated(text: str, term: str) -> bool:
    """Was this term explicitly ruled out?

    The trailing forms are Sinhala: studio users write "docker nathuwa" and
    "docker epa" to mean "without docker", and a skill pack that ignored that
    pulled in guidance the user had just asked not to have.
    """
    hay, needle = _normalise(text), _normalise(term)
    if not hay or not needle:
        return False
    escaped = re.escape(needle)
    patterns = (
        rf"(?:^| )(?:no|without|avoid|exclude|excluding|disable|remove) (?:use |using )?{escaped}(?: |$)",
        rf"(?:^| )do not (?:use |select |install |add )?{escaped}(?: |$)",
        rf"(?:^| ){escaped} (?:nathuwa|epa|disabled|excluded|removed)(?: |$)",
    )
    return any(re.search(p, hay) for p in patterns)


@dataclass
class SkillPack:
    managed: list[str] = field(default_factory=list)
    selected: list[str] = field(default_factory=list)
    installed: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)
    phase_skills: dict[str, list[str]] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def read_manifest() -> dict[str, dict]:
    parsed = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if parsed.get("version") != 1 or not isinstance(parsed.get("skills"), list):
        raise ValueError("Unsupported bundled skill-pack manifest.")
    entries = {}
    for item in parsed["skills"]:
        name = item.get("name", "")
        phases = item.get("verificationPhases") or []
        if not SKILL_NAME.match(name) or not isinstance(item.get("match"), list) \
                or any(phase not in VERIFICATION_PHASES for phase in phases):
            raise ValueError(f"Invalid bundled skill-pack entry: {name!r}")
        entries[name] = {
            "name": name,
            "match": [str(term) for term in item["match"]],
            "requires": [str(term) for term in item.get("requires") or []],
            "phases": list(phases),
            "stacks": list(item["stacks"]) if isinstance(item.get("stacks"), list) else None,
        }
    return entries


def select(entries: dict, evidence: str, task: str, stack_id: str) -> list[str]:
    # The task is always part of what a skill is matched against. Keeping it a
    # separate argument that only the negation check reads was a foot-gun: a
    # caller that passed them apart got selection from the project alone.
    corpus = _normalise(task + "\n" + str(evidence or ""))
    stack = stack_for(stack_id)

    def available(name: str) -> bool:
        item = entries.get(name)
        # A skill declared for another stack is never selectable here. Without
        # this, ordinary project evidence - an express dependency, a stray
        # Dockerfile - pulls another stack's guidance into this build.
        return bool(item) and (not item["stacks"] or stack.id in item["stacks"]) \

    selected = {name for name in stack.skills if available(name)}
    for item in entries.values():
        if not available(item["name"]):
            continue
        if any(_negated(task, term) for term in item["match"]):
            continue
        if any(_contains(corpus, term) for term in item["match"]):
            selected.add(item["name"])
    # An extra is not part of the stack contract, so the request decides: it is
    # added when mentioned and left out when ruled out.
    for name in stack.extras:
        if available(name) and name in selected and any(
                _negated(task, term) for term in entries[name]["match"]):
            selected.discard(name)

    def visit(name: str) -> None:
        item = entries.get(name)
        if not item:
            raise ValueError(f"Bundled skill {name} requires an unknown skill.")
        for dependency in item["requires"]:
            if dependency not in selected:
                selected.add(dependency)
                visit(dependency)

    for name in list(selected):
        visit(name)
    return sorted(selected)


def install_skill_pack(workspace: Path | str, task: str = "", stack_id: str = "") -> SkillPack:
    """Copy the selected skills into the project, without ever overwriting."""
    pack = SkillPack()
    workspace = Path(workspace)
    try:
        entries = read_manifest()
        pack.managed = sorted(entries)
        manifest_text = ""
        package = workspace / "package.json"
        if package.is_file() and package.stat().st_size <= MAX_SKILL_BYTES:
            manifest_text = package.read_text(encoding="utf-8", errors="replace")
        stack = stack_for(stack_id)
        evidence = "\n".join([task, stack.tech, stack.unit_tool, stack.e2e_tool, manifest_text])
        pack.selected = select(entries, evidence, task, stack_id)

        for name in pack.selected:
            for phase in entries[name]["phases"]:
                pack.phase_skills.setdefault(phase, []).append(name)

        destination_root = workspace / ".agents" / "skills"
        for name in pack.selected:
            source = SKILL_ROOT / name
            if not source.is_dir():
                raise ValueError(f"Bundled skill directory is missing: {name}")
            destination = destination_root / name
            # A project's own version of a managed skill wins and is never
            # replaced: overriding a skill is the supported way to change it.
            if destination.exists():
                pack.preserved.append(name)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)
            pack.installed.append(name)
    except Exception as error:  # noqa: BLE001 - a missing pack must not stop a build
        pack.warnings.append(f"The project skill pack could not be prepared: {error}")
    return pack


# ---------------------------------------------------------------------------
# Reading skills at run time
# ---------------------------------------------------------------------------
def _front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    head, body = text[3:end], text[end + 4:]
    meta = {}
    for line in head.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip().strip("'\"")
    return meta, body.lstrip("\n")


def skill_index(workspace: Path | str, name: str) -> str:
    """A pack's index, front matter removed, for placing straight in a prompt.

    A pack index is a few kilobytes and every build needs it, so it is cheaper
    to carry it in the system prompt than to spend the first turn discovering
    it. Returns an empty string when the pack is not installed.
    """
    try:
        _, body = _front_matter(read_skill(workspace, name))
    except Exception:  # noqa: BLE001 - a missing pack must not stop a build
        return ""
    return body.strip()


def catalog(workspace: Path | str) -> list[dict]:
    """Every skill this project can read, project copies taking precedence."""
    found: dict[str, dict] = {}
    for root, source in ((SKILL_ROOT, "bundled"),
                         (Path(workspace) / ".agents" / "skills", "project")):
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            skill = entry / "SKILL.md"
            if not skill.is_file():
                continue
            meta, _ = _front_matter(skill.read_text(encoding="utf-8", errors="replace")[:4000])
            found[entry.name] = {"name": entry.name, "source": source,
                                 "description": meta.get("description", "")[:300]}
    return list(found.values())


def _unguarded(path: str) -> str:
    for guard in GUARD_SUFFIXES:
        if path.endswith(guard):
            return path[: -len(guard)]
    return path


def read_skill(workspace: Path | str, name: str, resource: str = "") -> str:
    """Read a skill body, or one of the files it references."""
    if not SKILL_NAME.match(str(name or "")):
        raise ValueError(f"Not a valid skill name: {name!r}")
    for root in (Path(workspace) / ".agents" / "skills", SKILL_ROOT):
        base = root / name
        if not base.is_dir():
            continue
        target = (base / resource) if resource else (base / "SKILL.md")
        # A resource path is model-supplied; it must not walk out of the skill.
        try:
            resolved = target.resolve()
            resolved.relative_to(base.resolve())
        except (OSError, ValueError):
            raise ValueError(f"{resource!r} is outside the {name} skill.") from None
        # Example files carry a guard suffix so npm does not treat a sketch as
        # a workspace and the project's own runner does not collect its tests.
        # The model asks for the logical name, which is the right thing to ask
        # for, so resolve the suffix here rather than spending a turn on it.
        for candidate in (resolved, *(resolved.with_name(resolved.name + guard)
                                      for guard in GUARD_SUFFIXES)):
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8", errors="replace")[:MAX_SKILL_BYTES]
        # The skill is real but that file is not. Naming what it does have
        # saves the turn that would otherwise be spent guessing again.
        have = sorted({_unguarded(item.relative_to(base).as_posix())
                       for item in base.rglob("*") if item.is_file()})
        raise ValueError(f"The {name} skill has no file {resource!r}. It contains: "
                         + ", ".join(have[:20]))
    raise ValueError(f"No skill named {name!r}. Call listSkills for the catalog.")
