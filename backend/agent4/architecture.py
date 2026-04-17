from __future__ import annotations

from pathlib import Path
import json
import re

from .models import ArchitectureAnalysis, ServiceDescriptor, resolve_path, slugify


ARCHITECTURE_ALIASES = {
    "monolith": "monolith",
    "monolithic": "monolith",
    "modular monolith": "modular_monolith",
    "modular_monolith": "modular_monolith",
    "layered": "layered",
    "n-tier": "layered",
    "microservices": "microservices",
    "microservice": "microservices",
    "event-driven": "event_driven",
    "event_driven": "event_driven",
    "serverless": "serverless",
}


class ArchitectureDetector:
    def analyze(
        self,
        source_path: str,
        srs_path: str = "",
        architecture_manifest_path: str = "",
    ) -> ArchitectureAnalysis:
        source_root = resolve_path(source_path)
        srs_payload = self._read_json(resolve_path(srs_path)) if srs_path else {}
        manifest_payload = self._read_json(resolve_path(architecture_manifest_path)) if architecture_manifest_path else {}

        declared_architecture = self._declared_architecture(srs_payload, manifest_payload)
        selected_stack = str(srs_payload.get("selectedStack", ""))
        project_name = str(srs_payload.get("projectName") or source_root.name)

        services = self._discover_services(source_root)
        infrastructure = self._detect_infrastructure(source_root, selected_stack)
        scanned_architecture, confidence, evidence = self._scan_architecture(
            source_root,
            services,
            infrastructure,
            selected_stack,
        )

        conflict = bool(declared_architecture and declared_architecture != scanned_architecture)
        final_architecture = declared_architecture or scanned_architecture
        if declared_architecture and not conflict:
            confidence = max(confidence, 0.95)
            evidence.append(f"Declared architecture '{declared_architecture}' matched repository scan.")
        elif conflict:
            evidence.append(
                f"Declared architecture '{declared_architecture}' conflicts with scanned architecture '{scanned_architecture}'."
            )
            confidence = min(confidence, 0.45)

        return ArchitectureAnalysis(
            declared_architecture=declared_architecture,
            scanned_architecture=scanned_architecture,
            final_architecture=final_architecture,
            confidence=round(confidence, 2),
            conflict=conflict,
            project_name=project_name,
            source_path=str(source_root),
            selected_stack=selected_stack,
            services=services,
            infrastructure=infrastructure,
            evidence=evidence,
        )

    def _read_json(self, path: Path) -> dict:
        if not path or not path.exists() or not path.is_file():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _declared_architecture(self, srs_payload: dict, manifest_payload: dict) -> str | None:
        candidates = [
            manifest_payload.get("architecture"),
            manifest_payload.get("architectureType"),
            srs_payload.get("architecture"),
            srs_payload.get("architectureType"),
            srs_payload.get("selectedArchitecture"),
        ]
        for value in candidates:
            normalized = self._normalize_architecture(value)
            if normalized:
                return normalized
        return None

    def _normalize_architecture(self, value: object) -> str | None:
        if not value:
            return None
        normalized = str(value).strip().lower().replace("_", " ")
        return ARCHITECTURE_ALIASES.get(normalized)

    def _discover_services(self, source_root: Path) -> list[ServiceDescriptor]:
        services: list[ServiceDescriptor] = []
        assigned_ports = set()

        server_root = source_root / "server"
        if server_root.exists():
            for child in sorted(server_root.iterdir()):
                if child.is_dir() and self._is_service_dir(child):
                    descriptor = self._describe_service(child, source_root, kind="backend")
                    if descriptor.port in assigned_ports:
                        descriptor.port = self._next_port(assigned_ports, 3000)
                    assigned_ports.add(descriptor.port)
                    services.append(descriptor)

        client_root = None
        for candidate in ("client", "frontend"):
            path = source_root / candidate
            if path.exists() and path.is_dir():
                client_root = path
                break
        if client_root:
            descriptor = self._describe_service(client_root, source_root, kind="frontend")
            if descriptor.port in assigned_ports:
                descriptor.port = self._next_port(assigned_ports, 5173)
            assigned_ports.add(descriptor.port)
            services.append(descriptor)

        if not services and self._is_service_dir(source_root):
            services.append(self._describe_service(source_root, source_root, kind="backend"))

        return services

    def _is_service_dir(self, path: Path) -> bool:
        markers = ["package.json", "pyproject.toml", "requirements.txt", "pom.xml", "Dockerfile"]
        return any((path / marker).exists() for marker in markers)

    def _describe_service(self, path: Path, source_root: Path, kind: str) -> ServiceDescriptor:
        package_json = self._read_json(path / "package.json")
        name = str(package_json.get("name") or path.name)
        service_key = slugify(name).replace("-", "_")
        runtime = self._runtime_for(path, package_json, kind)
        entrypoint = self._entrypoint_for(path, package_json, runtime, kind)
        contents = self._combined_text(path)
        port = self._detect_port(contents, package_json, kind)
        has_health_endpoint = "/health" in contents or "health" in entrypoint.lower()
        env_vars = sorted(set(re.findall(r"process\.env\.([A-Z0-9_]+)", contents)))
        dependencies = self._service_dependencies(contents)

        return ServiceDescriptor(
            name=name,
            service_key=service_key,
            relative_path=str(path.relative_to(source_root)),
            runtime=runtime,
            kind=kind,
            port=port,
            has_health_endpoint=has_health_endpoint,
            entrypoint=entrypoint,
            dependencies=dependencies,
            env_vars=env_vars,
            inferred_from=[str(path)],
        )

    def _runtime_for(self, path: Path, package_json: dict, kind: str) -> str:
        if (path / "package.json").exists():
            deps = package_json.get("dependencies", {})
            if "next" in deps:
                return "nextjs"
            if kind == "frontend":
                return "node-frontend"
            return "node"
        if (path / "requirements.txt").exists() or (path / "pyproject.toml").exists():
            return "python"
        return "unknown"

    def _entrypoint_for(self, path: Path, package_json: dict, runtime: str, kind: str) -> str:
        if runtime in {"node", "node-frontend", "nextjs"}:
            main = package_json.get("main")
            if main:
                return str(main)
            for candidate in ("Server.js", "server.js", "index.js", "app.js", "main.js"):
                if (path / candidate).exists():
                    return candidate
            return "server.js" if kind == "backend" else "index.js"
        if runtime == "python":
            for candidate in ("main.py", "app.py", "server.py"):
                if (path / candidate).exists():
                    return candidate
            return "main.py"
        return ""

    def _combined_text(self, path: Path) -> str:
        chunks: list[str] = []
        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix in {".js", ".jsx", ".ts", ".tsx", ".py", ".json", ".yml", ".yaml"}:
                try:
                    chunks.append(file_path.read_text(encoding="utf-8"))
                except UnicodeDecodeError:
                    continue
        return "\n".join(chunks)

    def _detect_port(self, contents: str, package_json: dict, kind: str) -> int:
        patterns = [
            r"PORT\s*\|\|\s*(\d+)",
            r"localhost:(\d+)",
            r"EXPOSE\s+(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, contents)
            if match:
                return int(match.group(1))
        scripts = " ".join(str(value) for value in package_json.get("scripts", {}).values())
        if "vite" in scripts:
            return 5173
        if "next" in scripts:
            return 3000
        return 5173 if kind == "frontend" else 3000

    def _service_dependencies(self, contents: str) -> list[str]:
        env_matches = re.findall(r"([A-Z0-9_]+)_URL", contents)
        hardcoded_matches = re.findall(r"http://([a-z0-9_\-]+)(?:_container)?:\d+", contents, re.IGNORECASE)
        values = {
            slugify(item.replace("_URL", "").replace("_SERVICE", "_service")).replace("-", "_")
            for item in env_matches
            if item not in {"SERVER", "API_DOCS"}
        }
        values.update(slugify(item).replace("-", "_") for item in hardcoded_matches)
        return sorted(values)

    def _next_port(self, assigned_ports: set[int], start: int) -> int:
        port = start
        while port in assigned_ports:
            port += 1
        return port

    def _detect_infrastructure(self, source_root: Path, selected_stack: str) -> dict[str, bool]:
        stack = selected_stack.lower()
        contents = self._combined_text(source_root)
        return {
            "mongo": any(token in contents.lower() for token in ("mongoose", "mongodb")) or "mongodb" in stack,
            "postgres": any(token in contents.lower() for token in ("postgres", "psycopg", "sequelize")) or "postgres" in stack,
            "redis": "redis" in contents.lower() or "redis" in stack,
            "rabbitmq": any(token in contents.lower() for token in ("rabbitmq", "amqplib", "pika")) or "rabbitmq" in stack,
        }

    def _scan_architecture(
        self,
        source_root: Path,
        services: list[ServiceDescriptor],
        infrastructure: dict[str, bool],
        selected_stack: str,
    ) -> tuple[str, float, list[str]]:
        evidence: list[str] = []
        service_count = len([service for service in services if service.kind == "backend"])
        stack_lower = selected_stack.lower()
        files = {path.name.lower() for path in source_root.rglob("*") if path.is_file()}
        combined = self._combined_text(source_root).lower()
        path_strings = [str(path.relative_to(source_root)).lower() for path in source_root.rglob("*") if path.is_dir()]

        if {"serverless.yml", "template.yaml", "samconfig.toml"} & files or "aws lambda" in stack_lower:
            evidence.append("Found serverless deployment files or AWS Lambda indicators.")
            return "serverless", 0.82, evidence

        if infrastructure.get("rabbitmq") and service_count > 1:
            evidence.append("Found broker usage with multiple services, suggesting event-driven architecture.")
            return "event_driven", 0.84, evidence

        if service_count > 1:
            evidence.append(f"Detected {service_count} backend services with independent manifests.")
            if any(service.kind == "frontend" for service in services):
                evidence.append("Detected a separate client application alongside backend services.")
            return "microservices", 0.88, evidence

        layered_markers = ("controllers", "services", "repositories", "models")
        modular_markers = ("modules", "domains", "features")
        if sum(1 for marker in layered_markers if any(marker in path_string.split("/") for path_string in path_strings)) >= 2:
            evidence.append("Detected presentation/business/data style folders consistent with layered architecture.")
            return "layered", 0.74, evidence

        if sum(1 for marker in modular_markers if any(marker in path_string.split("/") for path_string in path_strings)) >= 2:
            evidence.append("Detected modular folder structure inside a single deployable application.")
            return "modular_monolith", 0.72, evidence

        evidence.append("Defaulted to monolith because only one deployable application was detected.")
        return "monolith", 0.65, evidence
