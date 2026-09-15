from __future__ import annotations

import json
import re
import shutil
from pathlib import Path, PurePosixPath
from typing import Callable

from deployment_agent.config import GIT_TIMEOUT_SECONDS, SKIP_DIRS, SOURCE_EXTENSIONS
from deployment_agent.models import EnvironmentVariable, ProjectSpec, RepositorySpec, ServiceSpec
from deployment_agent.security import is_secret_name
from deployment_agent.tools import command_exists, run_command


ENV_RE = re.compile(r"process\.env(?:\.([A-Z][A-Z0-9_]+)|\[['\"]([A-Z][A-Z0-9_]+)['\"]\])")
# process.env handed in under another name, as in `loadConfig(env = process.env)`.
# Never `import.meta.env.NAME`, which belongs to the browser bundle.
ALIASED_ENV_RE = re.compile(r"(?<![\w.$])env\.([A-Z][A-Z0-9_]+)")
# `env.PORT ?? 4000` brings its own value, so the platform need not supply one.
FALLBACK_RE = re.compile(r"\s*(?:\?\?|\|\|)")
NODE_ENTRY_RE = re.compile(r"^\s*node\s+(?:-\S+\s+)*(\S+\.[cm]?js)\s*$")
WORKSPACE_FLAG_RE = re.compile(r"(?:--workspace(?:=|\s+)|-w\s+)(\S+)")
ROUTE_RE = re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete|all|use)\(\s*['\"](/[^'\"]*)['\"]")
PORT_FALLBACK_RE = re.compile(r"\b([A-Z][A-Z0-9_]*_)?PORT\s*(?:\?\?|\|\|)\s*(\d{2,5})\b")
HEALTH_PATHS = ("/health", "/healthz", "/api/health", "/ready", "/readyz", "/livez", "/status")
SERVER_FRAMEWORKS = ("express", "fastify", "koa")
CODE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
TEST_DIRS = {"test", "tests", "__tests__"}
TEST_FILE_RE = re.compile(r"\.(?:test|spec)\.[cm]?[jt]sx?$")


class IntakeAgent:
    def __init__(self, emit: Callable[..., object] | None = None):
        self.emit = emit or (lambda *args, **kwargs: None)
        # Workspace packages whose start script is not `node <file>`.
        self.skipped: list[str] = []

    def stage_and_analyze(self, run_id: str, source: Path, staged_root: Path) -> ProjectSpec:
        source = source.resolve()
        if not source.is_dir():
            raise ValueError(f"Project folder does not exist: {source}")
        self.emit(run_id, "step", "intake", "running", 4, "Copying project into an isolated review workspace")
        if staged_root.exists():
            shutil.rmtree(staged_root)
        shutil.copytree(source, staged_root, ignore=self._ignore)
        repository = self._repository_spec(source)
        services = self._discover(staged_root)
        if not services:
            raise ValueError(
                "No deployable application was found. v1 requires a package.json with a Next.js dependency, "
                "or a workspace whose root start script runs one of its Node.js services."
            )
        workspace = services[0].framework != "nextjs"
        warnings: list[str] = []
        # A workspace installs from its root, so that is the one lockfile it can lack.
        lock_warnings = self._ensure_lockfiles(run_id, staged_root, services[:1] if workspace else services)
        if any(not service.lockfile for service in services):
            services = self._discover(staged_root)
        warnings.extend(lock_warnings)
        warnings.extend(
            f"{root} has a start script that is not `node <file>`, so it is not deployed." for root in self.skipped
        )
        if len(services) > 1 and not workspace:
            warnings.append("Multiple Next.js services were detected; the first service is the primary deployment target.")
        if repository.dirty_files:
            warnings.append("The source repository has uncommitted files. Only agent-owned files will be staged on deploy.")
        project_name = self._project_name(source, services[0])
        spec = ProjectSpec(
            name=project_name,
            source_path=str(source),
            staged_path=str(staged_root),
            services=services,
            repository=repository,
            warnings=warnings,
        )
        self.emit(
            run_id,
            "step",
            "intake",
            "complete",
            14,
            f"Detected {len(services)} {'Node.js' if workspace else 'Next.js'} service(s); primary root: {services[0].root or '.'}",
            {"services": len(services), "primary_root": services[0].root or "."},
        )
        return spec

    @staticmethod
    def _ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in SKIP_DIRS or name.startswith(".env")}

    def _discover_services(self, root: Path) -> list[ServiceSpec]:
        candidates: list[tuple[Path, dict]] = []
        for package_path in root.rglob("package.json"):
            if any(part in SKIP_DIRS for part in package_path.parts):
                continue
            try:
                package = json.loads(package_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                continue
            dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
            if "next" in dependencies:
                candidates.append((package_path.parent, package))
        candidates.sort(key=lambda item: (len(item[0].relative_to(root).parts), str(item[0])))
        return [self._service_spec(root, service_root, package) for service_root, package in candidates]

    def _discover(self, root: Path) -> list[ServiceSpec]:
        return self._discover_services(root) or self._discover_workspace(root)

    def _discover_workspace(self, root: Path) -> list[ServiceSpec]:
        """A MERN workspace. The root start script runs the gateway, and every
        other workspace package with a start script runs beside it."""
        self.skipped = []
        package = self._read_package(root / "package.json")
        if not package:
            return []
        members = self._workspace_members(root, package)
        entry = self._root_entry(root, package, members)
        gateway = next((path for path in members if entry and path in (root / entry).parents), None)
        if gateway is None:
            return []
        package_manager, install_command, lockfile = self._package_manager(root, package)
        companions: list[tuple[Path, str]] = []
        for path, member in members.items():
            start = str(member.get("scripts", {}).get("start", ""))
            if path == gateway or not start:
                continue
            if self._node_entry(start):
                companions.append((path, self._node_entry(start)))
            else:
                self.skipped.append(path.relative_to(root).as_posix())
        running = [gateway, *(path for path, _entry in companions)]
        dependencies: dict = {}
        for path in running:
            dependencies.update(self._dependencies(members[path]))
        scripts = {str(key): str(value) for key, value in package.get("scripts", {}).items()}
        routes = self._scan_server_routes(gateway)
        framework, version = self._server_framework(members[gateway])
        services = [
            ServiceSpec(
                name=self._slug(members[gateway].get("name") or gateway.name),
                # Installed and built from the workspace root, as a Next.js app
                # is from its own. The root build is what bundles the client.
                root="",
                framework=framework,
                version=version,
                package_manager=package_manager,
                install_command=install_command,
                build_command=f"{package_manager} run build" if scripts.get("build") else "",
                start_command=f"node {entry}",
                port=self._code_port(gateway, exact=True) or self._detect_port(scripts),
                health_path=self._health_path(routes),
                routes=routes,
                environment=self._merge_environment(root, running),
                dependencies=sorted(dependencies),
                scripts=scripts,
                lockfile=lockfile,
                has_mongodb="mongodb" in dependencies or "mongoose" in dependencies,
                has_better_auth="better-auth" in dependencies,
            )
        ]
        for path, member_entry in companions:
            member = members[path]
            member_dependencies = self._dependencies(member)
            member_routes = self._scan_server_routes(path)
            framework, version = self._server_framework(member)
            services.append(
                ServiceSpec(
                    name=self._slug(member.get("name") or path.name),
                    root=path.relative_to(root).as_posix(),
                    framework=framework,
                    version=version,
                    package_manager=package_manager,
                    install_command=install_command,
                    build_command="",
                    start_command=f"node {member_entry}",
                    port=self._code_port(path),
                    health_path=self._health_path(member_routes),
                    routes=member_routes,
                    environment=self._scan_environment(path, root, aliases=True),
                    dependencies=sorted(member_dependencies),
                    scripts={str(key): str(value) for key, value in member.get("scripts", {}).items()},
                    lockfile=lockfile,
                    has_mongodb="mongodb" in member_dependencies or "mongoose" in member_dependencies,
                    has_better_auth="better-auth" in member_dependencies,
                )
            )
        return services

    def _workspace_members(self, root: Path, package: dict) -> dict[Path, dict]:
        patterns = package.get("workspaces") or []
        if isinstance(patterns, dict):
            patterns = patterns.get("packages") or []
        members: dict[Path, dict] = {}
        for pattern in patterns if isinstance(patterns, list) else []:
            for path in sorted(root.glob(str(pattern))):
                if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
                    continue
                member = self._read_package(path / "package.json")
                if member is not None:
                    members[path] = member
        return members

    def _root_entry(self, root: Path, package: dict, members: dict[Path, dict]) -> str:
        """The file the root start script runs, relative to the root."""
        start = str(package.get("scripts", {}).get("start", ""))
        entry = self._node_entry(start)
        if entry:
            return entry
        flag = WORKSPACE_FLAG_RE.search(start)
        wanted = flag.group(1).strip("'\"") if flag else ""
        for path, member in members.items():
            relative = path.relative_to(root).as_posix()
            if wanted and wanted in (member.get("name"), relative):
                inner = self._node_entry(str(member.get("scripts", {}).get("start", "")))
                return f"{relative}/{inner}" if inner else ""
        return ""

    @staticmethod
    def _node_entry(script: str) -> str:
        match = NODE_ENTRY_RE.match(script or "")
        return PurePosixPath(match.group(1)).as_posix() if match else ""

    @staticmethod
    def _read_package(path: Path) -> dict | None:
        try:
            package = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        return package if isinstance(package, dict) else None

    @staticmethod
    def _dependencies(package: dict) -> dict:
        return {**package.get("dependencies", {}), **package.get("devDependencies", {})}

    @staticmethod
    def _server_framework(package: dict) -> tuple[str, str]:
        dependencies = package.get("dependencies", {})
        name = next((item for item in SERVER_FRAMEWORKS if item in dependencies), "")
        return (name, str(dependencies[name])) if name else ("node", "unknown")

    def _merge_environment(self, root: Path, directories: list[Path]) -> list[EnvironmentVariable]:
        """One list for all of them: services on one host share one environment."""
        merged: dict[str, EnvironmentVariable] = {}
        for directory in directories:
            for variable in self._scan_environment(directory, root, aliases=True):
                known = merged.setdefault(variable.name, variable)
                if known is not variable:
                    known.required = known.required or variable.required
                    known.sources = sorted(set(known.sources) | set(variable.sources))
        return [merged[name] for name in sorted(merged)]

    @staticmethod
    def _code_files(directory: Path) -> list[Path]:
        files = []
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in CODE_EXTENSIONS:
                continue
            parts = path.relative_to(directory).parts
            if any(part in SKIP_DIRS or part in TEST_DIRS for part in parts) or TEST_FILE_RE.search(path.name):
                continue
            files.append(path)
        return files

    @classmethod
    def _scan_server_routes(cls, directory: Path) -> list[dict[str, str]]:
        routes: dict[tuple[str, str], dict[str, str]] = {}
        for path in cls._code_files(directory):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for method, route in ROUTE_RE.findall(content):
                routes[(route, method)] = {
                    "path": route,
                    "method": method,
                    "type": "api" if route.startswith("/api") else "page",
                }
        return [routes[key] for key in sorted(routes)]

    @staticmethod
    def _health_path(routes: list[dict[str, str]]) -> str:
        """A health route the service already serves, else its home page."""
        served = {route["path"] for route in routes if route.get("method") in ("get", "all")}
        return next((path for path in HEALTH_PATHS if path in served), "/")

    @classmethod
    def _code_port(cls, directory: Path, exact: bool = False) -> int:
        """The port a service falls back to in its own code, as in `env.AUTH_PORT ?? 4101`.
        `exact` takes PORT itself only, the one the platform sets."""
        for path in cls._code_files(directory):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in PORT_FALLBACK_RE.finditer(content):
                if not (exact and match.group(1)):
                    return int(match.group(2))
        return 0

    def _service_spec(self, repo_root: Path, root: Path, package: dict) -> ServiceSpec:
        relative_root = root.relative_to(repo_root).as_posix()
        if relative_root == ".":
            relative_root = ""
        dependencies = {**package.get("dependencies", {}), **package.get("devDependencies", {})}
        scripts = package.get("scripts", {})
        package_manager, install_command, lockfile = self._package_manager(root, package)
        environment = self._scan_environment(root)
        routes = self._scan_routes(root)
        name = package.get("name") or root.name
        version = str(dependencies.get("next", "unknown"))
        return ServiceSpec(
            name=self._slug(name),
            root=relative_root,
            framework="nextjs",
            version=version,
            package_manager=package_manager,
            install_command=install_command,
            build_command=f"{package_manager} run build" if scripts.get("build") else "",
            start_command=f"{package_manager} run start" if scripts.get("start") else "node server.js",
            port=self._detect_port(scripts),
            routes=routes,
            environment=environment,
            dependencies=sorted(dependencies.keys()),
            scripts={str(key): str(value) for key, value in scripts.items()},
            lockfile=lockfile,
            has_mongodb="mongodb" in dependencies or "mongoose" in dependencies,
            has_better_auth="better-auth" in dependencies,
        )

    @staticmethod
    def _package_manager(root: Path, package: dict | None = None) -> tuple[str, str, str]:
        if (root / "pnpm-lock.yaml").exists():
            return "pnpm", "pnpm install --frozen-lockfile", "pnpm-lock.yaml"
        if (root / "yarn.lock").exists():
            return "yarn", "yarn install --frozen-lockfile", "yarn.lock"
        if (root / "bun.lockb").exists() or (root / "bun.lock").exists():
            name = "bun.lock" if (root / "bun.lock").exists() else "bun.lockb"
            return "bun", "bun install --frozen-lockfile", name
        if (root / "package-lock.json").exists():
            return "npm", "npm ci", "package-lock.json"
        declared = str((package or {}).get("packageManager", "")).split("@", 1)[0].lower()
        if declared in {"pnpm", "yarn", "bun"}:
            return declared, f"{declared} install --frozen-lockfile", ""
        return "npm", "npm ci", ""

    def _ensure_lockfiles(self, run_id: str, staged_root: Path, services: list[ServiceSpec]) -> list[str]:
        warnings: list[str] = []
        for service in services:
            if service.lockfile:
                continue
            root = staged_root / service.root if service.root else staged_root
            if service.package_manager != "npm" or not command_exists("npm"):
                warnings.append(
                    f"A reproducible {service.package_manager} lockfile is missing for {service.root or '.'}."
                )
                continue
            self.emit(run_id, "step", "lockfile", "running", 12, "Generating package-lock.json in the isolated workspace")
            result = run_command(
                ["npm", "install", "--package-lock-only", "--ignore-scripts", "--no-audit", "--no-fund"],
                cwd=root,
                timeout=600,
                authenticated=False,
            )
            if result.returncode or not (root / "package-lock.json").is_file():
                warnings.append("package-lock.json generation failed; the package lock gate will block deployment.")
        return warnings

    def _scan_environment(
        self, root: Path, base: Path | None = None, aliases: bool = False
    ) -> list[EnvironmentVariable]:
        """What the code reads from the environment. With `aliases`, as for a
        workspace service, reads through a renamed process.env count too, and a
        variable only ever read with a fallback of its own is not required."""
        found: dict[str, set[str]] = {}
        fallback: dict[str, bool] = {}
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SOURCE_EXTENSIONS:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            reads = [(match.group(1) or match.group(2), match.end()) for match in ENV_RE.finditer(content)]
            if aliases and "process.env" in content:
                reads += [(match.group(1), match.end()) for match in ALIASED_ENV_RE.finditer(content)]
            for name, end in reads:
                if name:
                    found.setdefault(name, set()).add(path.relative_to(base or root).as_posix())
                    fallback[name] = fallback.get(name, True) and bool(FALLBACK_RE.match(content, end))
        result = []
        for name, sources in sorted(found.items()):
            scope = "build" if name.startswith("NEXT_PUBLIC_") else "runtime"
            result.append(
                EnvironmentVariable(
                    name=name,
                    required=not (aliases and fallback[name]),
                    secret=is_secret_name(name),
                    scope=scope,
                    sources=sorted(sources),
                )
            )
        return result

    @staticmethod
    def _scan_routes(root: Path) -> list[dict[str, str]]:
        app_dir = root / "app"
        if not app_dir.exists():
            app_dir = root / "src" / "app"
        routes: list[dict[str, str]] = []
        if not app_dir.exists():
            return routes
        for path in app_dir.rglob("*"):
            if not path.is_file() or path.name not in {"page.js", "page.jsx", "page.ts", "page.tsx", "route.js", "route.ts"}:
                continue
            rel = path.parent.relative_to(app_dir)
            parts = [part for part in rel.parts if not part.startswith("(")]
            route = "/" + "/".join(parts)
            route = route.replace("/page", "") or "/"
            routes.append({"path": route, "type": "api" if path.name.startswith("route") else "page"})
        return sorted(routes, key=lambda item: item["path"])

    @staticmethod
    def _detect_port(scripts: dict) -> int:
        text = " ".join(str(value) for value in scripts.values())
        match = re.search(r"(?:--port|-p)\s+(\d{2,5})", text)
        return int(match.group(1)) if match else 3000

    @staticmethod
    def _repository_spec(source: Path) -> RepositorySpec:
        if not (source / ".git").exists() or not command_exists("git"):
            return RepositorySpec(is_git=False)
        branch = run_command(["git", "branch", "--show-current"], cwd=source).stdout.strip() or "main"
        remote_proc = run_command(["git", "remote", "get-url", "origin"], cwd=source)

        status = run_command(
            ["git", "status", "--porcelain"], cwd=source, timeout=GIT_TIMEOUT_SECONDS
        ).stdout.splitlines()
        return RepositorySpec(
            is_git=True,
            branch=branch,
            remote=remote_proc.stdout.strip() if remote_proc.returncode == 0 else "",
            dirty_files=[line[3:] if len(line) > 3 else line for line in status],
        )

    @staticmethod
    def _project_name(source: Path, service: ServiceSpec) -> str:
        return IntakeAgent._slug(source.name or service.name)

    @staticmethod
    def _slug(value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return slug[:40] or "nextjs-app"
