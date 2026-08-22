from __future__ import annotations

import difflib
import json
import re
import textwrap
from dataclasses import replace
from pathlib import Path
from typing import Callable

from deployment_agent.environment import (DEPLOYER_INJECTED,
                                          EnvironmentContractResolver)
from deployment_agent.providers import profile_for
from deployment_agent.models import (
    ArtifactRecord,
    DeploymentPlan,
    DeploymentTarget,
    EnvironmentContract,
    EnvironmentEntry,
    ProjectSpec,
    ServiceSpec,
)
from deployment_agent.config import ARTIFACT_SCHEMA_VERSION
from deployment_agent.security import sha256_file


_EAGER_CONNECT = re.compile(
    r"let\s+clientPromise\b.*?export\s+default\s+clientPromise",
    re.DOTALL,
)

_LAZY_CONNECT = """let clientPromise

// Reuse across HMR reloads so dev doesn't leak a connection per edit.
if (process.env.NODE_ENV === 'development' && global._mongoClientPromise) {
  clientPromise = global._mongoClientPromise
}

// Connected on FIRST USE, never at import. `next build` imports every page and
// route while collecting page data, so connecting here made a running database
// a requirement to COMPILE — and CI has none.
function connection() {
  if (!clientPromise) {
    if (!uri) throw new Error('MONGODB_URI is not set')
    clientPromise = new MongoClient(uri).connect()
    if (process.env.NODE_ENV === 'development') {
      global._mongoClientPromise = clientPromise
    }
  }
  return clientPromise
}

/** Awaitable exactly like the promise it replaced. */
export default { then: (ok, no) => connection().then(ok, no) }"""

BUILD_PLACEHOLDER_MONGODB_URI = "mongodb://127.0.0.1:27017/deployment_agent_build"
BUILD_PLACEHOLDER_AUTH_SECRET = "build-only-placeholder-real-value-injected-at-runtime"
BUILD_PLACEHOLDER_AUTH_URL = "http://localhost:3000"


class ArtifactGeneratorAgent:
    def __init__(self, emit: Callable[..., object] | None = None):
        self.emit = emit or (lambda *args, **kwargs: None)

    def generate(
        self,
        run_id: str,
        spec: ProjectSpec,
        plan: DeploymentPlan,
        staged_root: Path,
        target: DeploymentTarget = DeploymentTarget.AWS_EC2,
        contract: EnvironmentContract | None = None,
    ) -> list[ArtifactRecord]:
        service = self._render_service(spec.services[0], plan)
        contract = contract or EnvironmentContractResolver.discover(
            service,
            staged_root / service.root if service.root else staged_root,
        )
        plan.target = target.value

        plan.runtime_strategy = profile_for(target).runtime_strategy
        plan.environment = contract.to_dict()
        self.emit(run_id, "step", "runtime", "running", 32, "Generating runtime assets")
        records: list[ArtifactRecord] = []
        prefix = f"{service.root}/" if service.root else ""
        records.append(
            self._write(spec, staged_root, f"{prefix}.env.example", self._env_example(service, contract), "environment")
        )
        self.emit(run_id, "step", "runtime", "complete", 44, "Runtime assets generated")

        patch_records, applied_patches = self._apply_compatibility_patches(spec, staged_root, service, target)
        records.extend(patch_records)
        plan.source_patches.extend(applied_patches)

        self.emit(run_id, "step", "cicd", "running", 48, "Generating GitHub Actions workflows")
        records.append(
            self._write(spec, staged_root, ".github/workflows/ci.yml", self._ci_workflow(service, spec, target), "cicd")
        )

        if target == DeploymentTarget.AWS_EC2:
            deploy_workflow = self._deploy_workflow(service, spec, plan)
        elif target == DeploymentTarget.AWS_ECS:
            deploy_workflow = self._ecs_deploy_workflow(service, spec, plan)
        else:
            deploy_workflow = self._vercel_deploy_workflow(service, spec, plan)
        records.append(
            self._write(spec, staged_root, ".github/workflows/deploy.yml", deploy_workflow, "cicd")
        )
        self.emit(run_id, "step", "cicd", "complete", 57, "CI/CD workflows generated")

        if target == DeploymentTarget.AWS_EC2:

            self.emit(run_id, "step", "aws", "running", 60, "Generating AWS EC2 artifacts")
            records.extend(
                [
                    self._write(spec, staged_root, "infra/bootstrap.yml", self._bootstrap_template(service, plan), "aws"),
                    self._write(
                        spec,
                        staged_root,
                        "infra/parameters.example.json",
                        json.dumps(self._parameters_example(spec, plan, service), indent=2) + "\n",
                        "aws",
                    ),
                    self._write(spec, staged_root, "deploy/release.sh", self._release_script(service, contract), "aws"),
                ]
            )
            self.emit(run_id, "step", "aws", "complete", 70, "AWS EC2 artifacts generated")
        elif target == DeploymentTarget.AWS_ECS:

            self.emit(run_id, "step", "aws", "running", 60, "Generating AWS ECS artifacts")
            records.extend(
                [
                    self._write(spec, staged_root, "infra/bootstrap.yml",
                                self._ecs_bootstrap_template(service, plan), "aws"),
                    self._write(
                        spec,
                        staged_root,
                        "infra/parameters.example.json",
                        json.dumps(self._parameters_example(spec, plan, service), indent=2) + "\n",
                        "aws",
                    ),

                    self._write(spec, staged_root, f"{prefix}Dockerfile",
                                self._dockerfile(service), "aws"),
                    self._write(spec, staged_root, f"{prefix}.dockerignore",
                                self._dockerignore(), "aws"),
                    self._write(
                        spec,
                        staged_root,
                        "deploy/task-definition.json",
                        json.dumps(self._task_definition(service, plan, contract), indent=2) + "\n",
                        "aws",
                    ),
                ]
            )
            self.emit(run_id, "step", "aws", "complete", 70, "AWS ECS artifacts generated")
        else:
            self.emit(run_id, "step", "provider", "running", 60, "Generating Vercel artifacts")
            records.append(
                self._write(
                    spec,
                    staged_root,
                    "deploy/vercel-environment.json",
                    json.dumps(self._vercel_environment(contract), indent=2) + "\n",
                    "vercel",
                )
            )

            config_path = f"{prefix}vercel.json"
            if (staged_root / config_path).is_file():
                plan.recommendations.append(
                    f"Kept your existing {config_path}; the agent did not overwrite it."
                )
            else:
                records.append(
                    self._write(spec, staged_root, config_path, self._vercel_config(service), "vercel")
                )
            self.emit(run_id, "step", "provider", "complete", 70, "Vercel artifacts generated")

        readiness = self._initial_readiness(records, target)
        report = self._report(spec, plan, readiness, target)
        records.append(self._write(spec, staged_root, "deployment-report.md", report, "report"))
        records.append(
            self._write(
                spec,
                staged_root,
                "readiness-score.json",
                json.dumps(readiness, indent=2) + "\n",
                "report",
            )
        )
        manifest = {
            "version": ARTIFACT_SCHEMA_VERSION,
            "project": spec.name,
            "project_slug": plan.project_slug,
            "primary_service": service.name,
            "service_root": service.root,
            "model": plan.model,
            "model_used": plan.model_used,
            "target": target.value,
            "environment_contract": contract.to_dict(),
            "generation": {
                "service_root": plan.service_root,
                "package_manager": plan.package_manager,
                "install_command": plan.install_command,
                "build_command": plan.build_command,
                "start_command": plan.start_command,
                "port": plan.port,
                "health_path": plan.health_path,
                "environment_contract": plan.environment_contract,
                "runtime_strategy": plan.runtime_strategy,
                "github_jobs": plan.github_jobs,
                "aws_sizing": plan.aws_sizing,
                "required_patches": plan.required_patches,
            },
            "artifacts": [record.path for record in records] + ["deployment-manifest.json"],
            "agent_owned_files": [record.path for record in records] + ["deployment-manifest.json"],
        }
        records.append(
            self._write(
                spec,
                staged_root,
                "deployment-manifest.json",
                json.dumps(manifest, indent=2) + "\n",
                "manifest",
            )
        )
        self.emit(run_id, "step", "generator", "complete", 76, f"Generated {len(records)} reviewed artifacts")
        return records

    @staticmethod
    def _render_service(service: ServiceSpec, plan: DeploymentPlan) -> ServiceSpec:
        """Use the validated AI plan while keeping discovery authoritative for unsafe fields."""
        return replace(
            service,
            root=plan.service_root or service.root,
            package_manager=plan.package_manager or service.package_manager,
            install_command=plan.install_command or service.install_command,
            build_command=plan.build_command or service.build_command,
            start_command=plan.start_command or service.start_command,
            port=plan.port or service.port,
            health_path=plan.health_path or service.health_path,
        )

    def repair_compatibility(
        self,
        spec: ProjectSpec,
        plan: DeploymentPlan,
        staged_root: Path,
        records: list[ArtifactRecord],
        actions: list[str],
        build_error: str,
    ) -> tuple[list[ArtifactRecord], bool]:
        """Apply only bounded, predefined compatibility repairs in the isolated review copy."""
        if not actions:
            return records, False
        service = self._render_service(spec.services[0], plan)
        record_map = {record.path: record for record in records}
        before = {path: record.sha256 for path, record in record_map.items()}
        service_root = staged_root / service.root if service.root else staged_root
        if "ensure-type-safe-health-route" in actions and (service_root / "tsconfig.json").exists():
            for app_root in (service_root / "app", service_root / "src" / "app"):
                legacy = app_root / "api" / "health" / "route.js"
                relative = legacy.relative_to(staged_root).as_posix()
                record = record_map.get(relative)
                if legacy.exists() and record and record.kind == "source-patch" and not record.original_exists:
                    legacy.unlink()
                    record_map.pop(relative, None)

        patch_records, applied = self._apply_compatibility_patches(
            spec, staged_root, service, DeploymentTarget(plan.target)
        )
        for record in patch_records:
            record_map[record.path] = record
        if "normalize-alert-variant" in actions:

            alert_pattern = re.compile(r"(<Alert\b[^>]*\bvariant\s*=\s*[\"'])info([\"'])")
            scanned = 0
            for candidate in service_root.rglob("*"):

                if scanned >= 2000:
                    break
                if not candidate.is_file() or candidate.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
                    continue
                try:
                    if candidate.stat().st_size > 512_000:
                        continue
                    content = candidate.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                scanned += 1
                updated, count = alert_pattern.subn(r"\1default\2", content)
                if not count or updated == content:
                    continue
                relative = candidate.relative_to(staged_root).as_posix()
                record_map[relative] = self._write(spec, staged_root, relative, updated, "source-patch")
                applied_patch = {
                    "path": relative,
                    "reason": "Type-safe Alert variant compatibility",
                    "change": "Normalize unsupported Alert variant info to default",
                }
                if applied_patch not in applied:
                    applied.append(applied_patch)
        if applied:
            plan.source_patches.extend(item for item in applied if item not in plan.source_patches)
        changed = set(record_map) != set(before) or any(
            record.sha256 != before.get(path) for path, record in record_map.items()
        )
        if changed:
            manifest_path = staged_root / "deployment-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["generation"]["repair_actions"] = list(plan.repair_actions)
            owned = sorted(set(record_map) | {"deployment-manifest.json"})
            manifest["artifacts"] = owned
            manifest["agent_owned_files"] = owned
            record_map["deployment-manifest.json"] = self._write(
                spec,
                staged_root,
                "deployment-manifest.json",
                json.dumps(manifest, indent=2) + "\n",
                "manifest",
            )
        if not changed and "route.js" in build_error and "allowJs" in build_error:
            plan.risks.append("The bounded type-safe health repair made no change; manual application code review is required.")
        return list(record_map.values()), changed

    @staticmethod
    def diff(spec: ProjectSpec, staged_root: Path, records: list[dict]) -> str:
        source_root = Path(spec.source_path)
        chunks: list[str] = []
        for record in records:
            relative = record["path"]
            staged = staged_root / relative
            original = source_root / relative
            try:
                after = staged.read_text(encoding="utf-8").splitlines(keepends=True)
                before = original.read_text(encoding="utf-8").splitlines(keepends=True) if original.exists() else []
            except (UnicodeDecodeError, OSError):
                continue
            chunks.extend(
                difflib.unified_diff(
                    before,
                    after,
                    fromfile=f"a/{relative}",
                    tofile=f"b/{relative}",
                )
            )
        return "".join(chunks)

    def _write(self, spec: ProjectSpec, root: Path, relative: str, content: str, kind: str) -> ArtifactRecord:
        relative = relative.replace("\\", "/").lstrip("/")
        target = root / relative
        original = Path(spec.source_path) / relative
        original_exists = original.exists()
        original_hash = sha256_file(original) if original_exists and original.is_file() else ""
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        return ArtifactRecord(
            path=relative,
            kind=kind,
            sha256=sha256_file(target),
            size=target.stat().st_size,
            original_exists=original_exists,
            original_sha256=original_hash,
        )

    def _apply_compatibility_patches(
        self,
        spec: ProjectSpec,
        staged_root: Path,
        service: ServiceSpec,
        target: DeploymentTarget = DeploymentTarget.AWS_EC2,
    ) -> tuple[list[ArtifactRecord], list[dict[str, str]]]:
        records: list[ArtifactRecord] = []
        patches: list[dict[str, str]] = []
        service_root = staged_root / service.root if service.root else staged_root
        prefix = f"{service.root}/" if service.root else ""

        config = next(
            (
                service_root / name
                for name in ("next.config.mjs", "next.config.js", "next.config.cjs", "next.config.ts")
                if (service_root / name).exists()
            ),
            None,
        )

        wants_standalone = target in (DeploymentTarget.AWS_EC2, DeploymentTarget.AWS_ECS)
        if not wants_standalone:
            pass
        elif config:
            content = config.read_text(encoding="utf-8")
            updated = content
            if not re.search(r"\boutput\s*:\s*['\"]standalone['\"]", content):
                updated, count = re.subn(
                    r"const\s+nextConfig\s*=\s*\{\s*\}\s*;?",
                    'const nextConfig = {\n  output: "standalone",\n};',
                    content,
                    count=1,
                )
                if count == 0:
                    updated, count = re.subn(
                        r"(const\s+(?:nextConfig|config)\s*=\s*\{)",
                        r'\1\n  output: "standalone",',
                        content,
                        count=1,
                    )
                if count == 0:
                    updated, count = re.subn(
                        r"((?:module\.exports\s*=|export\s+default)\s*\{)",
                        r'\1\n  output: "standalone",',
                        content,
                        count=1,
                    )
                if count == 0:
                    updated = content
            if updated != content:
                relative = f"{prefix}{config.name}"
                records.append(self._write(spec, staged_root, relative, updated, "source-patch"))
                patches.append({"path": relative, "reason": "Next.js standalone build output", "change": "Add output: standalone"})
        elif wants_standalone:
            relative = f"{prefix}next.config.mjs"
            content = 'const nextConfig = {\n  output: "standalone",\n};\n\nexport default nextConfig;\n'
            records.append(self._write(spec, staged_root, relative, content, "source-patch"))
            patches.append({"path": relative, "reason": "Next.js standalone build output", "change": "Create a minimal standalone Next.js config"})

        app_root = service_root / "app"
        if not app_root.exists() and (service_root / "src" / "app").exists():
            app_root = service_root / "src" / "app"
        typescript_project = (service_root / "tsconfig.json").exists()
        suffixes = (".ts", ".tsx", ".js", ".jsx") if typescript_project else (".js", ".jsx", ".ts", ".tsx")
        health_candidates = [app_root / "api" / "health" / f"route{suffix}" for suffix in suffixes]
        health = app_root / "api" / "health" / ("route.ts" if typescript_project else "route.js")
        if app_root.exists() and not any(path.exists() for path in health_candidates):
            relative = health.relative_to(staged_root).as_posix()
            health_content = textwrap.dedent(
                """
                export const dynamic = "force-dynamic";

                export async function GET() {
                  return Response.json({ status: "ok", service: "nextjs", timestamp: new Date().toISOString() });
                }
                """
            ).lstrip()
            records.append(self._write(spec, staged_root, relative, health_content, "source-patch"))
            patches.append({"path": relative, "reason": "nginx and release health checks", "change": "Add safe GET /api/health endpoint"})
        elif not app_root.exists() and (service_root / "pages").exists():
            pages_health = service_root / "pages" / "api" / "health.js"
            pages_candidates = [pages_health.with_suffix(suffix) for suffix in (".js", ".ts", ".jsx", ".tsx")]
            if not any(path.exists() for path in pages_candidates):
                relative = pages_health.relative_to(staged_root).as_posix()
                health_content = textwrap.dedent(
                    """
                    export default function handler(_request, response) {
                      response.status(200).json({ status: "ok", service: "nextjs", timestamp: new Date().toISOString() });
                    }
                    """
                ).lstrip()
                records.append(self._write(spec, staged_root, relative, health_content, "source-patch"))
                patches.append({"path": relative, "reason": "nginx and release health checks", "change": "Add safe GET /api/health endpoint"})

        for name in ("mongodb", "db", "mongo"):
            for suffix in (".ts", ".js"):
                mongo_lib = service_root / "lib" / f"{name}{suffix}"
                if not mongo_lib.exists():
                    continue
                source = mongo_lib.read_text(encoding="utf-8")
                if "function connection()" in source:
                    continue
                updated, count = _EAGER_CONNECT.subn(_LAZY_CONNECT, source, count=1)
                if not count:
                    continue

                updated = updated.replace("await clientPromise", "await connection()")
                relative = mongo_lib.relative_to(staged_root).as_posix()
                records.append(self._write(spec, staged_root, relative, updated, "source-patch"))
                patches.append({
                    "path": relative,
                    "reason": "next build imports every module and has no database",
                    "change": "Connect to MongoDB on first use instead of at import",
                })
                break

        for suffix in (".ts", ".js", ".tsx", ".jsx"):
            auth_route = app_root / "api" / "auth" / "[...all]" / f"route{suffix}"
            if not auth_route.exists():
                continue
            source = auth_route.read_text(encoding="utf-8")
            eager = re.search(r"toNextJsHandler\s*\(\s*auth\.handler\s*\)", source)
            deferred = "await import(" in source
            if not eager or deferred:
                break
            relative = auth_route.relative_to(staged_root).as_posix()
            patched = textwrap.dedent(
                """
                import { toNextJsHandler } from 'better-auth/next-js'

                // Deferred by the deployment agent: importing `@/lib/auth` at
                // module scope builds Better Auth, which connects to MongoDB,
                // and `next build` imports this file while collecting page
                // data. The build has no database, so that failed CI with
                // ECONNREFUSED 127.0.0.1:27017 while working locally.
                let handlers
                async function ready() {
                  if (!handlers) {
                    const { auth } = await import('@/lib/auth')
                    handlers = toNextJsHandler(auth.handler)
                  }
                  return handlers
                }

                export const dynamic = 'force-dynamic'

                export async function GET(request) {
                  return (await ready()).GET(request)
                }

                export async function POST(request) {
                  return (await ready()).POST(request)
                }
                """
            ).lstrip()
            records.append(self._write(spec, staged_root, relative, patched, "source-patch"))
            patches.append({
                "path": relative,
                "reason": "next build imports route modules and has no database",
                "change": "Build the Better Auth handler on first request, not at import",
            })
            break

        auth_client = next(
            (service_root / "lib" / f"auth-client{suffix}" for suffix in (".js", ".ts", ".jsx", ".tsx") if (service_root / "lib" / f"auth-client{suffix}").exists()),
            None,
        )
        if auth_client:
            content = auth_client.read_text(encoding="utf-8")
            if "process.env.BETTER_AUTH_URL" in content:
                updated = re.sub(
                    r"createAuthClient\(\s*\{[\s\S]*?baseURL\s*:\s*process\.env\.BETTER_AUTH_URL[\s\S]*?\}\s*\)",
                    "createAuthClient()",
                    content,
                    count=1,
                )
                if updated != content:
                    relative = auth_client.relative_to(staged_root).as_posix()
                    records.append(self._write(spec, staged_root, relative, updated, "source-patch"))
                    patches.append({"path": relative, "reason": "Same-origin authentication behind nginx", "change": "Use Better Auth same-origin client defaults"})

        if app_root.exists():
            reads_db = re.compile(
                r"@/lib/mongodb|getCollection|getSessionUser|ensureSeeded|\bgetDb\b"
            )
            declares = re.compile(r"export\s+const\s+dynamic\b")
            for candidate in sorted(app_root.rglob("*")):
                if candidate.name.split(".")[0] not in ("page", "layout"):
                    continue
                if candidate.suffix not in (".js", ".jsx", ".ts", ".tsx"):
                    continue
                try:
                    content = candidate.read_text(encoding="utf-8")
                except OSError:
                    continue
                if not reads_db.search(content) or declares.search(content):
                    continue

                lines = content.splitlines()
                insert_at = 0
                for index, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("'use ") or line.startswith('"use '):
                        insert_at = index + 1
                updated = "\n".join(
                    lines[:insert_at]
                    + ["", "export const dynamic = 'force-dynamic'"]
                    + lines[insert_at:]
                ) + "\n"
                relative = candidate.relative_to(staged_root).as_posix()
                records.append(self._write(spec, staged_root, relative, updated, "source-patch"))
                patches.append({
                    "path": relative,
                    "reason": "Reads the database at request time",
                    "change": "Add export const dynamic = 'force-dynamic' so it is not prerendered",
                })
        return records, patches

    @staticmethod
    def _build_environment(service: ServiceSpec) -> list[tuple[str, str]]:
        """Placeholders every build site must set, in one place.

        There are three of them — the CI workflow, the EC2 deploy workflow and
        the Dockerfile the ECS target builds from — and they were drifting for
        the same reason the runtime secret drifted: each spelled its own env
        block out by hand. Only `MONGODB_URI` was ever added to all three, so a
        better-auth app built with no secret and no base URL on every target.

        The runtime counterpart of this list is `_runtime_secret_entries`. Both
        exist so that the answer to "what does the app need to run" is written
        down once instead of rediscovered after a deployment fails.
        """
        env = [("MONGODB_URI", BUILD_PLACEHOLDER_MONGODB_URI)]
        if service.has_better_auth:
            env.append(("BETTER_AUTH_SECRET", BUILD_PLACEHOLDER_AUTH_SECRET))
            env.append(("BETTER_AUTH_URL", BUILD_PLACEHOLDER_AUTH_URL))
        return env

    @staticmethod
    def _build_env_yaml(service: ServiceSpec, indent: int) -> str:
        """The build placeholders as YAML `env:` entries, already indented."""
        pad = " " * indent
        return f"\n{pad}".join(
            f"{name}: {value}"
            for name, value in ArtifactGeneratorAgent._build_environment(service))

    @staticmethod
    def _build_env_docker(service: ServiceSpec, indent: int) -> str:
        """The same placeholders as Dockerfile `ENV` instructions."""
        pad = " " * indent
        return f"\n{pad}".join(
            f"ENV {name}={value}"
            for name, value in ArtifactGeneratorAgent._build_environment(service))

    @staticmethod
    def _build_services_yaml(indent: int) -> str:
        """A real MongoDB on 127.0.0.1:27017 for the duration of the build job.

        `next build` imports every page and route during its "Collecting page
        data" pass, so any module that touches the database at import — a
        top-level `await getDb()`, a `new MongoClient(uri).connect()`, a Better
        Auth instance built at module scope — opens a socket while the app is
        being COMPILED. `MONGODB_URI` already points at 127.0.0.1:27017, and on
        a GitHub runner nothing was listening there:

            Error: Failed to collect configuration for /api/auth/[...all]
              [cause]: MongoServerSelectionError: connect ECONNREFUSED

        The generated templates avoid connecting at import, but the model
        writes application code too and cannot be relied on never to. Making
        the placeholder true is the fix that does not depend on predicting
        what the app does: reproduced against a real failing deployment, the
        same tree builds with a database and fails without one.

        It is a throwaway database. Nothing reads it, and it is gone with the
        job — the running app gets its real URI from Secrets Manager.
        """
        pad = " " * indent
        lines = [
            "services:",
            "  mongodb:",
            "    image: mongo:7",
            "    ports:",
            "      - 27017:27017",
            "    options: >-",
            '      --health-cmd "mongosh --quiet --eval \'db.runCommand({ping:1})\'"',
            "      --health-interval 10s",
            "      --health-timeout 5s",
            "      --health-retries 10",
        ]
        return f"\n{pad}".join(lines)

    @staticmethod
    def _dockerfile(service: ServiceSpec) -> str:
        """The image, built in GitHub Actions and never on the user's machine.

        Three-stage so the runtime layer carries neither the toolchain nor the
        dev dependencies.

        The copy dance in the last stage is the part that matters. Next.js emits
        `.next/static` and `public/` OUTSIDE `.next/standalone`, and the
        standalone server expects to find them beside it. An image built from
        the standalone tree alone starts, answers 200, and serves an
        application with no CSS and no images — so nothing catches it. The EC2
        release path already documents this; the Dockerfile has to do exactly
        the same thing.
        """
        port = service.port or 3000
        install = service.install_command or "npm ci"
        build = service.build_command or "npm run build"
        build_env = ArtifactGeneratorAgent._build_env_docker(service, 12)
        return textwrap.dedent(
            f"""
            # syntax=docker/dockerfile:1
            # Written by the deployment agent. Built by GitHub Actions — there is
            # no need for Docker on the machine that generated this.

            FROM node:20-alpine AS deps
            WORKDIR /app
            COPY package.json package-lock.json* ./
            RUN {install}

            FROM node:20-alpine AS build
            WORKDIR /app
            COPY --from=deps /app/node_modules ./node_modules
            COPY . .
            # Parseable placeholders: the real values are injected at runtime
            # from Secrets Manager. Some pages construct a client at module
            # scope, and an unparseable URI fails the build rather than the
            # request — `lib/auth.js` calls betterAuth() the same way.
            {build_env}
            ENV NEXT_TELEMETRY_DISABLED=1
            RUN {build}
            # Both must exist before the runtime stage copies them. A generated
            # app usually has no `public/` at all — neither of the two on this
            # machine did — and an unconditional COPY of a missing directory
            # fails the build outright: "/app/public: not found". The EC2
            # release path guards the same copy with `if [ -d public ]`; a
            # Dockerfile has no conditionals, so the directory is created
            # instead. Empty is fine; absent is not.
            RUN test -f .next/standalone/server.js && mkdir -p public .next/static

            FROM node:20-alpine AS runtime
            WORKDIR /app
            ENV NODE_ENV=production
            ENV NEXT_TELEMETRY_DISABLED=1
            ENV PORT={port}
            ENV HOSTNAME=0.0.0.0

            # Not root. A container that is compromised should not also be
            # privileged inside its own filesystem.
            RUN addgroup --system --gid 1001 nodejs \\
             && adduser  --system --uid 1001 nextjs

            COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
            # These two are why this is not a single COPY: the standalone tree
            # does not contain them, and the server will not find them anywhere
            # else.
            COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
            COPY --from=build --chown=nextjs:nodejs /app/public ./public

            USER nextjs
            EXPOSE {port}
            CMD ["node", "server.js"]
            """
        ).lstrip()

    @staticmethod
    def _dockerignore() -> str:
        """Keep the build context small and secrets out of it entirely."""
        return textwrap.dedent(
            """
            # Written by the deployment agent.
            node_modules
            .next
            .git
            .github
            .agentforge
            coverage
            test-results
            playwright-report
            # Never into the build context: an image layer is readable by anyone
            # who can pull the image.
            .env
            .env.*
            !.env.example
            npm-debug.log*
            Dockerfile
            .dockerignore
            """
        ).lstrip()

    @staticmethod
    def _task_definition(service: ServiceSpec, plan: DeploymentPlan,
                         contract: EnvironmentContract | None = None) -> dict:
        """The Fargate task definition, rendered by the workflow at deploy time.

        Secrets go in `secrets:` with a `valueFrom` ARN, never in
        `environment:`. Anything in `environment:` is returned in plain text by
        `describe-task-definition`, which any read-only role can call.

        `image` is a placeholder the workflow substitutes with the freshly built
        tag — the deployed revision must name the commit it came from, or
        rollback has nothing to roll back to and readiness cannot tell whether
        the running service is the one this deployment produced.
        """
        port = service.port or 3000
        entries = ArtifactGeneratorAgent._runtime_secret_entries(contract)
        secrets = [
            {"name": entry.name, "valueFrom": f"__RUNTIME_SECRET_ARN__:{entry.name}::"}
            for entry in entries
        ]
        return {
            "family": f"{plan.project_slug}-task",
            "networkMode": "awsvpc",
            "requiresCompatibilities": ["FARGATE"],
            "cpu": "256",
            "memory": "512",
            "executionRoleArn": "__EXECUTION_ROLE_ARN__",
            "taskRoleArn": "__TASK_ROLE_ARN__",
            "containerDefinitions": [
                {
                    "name": f"{plan.project_slug}-app",
                    "image": "__IMAGE__",
                    "essential": True,
                    "portMappings": [{"containerPort": port, "protocol": "tcp"}],
                    "environment": [
                        {"name": "NODE_ENV", "value": "production"},
                        {"name": "PORT", "value": str(port)},
                        {"name": "HOSTNAME", "value": "0.0.0.0"},
                    ],
                    "secrets": secrets,
                    "logConfiguration": {
                        "logDriver": "awslogs",
                        "options": {
                            "awslogs-group": f"/deployment-agent/{plan.project_slug}",
                            "awslogs-region": "__AWS_REGION__",
                            "awslogs-stream-prefix": "app",
                        },
                    },
                }
            ],
        }

    @staticmethod
    def _release_script(service: ServiceSpec, contract: EnvironmentContract | None = None) -> str:
        """The script SSM Run Command executes on the instance for each release.

        It is fetched from S3 per deployment rather than baked into UserData, so
        changing it does not require replacing the instance.
        """
        contract = contract or EnvironmentContract([])
        secret_names = [entry.name for entry in ArtifactGeneratorAgent._runtime_secret_entries(contract)]

        allowed = json.dumps(secret_names)
        return textwrap.dedent(
            f"""
            #!/usr/bin/env bash
            # Deployment Agent release script. Runs on the EC2 instance via SSM.
            # Usage: BUCKET=... SHA=... SECRET_ID=... release.sh
            set -euo pipefail

            : "${{BUCKET:?BUCKET is required}}"
            : "${{SHA:?SHA is required}}"
            : "${{SECRET_ID:?SECRET_ID is required}}"

            APP_DIR=/opt/app
            RELEASES="$APP_DIR/releases"
            SHARED="$APP_DIR/shared"
            RELEASE="$RELEASES/$SHA"
            PORT={service.port}
            HEALTH_PATH={service.health_path}

            mkdir -p "$RELEASES" "$SHARED"

            echo "==> Downloading release $SHA"
            aws s3 cp "s3://$BUCKET/releases/$SHA/app.tar.gz" /tmp/"$SHA".tar.gz

            echo "==> Unpacking"
            rm -rf "$RELEASE"
            mkdir -p "$RELEASE"
            tar -xzf /tmp/"$SHA".tar.gz -C "$RELEASE"
            rm -f /tmp/"$SHA".tar.gz

            echo "==> Refreshing runtime environment"
            env_tmp=$(mktemp)
            chmod 0600 "$env_tmp"
            {{
              echo "NODE_ENV=production"
              echo "PORT=$PORT"
              echo "HOSTNAME=127.0.0.1"
              aws secretsmanager get-secret-value --secret-id "$SECRET_ID" \\
                --query SecretString --output text \\
                | jq -r --argjson allowed '{allowed}' \\
                    'to_entries[] | select(.key as $k | $allowed | index($k)) | "\\(.key)=\\(.value|@sh)"'
            }} > "$env_tmp"
            install -o root -g nextjs -m 0640 "$env_tmp" "$SHARED/.env"
            rm -f "$env_tmp"

            chown -R nextjs:nextjs "$RELEASE"
            ln -sfn "$RELEASE" "$APP_DIR/current.new"
            mv -Tf "$APP_DIR/current.new" "$APP_DIR/current"

            echo "==> Restarting service"
            systemctl restart nextjs

            echo "==> Waiting for health check"
            for attempt in $(seq 1 30); do
              if curl -fsS --max-time 5 "http://127.0.0.1:$PORT$HEALTH_PATH" >/dev/null 2>&1; then
                echo "Health check passed on attempt $attempt"
                # Keep the five most recent releases so rollback has somewhere to go.
                ls -1dt "$RELEASES"/*/ 2>/dev/null | tail -n +6 | xargs -r rm -rf
                echo "$SHA" > "$SHARED/current-sha"
                exit 0
              fi
              sleep 2
            done

            echo "Health check failed; dumping recent service logs" >&2
            journalctl -u nextjs -n 50 --no-pager >&2 || true
            exit 1
            """
        ).lstrip()

    @staticmethod
    def _env_example(service: ServiceSpec, contract: EnvironmentContract | None = None) -> str:
        lines = ["# Copy to .env for local use. Never commit real values."]
        contract = contract or EnvironmentContractResolver.discover(service)
        names: set[str] = set()
        for entry in contract.entries:
            if entry.name in names or entry.resolution == "provider_managed" or entry.development_only:
                continue
            names.add(entry.name)
            suffix = " # optional" if not entry.required else ""
            lines.append(f"{entry.name}={suffix}")
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _vercel_config(service: ServiceSpec) -> str:
        value = {
            "$schema": "https://openapi.vercel.sh/vercel.json",
            "framework": "nextjs",
            "installCommand": service.install_command,
            "buildCommand": service.build_command or "npm run build",
        }
        return json.dumps(value, indent=2) + "\n"

    @staticmethod
    def _vercel_deploy_workflow(service: ServiceSpec, spec: ProjectSpec, plan: DeploymentPlan) -> str:
        root = service.root or "."
        toolchain = ArtifactGeneratorAgent._toolchain(service)
        preinstall = toolchain["preinstall"]
        branch = spec.repository.branch or "main"
        trigger_branches = ", ".join(dict.fromkeys([branch, "main", "master"]))
        return textwrap.dedent(
            f"""
            name: Deploy to Vercel

            on:
              push:
                branches: [{trigger_branches}]
              workflow_dispatch:

            permissions:
              contents: read

            concurrency:
              group: production-{plan.project_slug}
              cancel-in-progress: false

            jobs:
              deploy:
                runs-on: ubuntu-latest
                defaults:
                  run:
                    working-directory: {root}
                env:
                  VERCEL_ORG_ID: ${{{{ vars.VERCEL_ORG_ID }}}}
                  VERCEL_PROJECT_ID: ${{{{ vars.VERCEL_PROJECT_ID }}}}
                  VERCEL_TOKEN: ${{{{ secrets.VERCEL_TOKEN }}}}
                steps:
                  - uses: actions/checkout@v4
            __SETUP_STEP__
                  - name: Install dependencies
                    run: |
                      {preinstall.rstrip() if preinstall else '# package manager is ready'}
                      {service.install_command}
                  - name: Install the Vercel CLI
                    run: npm install --global vercel@latest
                  - name: Pull the production environment
                    # Also supplies the production environment variables the
                    # Next.js build itself reads.
                    run: vercel pull --yes --environment=production --token="$VERCEL_TOKEN"
                  - name: Build
                    run: vercel build --prod --token="$VERCEL_TOKEN"
                  - id: deploy
                    name: Deploy prebuilt output
                    run: |
                      url="$(vercel deploy --prebuilt --prod --token="$VERCEL_TOKEN")"
                      echo "Deployed to $url"
                      echo "url=$url" >> "$GITHUB_OUTPUT"
                  - name: Smoke test
                    run: |
                      curl --fail --retry 12 --retry-delay 5 \\
                        "${{{{ steps.deploy.outputs.url }}}}{service.health_path}"
            """
        ).lstrip().replace("__SETUP_STEP__", toolchain["setup_step"])

    @staticmethod
    def _vercel_environment(contract: EnvironmentContract) -> dict:
        variables = []
        for entry in EnvironmentContractResolver.production_entries(contract):
            if entry.resolution in {"provider_managed", "optional"}:
                continue
            variables.append(
                {
                    "name": entry.name,
                    "targets": ["production", "preview"],
                    "type": "sensitive" if entry.secret else "plain",
                    "scope": entry.scope,
                    "resolution": entry.resolution,
                }
            )
        return {"variables": variables}

    @staticmethod
    def _toolchain(service: ServiceSpec) -> dict[str, str]:
        """Package-manager specific workflow fragments shared by both workflows."""
        lock_name = {
            "npm": "package-lock.json",
            "pnpm": "pnpm-lock.yaml",
            "yarn": "yarn.lock",
            "bun": "bun.lock",
        }.get(service.package_manager, "package-lock.json")
        dependency = f"{service.root}/{lock_name}" if service.root else lock_name
        preinstall = "corepack enable\n" if service.package_manager in {"pnpm", "yarn"} else ""
        if service.package_manager == "bun":
            setup_step = "      - uses: oven-sh/setup-bun@v2"
            audit_command = "bun audit"
        else:
            cache_options = ""
            if not (service.package_manager == "npm" and service.install_command == "npm install"):
                cache_options = (
                    f"          cache: {service.package_manager}\n"
                    f"          cache-dependency-path: {dependency}"
                )
            setup_step = (
                "      - uses: actions/setup-node@v4\n"
                "        with:\n"
                "          node-version: 20"
                + ("\n" + cache_options if cache_options else "")
            )
            audit_command = {
                "pnpm": "pnpm audit --prod --audit-level high",
                "yarn": "yarn audit --groups dependencies --level high",
            }.get(service.package_manager, "npm audit --omit=dev --audit-level=high")
        return {
            "dependency": dependency,
            "preinstall": preinstall,
            "setup_step": setup_step,
            "audit_command": audit_command,
        }

    @staticmethod
    def _ci_workflow(
        service: ServiceSpec,
        spec: ProjectSpec,
        target: DeploymentTarget = DeploymentTarget.AWS_EC2,
    ) -> str:
        root = service.root or "."
        toolchain = ArtifactGeneratorAgent._toolchain(service)
        dependency = toolchain["dependency"]
        preinstall = toolchain["preinstall"]
        setup_step = toolchain["setup_step"]
        audit_command = toolchain["audit_command"]
        install = service.install_command
        build_env = ArtifactGeneratorAgent._build_env_yaml(service, 22)
        build_services = ArtifactGeneratorAgent._build_services_yaml(16)
        paths = f"      - '{service.root}/**'\n" if service.root else "      - '**'\n"
        workflow = textwrap.dedent(
            f"""
            name: CI

            on:
              pull_request:
              push:
                branches: [{spec.repository.branch or 'main'}]
                paths:
            {paths.rstrip()}

            permissions:
              contents: read

            jobs:
              validate:
                runs-on: ubuntu-latest
                {build_services}
                defaults:
                  run:
                    working-directory: {root}
                steps:
                  - uses: actions/checkout@v4
            __SETUP_STEP__
                  - name: Install dependencies
                    run: |
                      {preinstall.rstrip() if preinstall else '# package manager is ready'}
                      {install}
                  - name: Build application
                    env:
                      {build_env}
                    run: {service.build_command or 'npm run build'}
                  - name: Dependency audit
                    if: ${{{{ always() && hashFiles('{dependency}') != '' }}}}
                    continue-on-error: true
                    run: {audit_command}
            __STANDALONE_CHECK__
            """
        ).lstrip()

        standalone_check = (
            "      - name: Verify standalone output\n        run: test -f .next/standalone/server.js\n"
            if target == DeploymentTarget.AWS_EC2
            else ""
        )
        workflow = workflow.replace("__STANDALONE_CHECK__\n", standalone_check)
        return workflow.replace("__SETUP_STEP__", setup_step)

    @staticmethod
    def _ecs_deploy_workflow(service: ServiceSpec, spec: ProjectSpec, plan: DeploymentPlan) -> str:
        """Build the image on a runner, push it to ECR, roll the ECS service.

        This workflow is the whole reason the target exists: `docker build`
        happens here, on GitHub's hardware, so nothing needs Docker installed
        locally. `required_tools` deliberately omits it.

        The image is tagged with `github.sha` and never `latest`. Two things
        depend on that and both break silently without it — rollback has no
        earlier revision to name, and the readiness check cannot tell whether
        the running service came from this commit or an older one.
        """
        root = service.root or "."
        build_services = ArtifactGeneratorAgent._build_services_yaml(16)
        branch = spec.repository.branch or "main"
        trigger_branches = ", ".join(dict.fromkeys([branch, "main", "master"]))
        return textwrap.dedent(
            f"""
            name: Deploy to AWS ECS

            on:
              push:
                branches: [{trigger_branches}]
              workflow_dispatch:

            permissions:
              contents: read
              id-token: write

            concurrency:
              group: production-{plan.project_slug}
              cancel-in-progress: false

            jobs:
              deploy:
                runs-on: ubuntu-latest
                {build_services}
                steps:
                  - uses: actions/checkout@v4
                  - uses: aws-actions/configure-aws-credentials@v4
                    with:
                      role-to-assume: ${{{{ vars.AWS_DEPLOY_ROLE_ARN }}}}
                      aws-region: ${{{{ vars.AWS_REGION }}}}
                  - id: ecr
                    uses: aws-actions/amazon-ecr-login@v2
                  - name: Build and push the image
                    # Tagged with the commit, never :latest. Rollback and the
                    # readiness commit-match both read this tag.
                    run: |
                      IMAGE="${{{{ vars.ECR_REPOSITORY_URI }}}}:${{{{ github.sha }}}}"
                      # --network=host so `next build` inside the image can
                      # reach the MongoDB service on the runner's loopback.
                      # Without it the build container has its own network
                      # namespace, 127.0.0.1:27017 answers nothing, and any
                      # module that touches the database at import fails the
                      # build — the same failure the service exists to prevent.
                      docker build --network=host -t "$IMAGE" {root}
                      docker push "$IMAGE"
                      echo "IMAGE=$IMAGE" >> "$GITHUB_ENV"
                  - name: Render the task definition
                    run: |
                      python3 - <<'PY'
                      import json, os
                      spec = json.load(open("deploy/task-definition.json"))
                      spec["executionRoleArn"] = os.environ["EXECUTION_ROLE_ARN"]
                      spec["taskRoleArn"] = os.environ["TASK_ROLE_ARN"]
                      container = spec["containerDefinitions"][0]
                      container["image"] = os.environ["IMAGE"]
                      for item in container.get("secrets", []):
                          item["valueFrom"] = item["valueFrom"].replace(
                              "__RUNTIME_SECRET_ARN__", os.environ["RUNTIME_SECRET_ID"])
                      container["logConfiguration"]["options"]["awslogs-region"] = \\
                          os.environ["AWS_REGION"]
                      json.dump(spec, open("task-definition.rendered.json", "w"), indent=2)
                      PY
                    env:
                      EXECUTION_ROLE_ARN: ${{{{ vars.ECS_EXECUTION_ROLE_ARN }}}}
                      TASK_ROLE_ARN: ${{{{ vars.ECS_TASK_ROLE_ARN }}}}
                      RUNTIME_SECRET_ID: ${{{{ vars.RUNTIME_SECRET_ID }}}}
                      AWS_REGION: ${{{{ vars.AWS_REGION }}}}
                  - id: register
                    name: Register the revision
                    run: |
                      ARN="$(aws ecs register-task-definition \\
                        --cli-input-json file://task-definition.rendered.json \\
                        --query 'taskDefinition.taskDefinitionArn' --output text)"
                      echo "Registered $ARN"
                      echo "arn=$ARN" >> "$GITHUB_OUTPUT"
                  - name: Roll the service
                    run: |
                      # --desired-count 1 as well as the new revision. The stack
                      # creates the service with ZERO tasks so CloudFormation
                      # never waits on a placeholder image that cannot pass a
                      # health check; this step is what actually starts the
                      # application, with an image that can answer.
                      aws ecs update-service \\
                        --cluster "${{{{ vars.ECS_CLUSTER }}}}" \\
                        --service "${{{{ vars.ECS_SERVICE }}}}" \\
                        --task-definition "${{{{ steps.register.outputs.arn }}}}" \\
                        --desired-count 1 \\
                        --no-cli-pager
                      # Waits for the new tasks to pass their target-group health
                      # check and the old ones to drain. Fails the workflow if
                      # the rollout stalls, rather than reporting a green deploy
                      # over a service still running the previous image.
                      aws ecs wait services-stable \\
                        --cluster "${{{{ vars.ECS_CLUSTER }}}}" \\
                        --services "${{{{ vars.ECS_SERVICE }}}}"
                  - name: Smoke test
                    run: |
                      URL="$(aws cloudformation describe-stacks \\
                        --stack-name "${{{{ vars.PROJECT_SLUG }}}}-bootstrap" \\
                        --query "Stacks[0].Outputs[?OutputKey=='ApplicationUrl'].OutputValue" \\
                        --output text)"
                      echo "Checking $URL"
                      curl --fail --retry 12 --retry-delay 5 "$URL{service.health_path or '/api/health'}"
            """
        ).lstrip()

    @staticmethod
    def _deploy_workflow(service: ServiceSpec, spec: ProjectSpec, plan: DeploymentPlan) -> str:
        root = service.root or "."
        toolchain = ArtifactGeneratorAgent._toolchain(service)
        preinstall = toolchain["preinstall"]

        branch = spec.repository.branch or "main"
        trigger_branches = ", ".join(dict.fromkeys([branch, "main", "master"]))
        build_env = ArtifactGeneratorAgent._build_env_yaml(service, 22)
        build_services = ArtifactGeneratorAgent._build_services_yaml(16)
        return textwrap.dedent(
            f"""
            name: Deploy to AWS EC2

            on:
              push:
                branches: [{trigger_branches}]
              workflow_dispatch:

            permissions:
              contents: read
              id-token: write

            concurrency:
              group: production-{plan.project_slug}
              cancel-in-progress: false

            jobs:
              deploy:
                runs-on: ubuntu-latest
                {build_services}
                defaults:
                  run:
                    working-directory: {root}
                steps:
                  - uses: actions/checkout@v4
            __SETUP_STEP__
                  - name: Install dependencies
                    run: |
                      {preinstall.rstrip() if preinstall else '# package manager is ready'}
                      {service.install_command}
                  - name: Build application
                    env:
                      {build_env}
                    run: {service.build_command or 'npm run build'}
                  - name: Package standalone release
                    run: |
                      test -f .next/standalone/server.js
                      # Next.js emits static assets and public/ outside the
                      # standalone tree; the runtime expects them alongside it.
                      mkdir -p .next/standalone/.next
                      cp -r .next/static .next/standalone/.next/static
                      if [ -d public ]; then cp -r public .next/standalone/public; fi
                      tar -czf /tmp/app.tar.gz -C .next/standalone .
                  - uses: aws-actions/configure-aws-credentials@v4
                    with:
                      role-to-assume: ${{{{ vars.AWS_DEPLOY_ROLE_ARN }}}}
                      aws-region: ${{{{ vars.AWS_REGION }}}}
                  - name: Upload release to S3
                    run: |
                      aws s3 cp /tmp/app.tar.gz \\
                        "s3://${{{{ vars.ARTIFACT_BUCKET }}}}/releases/${{{{ github.sha }}}}/app.tar.gz"
                      aws s3 cp deploy/release.sh \\
                        "s3://${{{{ vars.ARTIFACT_BUCKET }}}}/releases/${{{{ github.sha }}}}/release.sh"
                    working-directory: .
                  - name: Release via SSM
                    run: |
                      COMMAND_ID=$(aws ssm send-command \\
                        --instance-ids "${{{{ vars.INSTANCE_ID }}}}" \\
                        --document-name AWS-RunShellScript \\
                        --comment "Deploy ${{{{ github.sha }}}}" \\
                        --timeout-seconds 600 \\
                        --parameters commands='[
                          "set -euo pipefail",
                          "aws s3 cp s3://${{{{ vars.ARTIFACT_BUCKET }}}}/releases/${{{{ github.sha }}}}/release.sh /tmp/release-${{{{ github.sha }}}}.sh",
                          "chmod +x /tmp/release-${{{{ github.sha }}}}.sh",
                          "BUCKET=${{{{ vars.ARTIFACT_BUCKET }}}} SHA=${{{{ github.sha }}}} SECRET_ID=${{{{ vars.RUNTIME_SECRET_ID }}}} /tmp/release-${{{{ github.sha }}}}.sh"
                        ]' \\
                        --query Command.CommandId --output text)
                      echo "SSM command $COMMAND_ID dispatched"
                      # The invocation is not queryable the instant send-command
                      # returns, and the built-in waiter caps out well below the
                      # release timeout, so poll it directly.
                      STATUS=Pending
                      for _ in $(seq 1 60); do
                        sleep 5
                        STATUS=$(aws ssm get-command-invocation \\
                          --command-id "$COMMAND_ID" \\
                          --instance-id "${{{{ vars.INSTANCE_ID }}}}" \\
                          --query Status --output text 2>/dev/null || echo Pending)
                        case "$STATUS" in
                          Success|Failed|Cancelled|TimedOut) break ;;
                        esac
                      done
                      aws ssm get-command-invocation \\
                        --command-id "$COMMAND_ID" \\
                        --instance-id "${{{{ vars.INSTANCE_ID }}}}" \\
                        --query 'StandardOutputContent' --output text || true
                      if [ "$STATUS" != "Success" ]; then
                        echo "::error::Release finished with status $STATUS"
                        aws ssm get-command-invocation \\
                          --command-id "$COMMAND_ID" \\
                          --instance-id "${{{{ vars.INSTANCE_ID }}}}" \\
                          --query 'StandardErrorContent' --output text || true
                        exit 1
                      fi
                    working-directory: .
                  - name: Smoke test
                    run: |
                      BASE_URL=$(aws cloudformation describe-stacks \\
                        --stack-name "${{{{ vars.PROJECT_SLUG }}}}-bootstrap" \\
                        --query "Stacks[0].Outputs[?OutputKey=='ApplicationUrl'].OutputValue" \\
                        --output text)
                      curl --fail --retry 12 --retry-delay 10 "$BASE_URL{service.health_path}"
                    working-directory: .
            """
        ).lstrip().replace("__SETUP_STEP__", toolchain["setup_step"])

    @staticmethod
    def _ecs_bootstrap_template(service: ServiceSpec, plan: DeploymentPlan | None = None) -> str:
        """ECR, a Fargate service, and a load balancer in front of it.

        A separate template rather than a fork of the EC2 one. The only genuinely
        shared parts are the OIDC provider, the log group, the runtime secret and
        the network scaffolding; everything else — the instance, the Elastic IP,
        nginx, systemd, the S3 release bucket — has no ECS meaning.

        Two subnets, and that is not optional: an Application Load Balancer must
        span at least two availability zones. `_select_bootstrap_network` has
        always computed a `subnet_b` that nothing passed; this is the template
        that needs it.

        The load balancer is also what makes the URL stable. A Fargate task's
        public IP changes every time the task is replaced, which would rewrite
        `application_url`, break the health probe and invalidate BETTER_AUTH_URL
        on every single deployment.
        """
        port = service.port or 3000
        health = service.health_path or "/api/health"
        return textwrap.dedent(
            f"""
            AWSTemplateFormatVersion: '2010-09-09'
            Description: Deployment Agent bootstrap infrastructure for a Next.js application on ECS Fargate

            Parameters:
              ProjectSlug:
                Type: String
                AllowedPattern: '[a-z0-9-]+'
              GitHubSubjects:
                Type: CommaDelimitedList
                Description: Exact classic and immutable GitHub OIDC subjects for the authenticated repository and default branch
              AppPort:
                Type: Number
                Default: {port}
              ExistingOidcProviderArn:
                Type: String
                Default: ''
              ExistingVpcId:
                Type: String
                Default: ''
                Description: Optional existing VPC to reuse when the regional VPC quota is exhausted
              ExistingSubnetA:
                Type: String
                Default: ''
              ExistingSubnetB:
                Type: String
                Default: ''
                Description: A load balancer requires two availability zones

            Conditions:
              CreateOidcProvider: !Equals [!Ref ExistingOidcProviderArn, '']
              CreateNetwork: !Equals [!Ref ExistingVpcId, '']

            Resources:
              Vpc:
                Type: AWS::EC2::VPC
                Condition: CreateNetwork
                Properties:
                  CidrBlock: 10.42.0.0/16
                  EnableDnsHostnames: true
                  EnableDnsSupport: true
                  Tags: [{{Key: Name, Value: !Sub '${{ProjectSlug}}-vpc'}}]
              InternetGateway:
                Type: AWS::EC2::InternetGateway
                Condition: CreateNetwork
              GatewayAttachment:
                Type: AWS::EC2::VPCGatewayAttachment
                Condition: CreateNetwork
                Properties:
                  VpcId: !Ref Vpc
                  InternetGatewayId: !Ref InternetGateway
              PublicSubnetA:
                Type: AWS::EC2::Subnet
                Condition: CreateNetwork
                Properties:
                  VpcId: !Ref Vpc
                  CidrBlock: 10.42.0.0/24
                  AvailabilityZone: !Select [0, !GetAZs '']
                  MapPublicIpOnLaunch: true
              PublicSubnetB:
                Type: AWS::EC2::Subnet
                Condition: CreateNetwork
                Properties:
                  VpcId: !Ref Vpc
                  CidrBlock: 10.42.1.0/24
                  AvailabilityZone: !Select [1, !GetAZs '']
                  MapPublicIpOnLaunch: true
              PublicRouteTable:
                Type: AWS::EC2::RouteTable
                Condition: CreateNetwork
                Properties:
                  VpcId: !Ref Vpc
              PublicRoute:
                Type: AWS::EC2::Route
                Condition: CreateNetwork
                DependsOn: GatewayAttachment
                Properties:
                  RouteTableId: !Ref PublicRouteTable
                  DestinationCidrBlock: 0.0.0.0/0
                  GatewayId: !Ref InternetGateway
              SubnetARouteAssociation:
                Type: AWS::EC2::SubnetRouteTableAssociation
                Condition: CreateNetwork
                Properties:
                  SubnetId: !Ref PublicSubnetA
                  RouteTableId: !Ref PublicRouteTable
              SubnetBRouteAssociation:
                Type: AWS::EC2::SubnetRouteTableAssociation
                Condition: CreateNetwork
                Properties:
                  SubnetId: !Ref PublicSubnetB
                  RouteTableId: !Ref PublicRouteTable

              # Only the load balancer faces the internet.
              LoadBalancerSecurityGroup:
                Type: AWS::EC2::SecurityGroup
                Properties:
                  GroupDescription: !Sub 'Public ingress for ${{ProjectSlug}}'
                  VpcId: !If [CreateNetwork, !Ref Vpc, !Ref ExistingVpcId]
                  SecurityGroupIngress:
                    - IpProtocol: tcp
                      FromPort: 80
                      ToPort: 80
                      CidrIp: 0.0.0.0/0
              # The task accepts traffic from the load balancer and from nothing
              # else. An open task security group would make the ALB decorative.
              TaskSecurityGroup:
                Type: AWS::EC2::SecurityGroup
                Properties:
                  GroupDescription: !Sub 'Task ingress for ${{ProjectSlug}}, load balancer only'
                  VpcId: !If [CreateNetwork, !Ref Vpc, !Ref ExistingVpcId]
                  SecurityGroupIngress:
                    - IpProtocol: tcp
                      FromPort: !Ref AppPort
                      ToPort: !Ref AppPort
                      SourceSecurityGroupId: !Ref LoadBalancerSecurityGroup

              EcrRepository:
                Type: AWS::ECR::Repository
                Properties:
                  RepositoryName: !Ref ProjectSlug
                  ImageScanningConfiguration: {{ScanOnPush: true}}
                  ImageTagMutability: IMMUTABLE
                  LifecyclePolicy:
                    LifecyclePolicyText: |
                      {{"rules":[{{"rulePriority":1,"description":"Keep the 10 most recent images",
                        "selection":{{"tagStatus":"any","countType":"imageCountMoreThan","countNumber":10}},
                        "action":{{"type":"expire"}}}}]}}

              LogGroup:
                Type: AWS::Logs::LogGroup
                Properties:
                  LogGroupName: !Sub '/deployment-agent/${{ProjectSlug}}'
                  RetentionInDays: 14

              RuntimeSecret:
                Type: AWS::SecretsManager::Secret
                Properties:
                  Name: !Sub '${{ProjectSlug}}/runtime'
                  Description: Runtime configuration injected into the task

              # Pulls the image and resolves the task definition's `secrets`.
              # It is the EXECUTION role, not the task role, that reads them.
              TaskExecutionRole:
                Type: AWS::IAM::Role
                Properties:
                  AssumeRolePolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Principal: {{Service: ecs-tasks.amazonaws.com}}
                        Action: sts:AssumeRole
                  ManagedPolicyArns:
                    - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
                  Policies:
                    - PolicyName: read-runtime-secret
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: [secretsmanager:GetSecretValue]
                            Resource: !Ref RuntimeSecret
              # The application's own identity. Deliberately empty: this is what
              # a compromised container gets.
              TaskRole:
                Type: AWS::IAM::Role
                Properties:
                  AssumeRolePolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Principal: {{Service: ecs-tasks.amazonaws.com}}
                        Action: sts:AssumeRole

              Cluster:
                Type: AWS::ECS::Cluster
                Properties:
                  ClusterName: !Ref ProjectSlug

              TaskDefinition:
                Type: AWS::ECS::TaskDefinition
                Properties:
                  Family: !Sub '${{ProjectSlug}}-task'
                  Cpu: '256'
                  Memory: '512'
                  NetworkMode: awsvpc
                  RequiresCompatibilities: [FARGATE]
                  ExecutionRoleArn: !GetAtt TaskExecutionRole.Arn
                  TaskRoleArn: !GetAtt TaskRole.Arn
                  ContainerDefinitions:
                    # A placeholder image so the stack can create before any
                    # build exists. The workflow registers a new revision with
                    # the real image on the first deployment.
                    - Name: !Sub '${{ProjectSlug}}-app'
                      Image: public.ecr.aws/docker/library/busybox:latest
                      Essential: true
                      Command: ['sh', '-c', 'sleep 3600']
                      PortMappings: [{{ContainerPort: !Ref AppPort, Protocol: tcp}}]
                      LogConfiguration:
                        LogDriver: awslogs
                        Options:
                          awslogs-group: !Ref LogGroup
                          awslogs-region: !Ref 'AWS::Region'
                          awslogs-stream-prefix: app

              LoadBalancer:
                Type: AWS::ElasticLoadBalancingV2::LoadBalancer
                Properties:
                  # No explicit Name, deliberately. Elastic Load Balancing caps
                  # these at 32 characters, and a project slug is already up to
                  # 31 — `a-neighbourhood-plant-nurser-16-tg` is 35 and failed
                  # the stack outright. CloudFormation generates a name from the
                  # stack and logical id that always fits.
                  Scheme: internet-facing
                  Type: application
                  SecurityGroups: [!Ref LoadBalancerSecurityGroup]
                  Subnets:
                    - !If [CreateNetwork, !Ref PublicSubnetA, !Ref ExistingSubnetA]
                    - !If [CreateNetwork, !Ref PublicSubnetB, !Ref ExistingSubnetB]
              TargetGroup:
                Type: AWS::ElasticLoadBalancingV2::TargetGroup
                Properties:
                  # Unnamed for the same reason as the load balancer above.
                  Port: !Ref AppPort
                  Protocol: HTTP
                  TargetType: ip
                  VpcId: !If [CreateNetwork, !Ref Vpc, !Ref ExistingVpcId]
                  HealthCheckPath: {health}
                  HealthCheckIntervalSeconds: 30
                  HealthyThresholdCount: 2
                  UnhealthyThresholdCount: 5
                  Matcher: {{HttpCode: '200-399'}}
                  TargetGroupAttributes:
                    - {{Key: deregistration_delay.timeout_seconds, Value: '15'}}
              Listener:
                Type: AWS::ElasticLoadBalancingV2::Listener
                Properties:
                  LoadBalancerArn: !Ref LoadBalancer
                  Port: 80
                  Protocol: HTTP
                  DefaultActions:
                    - Type: forward
                      TargetGroupArn: !Ref TargetGroup

              Service:
                Type: AWS::ECS::Service
                DependsOn: Listener
                Properties:
                  ServiceName: !Sub '${{ProjectSlug}}-service'
                  Cluster: !Ref Cluster
                  LaunchType: FARGATE
                  # Zero, and the workflow scales it to one.
                  #
                  # CloudFormation waits for a load-balanced service to
                  # stabilise, and the placeholder image below can never pass a
                  # health check on the application's own health path — it is
                  # busybox, it serves nothing. Measured on a real account: ECS
                  # killed and replaced the task on a loop ("replaced 1 tasks
                  # due to an unhealthy status") while the stack sat in
                  # CREATE_IN_PROGRESS and the load balancer billed by the hour.
                  #
                  # With no desired tasks the service creates immediately, and
                  # the first real rollout is the one that starts a container.
                  DesiredCount: 0
                  TaskDefinition: !Ref TaskDefinition
                  # The workflow registers new revisions; CloudFormation must not
                  # drag the service back to the placeholder on the next update.
                  DeploymentController: {{Type: ECS}}
                  NetworkConfiguration:
                    AwsvpcConfiguration:
                      AssignPublicIp: ENABLED
                      SecurityGroups: [!Ref TaskSecurityGroup]
                      Subnets:
                        - !If [CreateNetwork, !Ref PublicSubnetA, !Ref ExistingSubnetA]
                        - !If [CreateNetwork, !Ref PublicSubnetB, !Ref ExistingSubnetB]
                  LoadBalancers:
                    - ContainerName: !Sub '${{ProjectSlug}}-app'
                      ContainerPort: !Ref AppPort
                      TargetGroupArn: !Ref TargetGroup

              GitHubOidcProvider:
                Type: AWS::IAM::OIDCProvider
                Condition: CreateOidcProvider
                Properties:
                  Url: https://token.actions.githubusercontent.com
                  ClientIdList: [sts.amazonaws.com]
                  ThumbprintList: [6938fd4d98bab03faadb97b34396831e3780aea1]

              GitHubDeployRole:
                Type: AWS::IAM::Role
                Properties:
                  RoleName: !Sub '${{ProjectSlug}}-github-deploy'
                  AssumeRolePolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Principal:
                          Federated: !If
                            - CreateOidcProvider
                            - !Ref GitHubOidcProvider
                            - !Ref ExistingOidcProviderArn
                        Action: sts:AssumeRoleWithWebIdentity
                        Condition:
                          StringEquals:
                            token.actions.githubusercontent.com:aud: sts.amazonaws.com
                            token.actions.githubusercontent.com:sub: !Ref GitHubSubjects
                  Policies:
                    - PolicyName: ecs-deploy
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          # Accepts no resource ARN.
                          - Effect: Allow
                            Action: [ecr:GetAuthorizationToken]
                            Resource: '*'
                          - Effect: Allow
                            Action:
                              - ecr:BatchCheckLayerAvailability
                              - ecr:InitiateLayerUpload
                              - ecr:UploadLayerPart
                              - ecr:CompleteLayerUpload
                              - ecr:PutImage
                              - ecr:BatchGetImage
                              - ecr:GetDownloadUrlForLayer
                              - ecr:DescribeImages
                            Resource: !GetAtt EcrRepository.Arn
                          - Effect: Allow
                            Action: [ecs:RegisterTaskDefinition, ecs:DescribeTaskDefinition]
                            Resource: '*'
                          - Effect: Allow
                            Action: [ecs:UpdateService, ecs:DescribeServices]
                            Resource: !Ref Service
                          - Effect: Allow
                            Action: [ecs:ListTasks, ecs:DescribeTasks]
                            Resource: '*'
                            Condition:
                              ArnEquals:
                                ecs:cluster: !GetAtt Cluster.Arn
                          # Scoped, and conditioned on the service it may be
                          # passed to. An unconditional iam:PassRole here would
                          # let anyone who can run this workflow assume any role
                          # in the account.
                          - Effect: Allow
                            Action: [iam:PassRole]
                            Resource:
                              - !GetAtt TaskExecutionRole.Arn
                              - !GetAtt TaskRole.Arn
                            Condition:
                              StringEquals:
                                iam:PassedToService: ecs-tasks.amazonaws.com
                          - Effect: Allow
                            Action: [cloudformation:DescribeStacks]
                            Resource: !Sub 'arn:aws:cloudformation:${{AWS::Region}}:${{AWS::AccountId}}:stack/${{ProjectSlug}}-bootstrap/*'

            Outputs:
              ApplicationUrl:
                Value: !Sub 'http://${{LoadBalancer.DNSName}}'
              EcrRepositoryUri:
                Value: !GetAtt EcrRepository.RepositoryUri
              ClusterName:
                Value: !Ref Cluster
              ServiceName:
                Value: !GetAtt Service.Name
              TaskFamily:
                Value: !Sub '${{ProjectSlug}}-task'
              ContainerName:
                Value: !Sub '${{ProjectSlug}}-app'
              ExecutionRoleArn:
                Value: !GetAtt TaskExecutionRole.Arn
              TaskRoleArn:
                Value: !GetAtt TaskRole.Arn
              DeployRoleArn:
                Value: !GetAtt GitHubDeployRole.Arn
              RuntimeSecretArn:
                Value: !Ref RuntimeSecret
              LogGroupName:
                Value: !Ref LogGroup
              LoadBalancerDns:
                Value: !GetAtt LoadBalancer.DNSName
            """
        ).lstrip()

    @staticmethod
    def _bootstrap_template(service: ServiceSpec, plan: DeploymentPlan | None = None) -> str:
        sizing = (plan.aws_sizing if plan else None) or {}
        instance_type = str(sizing.get("instance_type", "t3.micro"))
        template = textwrap.dedent(
            """
            AWSTemplateFormatVersion: '2010-09-09'
            Description: Deployment Agent bootstrap infrastructure for a Next.js application on a single EC2 instance

            Parameters:
              ProjectSlug:
                Type: String
                AllowedPattern: '[a-z0-9-]+'
              GitHubSubjects:
                Type: CommaDelimitedList
                Description: Exact classic and immutable GitHub OIDC subjects for the authenticated repository and default branch
              AppPort:
                Type: Number
                Default: 3000
              InstanceType:
                Type: String
                Default: __INSTANCE_TYPE__
                AllowedValues: [t3.micro, t3.small, t3.medium, t4g.micro, t4g.small]
              LatestAmiId:
                Type: 'AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>'
                Default: /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64
              ExistingOidcProviderArn:
                Type: String
                Default: ''
              ExistingVpcId:
                Type: String
                Default: ''
                Description: Optional existing VPC to reuse when the regional VPC quota is exhausted
              ExistingSubnetA:
                Type: String
                Default: ''

            Conditions:
              CreateOidcProvider: !Equals [!Ref ExistingOidcProviderArn, '']
              CreateNetwork: !Equals [!Ref ExistingVpcId, '']

            Resources:
              Vpc:
                Type: AWS::EC2::VPC
                Condition: CreateNetwork
                Properties:
                  CidrBlock: 10.42.0.0/16
                  EnableDnsHostnames: true
                  EnableDnsSupport: true
                  Tags: [{Key: Name, Value: !Sub '${ProjectSlug}-vpc'}]
              InternetGateway:
                Type: AWS::EC2::InternetGateway
                Condition: CreateNetwork
              GatewayAttachment:
                Type: AWS::EC2::VPCGatewayAttachment
                Condition: CreateNetwork
                Properties: {VpcId: !Ref Vpc, InternetGatewayId: !Ref InternetGateway}
              PublicSubnetA:
                Type: AWS::EC2::Subnet
                Condition: CreateNetwork
                Properties:
                  VpcId: !Ref Vpc
                  CidrBlock: 10.42.0.0/24
                  AvailabilityZone: !Select [0, !GetAZs '']
                  MapPublicIpOnLaunch: true
                  Tags: [{Key: Name, Value: !Sub '${ProjectSlug}-public-a'}]
              PublicRouteTable:
                Type: AWS::EC2::RouteTable
                Condition: CreateNetwork
                Properties: {VpcId: !Ref Vpc}
              DefaultRoute:
                Type: AWS::EC2::Route
                Condition: CreateNetwork
                DependsOn: GatewayAttachment
                Properties:
                  RouteTableId: !Ref PublicRouteTable
                  DestinationCidrBlock: 0.0.0.0/0
                  GatewayId: !Ref InternetGateway
              SubnetARouteAssociation:
                Type: AWS::EC2::SubnetRouteTableAssociation
                Condition: CreateNetwork
                Properties: {SubnetId: !Ref PublicSubnetA, RouteTableId: !Ref PublicRouteTable}
              InstanceSecurityGroup:
                Type: AWS::EC2::SecurityGroup
                Properties:
                  GroupDescription: Public HTTP access to the nginx reverse proxy
                  VpcId: !If [CreateNetwork, !Ref Vpc, !Ref ExistingVpcId]
                  SecurityGroupIngress:
                    - {IpProtocol: tcp, FromPort: 80, ToPort: 80, CidrIp: 0.0.0.0/0, Description: Public HTTP}
                  Tags: [{Key: Name, Value: !Sub '${ProjectSlug}-instance'}]
              ArtifactBucket:
                Type: AWS::S3::Bucket
                Properties:
                  BucketName: !Sub '${ProjectSlug}-artifacts-${AWS::AccountId}-${AWS::Region}'
                  BucketEncryption:
                    ServerSideEncryptionConfiguration:
                      - ServerSideEncryptionByDefault: {SSEAlgorithm: AES256}
                  PublicAccessBlockConfiguration:
                    BlockPublicAcls: true
                    BlockPublicPolicy: true
                    IgnorePublicAcls: true
                    RestrictPublicBuckets: true
                  VersioningConfiguration: {Status: Enabled}
                  LifecycleConfiguration:
                    Rules:
                      - Id: ExpireOldReleases
                        Status: Enabled
                        Prefix: releases/
                        ExpirationInDays: 30
                        NoncurrentVersionExpirationInDays: 7
              LogGroup:
                Type: AWS::Logs::LogGroup
                Properties:
                  LogGroupName: !Sub '/deployment-agent/${ProjectSlug}'
                  RetentionInDays: 30
              RuntimeSecret:
                Type: AWS::SecretsManager::Secret
                Properties:
                  Name: !Sub '/deployment-agent/${ProjectSlug}/runtime'
                  GenerateSecretString:
                    SecretStringTemplate: '{}'
                    GenerateStringKey: INITIAL_PLACEHOLDER
                    PasswordLength: 32
              InstanceRole:
                Type: AWS::IAM::Role
                Properties:
                  RoleName: !Sub '${ProjectSlug}-instance'
                  AssumeRolePolicyDocument:
                    Version: '2012-10-17'
                    Statement: [{Effect: Allow, Principal: {Service: ec2.amazonaws.com}, Action: 'sts:AssumeRole'}]
                  ManagedPolicyArns:
                    - arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore
                  Policies:
                    - PolicyName: RuntimeAccess
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: ['s3:GetObject']
                            Resource: !Sub '${ArtifactBucket.Arn}/releases/*'
                          - Effect: Allow
                            Action: ['secretsmanager:GetSecretValue']
                            Resource: !Ref RuntimeSecret
                          - Effect: Allow
                            Action: ['logs:CreateLogStream', 'logs:PutLogEvents', 'logs:DescribeLogStreams']
                            Resource: !Sub '${LogGroup.Arn}:*'
              InstanceProfile:
                Type: AWS::IAM::InstanceProfile
                Properties:
                  Roles: [!Ref InstanceRole]
              AppInstance:
                Type: AWS::EC2::Instance
                Properties:
                  ImageId: !Ref LatestAmiId
                  InstanceType: !Ref InstanceType
                  IamInstanceProfile: !Ref InstanceProfile
                  SubnetId: !If [CreateNetwork, !Ref PublicSubnetA, !Ref ExistingSubnetA]
                  SecurityGroupIds: [!Ref InstanceSecurityGroup]
                  Tags:
                    - {Key: Name, Value: !Sub '${ProjectSlug}-app'}
                    - {Key: DeploymentAgentProject, Value: !Ref ProjectSlug}
                  BlockDeviceMappings:
                    - DeviceName: /dev/xvda
                      Ebs: {VolumeSize: 20, VolumeType: gp3, Encrypted: true, DeleteOnTermination: true}
                  UserData:
                    Fn::Base64: !Sub |
                      #!/bin/bash
                      set -euxo pipefail

                      dnf install -y nginx jq
                      curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
                      dnf install -y nodejs

                      id -u nextjs >/dev/null 2>&1 || useradd --system --create-home --shell /sbin/nologin nextjs
                      mkdir -p /opt/app/releases /opt/app/shared
                      chown -R nextjs:nextjs /opt/app

                      # Placeholder until the first release lands.
                      printf 'NODE_ENV=production\\nPORT=${AppPort}\\nHOSTNAME=127.0.0.1\\n' > /opt/app/shared/.env
                      chown root:nextjs /opt/app/shared/.env
                      chmod 0640 /opt/app/shared/.env

                      cat > /etc/systemd/system/nextjs.service <<'UNIT'
                      [Unit]
                      Description=Next.js application
                      After=network-online.target
                      Wants=network-online.target

                      [Service]
                      Type=simple
                      User=nextjs
                      Group=nextjs
                      WorkingDirectory=/opt/app/current
                      EnvironmentFile=/opt/app/shared/.env
                      ExecStart=/usr/bin/node /opt/app/current/server.js
                      Restart=always
                      RestartSec=5
                      NoNewPrivileges=true
                      PrivateTmp=true
                      ProtectSystem=strict
                      ProtectHome=true
                      ReadWritePaths=/opt/app
                      StandardOutput=journal
                      StandardError=journal

                      [Install]
                      WantedBy=multi-user.target
                      UNIT

                      cat > /etc/nginx/conf.d/app.conf <<'NGINX'
                      server {
                        listen 80 default_server;
                        server_name _;
                        client_max_body_size 10m;

                        location / {
                          proxy_pass http://127.0.0.1:${AppPort};
                          proxy_http_version 1.1;
                          proxy_set_header Upgrade $http_upgrade;
                          proxy_set_header Connection 'upgrade';
                          proxy_set_header Host $host;
                          proxy_set_header X-Real-IP $remote_addr;
                          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                          proxy_set_header X-Forwarded-Proto $scheme;
                          proxy_cache_bypass $http_upgrade;
                          proxy_read_timeout 60s;
                        }
                      }
                      NGINX
                      rm -f /etc/nginx/conf.d/default.conf

                      systemctl daemon-reload
                      systemctl enable --now nginx
                      # nextjs is enabled but only starts once /opt/app/current exists.
                      systemctl enable nextjs
              ElasticIp:
                Type: AWS::EC2::EIP
                Properties:
                  Domain: vpc
                  Tags: [{Key: Name, Value: !Sub '${ProjectSlug}-eip'}]
              ElasticIpAssociation:
                Type: AWS::EC2::EIPAssociation
                Properties:
                  AllocationId: !GetAtt ElasticIp.AllocationId
                  InstanceId: !Ref AppInstance
              GitHubOidcProvider:
                Type: AWS::IAM::OIDCProvider
                Condition: CreateOidcProvider
                Properties:
                  Url: https://token.actions.githubusercontent.com
                  ClientIdList: [sts.amazonaws.com]
              GitHubDeployRole:
                Type: AWS::IAM::Role
                Properties:
                  RoleName: !Sub '${ProjectSlug}-github-deploy'
                  AssumeRolePolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Principal:
                          Federated: !If [CreateOidcProvider, !Ref GitHubOidcProvider, !Ref ExistingOidcProviderArn]
                        Action: 'sts:AssumeRoleWithWebIdentity'
                        Condition:
                          StringEquals:
                            'token.actions.githubusercontent.com:aud': sts.amazonaws.com
                            'token.actions.githubusercontent.com:sub': !Ref GitHubSubjects
                  Policies:
                    - PolicyName: ProjectDeployment
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: ['s3:PutObject', 's3:GetObject', 's3:AbortMultipartUpload']
                            Resource: !Sub '${ArtifactBucket.Arn}/releases/*'
                          - Effect: Allow
                            Action: ['s3:ListBucket']
                            Resource: !GetAtt ArtifactBucket.Arn
                          - Effect: Allow
                            Action: ['ssm:SendCommand']
                            Resource:
                              - !Sub 'arn:${AWS::Partition}:ssm:${AWS::Region}::document/AWS-RunShellScript'
                              - !Sub 'arn:${AWS::Partition}:ec2:${AWS::Region}:${AWS::AccountId}:instance/${AppInstance}'
                          - Effect: Allow
                            Action: ['ssm:GetCommandInvocation', 'ssm:ListCommandInvocations', 'ssm:ListCommands']
                            Resource: '*'
                          - Effect: Allow
                            Action: ['cloudformation:DescribeStacks']
                            Resource: !Sub 'arn:${AWS::Partition}:cloudformation:${AWS::Region}:${AWS::AccountId}:stack/${ProjectSlug}-*/*'
                          - Effect: Allow
                            Action: ['ec2:DescribeInstances', 'ec2:DescribeInstanceStatus']
                            Resource: '*'

            Outputs:
              ApplicationUrl:
                Value: !Sub 'http://${ElasticIp}'
              ArtifactBucket: {Value: !Ref ArtifactBucket}
              InstanceId: {Value: !Ref AppInstance}
              PublicIp: {Value: !Ref ElasticIp}
              DeployRoleArn: {Value: !GetAtt GitHubDeployRole.Arn}
              RuntimeSecretArn: {Value: !Ref RuntimeSecret}
              LogGroupName: {Value: !Ref LogGroup}
              InstanceSecurityGroup: {Value: !Ref InstanceSecurityGroup}
            """
        ).lstrip()
        return template.replace("__INSTANCE_TYPE__", instance_type)

    @staticmethod
    def _runtime_secret_entries(contract: EnvironmentContract) -> list[EnvironmentEntry]:
        """Every key the runtime secret carries — contract-declared or injected.

        Both delivery mechanisms are built from this one list: the jq allow-list
        in the EC2 release script, and the `secrets:` block of the Fargate task
        definition. Anything missing here is stored in Secrets Manager and then
        silently discarded on the way to the process, which is exactly how
        BETTER_AUTH_URL was lost. Keeping the injected names in the same list is
        what stops the two ends drifting apart again.
        """
        entries = [
            entry for entry in EnvironmentContractResolver.production_entries(contract)
            if entry.secret and entry.scope in {"runtime", "both"}
        ]
        declared = {entry.name for entry in entries}
        entries.extend(
            EnvironmentEntry(
                name=name, required=False, secret=True, scope="runtime",
                resolution="provider_managed", value_present=True,
                sources=["deployer:stack-outputs"],
            )
            for name in DEPLOYER_INJECTED if name not in declared
        )
        return entries

    @staticmethod
    def _parameters_example(spec: ProjectSpec, plan: DeploymentPlan, service: ServiceSpec) -> dict:
        return {
            "ProjectSlug": plan.project_slug,
            "GitHubSubjects": [
                f"repo:owner/repository:ref:refs/heads/{spec.repository.branch or 'main'}",
                f"repo:owner@OWNER_ID/repository@REPOSITORY_ID:ref:refs/heads/{spec.repository.branch or 'main'}",
            ],
            "AppPort": service.port,
            "InstanceType": str((plan.aws_sizing or {}).get("instance_type", "t3.micro")),
            "ExistingOidcProviderArn": "",
        }

    @staticmethod
    def _initial_readiness(
        records: list[ArtifactRecord], target: DeploymentTarget = DeploymentTarget.AWS_EC2
    ) -> dict:
        kinds = {record.kind for record in records}
        profile = profile_for(target)
        categories = {
            "build": 0,
            "cicd": 20 if "cicd" in kinds else 0,
            "provider": 25 if profile.artifact_kind in kinds else 0,
            "security": 0,
            "monitoring": 0,
            "api": 0,
        }
        return {"score": sum(categories.values()), "categories": categories, "phase": "review"}

    def finalize_review(
        self,
        spec: ProjectSpec,
        plan: DeploymentPlan,
        staged_root: Path,
        readiness: dict,
        records: list[ArtifactRecord],
    ) -> list[ArtifactRecord]:
        """Synchronize user-visible review files after validation has finished."""
        replacements = {
            "deployment-report.md": self._report(spec, plan, readiness, DeploymentTarget(plan.target)),
            "readiness-score.json": json.dumps(readiness, indent=2) + "\n",
        }
        by_path = {record.path: index for index, record in enumerate(records)}
        for relative, content in replacements.items():
            updated = self._write(spec, staged_root, relative, content, "report")
            if relative in by_path:
                records[by_path[relative]] = updated
            else:
                records.append(updated)
        return records

    @staticmethod
    def _report(
        spec: ProjectSpec,
        plan: DeploymentPlan,
        readiness: dict,
        target: DeploymentTarget = DeploymentTarget.AWS_EC2,
    ) -> str:
        service = spec.services[0]
        env_names = ", ".join(item.name for item in service.environment) or "None detected"
        risks = "\n".join(f"- {item}" for item in plan.risks) or "- No model risks reported."
        recommendations = "\n".join(f"- {item}" for item in plan.recommendations) or "- Use the generated review checks."
        if target == DeploymentTarget.AWS_EC2:
            database_note = "MongoDB Atlas URI written directly to AWS Secrets Manager"
            security_notes = (
                "- No cloud access keys or provider tokens are written to GitHub; "
                "Actions authenticates through OIDC.\n"
                "- Provider credentials are kept only in the in-memory credential vault.\n"
                "- The instance security group exposes port 80 only; the Next.js process listens on loopback."
            )
        else:
            database_note = "MongoDB Atlas URI set as a Vercel production environment variable"
            security_notes = (
                "- The MongoDB URI is written to Vercel, not to GitHub.\n"
                "- **A Vercel deploy token is stored in this repository's GitHub Actions secrets.** "
                "Vercel has no OIDC equivalent for deploying, so unlike the AWS target this is a "
                "long-lived credential: anyone who can push a workflow to this repository can use it. "
                "Scope it to a team and rotate it if the repository changes hands.\n"
                "- The token is passed to GitHub over stdin and is never written to disk by the agent."
            )
        return textwrap.dedent(
            f"""
            # Deployment Readiness Report

            - Project: `{spec.name}`
            - Primary service: `{service.name}`
            - Detected root: `{service.root or '.'}`
            - Framework: Next.js `{service.version}`
            - Target: {f"AWS EC2 ({(plan.aws_sizing or {}).get('instance_type', 't3.micro')}) behind nginx, released from S3 via SSM" if target == DeploymentTarget.AWS_EC2 else "Vercel production deployment"}
            - Database: {database_note}
            - Readiness: **{readiness['score']}/100** (review phase)
            - Required environment variables: {env_names}

            ## Risks

            {risks}

            ## Recommendations

            {recommendations}

            ## Security invariants

            - Runtime secret values are never included in this report or generated artifacts.
            {security_notes}
            """
        ).lstrip()
