"""Failure digesting, repair acceptance, mocks and hoisting checks."""
from .author_common import *


class UnitAuthorRepairMixin:
    @staticmethod
    def _failure_signature(fails) -> str:
        """
        What this round failed on, as one comparable string.

        Sorted, because the runner's order is not stable, and truncated per
        message so a line number moving does not read as progress.
        """
        return "|".join(sorted(
            f"{getattr(f, 'name', '')}::{str(getattr(f, 'message', ''))[:80]}"
            for f in (fails or [])))

    def _restore(self, path, t, body, phase) -> None:
        """Put a known-better version of a test file back on disk."""
        if not (self.qa and body):
            return
        try:
            self.qa.write_test_file(path, body, target=(t.path if t else ""),
                                    phase=phase, tier=(t.tier if t else 0))
        except Exception as e:                              # noqa: BLE001
            self._log("WARN", f"   ⚠ could not restore {path}: {e}")

    @staticmethod
    def _failure_digest(fails, limit: int = 8) -> str:
        """
        The failures, with the same error said once.

        A file that forgot one `vi.mock` fails every case with the identical
        message. Listing it five times spends the prompt on repetition and
        makes five separate-looking problems out of one — measured, that is
        the exact shape of 39% of all first-run failures, where one mistake
        killed every case in the file.

        So: group by the message, name the cases it took down, and keep the
        stack from the copy that has one. Saying "5 cases, all of them this"
        is also the more useful sentence — it tells the model the fault is in
        the setup, not in five different assertions.
        """
        groups = {}
        for f in (fails or []):
            key = " ".join(str(getattr(f, "message", "")).split())[:200]
            g = groups.setdefault(key, {"names": [], "stack": "", "dom": "",
                                        "hint": ""})
            g["names"].append(str(getattr(f, "name", "")))
            if not g["stack"] and getattr(f, "stack", ""):
                g["stack"] = f.stack
            if not g["dom"] and getattr(f, "dom", ""):
                g["dom"] = f.dom
            if not g["hint"] and getattr(f, "hint", ""):
                g["hint"] = f.hint

        lines = []
        for index, (message, g) in enumerate(list(groups.items())[:limit]):
            names = g["names"]
            if len(names) == 1:
                head = f"  • {names[0]}"
            else:
                shown = ", ".join(names[:3])
                more = f" and {len(names) - 3} more" if len(names) > 3 else ""
                head = (f"  • {len(names)} cases failed with the SAME error "
                        f"— {shown}{more}")
            frames = [ln.strip() for ln in (g["stack"] or "").splitlines()
                      if ln.strip().startswith("at ")][:3]
            entry = (head + f"\n    {message}"
                     + ("\n" + "\n".join(f"      {ln}" for ln in frames)
                        if frames else ""))

            if g["dom"] and index < 2:
                body = "\n".join(f"      {ln}" for ln in g["dom"].splitlines())
                entry += "\n    what actually rendered:\n" + body

            if g["hint"]:
                body = "\n".join(f"    {ln}" for ln in g["hint"].splitlines())
                entry += "\n" + body
            lines.append(entry)
        if len(groups) == 1 and len(next(iter(groups.values()))["names"]) > 1:
            lines.append("\n  Every case failed the same way, so the fault is "
                         "almost certainly in the setup above the first test, "
                         "not in the assertions.")
        return "\n".join(lines)

    def _fix_prompt(self, path, t, target_src, test_src, fails) -> str:
        """Everything needed to fix one file, and nothing about the others."""

        parts = [f"This test file has been RUN and it is failing. Fix it.",
                 "",
                 "You may only write the TEST file — the application code is "
                 "not yours to change. But you are not required to pretend the "
                 "component is correct:\n"
                 "  • If the test asks for something the component genuinely "
                 "does differently, correct the test.\n"
                 "  • If `what actually rendered` shows the component produced "
                 "NOTHING where it should have produced something, then the "
                 "test is describing the app correctly and the APP is wrong. "
                 "Do NOT weaken the assertion to match empty output. Leave the "
                 "case as it is and add a comment above it beginning "
                 "`// AGENTFORGE-APP-BUG:` saying what the component should have "
                 "rendered and what it rendered instead.\n"
                 "Keep every case that already passes, and do NOT add new ones "
                 "— a round that fixes two cases and introduces three is a "
                 "round that made this file worse."]
        if t and target_src:
            parts.append(f"## The component under test — {t.path}\n"
                         f"```jsx\n{target_src[:12000]}\n```")
        parts.append(f"## The test as it stands — {path}\n"
                     f"```jsx\n{test_src[:12000]}\n```")

        advice = self._advice.get(path)
        if advice:
            parts.append(f"## A static check says\n{advice}.")
        if fails:
            parts.append("## What the run reported\n" + self._failure_digest(fails))

        parts.append(f"Emit the COMPLETE corrected file in ONE <write_file "
                     f'path="{path}"> block, and nothing else.')
        return "\n\n".join(parts)

    def _accept(self, path, content, assigned, written, rejected, phase,
                lock=None):
        """
        The write allowlist — the identity rule, not just the shape rule.

        `lock` is passed when several fixes are in flight at once. Only the
        shared bookkeeping needs it; the file write itself is one path per
        worker and cannot collide.

        `on_file_end` fires for a refused write too, and has to. It is the
        other half of the `on_file_start` the parser already fired when the
        model opened the block, and the studio's code pane treats an open
        stream as "a file is being written right now": it shows the live buffer
        and ignores clicks on the file list, because during a build the pane
        follows the writer rather than the reader. A write refused here never
        sent its end, so the pane stayed locked on a file that had stopped
        arriving — every click on every other file did nothing, for the rest of
        the session. Refusing the write is still refusing it: nothing is
        written to disk and the path goes on `rejected`.
        """
        guard = lock or _NULL_LOCK
        key = (path or "").strip().lstrip("./").replace("\\", "/")
        if key not in assigned:
            with guard:
                rejected.append(key)
            self._fire("on_file_end", key, content)
            return
        t = assigned[key]

        advice = ""

        if advice:
            self._log("WARN", f"   ⚠ {key}: {advice}")
        with guard:
            if advice:
                self._advice[key] = advice
            else:
                self._advice.pop(key, None)
        self._fire("on_file_end", key, content)

        with guard:
            if self.qa and self.qa.write_test_file(key, content, target=t.path,
                                                   phase=phase, tier=t.tier):

                if key not in written:
                    written.append(key)

    TESTID_Q_RE = re.compile(
        r"""\b(?:get|find|query)(?:All)?ByTestId\s*\(\s*(['"])(.+?)\1""")

    TEXTATTR_Q_RE = re.compile(
        r"""\b(?:get|find|query)(?:All)?By(LabelText|AltText|Title)\s*\(\s*(['"])(.+?)\2""")

    TEXTATTR_SOURCES = {
        "LabelText": ("aria-label", "<label", "aria-labelledby"),
        "AltText": ("alt",),
        "Title": ("title",),
    }

    ROLE_Q_RE = re.compile(
        r"""\b(?:get|find|query)(?:All)?ByRole\s*\(\s*(['"])(.+?)\1""")

    IMPLICIT_ROLES = {
        "heading": ("<h1", "<h2", "<h3", "<h4", "<h5", "<h6"),
        "button": ("<button",),
        "link": ("<a ", "<a\n", "<link", "<a>"),
        "img": ("<img", "<image"),
        "listitem": ("<li",),
        "list": ("<ul", "<ol"),
        "textbox": ("<input", "<textarea"),
        "searchbox": ("<input",),
        "checkbox": ("<input",),
        "radio": ("<input",),
        "switch": ("<input",),
        "slider": ("<input",),
        "spinbutton": ("<input",),
        "combobox": ("<select", "<input"),
        "option": ("<option",),
        "table": ("<table",),
        "row": ("<tr",),
        "cell": ("<td",),
        "columnheader": ("<th",),
        "rowheader": ("<th",),
        "form": ("<form",),
        "navigation": ("<nav",),
        "banner": ("<header",),
        "main": ("<main",),
        "contentinfo": ("<footer",),
        "article": ("<article",),
        "separator": ("<hr",),
        "dialog": ("<dialog",),

        "presentation": (),
        "none": (),
    }

    DECL_RE = re.compile(r"^\s*(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", re.M)
    HOISTED_RE = re.compile(
        r"(?:const|let|var)\s+(?:\{([^}]*)\}|([A-Za-z_$][\w$]*))\s*=\s*vi\.hoisted")
    IDENT_RE = re.compile(r"\b([A-Za-z_$][\w$]*)\b")

    @staticmethod
    def _mock_calls(test_src: str):
        """`(specifier, factory_body, start, end)` for every `vi.mock(…)`."""
        out = []
        for m in re.finditer(r"vi\.mock\s*\(\s*(['\"])(.+?)\1", test_src):
            i, depth = test_src.index("(", m.start()), 0
            while i < len(test_src):
                if test_src[i] == "(":
                    depth += 1
                elif test_src[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            out.append((m.group(2), test_src[m.end():i], m.start(), i))
        return out

    @classmethod
    def _mock_bodies(cls, test_src: str) -> list:
        return [b for _, b, _, _ in cls._mock_calls(test_src)]

    def _mock_paths(self, test_src: str, test_rel: str) -> str:
        """
        A `vi.mock` specifier that resolves to nothing.

        Vitest resolves the path against the file that CALLS `vi.mock` — the
        test — not against the component being tested. So a component at
        `components/RouteGrid.jsx` importing `'./RouteCard'` must be mocked
        from `tests/unit/components/RouteGrid.test.jsx` as
        `'@/components/RouteCard'`; copying the component's own `'./RouteCard'`
        points at `tests/unit/components/RouteCard`, which does not exist.

        Nothing complains. The mock is simply never applied, the real child
        renders, and every assertion about the stub's markup fails — measured
        as four failures in one file that survived three rounds of fixing,
        because the errors all pointed at a missing `data-testid` and none of
        them mentioned the mock.
        """
        if not self.project_dir:
            return ""
        base = Path(self.project_dir)
        here = (base / test_rel).parent
        bad = []
        for spec, _, _, _ in self._mock_calls(test_src):
            if not spec.startswith("."):
                continue
            cands = [here / spec, *(Path(str(here / spec) + e)
                                    for e in (".js", ".jsx", ".ts", ".tsx"))]
            if any(c.exists() for c in cands):
                continue

            name = Path(spec).name
            hit = next((p for p in base.glob(f"components/**/{name}.js*")), None)
            hint = (f" — write it as '@/{hit.relative_to(base).as_posix()}'"
                    .replace(".jsx'", "'").replace(".js'", "'")) if hit else ""
            bad.append(f"'{spec}'{hint}")
        if not bad:
            return ""
        return (f"its vi.mock path {', '.join(bad[:2])} resolves to nothing "
                f"from the TEST file, so the mock never applies")

    def _hoisting_error(self, test_src: str) -> str:
        """
        A `vi.mock` factory that closes over a variable declared below it.

        `vi.mock` is hoisted to the top of the file, above every `const`, so a
        factory referring to one throws
        "Cannot access 'MockThing' before initialization" at import time. The
        whole file then collects zero tests and AgentForge reports it as
        "the test file does not parse" — which sends the repair agent looking
        for a syntax error that is not there. Measured: one build quarantined a
        perfectly good component test for exactly this.

        `vi.hoisted` is the fix and the prompt already says so; this is the
        half that does not rely on the model remembering.
        """
        safe = set()
        for braced, plain in self.HOISTED_RE.findall(test_src):
            if plain:
                safe.add(plain)
            for part in (braced or "").split(","):
                part = part.split(":")[-1].strip()
                if part:
                    safe.add(part)

        bodies, spans = [], []
        for m in re.finditer(r"vi\.mock\s*\(", test_src):
            i, depth = m.end() - 1, 0
            while i < len(test_src):
                if test_src[i] == "(":
                    depth += 1
                elif test_src[i] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            bodies.append(test_src[m.end():i])
            spans.append((m.start(), i))

        if not bodies:
            return ""
        outside = test_src
        for start, end in reversed(spans):
            outside = outside[:start] + outside[end:]
        declared = set(self.DECL_RE.findall(outside)) - safe
        if not declared:
            return ""

        bad = set()
        for body in bodies:
            bad |= {n for n in self.IDENT_RE.findall(body) if n in declared}
        if not bad:
            return ""
        return (f"its vi.mock factory uses {', '.join(sorted(bad)[:3])}, which "
                f"is declared below it — vi.mock is hoisted, so this throws "
                f"\"Cannot access before initialization\". Use vi.hoisted")
