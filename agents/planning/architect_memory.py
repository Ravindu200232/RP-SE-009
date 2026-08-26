"""Conversation compaction, safe paths, test invalidation and owned-file restore."""
from agents.planning.architect_core import *
from agents.planning.architect_core import _fix_doubled_tags, _strip_fence, _safe_flush_len, _RefusalLoop
from agents.planning.architect_prompts import *


class ArchitectMemoryMixin:
    def _convo_chars(self) -> int:
        return sum(len(m.get("content") or "") for m in self.convo)

    def _budget_chars(self) -> int:
        return int(self.num_ctx * HISTORY_BUDGET * CHARS_PER_TOKEN)

    def _bodies_stubbed(self) -> bool:
        """Has compaction already swapped file bodies for receipts?

        Read from the conversation rather than remembered in a flag, so it is
        still right after `resume()` loads a `convo.json` that was compacted in
        a previous session.
        """
        return any(STUB_MARK in (m.get("content") or "") for m in self.convo)

    def _room_for_snapshot(self, used: int) -> dict:
        """Caps that let a snapshot fit in what is left of the budget.

        Returns `{}` when there is not enough room to be worth it — a snapshot
        that pushes the thread over budget is stripped by `_trim_convo` on the
        way back, so sending it costs a turn and buys nothing.
        """
        headroom = self._budget_chars() - self._convo_chars() - used - 2_000
        if headroom < 6_000:
            return {}
        caps = self._snapshot_caps()
        per_file = min(caps["per_file"], max(1_200, headroom // 8))
        max_files = max(3, min(caps["max_files"], headroom // per_file))
        return {"max_files": int(max_files), "per_file": int(per_file)}

    @staticmethod
    def _stub_files(text: str) -> str:
        """
        Replace written-out file bodies with a one-line receipt.

        The model still remembers *what* it created and where, it just stops
        re-reading its own source. Current file contents are re-injected from
        disk when a later phase actually needs them.
        """
        def repl(m):
            path = m.group(2)
            lines = m.group(3).count("\n") + 1
            return (f'<write_file path="{path}">'
                    f'\n// {STUB_MARK} {lines} lines, still on disk]\n'
                    f'</{m.group(1)}>')

        return re.sub(r"<(write_file|file)\s+path\s*=\s*[\"']([^\"'>]+)[\"']\s*>"
                      r"(.*?)</\1>", repl, text, flags=re.S | re.I)

    @staticmethod
    def _strip_snapshot(text: str) -> str:
        """
        Take the fenced current-source block back out.

        A snapshot is worth everything for the turn it is attached to and worse
        than nothing after it. `_stub_files` only ever touched assistant turns,
        so these blocks — which are USER turns — survived into `convo.json`
        untouched and were replayed by `FeaturesAgent._memory()` at every later
        edit under "this is how we built this app together". The model then had
        two versions of the same file in front of it, one current and one
        weeks old, with nothing to say which was which.
        """
        return SNAPSHOT_RE.sub(
            "(source snapshot removed — re-read the files from disk)", text)

    def _trim_convo(self):
        """
        Keep the thread inside the context window.

        Cloud models have room for the whole build, so this is usually a no-op
        there. Local models compact oldest-first: full bodies → receipts, then
        drop the oldest turns entirely if still over budget.
        """
        budget = self._budget_chars()
        if self._convo_chars() <= budget:
            return

        for i in range(3, len(self.convo) - 1):
            stripped = self._strip_snapshot(self.convo[i]["content"])
            if stripped != self.convo[i]["content"]:
                self.convo[i]["content"] = stripped
                if self._convo_chars() <= budget:
                    self._log("INFO", "   🧠 Dropped an old source snapshot "
                                      "from memory")
                    return

        for i in range(3, len(self.convo) - 1):
            if self.convo[i]["role"] != "assistant":
                continue
            stubbed = self._stub_files(self.convo[i]["content"])
            if stubbed != self.convo[i]["content"]:
                self.convo[i]["content"] = stubbed
                if self._convo_chars() <= budget:
                    self._log("INFO", "   🧠 Compacted older code out of memory")
                    return

        dropped = 0
        while self._convo_chars() > budget and len(self.convo) > 5:
            self.convo.pop(3)
            dropped += 1
        if dropped:
            self._log("INFO", f"   🧠 Dropped {dropped} old turn(s) from memory")

        if self._convo_chars() > budget:
            preamble = sum(len(m["content"]) for m in self.convo[:3])
            self._log("WARN",
                      f"   🧠 Context is tight: {self._convo_chars():,} chars "
                      f"vs a {budget:,} budget "
                      f"({preamble:,} of it is the prompt and plan). "
                      f"A larger model, or a bigger local context window in "
                      f"Settings, would give the agent more room.")

    def memory_stats(self) -> dict:
        chars = self._convo_chars()
        return {
            "turns": len(self.convo),
            "approx_tokens": int(chars / CHARS_PER_TOKEN),
            "num_ctx": self.num_ctx,
            "cloud": self.is_cloud,
        }

    def _safe_path(self, rel: str) -> Path:
        """Normalise and confine a model-supplied path to the project dir."""
        rel = (rel or "").strip().strip("/\\").replace("\\", "/")
        rel = re.sub(r"^\./", "", rel)
        parts = [p for p in rel.split("/") if p not in ("", ".", "..")]
        if not parts:
            raise ValueError("empty path")
        return self.project_dir / "/".join(parts)

    JS_ONLY_RE = re.compile(r"^(lib/|app/(.+/)?route\.jsx?$)")
    JSX_ROLE_RE = re.compile(
        r"^(components/|app/(.+/)?"
        r"(page|layout|template|loading|error|global-error|not-found|default)\.jsx?$)")

    @classmethod
    def canonical_path(cls, key: str) -> str:
        """
        `key` with the extension its role requires, or `key` unchanged.

        JSX lives in pages, layouts and components; route handlers and lib
        modules are plain modules that never contain a tag. Anything else —
        config, css, json, markdown — is left alone.
        """
        if not key.endswith((".js", ".jsx")):
            return key
        stem = key[:-4] if key.endswith(".jsx") else key[:-3]
        if cls.JS_ONLY_RE.match(key):
            return stem + ".js"
        if cls.JSX_ROLE_RE.match(key):
            return stem + ".jsx"
        return key

    def _drop_tests_for(self, key: str, content: str) -> None:
        """
        A file just lost its exports. Take its tests with it.

        Removing a component is a legitimate repair — "nothing imported
        SiteNav, so it was replaced with a comment explaining why" is a real
        and correct fix. What is not correct is leaving nine tests pointed at
        it. They cannot pass, no repair can make them honest, they burn every
        round of the QA loop, and the file is set aside at the end as a silent
        loss of cases. Measured on one build: exactly that, nine of them.

        The manifest is the authority on which test belongs to which file, and
        it is on disk, so this needs no reference to the QA session. Reading it
        costs one file read on the rare write that empties a component.
        """
        if not key.endswith((".jsx", ".js")):
            return
        if key.startswith(("tests/", "app/api/")):
            return

        if re.search(r"^\s*export\b", content, re.M):
            return

        manifest_path = self.project_dir / ".agentforge" / "qa" / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return
        doomed = [t for t, meta in manifest.items()
                  if (meta or {}).get("target") == key]
        if not doomed:
            return

        for test_path in doomed:
            try:
                (self.project_dir / test_path).unlink(missing_ok=True)
            except OSError as e:
                log.debug(f"drop {test_path}: {e}")
                continue
            manifest.pop(test_path, None)
            self.files.pop(test_path, None)
            self._log("INFO", f"   🗑 {test_path} — {key} no longer exports "
                              f"anything, so its tests went with it")
        try:
            manifest_path.write_text(json.dumps(manifest, indent=2),
                                     encoding="utf-8")
        except OSError as e:
            log.debug(f"manifest after drop: {e}")

    REFUSE_SAME_PATH = 3
    REFUSE_TOTAL = 10

    def _stuck_on_refusals(self) -> bool:
        counts = [v["n"] for v in self._refused.values()]
        return (bool(counts) and (max(counts) >= self.REFUSE_SAME_PATH
                                  or sum(counts) >= self.REFUSE_TOTAL))

    def _refusal_note(self) -> str:
        """
        What was refused this turn, said once, for the next turn to read.

        The whole reason the loop was possible is that this never existed: a
        refusal was a log line, and the model reads its own output, not ours.
        """
        if not self._refused:
            return ""
        lines = [f"  {path} — {v['why']}"
                 for path, v in list(self._refused.items())[:12]]
        return ("\n\nThese writes were REFUSED and are not on disk. Writing "
                "them again will be refused again — do not retry them, and do "
                "not write anything else under the same paths:\n"
                + "\n".join(lines))

    def _refuse(self, key: str, why: str) -> bool:
        """
        Say no to a write, out loud, and remember that we did.

        Every guard in `write_file` used to `return False` and log a line the
        model never sees. From inside the stream a refusal is invisible: the
        block was emitted, nothing came back, so the model writes it again.
        Measured on a real build — 3,832 refused writes, the same eleven
        `app/api/auth/*` paths cycling for over twelve minutes in a single
        turn, and the build never finished.

        So the refusal is recorded here and `_run_write_loop` does two things
        with it: stops the turn once the model is plainly stuck, and tells it
        what was refused and why before the next one.
        """
        self._log("WARN", f"   ⛔ {key} {why}")
        seen = self._refused.setdefault(key, {"n": 0, "why": why})
        seen["n"] += 1
        return False

    def write_own(self, rel: str, content: str) -> bool:
        """Write a file AgentForge owns, and remember it.

        Used for the pieces the app cannot run without and the model has no
        business rewriting — the Better Auth instance, its client, its route.
        `restore_owned` reads what is recorded here.
        """
        self._owned[rel] = content
        return self.write_file(rel, content)

    def restore_owned(self) -> list:
        """Put back any generated file that no longer matches what was written.

        Runs before the app is verified, so a build cannot finish green over
        infrastructure that was quietly replaced with a stub. Seen on a real
        build: `lib/auth.js` came back as `export const auth = { api: {...} }`
        commented "a mock … in a real app this would be the actual Better Auth
        instance", which leaves `auth.handler` undefined and 500s every
        /api/auth/* request while every PAGE still answers 200.

        Comparison is exact text, not a heuristic: this only ever restores a
        file whose content AgentForge itself produced, so there is nothing to
        misjudge and nothing of the model's work to lose.
        """
        restored = []
        for rel, content in list(self._owned.items()):
            path = self.project_dir / rel
            try:
                on_disk = path.read_text(encoding="utf-8") if path.is_file() else None
            except Exception:
                on_disk = None
            if on_disk == content:
                continue

            was = self._scaffolding
            self._scaffolding = True
            try:
                if self.write_file(rel, content):
                    restored.append(rel)
                    self._log("WARN",
                              f"   ⏮ put {rel} back — it is generated and it "
                              f"had been {'rewritten' if on_disk else 'deleted'}")
            finally:
                self._scaffolding = was
        return restored

    def _merge_package_json(self, content: str) -> str:
        """A rewritten package.json, with the build toolchain put back.

        package.json is not an owned file — the model has to be able to add a
        dependency it decided to use. But it rewrites the WHOLE file to do
        that, and what it writes back is its own idea of the project, which
        drops what it was not thinking about.

        Measured, end to end, on a gym build: the model rewrote package.json
        without the scaffold's `devDependencies`. `unresolved_packages` then
        correctly reported `tailwindcss` as neither declared nor installed,
        the repair loop ran `npm install tailwindcss` — no version, because
        none was known any more — and npm installed Tailwind 4 into a project
        whose `postcss.config.js`, `tailwind.config.js` and `globals.css`
        are all Tailwind 3. Every build round after that died on "trying to
        use `tailwindcss` directly as a PostCSS plugin", the app never went
        green, the end-to-end stage was skipped for it, and nineteen minutes
        produced a project that does not start. AgentForge broke its own
        build, from a file the model was free to rewrite.

        So: the model's dependencies are kept and merged, and the pinned
        toolchain — the scripts and devDependencies the scaffold chose, which
        the config files on disk are written to match — is restored.
        """
        pinned = getattr(self, "_pinned", None)
        if not pinned and self.stack == "next":
            pinned = self.NEXT_PINNED
        if not pinned:
            return content
        try:
            theirs = json.loads(content)
            if not isinstance(theirs, dict):
                return content
        except Exception:
            return content

        before = json.dumps(theirs, sort_keys=True)
        deps = dict(theirs.get("dependencies") or {})
        for name, ver in (json.loads(self.files.get("package.json", "{}"))
                          .get("dependencies") or {}).items():
            deps.setdefault(name, ver)
        theirs["dependencies"] = dict(sorted(deps.items()))

        dev = dict(theirs.get("devDependencies") or {})
        changed = [n for n, v in pinned["devDependencies"].items()
                   if dev.get(n) != v]
        dev.update(pinned["devDependencies"])
        theirs["devDependencies"] = dict(sorted(dev.items()))
        theirs["scripts"] = {**(theirs.get("scripts") or {}), **pinned["scripts"]}

        if changed:
            self._log("WARN", f"   📌 package.json came back without the "
                              f"pinned {', '.join(changed)} — put back, "
                              f"because the config files on disk are written "
                              f"for those versions")
        out = json.dumps(theirs, indent=2)
        return out if json.dumps(theirs, sort_keys=True) != before else content
