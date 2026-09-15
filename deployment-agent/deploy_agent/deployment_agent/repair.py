"""A bounded file/CLI agent for failures in an isolated deployment copy."""
from __future__ import annotations

import hashlib
import json
import os
import shlex
import threading
import uuid
from pathlib import Path

from . import owner_credentials
from .security import redact_text, sha256_file
from .tools import run_command
from .customization import FIELDS, validate_answers
from .dependency_audit import audit_dependencies, dependency_command

SKILLS = Path(__file__).resolve().parents[1] / "assets" / "skills"
BLOCKED = {".git", ".agentforge", ".agents", "node_modules", ".next", ".vercel", ".netlify", "dist", "build"}
ACTION_SCHEMA = {
    "type": "object", "required": ["summary", "actions"], "additionalProperties": False,
    "properties": {
        "summary": {"type": "string"},
        "actions": {"type": "array", "maxItems": 12, "items": {
            "type": "object", "required": ["tool"], "additionalProperties": False,
            "properties": {
                "tool": {"enum": ["list_files", "read_file", "write_file", "edit_file", "run_cli", "ask_user", "finish"]},
                "path": {"type": "string"}, "content": {"type": "string"},
                "old": {"type": "string"}, "new": {"type": "string"},
                "command": {"enum": ["install", "build", "dependency_audit", "refresh_lockfile", "git_status", "github_logs", "aws_events", "vercel_inspect", "netlify_status", "azure_status"]},
                "question": {"type": "string"}, "choices": {"type": "array", "items": {"type": "string"}},
                "setting": {"enum": sorted(FIELDS)},
            },
        }},
    },
}
_WAITERS: dict[str, threading.Event] = {}
_WAIT_LOCK = threading.RLock()


def submit_answer(store, run_id: str, question_id: str, answer: str) -> None:
    store.answer_question(run_id, question_id, answer)
    with _WAIT_LOCK:
        if run_id in _WAITERS:
            _WAITERS[run_id].set()


def wake_question(run_id: str) -> None:
    with _WAIT_LOCK:
        if run_id in _WAITERS:
            _WAITERS[run_id].set()


class DeploymentRepairAgent:
    def __init__(self, store, emit, client=None):
        self.store, self.emit = store, emit
        if client is None:
            from deploy_agent.bridge import ollama_client
            client = ollama_client()
        self.client = client
        self.changed: set[str] = set()
        self.baselines: dict[str, str] = {}
        self.observed: dict[str, str] = {}

    def _path(self, root: Path, value: str, write=False) -> Path:
        path = (root / value).resolve()
        parts = path.relative_to(root.resolve()).parts
        if not parts or any(part in BLOCKED or part.startswith(".env") or part.endswith(".pem") for part in parts):
            # Shared parent documents are context only.
            if not write and len(parts) == 3 and parts[:2] == (".agentforge", "handoff") and path.suffix == ".md":
                return path
            raise ValueError("Access is restricted to application and deployment source files")
        if path.exists() and not path.is_file():
            raise ValueError("Choose a source file, not a directory")
        return path

    def _ask(self, run_id, action, root):
        question = {"id": uuid.uuid4().hex, "text": action.get("question", ""), "choices": action.get("choices", [])[:8]}
        if not question["text"]:
            raise ValueError("A question is required")
        waiter = threading.Event()
        with _WAIT_LOCK:
            _WAITERS[run_id] = waiter
        self.store.ask_question(run_id, question)
        self.emit(run_id, "question", "repair", "waiting", 88, question["text"], question)
        try:
            waiter.wait(1800)
            response = self.store.get_question(run_id) or {}
            if response.get("answer") is None:
                raise RuntimeError("Deployment paused without an answer; retry after providing the missing setting")
            if action.get("setting"):
                self._apply_choice(run_id, root, action["setting"], response["answer"])
            return {"answer": redact_text(response["answer"])}
        finally:
            self.store.clear_question(run_id)
            with _WAIT_LOCK:
                _WAITERS.pop(run_id, None)

    def _apply_choice(self, run_id, root, setting, answer):
        from .models import DeploymentPlan, DeploymentTarget, ProjectSpec
        from dfagents.generator import ArtifactGeneratorAgent
        run = self.store.get_run(run_id)
        repo = run.get("repo") or {}
        if setting.startswith("repository_") and repo.get("repository"):
            raise ValueError("The recorded repository identity is retained; change names before its creation")
        if setting in {"project_name", "netlify_team", "netlify_site_id", "vercel_scope", "azure_resource_group", "azure_plan", "azure_location"} and any(repo.get(key) for key in ("netlify_site_id", "vercel_project_id", "azure_app_name", "bootstrap_stack")):
            raise ValueError("The recorded cloud application identity cannot change during repair")
        choices = validate_answers({**(run["plan"].get("customization") or {}), setting: answer})
        plan = DeploymentPlan(**run["plan"])
        plan.customization = choices
        if setting == "project_name":
            plan.project_slug = choices[setting].lower()
        if setting == "aws_instance_type":
            from deploy_agent.bridge import free_tier_only
            if free_tier_only() and choices[setting] not in {"t3.micro", "t4g.micro"}:
                raise ValueError("Choose a micro instance or change your free tier preference in Settings")
            plan.aws_sizing["instance_type"] = choices[setting]
        old_records = {item["path"]: item for item in self.store.get_artifacts(run_id)}
        before = {name: sha256_file(root / name) for name in old_records}
        records = ArtifactGeneratorAgent(self.emit).generate(run_id, ProjectSpec.from_dict(run["spec"]), plan, root,
                                                             target=DeploymentTarget(plan.target))
        for record in records:
            if before.get(record.path, "") != record.sha256:
                self.changed.add(record.path)
                self.baselines.setdefault(record.path, before.get(record.path, ""))
            old_records[record.path] = record.to_dict()
        self.store.set_artifacts(run_id, list(old_records.values()))
        self.store.update_run(run_id, plan_json=plan.to_dict())

    def _cli(self, root, run, command):
        service = run["spec"]["services"][0]
        repo = run.get("repo") or {}
        cwd = (root / service.get("root", "")).resolve()
        cwd.relative_to(root.resolve())
        if command == "dependency_audit":
            return audit_dependencies(cwd, service.get("package_manager", "npm"), runner=run_command)
        lockfiles = {}
        if command == "refresh_lockfile":
            for name in ('package-lock.json', 'npm-shrinkwrap.json', 'pnpm-lock.yaml', 'yarn.lock', 'bun.lock', 'bun.lockb'):
                path = self._path(root, (cwd / name).relative_to(root).as_posix(), write=True)
                lockfiles[path] = sha256_file(path)
        args = {
            "install": shlex.split(service["install_command"]),
            "build": shlex.split(service.get("build_command") or "npm run build"),
            "git_status": ["git", "status", "--short"],
        }.get(command)
        if command == "refresh_lockfile":
            args = dependency_command(cwd, service.get("package_manager", "npm"), refresh=True)
        if command == "github_logs":
            push = repo.get("push") or {}
            listed = run_command(["gh", "run", "list", "--repo", repo["repository"], "--workflow", "deploy.yml",
                                  "--limit", "10", "--json", "databaseId,headSha"], timeout=30, check=True)
            current = next((row for row in json.loads(listed.stdout) if row.get("headSha") == push.get("head_sha")), None)
            if not current:
                raise ValueError("No workflow for this deployment commit")
            args = ["gh", "run", "view", str(current["databaseId"]), "--repo", repo["repository"], "--log-failed"]
        elif command == "aws_events":
            if not repo.get("aws_profile"):
                raise ValueError("No project AWS profile recorded")
            args = ["aws", "cloudformation", "describe-stack-events", "--stack-name", repo["bootstrap_stack"],
                    "--profile", repo["aws_profile"], "--region", repo["region"], "--no-cli-pager"]
        elif command == "vercel_inspect":
            args = ["vercel", "inspect", repo["application_url"]]
        elif command == "netlify_status":
            args = ["netlify", "api", "getSite", "--data", json.dumps({"site_id": repo["netlify_site_id"]})]
        elif command == "azure_status":
            from .hosted import azure_command
            proc = azure_command(["webapp", "show", "--name", repo["azure_app_name"], "--resource-group", repo["azure_resource_group"]])
            return {"exit_code": proc.returncode, "output": proc.stdout + proc.stderr}
        if not args:
            raise ValueError("This diagnostic command is unavailable")
        # The commands are derived by the server; no model-supplied shell or cloud mutation is executed.
        local = command in {"install", "build", "refresh_lockfile"}
        proc = run_command(args, cwd=cwd, timeout=1200 if local else 90,
                           authenticated=not local,
                           env={"CI": "1", "NEXT_TELEMETRY_DISABLED": "1", "MONGODB_URI": "mongodb://127.0.0.1:27017/deployment_agent_build"})
        for path, baseline in lockfiles.items():
            relative = path.relative_to(root).as_posix()
            self._path(root, relative, write=True)
            after = sha256_file(path)
            if after != baseline:
                self.baselines.setdefault(relative, baseline)
                self.changed.add(relative)
                self.observed[relative] = after
        return {"exit_code": proc.returncode, "output": (proc.stdout + proc.stderr)[-16000:]}

    def _execute(self, run_id, root, run, action):
        tool = action["tool"]
        if tool == "list_files":
            files = []
            for folder, directories, names in os.walk(root, followlinks=False):
                directories[:] = sorted(name for name in directories if name not in BLOCKED and not (Path(folder) / name).is_symlink())
                for name in sorted(names):
                    path = Path(folder) / name
                    if not name.startswith(".env") and not name.endswith(".pem") and not path.is_symlink():
                        files.append(path.relative_to(root).as_posix())
                if len(files) >= 1200:
                    break
            return {"files": files[:1200]}
        if tool == "run_cli":
            return self._cli(root, run, action.get("command"))
        if tool == "ask_user":
            return self._ask(run_id, action, root)
        path = self._path(root, action.get("path", ""), write=tool != "read_file")
        relative = path.relative_to(root).as_posix()
        before = path.read_text(encoding="utf-8") if path.is_file() else ""
        if len(before.encode()) > 2 * 1024 * 1024:
            raise ValueError("Choose a source file under 2 MB")
        if tool == "read_file":
            self.observed[relative] = sha256_file(path)
            return {"content": redact_text(before)[:60000]}
        if path.exists() and self.observed.get(relative) != sha256_file(path):
            raise ValueError("Read the current file before editing it")
        content = action.get("content", "")
        if tool == "edit_file":
            old = action.get("old", "")
            if not old or before.count(old) != 1:
                raise ValueError("Edit must match exactly one current source fragment")
            content = before.replace(old, action.get("new", ""), 1)
        private = [value for value in owner_credentials.current().values() if isinstance(value, str) and len(value) > 8]
        try:
            private.append(json.loads(owner_credentials.current().get("azure_credentials", "{}" )).get("clientSecret", ""))
        except (TypeError, ValueError):
            pass
        if len(content.encode()) > 2 * 1024 * 1024 or redact_text(content) != content or any(value and value in content for value in private):
            raise ValueError("Source writes must be under 2 MB and cannot contain credential values")
        if content != before:
            self.baselines.setdefault(relative, sha256_file(path))
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(path.name + ".deploy-write.tmp")
            temporary.write_text(content, encoding="utf-8")
            temporary.replace(path)
            self.changed.add(relative)
            self.observed[relative] = sha256_file(path)
        return {"changed": content != before, "path": relative}

    def repair(self, run_id: str, root: Path, diagnostics: str, max_turns=18) -> list[str]:
        run = self.store.get_run(run_id)
        target = run["plan"]["target"]
        provider = "aws" if target.startswith("aws_") else target
        guidance = "\n\n".join((SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
                                 for name in ("deployment-repair", "github", provider))
        context = {"spec": run["spec"], "plan": run["plan"], "diagnostics": redact_text(diagnostics)[-20000:], "results": []}
        repeats = {}
        for turn in range(max_turns):
            if (self.store.get_run(run_id) or {}).get("state") in {"CANCELLED", "DESTROYED"}:
                raise RuntimeError("Deployment cancelled")
            context["plan"] = self.store.get_run(run_id)["plan"]
            response = self.client.chat_json(guidance + "\nChoose tool actions. Inspect before editing. Finish after a complete bundled repair; validation follows.",
                                             context, ACTION_SCHEMA)
            self.emit(run_id, "agent", "repair", "running", 88, response["summary"][:700])
            actions = response["actions"]
            if not actions:
                break
            for action in actions:
                if action["tool"] == "finish":
                    return sorted(self.changed)
                signature = hashlib.sha256(json.dumps(action, sort_keys=True).encode()).hexdigest()
                tool_call_id = uuid.uuid4().hex
                self.emit(run_id, "tool", "repair", "running", 88,
                          f"{action['tool']} {action.get('path') or action.get('command') or ''}", {"tool_call_id": tool_call_id})
                try:
                    result = self._execute(run_id, root, run, action)
                except Exception as exc:
                    result = {"error": redact_text(str(exc))}
                outcome = json.dumps(result, sort_keys=True)
                key = (signature, hashlib.sha256(outcome.encode()).hexdigest())
                repeats[key] = repeats.get(key, 0) + 1
                self.emit(run_id, "tool", "repair", "failed" if "error" in result else "complete", 88,
                          f"{action['tool']} {action.get('path') or action.get('command') or ''}",
                          {"tool_call_id": tool_call_id, "output": redact_text(outcome)[-16000:]})
                context["results"].append({"action": json.loads(redact_text(json.dumps(action))), "result": result})
                context["results"] = context["results"][-24:]
                if repeats[key] >= 3:
                    raise RuntimeError("Deployment repair stopped after repeated identical tool results without progress")
                if result.get("changed") or "answer" in result:
                    repeats.clear()
        if not self.changed:
            raise RuntimeError("Deployment repair produced no changes; inspect the recorded diagnostics")
        raise RuntimeError("Deployment repair reached its tool budget; no partial repair was applied to the project")
