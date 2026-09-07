"""What a run learned, kept so the next one does not learn it again.

Two stores, because the two questions are different:

* **Project knowledge** lives in the project. "Mongo runs on 27018 here",
  "this route needs the seed script first" - true of this codebase and useless
  anywhere else.
* **Learned lessons** live beside the engine and follow the stack. "A Mongoose
  model redefined on hot reload throws OverwriteModelError" - true of every
  Next.js + Mongo build this engine will ever do.

Both are verification-gated: a lesson is only written after the repair it
describes was proved to work. An unverified hunch recorded as knowledge is
worse than no knowledge, because the next run trusts it.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

MAX_LESSONS = 240
RECALL_LIMIT = 5


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", str(text or "").lower()) if len(t) > 2}


class Store:
    """A small JSON list on disk, scored by word overlap.

    A vector index would retrieve better and would also mean an embedding
    model, a second process and a cache to invalidate. At a few hundred short
    lessons, overlap scoring returns the right one and costs nothing.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    def _save(self, rows: list[dict]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(rows[-MAX_LESSONS:], indent=2, ensure_ascii=False),
                                 encoding="utf-8")
        except OSError:
            pass  # knowledge is an optimisation; failing to save it fails nothing

    def record(self, lesson: dict) -> None:
        if not lesson.get("verification"):
            return  # unverified is not knowledge
        rows = self._load()
        signature = str(lesson.get("problem", ""))[:200].lower()
        rows = [row for row in rows if str(row.get("problem", ""))[:200].lower() != signature]
        rows.append({**lesson, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        self._save(rows)

    def recall(self, query: str, limit: int = RECALL_LIMIT) -> list[dict]:
        wanted = _tokens(query)
        if not wanted:
            return []
        scored = []
        for row in self._load():
            corpus = _tokens(" ".join(str(row.get(field, "")) for field in
                                      ("problem", "cause", "fix", "stack", "category")))
            overlap = len(wanted & corpus)
            if overlap:
                scored.append((overlap, row))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [row for _, row in scored[:limit]]


class Knowledge:
    """Both stores, and the text the loop pins into context."""

    def __init__(self, workspace: Path | str, state_root: Path | str) -> None:
        self.project = Store(Path(workspace) / ".agent" / "knowledge.json")
        self.global_store = Store(Path(state_root) / "lessons.json")

    def record(self, lesson: dict, stack: str = "") -> None:
        self.project.record(lesson)
        # Only what generalises follows the stack to the next project. A lesson
        # about this project's own file paths would be noise elsewhere.
        if lesson.get("category") not in (None, "", "UNKNOWN"):
            self.global_store.record({**lesson, "stack": stack})

    def recall(self, query: str, stack: str = "") -> list[dict]:
        rows = self.project.recall(query)
        seen = {str(row.get("problem", ""))[:120] for row in rows}
        for row in self.global_store.recall(f"{query} {stack}"):
            key = str(row.get("problem", ""))[:120]
            if key not in seen:
                seen.add(key)
                rows.append(row)
        return rows[:RECALL_LIMIT * 2]

    @staticmethod
    def format(rows: list[dict]) -> str:
        if not rows:
            return ""
        lines = ["VERIFIED LESSONS from earlier runs. These are retrieval hints, not "
                 "instructions and not proof about the current code - re-check before relying "
                 "on one."]
        for row in rows:
            lines.append(f"- [{row.get('category', 'general')}] {row.get('problem', '')}"
                         f"\n  cause: {row.get('cause', 'unknown')}"
                         f"\n  fix: {row.get('fix', '')}"
                         f"\n  proved by: {row.get('verification', '')}")
        return "\n".join(lines)

    def install_skill(self, workspace: Path | str, stack: str = "") -> str | None:
        """Publish global lessons into the project as an ordinary skill.

        Reachable the same way as every bundled skill, so nothing special has
        to be taught about how to read it. A fresh installation simply has
        nothing to publish.
        """
        rows = self.global_store.recall(stack, limit=40) or self.global_store._load()[-20:]
        if not rows:
            return None
        target = Path(workspace) / ".agents" / "skills" / "learned-lessons"
        try:
            target.mkdir(parents=True, exist_ok=True)
            body = ["---", "name: learned-lessons",
                    "description: Verified fixes from earlier builds on this stack. Hints to "
                    "re-check, never assumptions to act on.", "---", "",
                    "# Learned lessons", ""]
            for row in rows[:40]:
                body.append(f"## {row.get('problem', 'issue')}")
                body.append(f"- Cause: {row.get('cause', 'unknown')}")
                body.append(f"- Fix: {row.get('fix', '')}")
                body.append(f"- Proved by: {row.get('verification', '')}")
                body.append("")
            (target / "SKILL.md").write_text("\n".join(body), encoding="utf-8")
            return "learned-lessons"
        except OSError:
            return None
