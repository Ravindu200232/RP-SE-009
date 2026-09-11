"""A MERN workspace deploys to AWS the way a Next.js app does.

On EC2 its services run under systemd on the one instance; on ECS they run as
containers of the one task. Either way they share a loopback, so the gateway
finds each service where its own code already looks.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from test import _support

# The deployment agent imports its own packages by their top-level names.
_AGENT = str(_support.ROOT / "deployment-agent" / "deploy_agent")
if _AGENT not in sys.path:
    sys.path.insert(0, _AGENT)

from deployment_agent.models import DeploymentPlan, DeploymentTarget  # noqa: E402
from dfagents.deployer_prepare import DeploymentPrepareMixin  # noqa: E402
from dfagents.generator import ArtifactGeneratorAgent  # noqa: E402
from dfagents.intake import IntakeAgent  # noqa: E402
from dfagents.planner import PlannerAgent  # noqa: E402
from dfagents.validator import SecurityValidatorAgent  # noqa: E402


def _write(root: Path, relative: str, content) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    text = content if isinstance(content, str) else json.dumps(content, indent=2)
    path.write_text(text, encoding="utf-8")


def _mern_workspace(root: Path) -> None:
    """The shape of the builder's MERN template, cut down to what deploying reads."""
    _write(root, "package.json", {
        "name": "recipes",
        "private": True,
        "workspaces": ["packages/*", "client"],
        "scripts": {
            "build": "npm run build --workspace client",
            "start": "node packages/gateway/src/server.js",
        },
    })
    _write(root, "package-lock.json", {"name": "recipes", "lockfileVersion": 3, "packages": {}})
    _write(root, "packages/gateway/package.json", {
        "name": "gateway",
        "scripts": {"start": "node src/server.js"},
        "dependencies": {"express": "^4.21.2"},
    })
    _write(root, "packages/gateway/src/config.js", (
        "export function loadConfig(env = process.env) {\n"
        "  return {\n"
        "    port: Number(env.PORT ?? 4000),\n"
        "    auth: env.AUTH_URL ?? `http://127.0.0.1:${env.AUTH_PORT ?? 4101}`,\n"
        "  };\n"
        "}\n"
    ))
    _write(root, "packages/gateway/src/app.js", (
        "import express from 'express';\n"
        "export function createApp() {\n"
        "  const app = express();\n"
        "  app.get('/ready', (req, res) => res.json({ ok: true }));\n"
        "  app.use('/api/auth', (req, res) => res.end());\n"
        "  return app;\n"
        "}\n"
    ))
    _write(root, "packages/gateway/src/server.js", (
        "import { createApp } from './app.js';\n"
        "import { loadConfig } from './config.js';\n"
        "const config = loadConfig();\n"
        "createApp(config).listen(config.port, '127.0.0.1', () => {\n"
        "  console.log('gateway listening on ' + config.port);\n"
        "});\n"
    ))
    _write(root, "packages/auth-service/package.json", {
        "name": "auth-service",
        "scripts": {"start": "node src/server.js", "test": "vitest run"},
        "dependencies": {"express": "^4.21.2", "mongoose": "^8.9.5"},
    })
    _write(root, "packages/auth-service/src/config.js", (
        "export function loadConfig(env = process.env) {\n"
        "  return {\n"
        "    port: Number(env.AUTH_PORT ?? 4101),\n"
        "    mongoUri: env.MONGODB_URI ?? 'mongodb://127.0.0.1:27017/app',\n"
        "    authSecret: env.AUTH_SECRET ?? 'dev-secret-change-me',\n"
        "  };\n"
        "}\n"
    ))
    _write(root, "packages/auth-service/src/server.js", (
        "import { loadConfig } from './config.js';\n"
        "const config = loadConfig();\n"
        "createApp(config).listen(config.port, '127.0.0.1');\n"
    ))
    # Not a service: it has no start script.
    _write(root, "packages/testing/package.json", {"name": "testing", "dependencies": {"mongoose": "^8.9.5"}})
    _write(root, "client/package.json", {
        "name": "client",
        "scripts": {"dev": "vite", "build": "vite build"},
        "dependencies": {"react": "^18.3.1"},
    })


class MernWorkspaceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.source = self.work / "recipes"
        _mern_workspace(self.source)

    def analyze(self):
        return IntakeAgent().stage_and_analyze("run", self.source, self.work / "staged")

    def generate(self, target):
        spec = self.analyze()
        plan = DeploymentPlan(project_slug="recipes", primary_service=spec.services[0].name)
        PlannerAgent._apply_deterministic_generation(plan, spec.services[0])
        plan.model_used = True
        records = ArtifactGeneratorAgent().generate("run", spec, plan, self.work / "staged", target=target)
        return plan, records

    def read(self, relative):
        return (self.work / "staged" / relative).read_text(encoding="utf-8")

    def assert_artifacts_valid(self, records, target):
        result = SecurityValidatorAgent().validate(
            "run", self.work / "staged", [record.to_dict() for record in records], target=target)
        self.assertEqual(result["errors"], [])

    def test_intake_takes_the_gateway_as_the_service_and_the_rest_as_its_companions(self):
        gateway, *companions = self.analyze().services
        self.assertEqual(
            (gateway.name, gateway.root, gateway.framework, gateway.start_command, gateway.build_command),
            ("gateway", "", "express", "node packages/gateway/src/server.js", "npm run build"),
        )
        # Both come from the gateway's own code.
        self.assertEqual((gateway.port, gateway.health_path), (4000, "/ready"))
        self.assertTrue(gateway.has_mongodb)
        self.assertEqual(
            [(item.name, item.root, item.start_command, item.port) for item in companions],
            [("auth-service", "packages/auth-service", "node src/server.js", 4101)],
        )

    def test_intake_reads_config_that_receives_process_env_as_a_parameter(self):
        variables = {item.name: item for item in self.analyze().services[0].environment}
        self.assertLessEqual({"MONGODB_URI", "AUTH_SECRET", "AUTH_URL", "AUTH_PORT", "PORT"}, set(variables))
        # Read with a fallback of its own, so it need not be supplied.
        self.assertFalse(variables["AUTH_PORT"].required)

    def test_ec2_runs_the_companions_under_systemd_beside_the_gateway(self):
        _, records = self.generate(DeploymentTarget.AWS_EC2)
        release = self.read("deploy/release.sh")
        self.assertIn("cat > /etc/systemd/system/app-auth-service.service <<'UNIT'", release)
        self.assertIn("ExecStart=/usr/bin/node /opt/app/current/packages/auth-service/src/server.js", release)
        # Rollback restarts nextjs only; PartOf carries the restart to the companions.
        self.assertIn("PartOf=nextjs.service", release)
        self.assertIn("systemctl restart app-auth-service nextjs", release)
        self.assertIn("ExecStart=/usr/bin/node /opt/app/current/packages/gateway/src/server.js",
                      self.read("infra/bootstrap.yml"))
        deploy = self.read(".github/workflows/deploy.yml")
        self.assertIn("npm ci --omit=dev", deploy)
        self.assertNotIn(".next", deploy)
        self.assertNotIn(".next/standalone", self.read(".github/workflows/ci.yml"))
        self.assertFalse((self.work / "staged" / "next.config.mjs").exists())
        # Behind nginx the gateway keeps its loopback address.
        self.assertIn("listen(config.port, '127.0.0.1'", self.read("packages/gateway/src/server.js"))
        self.assert_artifacts_valid(records, DeploymentTarget.AWS_EC2)

    def test_ecs_runs_the_companions_as_containers_of_the_one_task(self):
        _, records = self.generate(DeploymentTarget.AWS_ECS)
        task = json.loads(self.read("deploy/task-definition.json"))
        gateway, auth = task["containerDefinitions"]
        self.assertEqual(gateway["name"], "recipes-app")
        self.assertEqual(gateway["portMappings"][0]["containerPort"], 4000)
        self.assertIn({"name": "HOST", "value": "0.0.0.0"}, gateway["environment"])
        self.assertEqual(auth["name"], "recipes-auth-service")
        self.assertEqual(auth["command"], ["node", "src/server.js"])
        self.assertEqual(auth["workingDirectory"], "/app/packages/auth-service")
        # The one public port is the gateway's.
        self.assertNotIn("PORT", {item["name"] for item in auth["environment"]})
        self.assertEqual(auth["secrets"], gateway["secrets"])
        dockerfile = self.read("Dockerfile")
        self.assertIn('CMD ["node", "packages/gateway/src/server.js"]', dockerfile)
        self.assertIn("npm ci --omit=dev", dockerfile)
        self.assertNotIn(".next", dockerfile)
        self.assertIn("listen(config.port, process.env.HOST ?? '127.0.0.1'",
                      self.read("packages/gateway/src/server.js"))
        self.assertIn('for container in spec["containerDefinitions"]:', self.read(".github/workflows/deploy.yml"))
        self.assert_artifacts_valid(records, DeploymentTarget.AWS_ECS)

    def test_every_secret_the_task_names_is_one_the_deployer_writes(self):
        plan, _ = self.generate(DeploymentTarget.AWS_ECS)
        values = DeploymentPrepareMixin._runtime_secret_values(
            "mongodb+srv://cluster.example/recipes", {"ApplicationUrl": "http://app.example"}, plan.to_dict())
        named = {
            item["name"]
            for container in json.loads(self.read("deploy/task-definition.json"))["containerDefinitions"]
            for item in container["secrets"]
        }
        self.assertIn("AUTH_SECRET", named)
        self.assertLessEqual(named, set(values))

    def test_vercel_is_refused_for_a_workspace(self):
        with self.assertRaisesRegex(ValueError, "Vercel deploys Next.js only"):
            self.generate(DeploymentTarget.VERCEL)


class NextjsDeploymentTests(unittest.TestCase):
    """The Next.js path, which already deploys, comes out as it did."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        source = self.work / "shop"
        _write(source, "package.json", {
            "name": "shop",
            "scripts": {"build": "next build", "start": "next start"},
            "dependencies": {"next": "15.1.0", "react": "19.0.0"},
        })
        _write(source, "package-lock.json", {"name": "shop", "lockfileVersion": 3, "packages": {}})
        _write(source, "app/page.js", "export default function Page() { return null }\n")
        self.spec = IntakeAgent().stage_and_analyze("run", source, self.work / "staged")

    def generate(self, target):
        plan = DeploymentPlan(project_slug="shop", primary_service=self.spec.services[0].name)
        PlannerAgent._apply_deterministic_generation(plan, self.spec.services[0])
        ArtifactGeneratorAgent().generate("run", self.spec, plan, self.work / "staged", target=target)

    def read(self, relative):
        return (self.work / "staged" / relative).read_text(encoding="utf-8")

    def test_ec2_releases_the_standalone_build_under_one_unit(self):
        self.generate(DeploymentTarget.AWS_EC2)
        release = self.read("deploy/release.sh")
        self.assertIn("systemctl restart nextjs\n", release)
        self.assertIn("journalctl -u nextjs -n 50", release)
        self.assertNotIn("/etc/systemd/system/", release)
        self.assertIn("ExecStart=/usr/bin/node /opt/app/current/server.js", self.read("infra/bootstrap.yml"))
        self.assertIn("tar -czf /tmp/app.tar.gz -C .next/standalone .", self.read(".github/workflows/deploy.yml"))

    def test_ecs_task_is_one_container(self):
        self.generate(DeploymentTarget.AWS_ECS)
        task = json.loads(self.read("deploy/task-definition.json"))
        self.assertEqual(len(task["containerDefinitions"]), 1)
        self.assertEqual(task["memory"], "512")
        self.assertNotIn("HOST", {item["name"] for item in task["containerDefinitions"][0]["environment"]})
        self.assertIn('CMD ["node", "server.js"]', self.read("Dockerfile"))


if __name__ == "__main__":
    unittest.main()
