from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

from dfagents.generator import ArtifactGeneratorAgent
from dfagents.intake import IntakeAgent
from dfagents.planner import PlannerAgent
from dfagents.validator import SecurityValidatorAgent

from .config import RUNS_DIR
from .events import EventBus
from .models import DeploymentTarget, RunState
from .security import redact_text
from .state import StateStore
from .tools import command_exists, run_command
from .dependency_audit import audit_dependencies, repair_diagnostics, security_passed


class Orchestrator:
    def __init__(self, store: StateStore, events: EventBus):
        self.store = store
        self.events = events

    def start_analysis(
        self,
        source_path: str,
        validate_container: bool = True,
        target: DeploymentTarget = DeploymentTarget.AWS_EC2,
        customization: dict | None = None,
        previous_run_id: str = "",
        owner: str = "",
    ) -> str:
        source = Path(source_path).resolve()
        run_id = uuid.uuid4().hex
        run_dir = RUNS_DIR / run_id
        staged = run_dir / "worktree"
        from .customization import validate_answers
        previous = self.store.get_run(previous_run_id) if previous_run_id else None
        if previous and Path(previous["project_path"]).resolve() != source:
            raise ValueError("Previous deployment belongs to another project")
        if previous and owner and (previous.get("repo") or {}).get("owner") != owner:
            raise ValueError("Previous deployment belongs to another account")
        old_plan = (previous or {}).get("plan") or {}
        answers = validate_answers({**(old_plan.get("customization") or {}), **(customization or {})})
        if previous and old_plan.get("target") == target.value:
            answers["project_name"] = old_plan["project_slug"]
        self.store.create_run(run_id, source.name, str(source), str(staged))
        previous_repo = (previous or {}).get("repo") or {}
        previous_repo = {key: value for key, value in previous_repo.items() if key not in {"push", "repair_worker_active"}}
        if previous and (previous.get("plan") or {}).get("target") != target.value:
            previous_repo = {key: previous_repo[key] for key in ("repository", "owner") if key in previous_repo}
        self.store.update_run(run_id, repo_json={**previous_repo, "owner": owner, "previous_run_id": previous_run_id})
        from . import owner_credentials
        threading.Thread(
            target=owner_credentials.carry(self._analyze, owner),
            args=(run_id, source, staged, validate_container, target, answers),
            daemon=True,
        ).start()
        return run_id

    def _analyze(
        self,
        run_id: str,
        source: Path,
        staged: Path,
        validate_container: bool,
        target: DeploymentTarget = DeploymentTarget.AWS_EC2,
        customization: dict | None = None,
    ) -> None:
        emit = self.events.emit
        self.store.transition_run(run_id, RunState.ANALYZING)
        emit(run_id, "state", "analysis", "running", 1, "Deployment analysis started")
        try:
            spec = IntakeAgent(emit).stage_and_analyze(run_id, source, staged)
            self.store.update_run(run_id, project_name=spec.name, spec_json=spec.to_dict())

            try:
                from deploy_agent.bridge import ollama_client
                planner = PlannerAgent(emit=emit, client=ollama_client())
            except Exception:                                   # noqa: BLE001
                planner = PlannerAgent(emit=emit)
            plan = planner.plan(run_id, spec)
            plan.customization = customization or {}
            if plan.customization.get("project_name"):
                plan.project_slug = plan.customization["project_name"].lower()
            if plan.customization.get("aws_instance_type"):
                from deploy_agent.bridge import free_tier_only
                size = plan.customization["aws_instance_type"]
                if free_tier_only() and size not in {"t3.micro", "t4g.micro"}:
                    raise ValueError("This instance size exceeds your free tier preference; change the preference or select a micro instance")
                plan.aws_sizing["instance_type"] = size
            generator = ArtifactGeneratorAgent(emit)
            records = generator.generate(run_id, spec, plan, staged, target=target)
            record_dicts = [record.to_dict() for record in records]
            self.store.set_artifacts(run_id, record_dicts)
            self.store.update_run(run_id, plan_json=plan.to_dict())
            records, plan, validation, build_result = self._validate_and_repair(run_id, spec, plan, staged, target, records, validate_container)
            readiness_path = staged / "readiness-score.json"
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            security_ok = security_passed(validation, build_result)
            if security_ok:
                readiness["categories"]["security"] = 20
                readiness["score"] = sum(readiness["categories"].values())
            plan.risks.extend(validation["warnings"])
            if build_result.get("attempted"):
                if build_result["attempted"] and not build_result["passed"]:
                    readiness["categories"]["build"] = 8
                    readiness["score"] = sum(readiness["categories"].values())
                    plan.risks.append("Local build validation failed; inspect the terminal output before deployment.")
                elif build_result["passed"]:
                    readiness["categories"]["build"] = 15
                    readiness["score"] = sum(readiness["categories"].values())
                    if not plan.repair_actions:
                        emit(run_id, "step", "repair", "complete", 93, "No compatibility repair was required")
                findings = build_result.get("dependency_findings", {})
                if findings.get("total", 0):
                    if findings.get("critical", 0):
                        readiness["categories"]["security"] = min(readiness["categories"]["security"], 8)
                    elif findings.get("high", 0):
                        readiness["categories"]["security"] = min(readiness["categories"]["security"], 12)
                    else:
                        readiness["categories"]["security"] = min(readiness["categories"]["security"], 16)
                    readiness["score"] = sum(readiness["categories"].values())
                    plan.risks.append(
                        "Local dependency installation reported "
                        f"{findings['total']} vulnerability finding(s), including development dependencies; "
                        "automatic repair could not resolve all findings."
                    )
            if not security_ok:
                plan.risks.append("Security validation still has unresolved findings after automatic repair.")
            readiness["gates"] = {
                "model_used": plan.model_used,
                "artifacts_valid": validation["passed"],
                "build_validation": bool(build_result.get("passed")),
                "security_validation": security_ok,
            }
            review_ok = validation["passed"] and security_ok
            records = generator.finalize_review(spec, plan, staged, readiness, records)
            record_dicts = [record.to_dict() for record in records]
            self.store.set_artifacts(run_id, record_dicts)
            self.store.transition_run(
                run_id,
                RunState.REVIEW_READY if review_ok else RunState.FAILED,
                plan_json=plan.to_dict(),
                readiness_json=readiness,
                error="" if review_ok else ("; ".join(validation["errors"]) or "Dependency/security validation still fails after automatic repair"),
            )
            emit(run_id, "state", "analysis", "complete", 100,
                 "Deployment analysis complete")
            emit(
                run_id,
                "state",
                "review",
                "complete" if review_ok else "failed",
                100,
                "Review is ready. No source or cloud resources have been changed."
                if review_ok
                else "Security validation remains unresolved",
                {"readiness": readiness, "artifacts": len(records)},
            )
        except Exception as exc:
            self.store.transition_run(run_id, RunState.FAILED, error=str(exc))
            emit(run_id, "error", "analysis", "failed", 100, str(exc))

    def _validate_and_repair(self, run_id, spec, plan, staged, target, records, validate_container, max_repairs=2):
        from .models import ArtifactRecord, DeploymentPlan
        from .repair import DeploymentRepairAgent
        from .repair_records import record_repairs

        validate_build = validate_container and os.environ.get("DEPLOYMENT_AGENT_SKIP_BUILD_VALIDATION") != "1"
        max_repairs = max(0, min(2, max_repairs))
        for attempt in range(max_repairs + 1):
            if self.store.get_run(run_id)["state"] == RunState.CANCELLED.value:
                raise RuntimeError("Deployment cancelled")
            validation = SecurityValidatorAgent(self.events.emit).validate(run_id, staged, [record.to_dict() for record in records], target=target)
            build = self._validate_build(run_id, spec, staged, target) if validation["passed"] and validate_build else {"attempted": False, "passed": False, "output": ""}
            build_failed = build.get("attempted") and not build.get("passed")
            if (security_passed(validation, build) and not build_failed) or attempt == max_repairs or not plan.model_used:
                break
            self.events.emit(run_id, "agent", "repair", "running", 88,
                             "Reading all security, dependency and build findings for a bundled repair")
            agent = DeploymentRepairAgent(self.store, self.events.emit)
            agent.repair(run_id, staged, repair_diagnostics(validation, build))
            if not agent.changed:
                break
            plan = DeploymentPlan(**self.store.get_run(run_id)["plan"])
            records = [ArtifactRecord(**record) for record in record_repairs(self.store, run_id, agent)]
            plan.repair_actions.append("Bundled security/dependency/build repair")
            self.store.update_run(run_id, plan_json=plan.to_dict())
        self.events.emit(run_id, "step", "security", "complete" if security_passed(validation, build) else "failed", 94,
                         "Security and dependency validation passed" if security_passed(validation, build) else "Security findings remain after automatic repair")
        return records, plan, validation, build

    def _validate_build(
        self,
        run_id: str,
        spec,
        staged: Path,
        target: DeploymentTarget = DeploymentTarget.AWS_EC2,
    ) -> dict[str, Any]:
        """Install and build the staged copy exactly as CI will, without Docker."""
        if not command_exists("node"):
            self.events.emit(run_id, "warning", "build", "skipped", 86, "Node.js not found; build validation skipped")
            return {"attempted": False, "passed": False}
        service = spec.services[0]
        root = staged / service.root if service.root else staged
        steps = [
            ("install", service.install_command, 900),
            ("build", service.build_command or "npm run build", 1200),
        ]
        combined: list[str] = []
        returncode = 0
        installed = False
        for label, command, timeout in steps:
            self.events.emit(run_id, "terminal", "build", "running", 87, f"Running local {label}: {command}")
            try:
                result = run_command(
                    command.split(),
                    cwd=str(root),
                    timeout=timeout,
                    authenticated=False,

                    env={
                        "NODE_ENV": "",
                        "NEXT_TELEMETRY_DISABLED": "1",
                        "MONGODB_URI": "mongodb://127.0.0.1:27017/deployment_agent_build",
                    },
                )
            except Exception as exc:
                self.events.emit(run_id, "terminal", "build", "failed", 90, str(exc))
                return {"attempted": True, "passed": False, "output": redact_text(str(exc))}
            combined.append(f"$ {command}\n{result.stdout}\n{result.stderr}")
            returncode = result.returncode
            if label == "install" and returncode == 0:
                installed = True
            if returncode != 0:
                break
        output = redact_text("\n".join(combined)[-12000:])
        dependency_findings = self._dependency_findings(output)
        dependency_audit = audit_dependencies(root, service.package_manager, runner=run_command) if installed else {}
        if dependency_audit.get("attempted") and dependency_audit.get("findings"):
            dependency_findings = dependency_audit["findings"]

        if target in (DeploymentTarget.AWS_EC2, DeploymentTarget.AWS_ECS, DeploymentTarget.AZURE) and service.framework == "nextjs":
            standalone = (root / ".next" / "standalone" / "server.js").is_file()
            if returncode == 0 and not standalone:
                returncode = 1
                output += "\n[deployment-agent] .next/standalone/server.js was not produced; output: 'standalone' is required."
        self.events.emit(
            run_id,
            "terminal",
            "build",
            "complete" if returncode == 0 else "failed",
            90,
            "Local build passed" if returncode == 0 else "Local build failed",
            {"output": output, "returncode": returncode},
        )
        if dependency_findings.get("total", 0):
            self.events.emit(
                run_id,
                "warning",
                "security",
                "warning",
                92,
                (
                    f"Dependency installation reported {dependency_findings['total']} vulnerability finding(s) "
                    f"({dependency_findings.get('high', 0)} high, {dependency_findings.get('critical', 0)} critical)"
                ),
                dependency_findings,
            )
        return {
            "attempted": True,
            "passed": returncode == 0,
            "dependency_findings": dependency_findings,
            "dependency_audit": dependency_audit,
            "output": output,
        }

    @staticmethod
    def _dependency_findings(output: str) -> dict[str, int]:
        def count(label: str) -> int:
            matches = re.findall(rf"(\d+)\s+{label}\b", output, flags=re.IGNORECASE)
            return max((int(value) for value in matches), default=0)

        totals = re.findall(r"(\d+)\s+vulnerabilit(?:y|ies)\b", output, flags=re.IGNORECASE)
        return {
            "total": max((int(value) for value in totals), default=0),
            "moderate": count("moderate"),
            "high": count("high"),
            "critical": count("critical"),
        }
