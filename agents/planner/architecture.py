"""Application architecture and build execution from the approved LLM plan."""
from __future__ import annotations

import json
import logging
import os
import re
import textwrap
import time
from pathlib import Path

from agents.core import docsindex
from agents.core.commands import CommandRunner
from agents.core.exports_checks import check_named_imports, group_messages
from agents.core.ollama_client import OllamaClient, is_cloud_model, max_context
from agents.planner.architecture_runtime import (
    CMD_RE, FENCE_RE, OPEN_RE, PARTIAL_OPEN_RE, FileStreamParser, _strip_fence,
)
from agents.planner.build_templates import KNOWN_DEPENDENCIES, render_templates
from agents.planner.planning import NEXT_STACK, PROMPT_PATH, VITE_STACK, PlannerAgent


log = logging.getLogger("architect")
CHARS_PER_TOKEN = 3.4
HISTORY_BUDGET = 0.62
EDIT_TIMEOUT = 150

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Create or overwrite one complete project-relative file.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
            "required": ["path", "content"],
        },
    },
}

NEXT_BUILDER_SYSTEM = """\
You are a senior Next.js engineer implementing one approved AgentForge plan.
The plan is a contract, not a suggestion. Write finished production-quality
files in plan order using complete <write_file path="…">…</write_file> blocks.

QUALITY BAR
- Implement every section, action, requirement, API contract, data read/write,
  design decision, responsive rule, and E2E-visible outcome assigned to a file.
- No TODO, placeholder, coming-soon screen, href="#", fake JSX record, dead
  button, console-only error, or permanently disabled feature.
- A list/table/fetched panel has designed loading, empty, error, and success
  behavior. The empty state explains what belongs there and provides the real
  next action. Mutation success updates state, refreshes, or navigates without a
  manual reload. Pending controls disable and say what is happening.
- Preserve the approved palette, type scale, spacing, radii, depth, component
  states, content hierarchy, and mobile behavior. Every interactive element has
  rest, hover, visible keyboard focus, and disabled states when applicable.
- Use semantic elements, associated labels, stable accessible names, useful alt
  text, keyboard operation, readable contrast, and reduced-motion behavior.
- Put literal data-testid values only where the plan names them.

STACK AND FILE BOUNDARIES
- Next.js 16 App Router + React 19 + JavaScript. Never TypeScript, Pages Router,
  react-router-dom, Mongoose, Prisma, next/image, next/head, or a second Mongo client.
- JSX files contain UI; route and lib modules use .js. One default export per page
  or component. Route handlers have named GET/POST/PUT/PATCH/DELETE exports only.
- Server files must await every getCollection(name) and getSessionUser() call; both
  return promises. Server files must not use hooks or
  event handlers. Client files begin with 'use client', are never async, never
  import server/database modules, and reach persistence through planned APIs.
- A page needing DB reads and interaction stays a server page plus a planned
  client child. Serialize Mongo documents before crossing that boundary. Pass
  strings instead of icon component functions and never pass event callbacks
  from a server component into a client component.
- Await params and searchParams. Validate ObjectId strings and convert only at
  the database boundary. Use the declared field representation consistently.
- Files that read MongoDB export `const dynamic = 'force-dynamic'`.
- Imports use @/ across app/components/lib and may reference only files already
  present or named in the approved file plan. Fetch URLs are relative literals.

DATA, AUTH, AND ACTIONS
- Use exact collection and field names from the plan. Seed every planned demo
  row with stable identity upserts and $setOnInsert; keep seeds small and
  idempotent. Never count-gate seeding, make a unique index, or open a transaction.
- Add auth only when roles_and_access.authentication_required is true. Better
  Auth defaults already exist. Server code imports getSessionUser from
  @/lib/auth; client code imports signIn/signUp/signOut/useSession from
  @/lib/auth-client. Never create /api/auth routes, sessions, cookies, hashes,
  auth wrappers, or show demo credentials in the app.
- Better Auth defaults expose `ensureDemoAccounts()`, which creates credential
  provider accounts through `auth.api.signUpEmail` before auth requests. Product
  seed code may await that helper but must never insert `{ email, password }`
  directly into a Mongo users collection; that cannot sign in.
- Ownership, role, price, totals, and user identity come from the session and
  database, never trusted request fields. API status/messages match the plan.
- Every visible action completes its full UI -> API/server -> persistence -> UI
  path and every navigation target exists in the site map.

Write only the requested files. Do not narrate and do not stop halfway through
a file. When all requested files are complete, say BUILD COMPLETE.
"""

VITE_BUILDER_SYSTEM = """\
You are a senior React/Vite engineer implementing an approved AgentForge plan.
Write complete <write_file path="…">…</write_file> blocks. Implement every
planned screen, action, state, design decision, responsive rule, persistence
behavior, and E2E outcome. Use React 18, JavaScript .jsx, Tailwind,
react-router-dom v6, localStorage, lucide-react, and framer-motion. Do not write
stubs, fake controls, TypeScript, server code, private APIs, or unplanned files.
Every interaction has visible loading/error/success behavior, accessible names,
keyboard focus, and mobile layout. Do not narrate. Say BUILD COMPLETE at the end.
"""

NEXT_PLANNER_SYSTEM = PROMPT_PATH.read_text(encoding="utf-8") + "\n\n" + NEXT_STACK
VITE_PLANNER_SYSTEM = PROMPT_PATH.read_text(encoding="utf-8") + "\n\n" + VITE_STACK
NEXT_STACK_RULES, VITE_STACK_RULES = NEXT_STACK, VITE_STACK
PROMPTS = {
    "next": {"planner": NEXT_PLANNER_SYSTEM, "builder": NEXT_BUILDER_SYSTEM,
             "rules": NEXT_STACK_RULES, "roots": ("app/", "components/", "lib/"),
             "entry": ("app/page.jsx", "app/page.js")},
    "vite": {"planner": VITE_PLANNER_SYSTEM, "builder": VITE_BUILDER_SYSTEM,
             "rules": VITE_STACK_RULES, "roots": ("src/",),
             "entry": ("src/App.jsx", "src/App.js")},
}


class ArchitectAgent:
    """Plan, scaffold, build, resume, and update one generated application."""

    NEXT_SCAFFOLD = frozenset({
        "package.json", "next.config.mjs", "jsconfig.json", "tailwind.config.js",
        "postcss.config.js", "app/globals.css", "app/layout.jsx", "app/page.jsx",
        "lib/mongodb.js", "app/api/health/route.js", ".env.local", ".gitignore",
        "lib/auth.js", "lib/auth-client.js", "app/api/auth/[...all]/route.js",
    })
    NEXT_PROTECTED = NEXT_SCAFFOLD | {"vitest.config.mjs", "playwright.config.js"}
    VITE_PROTECTED = frozenset({
        "package.json", "vite.config.js", "tailwind.config.js",
        "postcss.config.js", "index.html", "src/main.jsx", "src/index.css",
        "vitest.config.mjs", "playwright.config.js",
    })
    NODE_BUILTINS = {"assert", "buffer", "child_process", "crypto", "events", "fs",
                     "fs/promises", "http", "https", "module", "net", "os", "path",
                     "process", "stream", "timers", "tls", "url", "util", "zlib"}
    PREINSTALLED = {"react", "react-dom", "next", "mongodb", "better-auth",
                    "@better-auth/mongo-adapter"}
    PKG_NAME_RE = re.compile(r"^(@[a-z0-9][\w.-]*/)?[a-z0-9][\w.-]*$", re.I)
    IMPORT_SPEC_RE = re.compile(r"(?:\bfrom\s*|\brequire\s*\(\s*|\bimport\s*\(\s*|\bimport\s+)[\"']([^\"'\s()]+)[\"']")
    LOCAL_IMPORT_RE = re.compile(r"(?:from\s+|import\s*)[\"'](\.[^\"']+)[\"']")
    ALIAS_IMPORT_RE = re.compile(r"(?:from\s+|import\s*)[\"']@/([^\"']+)[\"']")
    STRAY_DIRECTIVE_RE = re.compile(r"^[^\S\n]*[\"']use client[\"'][^\S\n]*;?", re.M)
    UNRESOLVED_RE = re.compile(r"(?:Can't resolve|Cannot find module)\s*[\"']([^\"'\n]+)[\"']")
    EDIT_TIMEOUT = EDIT_TIMEOUT

    def __init__(self, client: OllamaClient, model: str, project_dir: Path,
                 callbacks: dict | None = None, stack: str = "next",
                 mongo_uri: str = "", db_name: str = "", dev_port: int = 5173,
                 think: bool | None = None):
        self.client, self.model = client, model
        self.project_dir, self.cb = Path(project_dir), callbacks or {}
        self.stack = stack if stack in PROMPTS else "next"
        self.mongo_uri, self.db_name, self.dev_port = mongo_uri, db_name, dev_port
        self.files, self.plan, self.convo = {}, {}, []
        self.plan_md = self.architecture_md = self.design_md = ""
        self.tokens_in = self.tokens_out = self.write_seq = 0
        self.num_ctx, self.is_cloud, self.think = max_context(model), is_cloud_model(model), think
        self._scaffolding, self._scaffold_baseline = False, {}
        self._workspace_tool_cache, self._e2e_privileged_paths = {}, set()
        self.cmd = CommandRunner(
            self.project_dir, npm_bin=self.cb.get("npm_bin", "npm"),
            node_bin=self.cb.get("node_bin", "node"),
            on_log=lambda level, message: self._fire("on_log", level, message),
            on_event=lambda event: self._fire("on_command", event))

    def _fire(self, name: str, *args) -> None:
        callback = self.cb.get(name)
        if callable(callback):
            try:
                callback(*args)
            except Exception as exc:
                log.warning("callback %s failed: %s", name, exc)

    def _log(self, level: str, message: str) -> None:
        if callable(self.cb.get("on_log")):
            self._fire("on_log", level, message)
        else:
            log.info(message)

    @property
    def _P(self) -> dict:
        return PROMPTS[self.stack]

    def _planner_sys(self) -> str:
        return self._P["planner"]

    def _builder_sys(self) -> str:
        prompt = self._P["builder"]
        try:
            learned = __import__("agents.core.lessons", fromlist=["prompt_block"]).prompt_block()
            if learned:
                prompt += "\n\nPROJECT-GENERATION LESSONS\n" + learned
        except Exception as exc:
            log.debug("builder lessons unavailable: %s", exc)
        docs = docsindex.index_block(self.project_dir) if self.stack == "next" else ""
        return prompt + ("\n\nINSTALLED NEXT.JS DOCUMENT INDEX\n" + docs if docs else "")

    @property
    def source_roots(self) -> tuple:
        return self._P["roots"]

    def is_source(self, path: str) -> bool:
        return path.startswith(self.source_roots) and path.endswith((".js", ".jsx"))

    def _stream(self, messages, on_delta, tools=None, temperature=0.5,
                model=None, timeout=None, think=None):
        options = {"temperature": temperature, "top_p": 0.9, "num_ctx": self.num_ctx}
        selected_think = self.think if think is None else think
        started, chars = time.time(), 0
        calls = []
        for chunk in self.client.chat_stream(
                model or self.model, messages, tools=tools, options=options,
                keep_alive="10m", think=selected_think, timeout=timeout or 900):
            message = chunk.get("message") or {}
            delta = message.get("content") or ""
            if delta:
                chars += len(delta)
                on_delta(delta)
            calls.extend(message.get("tool_calls") or [])
            if chunk.get("done"):
                self.tokens_in += chunk.get("prompt_eval_count", 0) or 0
                self.tokens_out += chunk.get("eval_count", 0) or 0
            if chars >= 250_000:
                self._log("WARN", f"   ✂ stopped an oversized model turn after {chars:,} characters")
                break
            if time.time() - started > (timeout or 900):
                break
        return calls

    def _budget_chars(self) -> int:
        return int(self.num_ctx * HISTORY_BUDGET * CHARS_PER_TOKEN)

    def _trim_convo(self) -> None:
        budget = self._budget_chars()
        while sum(len(str(item.get("content") or "")) for item in self.convo) > budget and len(self.convo) > 4:
            self.convo.pop(3)

    def memory_stats(self) -> dict:
        chars = sum(len(str(item.get("content") or "")) for item in self.convo)
        return {"turns": len(self.convo), "approx_tokens": int(chars / CHARS_PER_TOKEN),
                "num_ctx": self.num_ctx, "cloud": self.is_cloud}

    def _safe_path(self, rel: str) -> Path:
        raw = str(rel or "").strip().replace("\\", "/").lstrip("/")
        parts = [part for part in raw.split("/") if part not in {"", ".", ".."}]
        if not parts:
            raise ValueError("empty project path")
        target = (self.project_dir / "/".join(parts)).resolve()
        root = self.project_dir.resolve()
        if target != root and root not in target.parents:
            raise ValueError("path leaves project")
        return target

    def write_file(self, rel: str, content: str) -> bool:
        try:
            target = self._safe_path(rel)
            key = target.relative_to(self.project_dir.resolve()).as_posix()
            protected = self.NEXT_PROTECTED if self.stack == "next" else self.VITE_PROTECTED
            planned = {item.get("path") for item in self._planned_files()}
            if key in protected and not self._scaffolding and key not in planned:
                self._log("WARN", f"   ⛔ kept scaffold-owned default {key}")
                return False
            body = _strip_fence(content).rstrip() + "\n"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            self.files[key], self.write_seq = body, self.write_seq + 1
            size = f"{len(body) / 1024:.1f}KB" if len(body) >= 1024 else f"{len(body)}B"
            self._fire("on_file_written", key, size, body)
            self._log("INFO", f"   📝 {key} ({size})")
            return True
        except Exception as exc:
            self._log("ERROR", f"   ❌ write failed {rel}: {exc}")
            return False

    def write_own(self, rel: str, content: str) -> bool:
        return self.write_file(rel, content)

    def make_plan(self, user_prompt: str, requirement_source: str = "") -> bool:
        self._log("INFO", "🧭 Planning — requirements, design, routes, architecture and E2E")
        self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "active"})
        planner = PlannerAgent(self.client, self.model, stack=self.stack,
                               callbacks=self.cb, think=self.think, stream=self._stream)
        bundle = planner.create(user_prompt, requirement_source)
        if not bundle:
            self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "error"})
            return False
        self.plan, self.plan_md = bundle.data, bundle.markdown
        self.architecture_md, self.design_md = bundle.architecture_markdown, bundle.design_markdown
        for path, body in (("plan.md", self.plan_md), ("architecture.md", self.architecture_md),
                           ("design.md", self.design_md)):
            self.write_file(path, body)
        self._save_plan_json()
        self.start_conversation(user_prompt)
        self.save_convo()
        self._fire("on_phase", {"phase": 0, "title": "Planning", "status": "done", "plan": self.plan})
        self._log("INFO", f"   ✅ Plan ready — {len(self.plan.get('requirements') or [])} requirements, "
                            f"{len(self.plan.get('routes') or [])} routes, "
                            f"{len(self.plan.get('file_plan') or [])} implementation files")
        return True

    def start_conversation(self, user_prompt: str) -> None:
        plan_json = json.dumps(self.plan, ensure_ascii=False, indent=2)
        self.convo = [
            {"role": "system", "content": self._builder_sys()},
            {"role": "user", "content": (
                "AUTHORITATIVE USER INPUT\n" + user_prompt +
                "\n\nAPPROVED PLAN JSON\n" + plan_json +
                "\n\nThe plan owns requirements, design, site map, routes, architecture, "
                "file contracts, and E2E proof. Do not alter it. Wait for the first build task.")},
            {"role": "assistant", "content": "Understood. I will implement the approved plan exactly, one complete file at a time."},
        ]

    def scaffold(self) -> None:
        self._log("INFO", f"🧱 Writing {self.stack} runtime defaults")
        self._scaffolding = True
        try:
            defaults = render_templates(self.stack, self.plan, mongo_uri=self.mongo_uri,
                                        db_name=self.db_name, dev_port=self.dev_port)
            for path, body in defaults.items():
                self.write_file(path, body)
                self._scaffold_baseline[path] = body.rstrip() + "\n"
        finally:
            self._scaffolding = False

    def _planned_files(self) -> list[dict]:
        return [item for item in self.plan.get("file_plan") or [] if isinstance(item, dict) and item.get("path")]

    def _implemented(self, path: str) -> bool:
        body = self.files.get(path)
        return body is not None and body != self._scaffold_baseline.get(path)

    def _outstanding(self) -> list[dict]:
        return [item for item in self._planned_files() if not self._implemented(item["path"])]

    def unfinished(self) -> list[str]:
        return [item["path"] for item in self._outstanding()]

    def _task_prompt(self, task: dict, files: list[dict]) -> str:
        payload = dict(task)
        payload["files"] = files
        cap_ids = {rid for file in files for rid in file.get("requirements") or []}
        capabilities = [cap for cap in self.plan.get("capabilities") or []
                        if cap_ids & set(cap.get("requirement_ids") or []) or
                        set(cap.get("files") or []) & {file["path"] for file in files}]
        apis = [api for api in self.plan.get("api_contracts") or []
                if api.get("handler_file") in {file["path"] for file in files} or
                set(api.get("called_from") or []) & {file["path"] for file in files}]
        return (
            "IMPLEMENT THIS APPROVED BUILD TASK. Write every listed file completely.\n\n"
            + json.dumps(payload, ensure_ascii=False, indent=2)
            + "\n\nCAPABILITIES TOUCHING THIS TASK\n"
            + json.dumps(capabilities, ensure_ascii=False, indent=2)
            + "\n\nAPI CONTRACTS TOUCHING THIS TASK\n"
            + json.dumps(apis, ensure_ascii=False, indent=2)
            + "\n\nUse exact planned names and paths. Output complete <write_file> blocks only."
        )

    def _run_write_loop(self, user_content: str, _tool_depth: int = 0) -> int:
        self._workspace_tool_cache = {} if _tool_depth == 0 else self._workspace_tool_cache
        self.convo.append({"role": "user", "content": user_content})
        self._trim_convo()
        raw, state = [], {"path": None, "count": 0}
        parser = FileStreamParser(
            lambda text: self._fire("on_chat", text.strip()) if text.strip() and "BUILD COMPLETE" not in text.upper() else None,
            lambda path: (state.update(path=path), self._fire("on_file_start", path)),
            lambda token: self._fire("on_file_token", state["path"], token),
            lambda path, body: (self._fire("on_file_end", path, body),
                                state.update(count=state["count"] + (1 if self.write_file(path, body) else 0), path=None)),
        )
        try:
            calls = self._stream(self.convo, lambda delta: (raw.append(delta), parser.feed(delta)), temperature=0.35)
        except Exception as exc:
            self._log("ERROR", f"   ❌ Generation failed: {exc}")
            calls = []
        parser.close()
        reply = "".join(raw)
        self.convo.append({"role": "assistant", "content": reply})
        self.run_requested_commands(reply)
        for call in calls:
            function = (call or {}).get("function") or {}
            if function.get("name") != "write_file":
                continue
            args = function.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    continue
            if args.get("path") and args.get("content") and self.write_file(args["path"], args["content"]):
                state["count"] += 1
        if state["count"] == 0 and _tool_depth < 2:
            try:
                from agents.core.workspace import WorkspaceTools
                observations, used = WorkspaceTools(self).serve(reply)
            except Exception as exc:
                observations, used = "", 0
                log.debug("workspace tool serving failed: %s", exc)
            if used:
                self.convo.append({"role": "user", "content": "Tool observations:\n" + observations})
                return self._run_write_loop("Continue the same task from those observations and write its files.", _tool_depth + 1)
        return state["count"]

    def build_app(self) -> int:
        total, phases, written = len(self._planned_files()), self.plan.get("phases") or [], 0
        self._log("INFO", f"⚙️  Building {total} planned files across {len(phases)} tasks")
        for index, task in enumerate(phases, 1):
            files = [item for item in task.get("files") or [] if not self._implemented(item.get("path", ""))]
            if not files:
                continue
            self._fire("on_phase", {"phase": index, "total": len(phases), "title": task.get("title"),
                                    "status": "active", "files": [item["path"] for item in files]})
            written += self._run_write_loop(self._task_prompt(task, files))
            left = [item for item in files if not self._implemented(item["path"])]
            if left:
                written += self._run_write_loop(
                    "Finish the same approved task. These planned files are still absent or still defaults:\n"
                    + "\n".join("- " + item["path"] for item in left)
                    + "\nWrite each complete file now; do not change the plan.")
            done = total - len(self._outstanding())
            self._fire("on_progress", f"Task {index}/{len(phases)} — {done}/{total} files", 18 + int(58 * done / max(1, total)))
            self._fire("on_phase", {"phase": index, "total": len(phases), "title": task.get("title"),
                                    "status": "done",
                                    "written": sum(self._implemented(item["path"]) for item in files)})
            self._fire("on_memory", self.memory_stats())
            self.save_convo()
        return written

    def run(self, user_prompt: str, *, requirement_source: str = "") -> bool:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._fire("on_progress", "Planning…", 5)
            if not self.make_plan(user_prompt, requirement_source):
                return False
            self._fire("on_progress", "Scaffolding…", 15)
            self.scaffold()
            self.install_planned_deps()
            self._fire("on_progress", "Writing files…", 18)
            self.build_app()
            if self._outstanding():
                self._log("WARN", f"   ⚠ Closing {len(self._outstanding())} remaining planned file(s)")
                self._run_write_loop(self._task_prompt(
                    {"id": "closure", "title": "Complete the approved plan", "goal": "No planned file remains"},
                    self._outstanding()))
            self.repair_missing_imports()
            self.sync_dependencies()
            self.install_unresolved()
            self.repair_lint()
            return self._verify_output()
        finally:
            self.save_convo()

    @classmethod
    def imported_packages(cls, content: str) -> list[str]:
        out = []
        for spec in cls.IMPORT_SPEC_RE.findall(content or ""):
            if spec.startswith((".", "/", "@/", "node:")) or spec.startswith("next/"):
                continue
            name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            if name not in cls.NODE_BUILTINS and name not in cls.PREINSTALLED and cls.PKG_NAME_RE.match(name) and name not in out:
                out.append(name)
        return out

    def unresolved_packages(self) -> list[str]:
        try:
            package = json.loads((self.project_dir / "package.json").read_text(encoding="utf-8"))
        except Exception:
            package = {}
        declared = set(package.get("dependencies") or {}) | set(package.get("devDependencies") or {})
        modules = self.project_dir / "node_modules"
        used = {name for path, body in self.files.items() if self.is_source(path)
                for name in self.imported_packages(body)}
        return sorted(name for name in used if name not in declared or not (modules / name / "package.json").exists())

    def sync_dependencies(self) -> int:
        path = self.project_dir / "package.json"
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return 0
        dependencies, added = package.setdefault("dependencies", {}), []
        for file, body in self.files.items():
            if not self.is_source(file):
                continue
            for name in self.imported_packages(body):
                if name not in dependencies and name in KNOWN_DEPENDENCIES:
                    dependencies[name], added = KNOWN_DEPENDENCIES[name], added + [name]
        if added:
            text = json.dumps(package, indent=2) + "\n"
            path.write_text(text, encoding="utf-8")
            self.files["package.json"] = text
            self._log("INFO", "   📦 Declared " + ", ".join(added))
        return len(added)

    def install_packages(self, names: list[str]) -> list[str]:
        names = list(dict.fromkeys(name for name in names if self.PKG_NAME_RE.match(name)))
        if not names:
            return []
        result = self.cmd.run("npm install " + " ".join(names))
        return names if result.ok else []

    def install_planned_deps(self) -> int:
        names = [item.get("name") if isinstance(item, dict) else item for item in self.plan.get("dependencies") or []]
        unknown = [str(name) for name in names if name and name not in KNOWN_DEPENDENCIES and name not in self.PREINSTALLED]
        return len(self.install_packages(unknown))

    def install_unresolved(self) -> int:
        return len(self.install_packages(self.unresolved_packages()))

    def packages_named_in(self, text: str) -> list[str]:
        out = []
        for spec in self.UNRESOLVED_RE.findall(text or ""):
            name = "/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0]
            if self.PKG_NAME_RE.match(name) and name not in out:
                out.append(name)
        return out

    def _resolve_import(self, owner: str, spec: str) -> bool:
        if spec.startswith("@/"):
            base = spec[2:]
        elif spec.startswith("."):
            base = os.path.normpath(str(Path(owner).parent / spec)).replace("\\", "/")
        else:
            return True
        return any(candidate in self.files or (self.project_dir / candidate).is_file()
                   for candidate in (base, base + ".js", base + ".jsx", base + "/index.js", base + "/index.jsx"))

    def repair_missing_imports(self) -> int:
        missing = []
        for owner, body in self.files.items():
            if not owner.endswith((".js", ".jsx")):
                continue
            for spec in self.LOCAL_IMPORT_RE.findall(body) + ["@/" + value for value in self.ALIAS_IMPORT_RE.findall(body)]:
                if not self._resolve_import(owner, spec):
                    missing.append(f"{owner} imports {spec}")
        if not missing:
            return 0
        return self._run_write_loop(
            "Resolve these missing local imports using approved file-plan paths. Create a planned file when absent or correct the importing file.\n"
            + "\n".join("- " + item for item in dict.fromkeys(missing)))

    def lint_generated(self) -> list[str]:
        errors = []
        better_auth = "betterAuth(" in self.files.get("lib/auth.js", "")
        for path, body in self.files.items():
            if not path.endswith((".js", ".jsx", ".mjs")):
                continue
            directive = self.STRAY_DIRECTIVE_RE.search(body)
            if directive and body[:directive.start()].strip():
                errors.append(f"{path}: 'use client' is not the first statement")
            if re.search(r"^\s*interface\s+\w+|:\s*(?:string|number|boolean|any)\s*[,)=;]", body, re.M):
                errors.append(f"{path}: contains TypeScript syntax")
            if self.stack == "next" and "react-router-dom" in body:
                errors.append(f"{path}: imports react-router-dom in a Next app")
            if path.endswith("route.js") and re.search(r"export\s+default", body):
                errors.append(f"{path}: route handlers cannot default export")
            if re.search(r"\b(?:const|let|var)\s+\w+\s*=\s*(?:getCollection|getSessionUser)\s*\(", body):
                errors.append(f"{path}: await async getCollection/getSessionUser before using its result")
            if ("{ params }" in body
                    and re.search(r"\b(?:const|let|var)\s+\{[^}]+\}\s*=\s*params\s*;", body)):
                errors.append(f"{path}: await Next.js dynamic-route params before destructuring")
            if (re.match(r"\s*[\"']use client[\"']", body)
                    and re.search(r"@/lib/(?:mongodb|auth|seed)(?:[\"'/]|$)|from\s+[\"']mongodb", body)):
                errors.append(f"{path}: client file imports server/database code")
            if (better_auth and "seed" in path.lower()
                    and re.search(r"\bpassword\s*:", body)
                    and not re.search(r"\b(?:auth\.api\.signUpEmail|ensureDemoAccounts)\s*\(", body)):
                errors.append(
                    f"{path}: Better Auth demo passwords must be created through "
                    "auth.api.signUpEmail; a plain users document cannot sign in")
        try:
            from agents.core.exports_syntax import check_syntax, syntax_messages
            broken, _ = check_syntax(self.project_dir, self.files)
            errors.extend(syntax_messages(broken))
        except Exception as exc:
            log.debug("syntax scan unavailable: %s", exc)
        errors.extend(group_messages(check_named_imports(self.files)))
        errors.extend(f"{path}: planned file was not implemented" for path in self.unfinished())
        errors.extend(f"{name}: imported package is unavailable" for name in self.unresolved_packages())
        return list(dict.fromkeys(errors))

    def repair_lint(self) -> int:
        errors = self.lint_generated()
        if not errors:
            return 0
        self._log("WARN", f"🔍 Repairing {len(errors)} generated-code issue(s)")
        return self._run_write_loop(
            "Fix these deterministic issues while preserving the approved plan. Rewrite complete affected files only.\n"
            + "\n".join("- " + item for item in errors[:30]))

    def _verify_output(self) -> bool:
        if not any(path in self.files for path in self._P["entry"]):
            self._log("ERROR", f"   ❌ Missing entry file {self._P['entry'][0]}")
            return False
        missing = self.unfinished()
        if missing:
            self._log("ERROR", "   ❌ Planned files remain: " + ", ".join(missing[:12]))
            return False
        errors = self.lint_generated()
        if errors:
            for error in errors[:10]:
                self._log("WARN", "   ⚠ " + error)
        return not errors

    def run_requested_commands(self, reply: str) -> list[str]:
        results = []
        for command in [item.strip() for item in CMD_RE.findall(reply or "") if item.strip()][:5]:
            results.append(self.cmd.run(command).as_feedback())
        return results

    def _snapshot(self, max_files: int = 35, per_file: int = 12_000) -> str:
        rows = []
        for path in sorted(self.files):
            if not self.is_source(path):
                continue
            body = self.files[path]
            rows.append(f"--- {path} ---\n" + (body if len(body) <= per_file else body[:per_file] + "\n// …truncated…"))
            if len(rows) >= max_files:
                break
        return "\n\n".join(rows)

    def _context_snapshot(self, max_files: int = 35, per_file: int = 12_000, wanted=None) -> str:
        return self._snapshot(max_files=max_files, per_file=per_file)

    def _snapshot_caps(self) -> dict:
        return {"max_files": 40 if self._budget_chars() >= 150_000 else 24,
                "per_file": 18_000 if self._budget_chars() >= 150_000 else 6_000}

    def update(self, instruction: str) -> int:
        if not self.convo:
            self.start_conversation(self.plan.get("source_input_summary") or self.plan_md or "existing app")
        prompt = (
            "CURRENT SOURCE\n" + self._snapshot(**self._snapshot_caps()) +
            "\n\nREQUESTED CHANGE\n" + instruction +
            "\n\nPreserve the approved plan/design unless the request explicitly changes it. "
            "Rewrite only complete affected files using <write_file> blocks."
        )
        count = self._run_write_loop(prompt)
        self.repair_missing_imports()
        self.sync_dependencies()
        return count

    def resume(self, brief: str = "") -> bool:
        if not self.plan.get("file_plan"):
            self._log("ERROR", "   ❌ No saved plan to resume")
            return False
        if not self.convo:
            self.start_conversation((self.plan.get("source_input_summary") or self.plan_md) + "\n" + brief)
        if self._outstanding():
            self.build_app()
        self.repair_missing_imports()
        self.sync_dependencies()
        self.install_unresolved()
        self.repair_lint()
        return self._verify_output()

    def load_existing(self) -> None:
        if (self.project_dir / "next.config.mjs").exists() or (self.project_dir / "next.config.js").exists():
            self.stack = "next"
        elif (self.project_dir / "vite.config.js").exists():
            self.stack = "vite"
        skip = {"node_modules", ".git", ".next", "dist", "out", ".agentforge", "public", "tests"}
        for path in self.project_dir.rglob("*"):
            if not path.is_file() or any(part in skip for part in path.parts) or path.name.startswith(".env"):
                continue
            if path.suffix not in {".js", ".jsx", ".mjs", ".json", ".css", ".html", ".md"} or path.stat().st_size > 250_000:
                continue
            rel = path.relative_to(self.project_dir).as_posix()
            self.files[rel] = path.read_text(encoding="utf-8", errors="replace")
        self.plan_md = self.files.get("plan.md", "")
        self.architecture_md = self.files.get("architecture.md", "")
        self.design_md = self.files.get("design.md", "")
        self.plan = self._load_plan_json()
        self.load_convo()

    PLAN_JSON, CONVO_JSON = ".agentforge/plan.json", ".agentforge/convo.json"

    def _write_atomic(self, rel: str, text: str) -> None:
        path = self.project_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)

    def _save_plan_json(self) -> None:
        if self.plan:
            self._write_atomic(self.PLAN_JSON, json.dumps(self.plan, ensure_ascii=False, indent=2))

    def _load_plan_json(self) -> dict:
        try:
            return json.loads((self.project_dir / self.PLAN_JSON).read_text(encoding="utf-8"))
        except Exception:
            return {}

    def save_convo(self) -> bool:
        if len(self.convo) < 3:
            return False
        try:
            messages = self.convo[-16:]
            self._write_atomic(self.CONVO_JSON, json.dumps(
                {"model": self.model, "stack": self.stack, "messages": messages},
                ensure_ascii=False, indent=1))
            return True
        except Exception as exc:
            log.warning("could not save conversation: %s", exc)
            return False

    def load_convo(self) -> bool:
        try:
            data = json.loads((self.project_dir / self.CONVO_JSON).read_text(encoding="utf-8"))
            messages = [item for item in data.get("messages") or [] if isinstance(item, dict)]
            if len(messages) >= 3:
                self.convo = messages
                return True
        except Exception:
            pass
        return False

    def _capability_ledger(self, wanted=None) -> str:
        paths = {item if isinstance(item, str) else item.get("path") for item in (wanted or [])}
        rows = []
        for cap in self.plan.get("capabilities") or []:
            if paths and not paths.intersection(cap.get("files") or []):
                continue
            proof = cap.get("proof_points") or cap.get("proof") or []
            proof = "; ".join(proof) if isinstance(proof, list) else str(proof)
            rows.append(f"{cap.get('id')}: {cap.get('behavior')} — {proof}")
        return "\n".join(rows)

    def _contract_ledger(self, wanted=None) -> str:
        paths = {item if isinstance(item, str) else item.get("path") for item in (wanted or [])}
        rows = []
        for api in self.plan.get("api_contracts") or []:
            touched = {api.get("handler_file"), *(api.get("called_from") or [])}
            if paths and not paths.intersection(touched):
                continue
            rows.append(f"{api.get('name')}: {api.get('method')} {api.get('path')} — {api.get('success_effect')}")
        return "\n".join(rows)

    def _data_ledger(self) -> str:
        rows = []
        for model in self.plan.get("data_model") or []:
            fields = ", ".join(f"{field.get('name')}:{field.get('type')}" for field in model.get("fields") or [])
            rows.append(f"{model.get('collection')} — {fields}")
        return "\n".join(rows)


__all__ = [
    "ArchitectAgent", "FileStreamParser", "CHARS_PER_TOKEN", "HISTORY_BUDGET",
    "EDIT_TIMEOUT", "CMD_RE", "FENCE_RE", "OPEN_RE", "PARTIAL_OPEN_RE",
    "WRITE_FILE_TOOL", "NEXT_PLANNER_SYSTEM", "NEXT_BUILDER_SYSTEM",
    "VITE_PLANNER_SYSTEM", "VITE_BUILDER_SYSTEM", "NEXT_STACK_RULES",
    "VITE_STACK_RULES", "PROMPTS", "log",
]
