"""Provision the selected Netlify site or Azure App Service without changing identities on retry."""
from __future__ import annotations

import json

from deployment_agent import owner_credentials
from deployment_agent.hosted import azure_command, netlify_api, runtime_values, set_azure_environment
from deployment_agent.providers import ProviderPrep


class DeploymentHostedMixin:
    def _prepare_netlify(self, run_id, run, plan, uri):
        answers = plan.get("customization") or {}
        recorded = run.get("repo") or {}
        site_id = recorded.get("netlify_site_id") or answers.get("netlify_site_id")
        site = netlify_api("GET", f"sites/{site_id}") if site_id else netlify_api(
            "POST", f"{answers['netlify_team']}/sites" if answers.get("netlify_team") else "sites",
            {"name": plan["project_slug"]})
        site_id, url = site["id"], site.get("ssl_url") or site["url"]
        repo_state = {**recorded, "netlify_site_id": site_id, "netlify_account_id": site["account_id"],
                      "application_url": url, "owner": owner_credentials.owner(),
                      "netlify_site_created": recorded.get("netlify_site_created", not bool(answers.get("netlify_site_id")))}
        self.store.update_run(run_id, repo_json=repo_state)
        existing = netlify_api("GET", f"accounts/{site['account_id']}/env?site_id={site_id}")
        previous = {}
        for entry in existing:
            options = {value.get("context"): value.get("value", "") for value in entry.get("values", [])}
            previous[entry["key"]] = options.get("production") or options.get("all") or ""
        values = runtime_values(plan, uri, url, previous)
        for key, value in values.items():
            body = {"key": key, "scopes": ["builds", "functions", "runtime"], "values": [{"context": "production", "value": value}]}
            if key in previous:
                netlify_api("PATCH", f"accounts/{site['account_id']}/env/{key}?site_id={site_id}", {"context": "production", "value": value})
            else:
                netlify_api("POST", f"accounts/{site['account_id']}/env?site_id={site_id}", [body])
        self.emit(run_id, "step", "env", "complete", 45, "Netlify production environment configured")
        return ProviderPrep(github_variables={"NETLIFY_SITE_ID": site_id, "APPLICATION_URL": url},
                            github_secrets={"NETLIFY_AUTH_TOKEN": owner_credentials.current()["netlify_token"]}, repo_state=repo_state)

    def _prepare_azure(self, run_id, run, spec, plan, uri):
        answers, recorded = plan.get("customization") or {}, run.get("repo") or {}
        app = recorded.get("azure_app_name") or plan["project_slug"]
        group = recorded.get("azure_resource_group") or answers.get("azure_resource_group") or f"{app}-rg"
        service_plan = recorded.get("azure_plan") or answers.get("azure_plan") or f"{app}-plan"
        location, sku = answers.get("azure_location", "centralindia"), answers.get("azure_sku", "B1")
        azure_command(["account", "show", "--output", "none"], authenticate=True)
        self.emit(run_id, "step", "bootstrap", "running", 20, f"Preparing Azure App Service {app}")
        if not recorded.get("azure_app_name"):
            group_exists = azure_command(["group", "exists", "--name", group, "--output", "tsv"]).stdout.strip().lower() == "true"
            existing = json.loads(azure_command(["webapp", "list", "--resource-group", group,
                                                 "--query", f"[?name=='{app}']"]).stdout or "[]") if group_exists else []
            if existing and (existing[0].get("tags") or {}).get("agentforge-project") != str(run["project_path"]):
                raise ValueError("The selected Azure app belongs to another project; choose another name")
            if not group_exists:
                azure_command(["group", "create", "--name", group, "--location", location, "--output", "none"])
            self.store.update_run(run_id, repo_json={**recorded, "azure_group_prepared": True})
            plans = json.loads(azure_command(["appservice", "plan", "list", "--resource-group", group,
                                             "--query", f"[?name=='{service_plan}']"]).stdout or "[]")
            if plans and not plans[0].get("reserved"):
                raise ValueError("The selected App Service plan must support Linux")
            if not plans:
                azure_command(["appservice", "plan", "create", "--name", service_plan, "--resource-group", group,
                                "--is-linux", "--sku", sku, "--output", "none"])
            if not existing:
                azure_command(["webapp", "create", "--name", app, "--resource-group", group, "--plan", service_plan,
                                "--runtime", "NODE:22-lts", "--tags", f"agentforge-project={run['project_path']}", "--output", "none"])
        info = json.loads(azure_command(["webapp", "show", "--name", app, "--resource-group", group]).stdout)
        url = f"https://{info['defaultHostName']}"
        repo_state = {**recorded, "azure_app_name": app, "azure_resource_group": group, "azure_plan": service_plan,
                       "azure_location": location, "application_url": url, "owner": owner_credentials.owner(), "azure_app_created": True}
        self.store.update_run(run_id, repo_json=repo_state)
        settings = json.loads(azure_command(["webapp", "config", "appsettings", "list", "--name", app, "--resource-group", group]).stdout)
        previous = {entry["name"]: entry["value"] for entry in settings}
        values = runtime_values(plan, uri, url, previous)
        set_azure_environment(app, group, {**values, "SCM_DO_BUILD_DURING_DEPLOYMENT": "false", "PORT": "8080", "HOSTNAME": "0.0.0.0"})
        service = spec["services"][0]
        startup = "node server.js" if service["framework"] == "nextjs" else service["start_command"]
        azure_command(["webapp", "config", "set", "--name", app, "--resource-group", group,
                       "--startup-file", startup, "--output", "none"])
        self.emit(run_id, "step", "env", "complete", 45, "Azure runtime and startup configured")
        return ProviderPrep(github_variables={"AZURE_WEBAPP_NAME": app, "AZURE_RESOURCE_GROUP": group, "APPLICATION_URL": url},
                            github_secrets={"AZURE_CREDENTIALS": owner_credentials.current()["azure_credentials"]}, repo_state=repo_state)
