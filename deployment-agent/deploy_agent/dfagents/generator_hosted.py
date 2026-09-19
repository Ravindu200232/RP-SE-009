"""GitHub delivery workflows for Netlify and Azure App Service."""
from __future__ import annotations

import json

import yaml


class GeneratorHostedMixin:
    def _hosted_deploy_workflow(self, service, spec, plan, target):
        setup = {"uses": "actions/setup-node@v4", "with": {"node-version": "22"}}
        steps = [{"uses": "actions/checkout@v4"}, setup]
        if service.package_manager in {"pnpm", "yarn"}:
            steps.append({"run": "corepack enable"})
        elif service.package_manager == "bun":
            steps.append({"uses": "oven-sh/setup-bun@v2"})
        steps.append({"name": "Install dependencies", "run": service.install_command})
        if target.value == "netlify":
            steps.extend([
                {"name": "Install Netlify tooling", "run": "npm install --global netlify-cli\nnpm install --no-save @netlify/plugin-nextjs"},
                {"name": "Build and deploy", "run": 'netlify deploy --build --prod --site "$NETLIFY_SITE_ID" --message "$GITHUB_SHA"'},
            ])
            env = {"NETLIFY_AUTH_TOKEN": "${{ secrets.NETLIFY_AUTH_TOKEN }}", "NETLIFY_SITE_ID": "${{ vars.NETLIFY_SITE_ID }}"}
        else:
            steps.extend([
                {"name": "Azure login", "uses": "azure/login@v2", "with": {"creds": "${{ secrets.AZURE_CREDENTIALS }}"}},
                {"name": "Read production build settings", "run": 'az webapp config appsettings list --name "$AZURE_WEBAPP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --output json > /tmp/agentforge-env.json\npython3 - <<\'PY\'\nimport json, os\nwith open(os.environ["GITHUB_ENV"], "a") as out:\n    for entry in json.load(open("/tmp/agentforge-env.json")):\n        value = entry["value"]\n        print("::add-mask::" + value)\n        marker = "AGENTFORGE_ENV_" + os.urandom(12).hex()\n        out.write(entry["name"] + "<<" + marker + "\\n" + value + "\\n" + marker + "\\n")\nPY\nrm /tmp/agentforge-env.json'},
                {"name": "Build application", "run": service.build_command or "npm run build"},
            ])
            if service.framework == "nextjs":
                steps.append({"name": "Package standalone app", "run": "test -f .next/standalone/server.js\nmkdir -p .next/standalone/.next\ncp -r .next/static .next/standalone/.next/static\nif [ -d public ]; then cp -r public .next/standalone/public; fi"})
                package = ((service.root + "/") if service.root else "") + ".next/standalone"
            else:
                steps.append({"name": "Package application", "run": "mkdir -p /tmp/agentforge-release\ntar --exclude=.git --exclude=.agentforge --exclude=.agents --exclude='.env*' --exclude='*.pem' -cf - . | tar -xf - -C /tmp/agentforge-release"})
                package = "/tmp/agentforge-release"
            steps.append({"name": "Deploy compiled app", "uses": "azure/webapps-deploy@v3", "with": {
                "app-name": "${{ vars.AZURE_WEBAPP_NAME }}", "package": package,
            }})
            if service.framework != "nextjs":
                # Start all workspace services concurrently from a single startup command in App Service.
                steps.append({"name": "Start every service, not just the gateway", "run": 'az webapp config set --name "$AZURE_WEBAPP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --startup-file "npm run start:all" --output none'})
            steps.append({"name": "Record deployed commit", "run": 'az webapp config appsettings set --name "$AZURE_WEBAPP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --settings AGENTFORGE_COMMIT_SHA="$GITHUB_SHA" --output none'})
            env = {"AZURE_WEBAPP_NAME": "${{ vars.AZURE_WEBAPP_NAME }}", "AZURE_RESOURCE_GROUP": "${{ vars.AZURE_RESOURCE_GROUP }}"}
        steps.append({"name": "Check homepage and health", "run": f'curl --fail --retry 12 --retry-delay 5 "$APPLICATION_URL/"\ncurl --fail --retry 12 --retry-delay 5 "$APPLICATION_URL{service.health_path}"'})
        env["APPLICATION_URL"] = "${{ vars.APPLICATION_URL }}"
        return yaml.safe_dump({
            "name": f"Deploy to {target.value.title()}",
            "on": {"push": {"branches": [spec.repository.branch or "main"]}, "workflow_dispatch": {}},
            "permissions": {"contents": "read"},
            "concurrency": {"group": f"production-{plan.project_slug}", "cancel-in-progress": False},
            "jobs": {"deploy": {"runs-on": "ubuntu-latest", "defaults": {"run": {"working-directory": service.root or "."}}, "env": env, "steps": steps}},
        }, sort_keys=False)

    @staticmethod
    def _netlify_config(service):
        return f'[build]\ncommand = {json.dumps(service.build_command or "npm run build")}\npublish = ".next"\n\n[[plugins]]\npackage = "@netlify/plugin-nextjs"\n'
