from __future__ import annotations

import json
import re
import secrets
import shutil
import textwrap
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

from dfagents.monitor import select_workflow_run
from deployment_agent.environment import DEPLOYER_INJECTED
from deployment_agent.models import DeploymentTarget, RunState
from deployment_agent.config import ARTIFACT_SCHEMA_VERSION, GIT_TIMEOUT_SECONDS
from deployment_agent.providers import ProviderPrep, TargetProfile, profile_for, target_of
from deployment_agent.security import redact_text, sha256_file
from deployment_agent.state import StateStore
from deployment_agent.tools import command_exists, resolve_command, run_command


_ACTIVE_PROJECTS: set[str] = set()
_ACTIVE_LOCK = threading.RLock()
_PERSISTED_ACTIVE_STATES = {
    RunState.BOOTSTRAPPING.value,
    RunState.CI_RUNNING.value,
    RunState.DEPLOYING.value,
    RunState.VALIDATING.value,
}


_CANCELLABLE_STATES = _PERSISTED_ACTIVE_STATES | {
    RunState.ANALYZING.value,
    RunState.REVIEW_READY.value,
}


def github_credential_args() -> list[str]:
    """Per-invocation git config that authenticates GitHub through `gh`.

    The agent runs git without a terminal, so Git Credential Manager - the
    default helper on Windows - cannot prompt and the push fails with
    "could not read Username", even while `gh` itself is signed in. Scope gh's
    own credential helper to the single command rather than mutating the user's
    global git config (which `gh auth setup-git` would do). The empty value
    first clears any helper inherited for this host, as git documents for
    multi-valued config.
    """
    executable = resolve_command("gh")
    command = Path(executable).as_posix() if executable else "gh"
    return [
        "-c", "credential.https://github.com.helper=",
        "-c", f"credential.https://github.com.helper=!'{command}' auth git-credential",
    ]


def active_project_keys() -> set[str]:
    """Project keys currently owned by a live in-process deployment worker.

    The set lives only in memory, so it is empty after an application restart.
    That is exactly the signal the reconciler needs: a run persisted in an
    active state whose project key is absent here has no worker driving it.
    """
    with _ACTIVE_LOCK:
        return set(_ACTIVE_PROJECTS)


class DeploymentConflictError(RuntimeError):
    pass


class DeploymentAgent:
    def __init__(self, store: StateStore, emit: Callable[..., object]):
        self.store = store
        self.emit = emit

    def start_deployment(
        self,
        run_id: str,
        aws_profile: str,
        region: str,
        mongodb_uri: str,
        approved: bool,
        credential_reference: str = "",
        vercel_token: str = "",
    ) -> None:
        _run, project_key = self._validate_request(run_id, mongodb_uri, approved)
        self._reserve_project(run_id, project_key)
        threading.Thread(
            target=self._deploy_reserved,
            args=(run_id, aws_profile, region, mongodb_uri, project_key, credential_reference, vercel_token),
            daemon=True,
        ).start()

    def deploy(
        self,
        run_id: str,
        aws_profile: str,
        region: str,
        mongodb_uri: str,
        approved: bool,
        credential_reference: str = "",
        vercel_token: str = "",
    ) -> None:
        _run, project_key = self._validate_request(run_id, mongodb_uri, approved)
        self._reserve_project(run_id, project_key)
        self._deploy_reserved(
            run_id, aws_profile, region, mongodb_uri, project_key, credential_reference, vercel_token
        )

    def _validate_request(self, run_id: str, mongodb_uri: str, approved: bool) -> tuple[dict[str, Any], str]:
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError("Run not found")
        if not approved:
            raise ValueError("The reviewed deployment must be explicitly approved")
        if run["state"] not in {RunState.REVIEW_READY.value, RunState.FAILED.value}:
            raise ValueError(f"Run cannot be deployed from state {run['state']}")
        plan = run.get("plan") or {}
        if plan.get("model_used") is not True:
            raise ValueError("A validated Ollama deployment plan is required before deployment")
        readiness = run.get("readiness") or {}
        gates = readiness.get("gates") or {}
        build_score = readiness.get("categories", {}).get("build")
        if gates.get("build_validation") is not True or build_score is None or int(build_score) < 15:
            raise ValueError("Local build validation must pass before deployment")
        if gates.get("security_validation") is not True or gates.get("artifacts_valid") is not True:
            raise ValueError("Artifact and security validation must pass before deployment")
        manifest_path = Path(run["staged_path"]) / "deployment-manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("Reviewed deployment manifest is missing or invalid; re-run analysis") from exc
        if manifest.get("version") != ARTIFACT_SCHEMA_VERSION:
            raise ValueError("Reviewed artifacts were produced by an older renderer; re-run analysis before deployment")
        if manifest.get("model_used") is not True:
            raise ValueError("Reviewed artifacts were not generated from a validated Ollama plan")
        generation = manifest.get("generation") or {}
        expected_strategy = profile_for(target_of(run)).runtime_strategy
        if generation.get("runtime_strategy") != expected_strategy:
            raise ValueError("Reviewed generation specification is missing or invalid; re-run analysis")
        records = self.store.get_artifacts(run_id)
        owned = set(manifest.get("agent_owned_files") or [])
        if not records or {record["path"] for record in records} != owned:
            raise ValueError("Reviewed artifact manifest does not match persisted run state; re-run analysis")
        staged_root = Path(run["staged_path"]).resolve()
        for record in records:
            path = (staged_root / record["path"]).resolve()
            if staged_root not in path.parents or not path.is_file() or sha256_file(path) != record.get("sha256"):
                raise ValueError(f"Reviewed artifact changed after validation; re-run analysis: {record['path']}")
        self._validate_mongodb_uri(mongodb_uri)
        project_key = str(Path(run["project_path"]).resolve()).lower()
        return run, project_key

    @staticmethod
    def _validate_mongodb_uri(value: str) -> None:
        if not value or len(value) > 8192 or any(character.isspace() for character in value):
            raise ValueError("MONGODB_URI is missing or malformed")
        try:
            parsed = urlsplit(value)
        except ValueError as exc:
            raise ValueError("MONGODB_URI is malformed") from exc
        if parsed.scheme not in {"mongodb", "mongodb+srv"} or not parsed.netloc or not parsed.hostname:
            raise ValueError("MONGODB_URI must contain a MongoDB host and use mongodb:// or mongodb+srv://")

    def _reserve_project(self, run_id: str, project_key: str) -> None:
        with _ACTIVE_LOCK:
            if project_key in _ACTIVE_PROJECTS:
                raise DeploymentConflictError("Another production deployment is already active for this project")
            for existing in self.store.list_runs(limit=250):
                if existing["id"] == run_id or existing["state"] not in _PERSISTED_ACTIVE_STATES:
                    continue
                existing_key = str(Path(existing["project_path"]).resolve()).lower()
                if existing_key == project_key:
                    raise DeploymentConflictError(
                        f"Run {existing['id'][:12]} already owns the active production deployment for this project"
                    )
            _ACTIVE_PROJECTS.add(project_key)

    def _deploy_reserved(
        self,
        run_id: str,
        aws_profile: str,
        region: str,
        mongodb_uri: str,
        project_key: str,
        credential_reference: str = "",
        vercel_token: str = "",
    ) -> None:
        try:
            self._deploy(run_id, aws_profile, region, mongodb_uri, credential_reference, vercel_token)
        except Exception as exc:

            current = (self.store.get_run(run_id) or {}).get("state", "")
            if current == RunState.CANCELLED.value:
                self.emit(run_id, "step", "cancel", "complete", 100,
                          "Deployment worker stopped after the run was cancelled")
            else:
                self.store.transition_run(run_id, RunState.FAILED, error=str(exc))
                self.emit(run_id, "error", "deploy", "failed", 100, str(exc))
        finally:
            with _ACTIVE_LOCK:
                _ACTIVE_PROJECTS.discard(project_key)

    def _deploy(
        self,
        run_id: str,
        profile: str,
        region: str,
        mongodb_uri: str,
        credential_reference: str = "",
        vercel_token: str = "",
    ) -> None:
        run = self.store.get_run(run_id)
        assert run
        spec = run["spec"]
        plan = run["plan"]
        source = Path(run["project_path"])
        staged = Path(run["staged_path"])
        slug = plan["project_slug"]
        branch = spec.get("repository", {}).get("branch") or "main"

        target_profile = profile_for(target_of(run))
        self._require_tools(target_profile)
        self.store.transition_run(run_id, RunState.BOOTSTRAPPING, error="")
        self.emit(run_id, "step", "bootstrap", "running", 5, "Validating provider identity and GitHub repository")

        repo = self._ensure_github_repository(source, slug)
        github_identity = self._github_repository_identity(repo)
        branch = str(github_identity.get("default_branch") or self._github_default_branch(repo, branch))
        oidc_subjects = self._github_oidc_subjects(repo, branch, github_identity)

        if target_profile.target is DeploymentTarget.VERCEL:
            prep = self._prepare_vercel(run_id, run, spec, plan, staged, mongodb_uri, vercel_token)
        elif target_profile.target is DeploymentTarget.AWS_ECS:
            prep = self._prepare_ecs(
                run_id, run, spec, plan, staged, profile, region, mongodb_uri, credential_reference, oidc_subjects
            )
        else:
            prep = self._prepare_aws(
                run_id, run, spec, plan, staged, profile, region, mongodb_uri, credential_reference, oidc_subjects
            )

        self._set_github_variables(repo, prep.github_variables)
        self._set_github_secrets(repo, prep.github_secrets)
        applied = self._apply_reviewed_artifacts(run_id, source, staged)
        push = self._commit_and_push(run_id, source, repo, branch, applied, target_profile)
        repo_state = {
            "repository": repo,
            "branch": branch,
            "push": push,
            "oidc_subjects": oidc_subjects,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            **prep.repo_state,
        }
        self.store.transition_run(run_id, RunState.CI_RUNNING, repo_json=repo_state)
        if push.get("mode") == "pull_request":
            self.emit(
                run_id,
                "step",
                "github",
                "waiting",
                70,
                "Branch protection requires the generated pull request to be merged before deployment",
                {"pull_request": push.get("url", "")},
            )
            return
        self.store.transition_run(run_id, RunState.DEPLOYING)
        self.emit(run_id, "step", "github", "running", 70, "GitHub Actions deployment triggered")
        conclusion = self._wait_for_workflow(
            run_id,
            source,
            repo,
            previous_url=push.get("previous_workflow_url", ""),
            head_sha=push.get("head_sha", ""),
        )
        if conclusion == "success":
            self.store.transition_run(run_id, RunState.VALIDATING)
            self.emit(run_id, "step", "deploy", "complete", 93, "GitHub Actions completed; validating the live service")
        elif conclusion in {"failure", "cancelled", "timed_out", "action_required"}:
            raise RuntimeError(f"GitHub deployment workflow concluded with {conclusion}")
        else:
            self.emit(run_id, "warning", "github", "waiting", 78, "Workflow is still running; monitoring will continue from the dashboard")

    @staticmethod
    def _require_tools(profile: TargetProfile | None = None) -> None:
        required = (profile or profile_for(None)).required_tools
        missing = [name for name in required if not command_exists(name)]
        if missing:
            raise RuntimeError("Missing required deployment tools: " + ", ".join(missing))

    @staticmethod
    def _runtime_secret_values(mongodb_uri: str, outputs: dict) -> dict:
        """Everything the running application needs, not just the database.

        This used to be two keys, and the missing third one is a real bug the
        owner hit on a deployed site: signing up returned **"Invalid origin"**,
        with `[better-auth] Base URL is not set` in the container log. Without
        `BETTER_AUTH_URL` the library derives an origin from the incoming
        request and then refuses it, so authentication is broken on a
        deployment that otherwise looks completely healthy — the homepage
        answers, `/api/health` answers, and readiness scores 100.

        The URL is knowable here and nowhere earlier: it is the load balancer's
        DNS name (ECS) or the Elastic IP (EC2), both of which only exist once
        the stack has been applied. That is why this reads the stack outputs.

        `MONGODB_DB` is deliberately absent: the driver falls back to the
        database named in the connection string, which is where it should come
        from. Writing an empty value here would override that with `test`.
        """
        url = str(outputs.get("ApplicationUrl") or "").rstrip("/")
        values = {
            "MONGODB_URI": mongodb_uri,
            "BETTER_AUTH_SECRET": secrets.token_urlsafe(48),
        }
        if url:

            values.update({name: url for name in DEPLOYER_INJECTED})
        return values

    def _prepare_aws(
        self,
        run_id: str,
        run: dict[str, Any],
        spec: dict[str, Any],
        plan: dict[str, Any],
        staged: Path,
        profile: str,
        region: str,
        mongodb_uri: str,
        credential_reference: str,
        oidc_subjects: list[str],
    ) -> ProviderPrep:
        """Bring the AWS account to the point where the workflow can deploy.

        Moved verbatim out of `_deploy` so the shared GitHub delivery half can be
        reused by a second provider; the behaviour is unchanged.
        """
        slug = plan["project_slug"]
        session = self._aws_session(profile, region, credential_reference)
        identity = session.client("sts").get_caller_identity()

        oidc_arn = self._find_github_oidc(session, f"{slug}-bootstrap")
        network = self._select_bootstrap_network(run_id, session)
        outputs = self._apply_bootstrap_stack(
            run_id,
            session,
            staged / "infra" / "bootstrap.yml",
            slug,
            oidc_subjects,
            spec["services"][0]["port"],
            oidc_arn,
            network,
        )
        runtime_secret = outputs.get("RuntimeSecretArn")
        if not runtime_secret:
            raise RuntimeError("Bootstrap stack did not return RuntimeSecretArn")
        session.client("secretsmanager").put_secret_value(
            SecretId=runtime_secret,
            SecretString=json.dumps(
                self._runtime_secret_values(mongodb_uri, outputs)
            ),
        )
        self.emit(run_id, "step", "secrets", "complete", 45, "Runtime secrets stored in AWS Secrets Manager")
        return ProviderPrep(
            github_variables={
                "AWS_DEPLOY_ROLE_ARN": outputs.get("DeployRoleArn", ""),
                "AWS_REGION": region,
                "ARTIFACT_BUCKET": outputs.get("ArtifactBucket", ""),
                "INSTANCE_ID": outputs.get("InstanceId", ""),

                "RUNTIME_SECRET_ID": runtime_secret,
                "PROJECT_SLUG": slug,
            },
            repo_state={
                "aws_profile": profile,
                "region": region,
                "account_id": identity.get("Account", ""),
                "bootstrap_stack": f"{slug}-bootstrap",
                "application_url": outputs.get("ApplicationUrl", ""),
                "artifact_bucket": outputs.get("ArtifactBucket", ""),
                "instance_id": outputs.get("InstanceId", ""),
                "public_ip": outputs.get("PublicIp", ""),
                "log_group": outputs.get("LogGroupName", ""),
                "runtime_secret_arn": runtime_secret,
            },
        )

    def _prepare_ecs(
        self,
        run_id: str,
        run: dict[str, Any],
        spec: dict[str, Any],
        plan: dict[str, Any],
        staged: Path,
        profile: str,
        region: str,
        mongodb_uri: str,
        credential_reference: str,
        oidc_subjects: list[str],
    ) -> ProviderPrep:
        """Bring the account to the point where the workflow can push an image.

        The same shape as `_prepare_aws` — session, identity, reuse the OIDC
        provider, pick a network, apply the stack, write the runtime secret —
        because the differences are all in the template, not in the sequence.

        What differs is the handover: the workflow needs the repository URI, the
        cluster and service names, the two task role ARNs and the secret id, and
        `_set_github_variables` raises on any empty value. Every one of these
        must therefore be an Output of the ECS template.
        """
        slug = plan["project_slug"]
        session = self._aws_session(profile, region, credential_reference)
        identity = session.client("sts").get_caller_identity()
        oidc_arn = self._find_github_oidc(session, f"{slug}-bootstrap")
        network = self._select_bootstrap_network(run_id, session)
        outputs = self._apply_bootstrap_stack(
            run_id,
            session,
            staged / "infra" / "bootstrap.yml",
            slug,
            oidc_subjects,
            spec["services"][0]["port"],
            oidc_arn,
            network,
        )
        runtime_secret = outputs.get("RuntimeSecretArn")
        if not runtime_secret:
            raise RuntimeError("Bootstrap stack did not return RuntimeSecretArn")
        session.client("secretsmanager").put_secret_value(
            SecretId=runtime_secret,
            SecretString=json.dumps(
                self._runtime_secret_values(mongodb_uri, outputs)
            ),
        )
        self.emit(run_id, "step", "secrets", "complete", 45,
                  "Runtime secrets stored in AWS Secrets Manager")
        return ProviderPrep(
            github_variables={
                "AWS_DEPLOY_ROLE_ARN": outputs.get("DeployRoleArn", ""),
                "AWS_REGION": region,
                "ECR_REPOSITORY_URI": outputs.get("EcrRepositoryUri", ""),
                "ECS_CLUSTER": outputs.get("ClusterName", ""),
                "ECS_SERVICE": outputs.get("ServiceName", ""),
                "ECS_TASK_FAMILY": outputs.get("TaskFamily", ""),
                "ECS_EXECUTION_ROLE_ARN": outputs.get("ExecutionRoleArn", ""),
                "ECS_TASK_ROLE_ARN": outputs.get("TaskRoleArn", ""),
                "CONTAINER_NAME": outputs.get("ContainerName", ""),

                "RUNTIME_SECRET_ID": runtime_secret,
                "PROJECT_SLUG": slug,
            },
            repo_state={
                "aws_profile": profile,
                "region": region,
                "account_id": identity.get("Account", ""),
                "bootstrap_stack": f"{slug}-bootstrap",

                "application_url": outputs.get("ApplicationUrl", ""),
                "ecr_repository": outputs.get("EcrRepositoryUri", ""),
                "ecs_cluster": outputs.get("ClusterName", ""),
                "ecs_service": outputs.get("ServiceName", ""),
                "task_family": outputs.get("TaskFamily", ""),
                "container_name": outputs.get("ContainerName", ""),
                "load_balancer_dns": outputs.get("LoadBalancerDns", ""),
                "log_group": outputs.get("LogGroupName", ""),
                "runtime_secret_arn": runtime_secret,
            },
        )

    def _prepare_vercel(
        self,
        run_id: str,
        run: dict[str, Any],
        spec: dict[str, Any],
        plan: dict[str, Any],
        staged: Path,
        mongodb_uri: str,
        vercel_token: str,
    ) -> ProviderPrep:
        """Create and configure the Vercel project, then hand GitHub what it needs.

        Runs entirely in the staged worktree: the `.vercel/` directory the CLI
        writes is not part of the reviewed artifact manifest, so it can never be
        copied into the user's repository.
        """
        from deployment_agent import vercel_api
        from deployment_agent.vercel_auth import require_vercel_token

        token = require_vercel_token(vercel_token)
        slug = plan["project_slug"]
        service_root = (spec.get("services") or [{}])[0].get("root") or ""
        cwd = staged / service_root if service_root else staged
        team_id = str((run.get("repo") or {}).get("vercel_team_id", ""))

        self.emit(run_id, "step", "link", "running", 20, f"Linking the Vercel project {slug}")
        link = run_command(
            ["vercel", "link", "--yes", "--project", slug, "--cwd", str(cwd)],
            cwd=cwd,
            timeout=180,

            env={"VERCEL_TOKEN": token} if token else None,
        )
        if link.returncode != 0:

            detail = (link.stderr or link.stdout or "").strip()[:300]
            why = ("The Vercel token was rejected."
                   if "token" in detail.lower()
                   else f"'{slug}' may already exist under another account or scope.")
            raise RuntimeError(f"Could not link the Vercel project. {why} {detail}")
        try:
            project_link = json.loads((cwd / ".vercel" / "project.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("Vercel link did not produce .vercel/project.json") from exc
        project_id = str(project_link.get("projectId", ""))
        org_id = str(project_link.get("orgId", ""))
        if not project_id or not org_id:
            raise RuntimeError("Vercel link returned no project or organisation id")

        if not team_id and org_id.startswith("team_"):
            team_id = org_id
        self.emit(run_id, "step", "link", "complete", 30,
                  f"Linked Vercel project {slug}"
                  + (f" (team {team_id})" if team_id else ""))

        try:
            project = vercel_api.get_project(token, project_id, team_id)
            application_url = vercel_api.production_url(project)
            project_name = str(project.get("name") or slug)
        except Exception:
            application_url = f"https://{slug}.vercel.app"
            project_name = slug

        self._sync_vercel_environment(run_id, cwd, token, project_id, team_id,
                                      plan, mongodb_uri, application_url, slug)

        return ProviderPrep(
            github_variables={
                "VERCEL_ORG_ID": org_id,
                "VERCEL_PROJECT_ID": project_id,
                "PROJECT_SLUG": slug,
            },

            github_secrets={"VERCEL_TOKEN": token},
            repo_state={
                "vercel_org_id": org_id,
                "vercel_project_id": project_id,
                "vercel_project_name": project_name,
                "vercel_team_id": team_id,
                "application_url": application_url,
            },
        )

    def _sync_vercel_environment(
        self,
        run_id: str,
        cwd: Path,
        token: str,
        project_id: str,
        team_id: str,
        plan: dict[str, Any],
        mongodb_uri: str,
        application_url: str = "",
        slug: str = "",
    ) -> None:
        """Write production environment variables straight to Vercel.

        Doing this here rather than in the workflow is what keeps the database
        URI out of GitHub entirely.
        """
        from deployment_agent import vercel_api

        entries = ((plan.get("environment") or {}).get("entries")) or []
        existing: set[str] = set()
        existing_ids: dict[str, str] = {}
        try:
            for item in vercel_api.list_env(token, project_id, team_id):
                if "production" not in (item.get("target") or []):
                    continue
                key = str(item.get("key"))
                existing.add(key)
                existing_ids[key] = str(item.get("id", ""))
        except Exception as exc:
            self.emit(run_id, "warning", "env", "warning", 35, redact_text(str(exc)))

        resolved = self._vercel_user_values(mongodb_uri, application_url, slug)

        values: dict[str, str] = {}
        unresolved: list[str] = []
        for entry in entries:
            name = str(entry.get("name", ""))
            if entry.get("resolution") == "user_required":
                if name in resolved and resolved[name]:
                    values[name] = resolved[name]
                elif name not in existing:
                    unresolved.append(name)
            elif entry.get("resolution") == "auto_generate":

                if name in existing:
                    continue
                values[name] = secrets.token_urlsafe(48)
        if unresolved:

            self.emit(run_id, "warning", "env", "warning", 36,
                      "No value for " + ", ".join(sorted(unresolved))
                      + " — set it on the Vercel project if the app needs it.")
        if not values:
            self.emit(run_id, "step", "env", "complete", 40, "No production environment variables to sync")
            return

        self.emit(run_id, "step", "env", "running", 35, f"Syncing {len(values)} Vercel environment variable(s)")
        for name, value in values.items():

            try:

                if name in existing_ids and existing_ids[name]:
                    try:
                        vercel_api.delete_env(token, project_id, existing_ids[name], team_id)
                    except Exception:
                        pass
                vercel_api.upsert_env(token, project_id, name, value, team_id)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not set the Vercel environment variable {name}: {redact_text(str(exc))[:200]}"
                ) from exc
        self.emit(run_id, "step", "env", "complete", 40, "Vercel production environment variables are set")

    @staticmethod
    def _vercel_user_values(mongodb_uri: str, application_url: str,
                           slug: str) -> dict[str, str]:
        """
        Values for the variables the contract leaves to a person.

        Every one of these is knowable here, so leaving them to a person was
        the bug. The database name comes from the URI when it carries one —
        a URI that names none would otherwise silently mean `test`.
        """
        from urllib.parse import urlsplit

        try:
            database = (urlsplit(mongodb_uri).path or "").lstrip("/").split("?")[0]
        except ValueError:
            database = ""
        url = (application_url or "").rstrip("/")
        values = {
            "MONGODB_URI": mongodb_uri,
            "MONGODB_DB": database or slug.replace("-", "_")[:63],
        }
        if url:

            values["BETTER_AUTH_URL"] = url
            values["BASE_URL"] = url
            values["NEXT_PUBLIC_BASE_URL"] = url
        return values

    def _set_github_secrets(self, repo: str, values: dict[str, str]) -> None:
        """Write Actions secrets with the value on stdin.

        `gh secret set --body` would put the credential in argv, where a process
        listing or an echoed stderr exposes it.
        """
        for name, value in values.items():
            if not value:
                continue
            run_command(["gh", "secret", "set", name, "--repo", repo], timeout=60, check=True, input=value)

    @staticmethod
    def _aws_session(profile: str, region: str, credential_reference: str = ""):

        if credential_reference:
            from deployment_agent.aws_onboarding import session_from_reference

            return session_from_reference(credential_reference, region)
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is not installed. Run setup.ps1.") from exc
        kwargs: dict[str, str] = {"region_name": region}
        if profile:
            kwargs["profile_name"] = profile
        return boto3.Session(**kwargs)

    def _ensure_github_repository(self, source: Path, slug: str) -> str:
        if not (source / ".git").exists():
            run_command(["git", "init"], cwd=source, timeout=GIT_TIMEOUT_SECONDS, check=True)
            run_command(["git", "branch", "-M", "main"], cwd=source, timeout=GIT_TIMEOUT_SECONDS, check=True)
        remote = run_command(["git", "remote", "get-url", "origin"], cwd=source)
        if remote.returncode == 0 and remote.stdout.strip():
            parsed = self._parse_github_repo(remote.stdout.strip())
            if not parsed:
                raise RuntimeError("The existing origin is not a GitHub repository")
            return parsed
        user = run_command(["gh", "api", "user", "--jq", ".login"], check=True).stdout.strip()
        repo = f"{user}/{slug}"
        create = run_command(["gh", "repo", "create", repo, "--private"], cwd=source)
        if create.returncode != 0:
            suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
            repo = f"{user}/{slug}-{suffix}"
            run_command(["gh", "repo", "create", repo, "--private"], cwd=source, check=True)
        run_command(["git", "remote", "add", "origin", f"https://github.com/{repo}.git"], cwd=source, check=True)
        return repo

    @staticmethod
    def _parse_github_repo(remote: str) -> str:
        match = re.search(r"github\.com[/:]([^/\s]+/[^/\s]+?)(?:\.git)?$", remote)
        return match.group(1).removesuffix(".git") if match else ""

    @staticmethod
    def _github_default_branch(repo: str, fallback: str = "main") -> str:
        result = run_command(
            ["gh", "repo", "view", repo, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"],
            timeout=30,
        )
        branch = result.stdout.strip() if result.returncode == 0 else ""
        return branch or fallback or "main"

    @staticmethod
    def _github_repository_identity(repo: str) -> dict[str, Any]:
        result = run_command(["gh", "api", f"repos/{repo}"], timeout=30, check=True)
        try:
            identity = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("GitHub repository identity response was not valid JSON") from exc
        oidc = run_command(["gh", "api", f"repos/{repo}/actions/oidc/customization/sub"], timeout=30)
        if oidc.returncode == 0:
            try:
                customization = json.loads(oidc.stdout or "{}")
            except json.JSONDecodeError:
                customization = {}
            if customization.get("use_default") is False:
                raise RuntimeError(
                    "This repository uses a custom GitHub OIDC subject template; reset it to the default before deployment"
                )
        return identity

    @staticmethod
    def _github_oidc_subjects(repo: str, branch: str, identity: dict[str, Any]) -> list[str]:
        owner, name = repo.split("/", 1)
        subjects = [f"repo:{owner}/{name}:ref:refs/heads/{branch}"]
        owner_id = str((identity.get("owner") or {}).get("id") or "")
        repository_id = str(identity.get("id") or "")
        if owner_id and repository_id:
            subjects.append(f"repo:{owner}@{owner_id}/{name}@{repository_id}:ref:refs/heads/{branch}")
        return subjects

    @staticmethod
    def _find_github_oidc(session, stack_name: str = "") -> str:
        """
        An existing GitHub OIDC provider, but never one this stack owns.

        `ExistingOidcProviderArn` tells the template "do not create one", which
        drops `GitHubOidcProvider` out of the stack. If the provider it names is
        the one the FIRST deployment created as a stack resource, CloudFormation
        does exactly what it is told and deletes it — while the deploy role's
        trust policy still names that ARN. Every second deployment of a project
        then fails at `configure-aws-credentials` with "The web identity token
        provided could not be validated", and nothing in that message points
        here. Measured on a-neighbourhood-repair-cafe: CREATE_COMPLETE at
        08:38 on the first deploy, DELETE_COMPLETE at 08:56 on the second.

        So a provider the stack manages is reported as absent, which leaves the
        stack managing it. An account-level one somebody else created is still
        adopted, which is what this was for.
        """
        iam = session.client("iam")
        arn = ""
        for item in iam.list_open_id_connect_providers().get("OpenIDConnectProviderList", []):
            candidate = item.get("Arn", "")
            try:
                provider = iam.get_open_id_connect_provider(OpenIDConnectProviderArn=candidate)
                if provider.get("Url") == "token.actions.githubusercontent.com":
                    arn = candidate
                    break
            except Exception:
                continue
        if not arn or not stack_name:
            return arn
        try:
            cfn = session.client("cloudformation")
            for page in cfn.get_paginator("list_stack_resources").paginate(StackName=stack_name):
                for res in page.get("StackResourceSummaries", []):
                    if res.get("ResourceType") == "AWS::IAM::OIDCProvider":
                        return ""
        except Exception:

            pass
        return arn

    @staticmethod
    def _template_declares(template_path: Path, parameter: str) -> bool:
        """Does this template take that parameter?

        CloudFormation rejects the whole change set for one parameter the
        template does not declare, so the two AWS stacks — which do not take the
        same set — cannot share an unconditional parameter list.
        """
        try:
            return f"{parameter}:" in template_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False

    def _apply_bootstrap_stack(
        self,
        run_id: str,
        session,
        template_path: Path,
        slug: str,
        oidc_subjects: list[str],
        port: int,
        oidc_arn: str,
        network: dict[str, str] | None = None,
    ) -> dict[str, str]:
        cfn = session.client("cloudformation")
        stack_name = f"{slug}-bootstrap"
        exists = True
        try:
            stack_status = cfn.describe_stacks(StackName=stack_name)["Stacks"][0].get("StackStatus", "")

            if stack_status == "ROLLBACK_COMPLETE":
                cfn.delete_stack(StackName=stack_name)
                cfn.get_waiter("stack_delete_complete").wait(
                    StackName=stack_name,
                    WaiterConfig={"Delay": 5, "MaxAttempts": 120},
                )
                exists = False
            elif stack_status == "ROLLBACK_IN_PROGRESS":
                for _ in range(120):
                    time.sleep(5)
                    try:
                        stack_status = cfn.describe_stacks(StackName=stack_name)["Stacks"][0].get("StackStatus", "")
                    except cfn.exceptions.ClientError:
                        stack_status = ""
                        break
                    if stack_status != "ROLLBACK_IN_PROGRESS":
                        break
                if stack_status == "ROLLBACK_COMPLETE":
                    cfn.delete_stack(StackName=stack_name)
                    cfn.get_waiter("stack_delete_complete").wait(
                        StackName=stack_name,
                        WaiterConfig={"Delay": 5, "MaxAttempts": 120},
                    )
                    exists = False
        except cfn.exceptions.ClientError as exc:
            if "does not exist" in str(exc):
                exists = False
            else:
                raise
        change_set = f"deployment-agent-{int(time.time())}"
        parameters = [
            {"ParameterKey": "ProjectSlug", "ParameterValue": slug},
            {"ParameterKey": "GitHubSubjects", "ParameterValue": ",".join(oidc_subjects)},
            {"ParameterKey": "AppPort", "ParameterValue": str(port)},
            {"ParameterKey": "ExistingOidcProviderArn", "ParameterValue": oidc_arn},
        ]
        if network:
            parameters.extend(
                [
                    {"ParameterKey": "ExistingVpcId", "ParameterValue": network["vpc_id"]},
                    {"ParameterKey": "ExistingSubnetA", "ParameterValue": network["subnet_a"]},
                ]
            )

            if network.get("subnet_b") and self._template_declares(
                template_path, "ExistingSubnetB"
            ):
                parameters.append(
                    {"ParameterKey": "ExistingSubnetB",
                     "ParameterValue": network["subnet_b"]}
                )
        cfn.create_change_set(
            StackName=stack_name,
            ChangeSetName=change_set,
            ChangeSetType="UPDATE" if exists else "CREATE",
            Description="Reviewed Deployment Agent bootstrap change set",
            TemplateBody=template_path.read_text(encoding="utf-8"),
            Parameters=parameters,
            Capabilities=["CAPABILITY_NAMED_IAM"],
        )
        self.emit(run_id, "step", "bootstrap", "running", 15, "CloudFormation change set created")
        no_changes = False
        while True:
            detail = cfn.describe_change_set(StackName=stack_name, ChangeSetName=change_set)
            status = detail.get("Status")
            if status == "CREATE_COMPLETE":
                break
            if status == "FAILED":
                reason = detail.get("StatusReason", "")
                if "didn't contain changes" in reason or "No updates" in reason:
                    no_changes = True
                    break
                raise RuntimeError(f"CloudFormation change set failed: {reason}")
            time.sleep(3)
        if not no_changes:
            changes = []
            for change in detail.get("Changes", []):
                resource = change.get("ResourceChange", {})
                changes.append(
                    {
                        "action": resource.get("Action", ""),
                        "logical_resource_id": resource.get("LogicalResourceId", ""),
                        "resource_type": resource.get("ResourceType", ""),
                        "replacement": resource.get("Replacement", ""),
                    }
                )
            self.emit(
                run_id,
                "change_set",
                "bootstrap",
                "preview",
                24,
                f"CloudFormation preview contains {len(changes)} reviewed resource change(s)",
                {"stack": stack_name, "changes": changes},
            )
            cfn.execute_change_set(StackName=stack_name, ChangeSetName=change_set)
            waiter_name = "stack_update_complete" if exists else "stack_create_complete"
            cfn.get_waiter(waiter_name).wait(
                StackName=stack_name,
                WaiterConfig={"Delay": 10, "MaxAttempts": 120},
            )
        stack = cfn.describe_stacks(StackName=stack_name)["Stacks"][0]
        self.emit(run_id, "step", "bootstrap", "complete", 40, "AWS bootstrap stack is ready")
        return {item["OutputKey"]: item.get("OutputValue", "") for item in stack.get("Outputs", [])}

    def _select_bootstrap_network(self, run_id: str, session) -> dict[str, str] | None:
        """Use the generated dedicated VPC normally, but reuse public subnets
        when the regional VPC/IGW quota is exhausted.

        Reusing an existing public VPC is scoped to the stack's security groups,
        ALB and subnets; existing VPC resources are never modified or deleted.
        """
        ec2 = session.client("ec2")
        vpcs = ec2.describe_vpcs().get("Vpcs", [])

        if len(vpcs) < 5:
            return None
        defaults = [vpc for vpc in vpcs if vpc.get("IsDefault")]
        candidates = defaults or [vpc for vpc in vpcs if vpc.get("State") == "available"]
        for vpc in candidates:
            vpc_id = vpc.get("VpcId", "")
            if not vpc_id:
                continue
            subnets = ec2.describe_subnets(
                Filters=[
                    {"Name": "vpc-id", "Values": [vpc_id]},
                    {"Name": "state", "Values": ["available"]},
                ]
            ).get("Subnets", [])
            public = [item for item in subnets if item.get("MapPublicIpOnLaunch")]
            if len(public) < 2:
                public = subnets
            by_az: dict[str, dict[str, Any]] = {}
            for subnet in sorted(public, key=lambda item: (item.get("AvailabilityZone", ""), item.get("SubnetId", ""))):
                by_az.setdefault(subnet.get("AvailabilityZone", ""), subnet)
            selected = list(by_az.values())[:2]
            if len(selected) == 2:
                network = {
                    "vpc_id": vpc_id,
                    "subnet_a": selected[0]["SubnetId"],
                    "subnet_b": selected[1]["SubnetId"],
                }
                self.emit(
                    run_id,
                    "warning",
                    "bootstrap",
                    "complete",
                    8,
                    "Regional VPC quota is full; reusing two existing public subnets safely",
                    {"vpc_id": vpc_id, "subnets": [network["subnet_a"], network["subnet_b"]]},
                )
                return network
        raise RuntimeError("AWS VPC quota is exhausted and no pair of public subnets is available for safe reuse")

    @staticmethod
    def _set_github_variables(repo: str, values: dict[str, str]) -> None:
        for name, value in values.items():
            if not value:
                raise RuntimeError(f"Bootstrap output is missing {name}")
            run_command(["gh", "variable", "set", name, "--body", value, "--repo", repo], check=True)

    def _apply_reviewed_artifacts(self, run_id: str, source: Path, staged: Path) -> list[str]:
        records = self.store.get_artifacts(run_id)
        backup_root = staged.parent / "backup"
        source_root = source.resolve()
        staged_root = staged.resolve()
        applied: list[str] = []
        for record in records:
            relative = record["path"]
            target = source / relative
            staged_file = staged / relative
            resolved_target = target.resolve()
            resolved_staged = staged_file.resolve()
            if source_root not in resolved_target.parents or staged_root not in resolved_staged.parents:
                raise RuntimeError(f"Reviewed artifact path escapes the project workspace: {relative}")
            if not staged_file.exists():
                raise RuntimeError(f"Reviewed artifact disappeared: {relative}")

            if target.exists() and sha256_file(target) == record["sha256"]:
                applied.append(relative)
                continue
            if record.get("original_exists"):
                if not target.exists() or sha256_file(target) != record.get("original_sha256"):
                    raise RuntimeError(f"Source file changed after review; re-run analysis: {relative}")
                backup = backup_root / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
            elif target.exists() and sha256_file(target) != record["sha256"]:
                raise RuntimeError(f"A new conflicting file appeared after review: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(staged_file, target)
            applied.append(relative)
        self.emit(run_id, "step", "apply", "complete", 58, f"Applied {len(applied)} reviewed files to the source repository")
        return applied

    def _commit_and_push(
        self,
        run_id: str,
        source: Path,
        repo: str,
        branch: str,
        applied: list[str],
        profile: TargetProfile | None = None,
    ) -> dict[str, str]:
        profile = profile or profile_for(None)
        previous_workflow_url = self._latest_workflow_url(source, repo)

        run_command(
            [
                "git", "add", "-A", "--", ".",
                ":(exclude)**/.env", ":(exclude)**/.env.local", ":(exclude)**/.env.production",
                ":(exclude)**/.env.development", ":(exclude)**/node_modules/**", ":(exclude)**/.next/**",
                ":(exclude)**/.vercel/**",
            ],
            cwd=source,
            timeout=GIT_TIMEOUT_SECONDS,
            check=True,
        )
        for relative in applied:

            if relative.endswith(".env.example"):
                run_command(["git", "add", "-f", "--", relative], cwd=source, timeout=GIT_TIMEOUT_SECONDS, check=True)
        staged_names = run_command(
            ["git", "diff", "--cached", "--name-only"], cwd=source, timeout=GIT_TIMEOUT_SECONDS, check=True
        ).stdout.splitlines()
        secret_files = [
            name for name in staged_names
            if Path(name).name.startswith(".env") and Path(name).name != ".env.example"
        ]
        if secret_files:
            raise RuntimeError("Refusing to commit environment value files: " + ", ".join(secret_files[:10]))

        if staged_names:
            commit = run_command(
                ["git", "commit", "-m", profile.commit_subject.format(run=run_id[:8])],
                cwd=source,
                timeout=GIT_TIMEOUT_SECONDS,
            )
            if commit.returncode != 0:
                raise RuntimeError(commit.stderr or commit.stdout)

        head_sha = run_command(["git", "rev-parse", "HEAD"], cwd=source).stdout.strip()
        push = run_command(
            ["git", *github_credential_args(), "push", "origin", f"HEAD:{branch}"],
            cwd=source,
            timeout=GIT_TIMEOUT_SECONDS,
        )
        if push.returncode == 0:
            if not staged_names:

                run_command(
                    ["gh", "workflow", "run", "deploy.yml", "--repo", repo, "--ref", branch],
                    cwd=source,
                    timeout=60,
                    check=True,
                )
            self.emit(run_id, "step", "github", "complete", 68, f"Pushed reviewed deployment commit to {repo}:{branch}")
            return {
                "mode": "direct",
                "branch": branch,
                "previous_workflow_url": previous_workflow_url,
                "head_sha": head_sha,
            }
        fallback = f"deployment-agent/{run_id[:8]}"
        run_command(
            ["git", *github_credential_args(), "push", "origin", f"HEAD:{fallback}"],
            cwd=source,
            timeout=GIT_TIMEOUT_SECONDS,
            check=True,
        )
        pr = run_command(
            [
                "gh",
                "pr",
                "create",
                "--repo",
                repo,
                "--base",
                branch,
                "--head",
                fallback,
                "--title",
                profile.pr_title,
                "--body",
                f"Generated and reviewed by Deployment Agent run `{run_id}`.",
            ],
            cwd=source,
            timeout=120,
            check=True,
        )
        return {
            "mode": "pull_request",
            "branch": fallback,
            "url": pr.stdout.strip(),
            "head_sha": head_sha,
        }

    @staticmethod
    def _latest_workflow_url(source: Path, repo: str) -> str:
        result = run_command(
            [
                "gh", "run", "list", "--repo", repo, "--workflow", "deploy.yml",
                "--limit", "1", "--json", "url",
            ],
            cwd=source,
            timeout=30,
        )
        if result.returncode:
            return ""
        try:
            runs = json.loads(result.stdout or "[]")
            return str(runs[0].get("url", "")) if runs else ""
        except (json.JSONDecodeError, IndexError, AttributeError):
            return ""

    def _wait_for_workflow(
        self,
        run_id: str,
        source: Path,
        repo: str,
        timeout: int = 900,
        previous_url: str = "",
        head_sha: str = "",
    ) -> str:
        deadline = time.time() + timeout
        seen = False
        last_reported = ""
        while time.time() < deadline:
            result = run_command(
                [
                    "gh",
                    "run",
                    "list",
                    "--repo",
                    repo,
                    "--workflow",
                    "deploy.yml",
                    "--limit",
                    "10",
                    "--json",
                    "status,conclusion,url,displayTitle,createdAt,headSha",
                ],
                cwd=source,
                timeout=30,
            )
            if result.returncode == 0:
                runs = json.loads(result.stdout or "[]")
                current = select_workflow_run(runs, head_sha, previous_url)
                if current:
                    seen = True
                    signature = f"{current.get('status', '')}:{current.get('conclusion', '')}"
                    if signature != last_reported:
                        last_reported = signature
                        self.emit(
                            run_id,
                            "monitor",
                            "github",
                            current.get("status", "running"),
                            76,
                            f"GitHub Actions: {current.get('displayTitle', 'deployment')}",
                            current,
                        )
                    if current.get("status") == "completed":
                        return current.get("conclusion") or "unknown"
            time.sleep(10 if seen else 5)
        return "running" if seen else "not_found"

    def cancel(self, run_id: str) -> dict[str, Any]:
        """Stop a run that is still in flight. Deletes nothing.

        Three things are true at once here and the method exists to hold them
        apart:

          * AgentForge stops advancing the run. The state becomes CANCELLED, which
            is outside `_RECONCILED_STATES`, so the supervisor will not sweep
            it back into life on its next pass.
          * GitHub stops deploying. A workflow run triggered by this deployment
            keeps going after AgentForge loses interest, and it is the thing that
            actually writes to the instance — so it is cancelled too.
          * AWS is left completely alone. Whatever the run already created is
            still there and still billing. `start_teardown` is what deletes it,
            and CANCELLED has an edge to DESTROYED so it stays reachable.

        The worker thread is NOT stopped, because it cannot be: it is inside a
        boto3 or git call with no cancellation point. It finds out when its
        next state transition is rejected, which `_deploy_reserved` handles.
        """
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError("Run not found")
        state = run["state"]
        if state not in _CANCELLABLE_STATES:
            raise ValueError(
                f"This deployment is not running (it is {state}), so there is "
                f"nothing to cancel"
            )
        workflow = self._cancel_workflow_run(run)
        self.store.transition_run(run_id, RunState.CANCELLED, error="")
        self.emit(
            run_id, "step", "cancel", "complete", 100,
            "Deployment cancelled"
            + (f"; GitHub Actions run {workflow} was stopped too" if workflow else "")
            + ". Cloud resources were not deleted — use Delete for those.",
        )
        return {"cancelled": True, "state": RunState.CANCELLED.value,
                "workflow_cancelled": workflow}

    def _cancel_workflow_run(self, run: dict[str, Any]) -> str:
        """Stop the GitHub Actions run this deployment started, if one is live.

        Best effort by design. `gh` may not be installed, the token may not
        carry the scope, or the run may have finished a second ago — none of
        which should stop the local cancellation, which is the part the user
        can see. Returns the run id it stopped, or "".
        """
        repository = str((run.get("repo") or {}).get("repository") or "")
        if not repository or not command_exists("gh"):
            return ""
        try:
            listed = run_command(
                ["gh", "run", "list", "--repo", repository, "--limit", "10",
                 "--json", "databaseId,status"],
                timeout=30,
            )
            if listed.returncode != 0:
                return ""
            live = [
                item for item in json.loads(listed.stdout or "[]")
                if str(item.get("status", "")) in
                {"queued", "in_progress", "waiting", "requested", "pending"}
            ]
            if not live:
                return ""
            target = str(live[0].get("databaseId", ""))
            cancelled = run_command(
                ["gh", "run", "cancel", target, "--repo", repository], timeout=30
            )
            return target if cancelled.returncode == 0 else ""
        except Exception:                                   # noqa: BLE001

            return ""

    def start_teardown(self, run_id: str, credential_reference: str = "",
                       force: bool = False) -> dict[str, Any]:
        """Delete every provider resource this run created. Irreversible.

        `force` tears down a run that is still active, by cancelling it first.

        Refusing outright was a dead end, and a costly one. "Wait for it to
        finish or fail" assumes it will do one or the other, and a run can sit
        in an active state forever: the monitor only ever stamped FAILED from
        CI_RUNNING and DEPLOYING, so anything that reached VALIDATING and then
        broke stayed VALIDATING. Measured on a real deployment — a run stuck
        there for over a day, its instance answering 502, still billing, and no
        way to delete it from the dashboard at all. The AWS console was the
        only way out, which is exactly the situation this button exists to
        prevent.

        Cancelling first is what a person means by deleting a stuck deployment:
        stop the workflow that is still writing to the instance, then remove
        what it built. Doing it in that order matters — a teardown racing a
        live GitHub Actions run can delete a stack the workflow then recreates.
        """
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError("Run not found")
        if run["state"] in {RunState.DESTROYED.value}:
            raise ValueError("This deployment has already been torn down")
        if run["state"] in _PERSISTED_ACTIVE_STATES:
            if not force:
                raise ValueError(
                    "This deployment is still running. Stop it first with "
                    "Cancel, or delete it anyway — that stops it and removes "
                    "its resources in one go."
                )

            self.cancel(run_id)
            run = self.store.get_run(run_id) or run
            self.emit(run_id, "step", "teardown", "running", 5,
                      "Deployment stopped; deleting what it created")
        plan = run.get("plan") or {}
        slug = plan.get("project_slug") or ""
        repo = run.get("repo") or {}
        if not slug or not repo:

            self.store.transition_run(run_id, RunState.DESTROYED, error="")
            self.emit(run_id, "step", "teardown", "complete", 100, "No cloud resources were created by this run")
            return {"deleted": [], "slug": slug}
        if target_of(run) is DeploymentTarget.VERCEL:
            threading.Thread(
                target=self._teardown_vercel, args=(run_id, slug, repo), daemon=True
            ).start()
            return {"accepted": True, "slug": slug}
        threading.Thread(
            target=self._teardown_worker, args=(run_id, slug, repo, credential_reference), daemon=True
        ).start()
        return {"accepted": True, "slug": slug}

    def _teardown_vercel(self, run_id: str, slug: str, repo: dict[str, Any]) -> None:
        from deployment_agent import vercel_api
        from deployment_agent.vercel_auth import require_vercel_token

        try:
            project_id = str(repo.get("vercel_project_id", ""))
            if not project_id:
                raise RuntimeError("No Vercel project is recorded for this deployment")
            self.emit(run_id, "step", "teardown", "running", 40, f"Deleting the Vercel project {slug}")
            vercel_api.delete_project(
                require_vercel_token(), project_id, str(repo.get("vercel_team_id", ""))
            )
            self.store.transition_run(run_id, RunState.DESTROYED, error="")
            self.emit(
                run_id, "step", "teardown", "complete", 100,
                "Teardown complete; the Vercel project and its deployments were deleted",
                {"deleted": [slug]},
            )
        except Exception as exc:

            self.emit(
                run_id, "error", "teardown", "failed", 100,
                f"Teardown failed; the Vercel project was NOT deleted: {redact_text(str(exc))}",
            )

    def _teardown_worker(
        self, run_id: str, slug: str, repo: dict[str, Any], credential_reference: str = ""
    ) -> None:
        try:

            session = self._aws_session(
                repo.get("aws_profile", ""), repo.get("region", "ap-south-1"), credential_reference
            )
            cfn = session.client("cloudformation")
            deleted: list[str] = []

            for index, stack_name in enumerate((f"{slug}-service", f"{slug}-bootstrap")):
                try:
                    cfn.describe_stacks(StackName=stack_name)
                except Exception as exc:

                    if "does not exist" in str(exc):
                        continue
                    raise
                self.emit(
                    run_id, "step", "teardown", "running", 20 + index * 40, f"Deleting stack {stack_name}"
                )

                self._drain_stack_resources(run_id, session, cfn, stack_name)
                cfn.delete_stack(StackName=stack_name)
                cfn.get_waiter("stack_delete_complete").wait(
                    StackName=stack_name, WaiterConfig={"Delay": 10, "MaxAttempts": 120}
                )
                deleted.append(stack_name)
                self.emit(run_id, "step", "teardown", "running", 40 + index * 40, f"Deleted {stack_name}")
            self.store.transition_run(run_id, RunState.DESTROYED, error="")
            self.emit(
                run_id,
                "step",
                "teardown",
                "complete",
                100,
                f"Teardown complete; deleted {len(deleted)} stack(s)" if deleted else "No stacks remained to delete",
                {"deleted": deleted},
            )
        except Exception as exc:

            self.emit(
                run_id,
                "error",
                "teardown",
                "failed",
                100,
                f"Teardown failed; resources were NOT deleted: {redact_text(str(exc))}",
            )

    def _drain_stack_resources(self, run_id: str, session, cfn, stack_name: str) -> None:
        """Empty the resources CloudFormation cannot delete while non-empty.

        Only resources owned by this stack are touched, so nothing outside the
        agent's own deployment can be affected.
        """
        try:
            resources = cfn.describe_stack_resources(StackName=stack_name)["StackResources"]
        except Exception:
            return
        for resource in resources:
            kind = resource.get("ResourceType")
            physical = resource.get("PhysicalResourceId")
            if not physical:
                continue
            try:
                if kind == "AWS::ECR::Repository":
                    self._empty_ecr_repository(session, physical)
                    self.emit(run_id, "step", "teardown", "running", 30, f"Emptied ECR repository {physical}")
                elif kind == "AWS::S3::Bucket":
                    self._empty_s3_bucket(session, physical)
                    self.emit(run_id, "step", "teardown", "running", 30, f"Emptied S3 bucket {physical}")
            except Exception as exc:
                self.emit(
                    run_id, "warning", "teardown", "warning", 30,
                    f"Could not empty {kind} {physical}: {redact_text(str(exc))}",
                )

    @staticmethod
    def _empty_ecr_repository(session, repository: str) -> None:
        ecr = session.client("ecr")
        paginator = ecr.get_paginator("list_images")
        for page in paginator.paginate(repositoryName=repository):
            ids = page.get("imageIds", [])
            if ids:
                ecr.batch_delete_image(repositoryName=repository, imageIds=ids)

    @staticmethod
    def _empty_s3_bucket(session, bucket: str) -> None:
        s3 = session.client("s3")

        for key in ("Versions", "DeleteMarkers"):
            paginator = s3.get_paginator("list_object_versions")
            for page in paginator.paginate(Bucket=bucket):
                items = [{"Key": item["Key"], "VersionId": item["VersionId"]} for item in page.get(key, [])]
                for index in range(0, len(items), 1000):
                    s3.delete_objects(Bucket=bucket, Delete={"Objects": items[index : index + 1000]})

    def _rollback_vercel(self, run_id: str, repo: dict[str, Any]) -> dict[str, Any]:
        """Promote the most recent healthy deployment that is not the current one."""
        from deployment_agent import vercel_api
        from deployment_agent.vercel_auth import require_vercel_token

        project_id = str(repo.get("vercel_project_id", ""))
        if not project_id:
            raise RuntimeError("No Vercel project is recorded for this deployment")
        token = require_vercel_token()
        team_id = str(repo.get("vercel_team_id", ""))
        ready = [
            item
            for item in vercel_api.list_deployments(token, project_id, team_id, limit=20)
            if item.get("readyState") == "READY" or item.get("state") == "READY"
        ]
        if len(ready) < 2:
            raise RuntimeError("No previous healthy Vercel deployment is available to roll back to")

        previous = ready[1]
        deployment_id = str(previous.get("uid") or previous.get("id") or "")
        vercel_api.promote_deployment(token, project_id, deployment_id, team_id)
        self.store.transition_run(run_id, RunState.ROLLED_BACK)
        self.emit(run_id, "step", "rollback", "complete", 100, "Promoted the previous Vercel deployment")
        return {"deployment_id": deployment_id, "url": previous.get("url", "")}

    def vercel_domains(self, run_id: str) -> list[dict[str, Any]]:
        from deployment_agent import vercel_api
        from deployment_agent.vercel_auth import require_vercel_token

        project_id, team_id = self._vercel_project(run_id)
        return vercel_api.list_domains(require_vercel_token(), project_id, team_id)

    def add_vercel_domain(self, run_id: str, domain: str) -> dict[str, Any]:
        from deployment_agent import vercel_api
        from deployment_agent.vercel_auth import require_vercel_token

        domain = str(domain or "").strip().lower()
        if not domain or "/" in domain or " " in domain:
            raise ValueError("Enter a bare hostname, for example app.example.com")
        project_id, team_id = self._vercel_project(run_id)
        result = vercel_api.add_domain(require_vercel_token(), project_id, domain, team_id)
        self.emit(run_id, "step", "domains", "complete", 100, f"Added the domain {domain}")

        return result

    def remove_vercel_domain(self, run_id: str, domain: str) -> dict[str, Any]:
        from deployment_agent import vercel_api
        from deployment_agent.vercel_auth import require_vercel_token

        project_id, team_id = self._vercel_project(run_id)
        result = vercel_api.remove_domain(require_vercel_token(), project_id, str(domain), team_id)
        self.emit(run_id, "step", "domains", "complete", 100, f"Removed the domain {domain}")
        return result

    def _vercel_project(self, run_id: str) -> tuple[str, str]:
        run = self.store.get_run(run_id)
        if not run:
            raise ValueError("Run not found")
        if target_of(run) is not DeploymentTarget.VERCEL:
            raise ValueError("This deployment does not target Vercel")
        repo = run.get("repo") or {}
        project_id = str(repo.get("vercel_project_id", ""))
        if not project_id:
            raise ValueError("This run has no linked Vercel project yet; deploy it first")
        return project_id, str(repo.get("vercel_team_id", ""))

    def rollback(self, run_id: str) -> dict[str, Any]:
        run = self.store.get_run(run_id)
        if not run or not run.get("repo"):
            raise ValueError("No deployed environment is available for rollback")
        repo = run["repo"]
        if target_of(run) is DeploymentTarget.VERCEL:
            return self._rollback_vercel(run_id, repo)
        session = self._aws_session(repo.get("aws_profile", ""), repo.get("region", "ap-south-1"))
        instance_id = repo.get("instance_id")
        if not instance_id:
            raise RuntimeError("No EC2 instance is recorded for this deployment")
        ssm = session.client("ssm")

        script = textwrap.dedent(
            """
            set -euo pipefail
            cd /opt/app/releases
            current=$(readlink -f /opt/app/current || true)
            previous=$(ls -1dt /opt/app/releases/*/ | grep -v "^${current}/$" | head -n 1)
            test -n "$previous"
            ln -sfn "${previous%/}" /opt/app/current.new
            mv -Tf /opt/app/current.new /opt/app/current
            systemctl restart nextjs
            basename "${previous%/}" > /opt/app/shared/current-sha
            echo "rolled back to ${previous%/}"
            """
        ).strip()
        command = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Comment="Deployment Agent rollback",
            TimeoutSeconds=600,
            Parameters={"commands": script.splitlines()},
        )
        command_id = command["Command"]["CommandId"]
        self.store.transition_run(run_id, RunState.ROLLED_BACK)
        self.emit(run_id, "step", "rollback", "complete", 100, "Rollback to the previous release dispatched")
        return {"command_id": command_id, "instance_id": instance_id}
