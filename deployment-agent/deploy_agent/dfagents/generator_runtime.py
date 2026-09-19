from __future__ import annotations

from .generator_shared import *
from .generator_shared import _EAGER_CONNECT, _LAZY_CONNECT, generator_class


class GeneratorRuntimeMixin:
    @staticmethod
    def _build_environment(service: ServiceSpec) -> list[tuple[str, str]]:
        """Placeholders every build site must set, in one place."""
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
            for name, value in generator_class()._build_environment(service))
    @staticmethod
    def _build_env_docker(service: ServiceSpec, indent: int) -> str:
        """The same placeholders as Dockerfile `ENV` instructions."""
        pad = " " * indent
        return f"\n{pad}".join(
            f"ENV {name}={value}"
            for name, value in generator_class()._build_environment(service))
    @staticmethod
    def _build_services_yaml(indent: int) -> str:
        """A real MongoDB on 127.0.0.1:27017 for the duration of the build job."""
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
        """The image, built in GitHub Actions and never on the user's machine."""
        if service.framework != "nextjs":
            return generator_class()._workspace_dockerfile(service)
        port = service.port or 3000
        install = service.install_command or "npm ci"
        build = service.build_command or "npm run build"
        build_env = generator_class()._build_env_docker(service, 12)
        return textwrap.dedent(
            f"""
            # syntax=docker/dockerfile:1 Written by the deployment agent.

            FROM node:20-alpine AS deps
            WORKDIR /app
            COPY package.json package-lock.json* ./
            RUN {install}

            FROM node:20-alpine AS build
            WORKDIR /app
            COPY --from=deps /app/node_modules ./node_modules
            COPY . .
            # Runtime values come from Secrets Manager.
            # These placeholders only keep the build parseable.
            {build_env}
            ENV NEXT_TELEMETRY_DISABLED=1
            RUN {build}
            # Both must exist before the runtime stage copies them.
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
            # Copy assets missing from the standalone tree.
            COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
            COPY --from=build --chown=nextjs:nodejs /app/public ./public

            USER nextjs
            EXPOSE {port}
            CMD ["node", "server.js"]
            """
        ).lstrip()
    @staticmethod
    def _production_install(service: ServiceSpec) -> str:
        """The install again, keeping only what the services need at runtime."""
        return {
            "pnpm": "pnpm install --frozen-lockfile --prod",
            "yarn": "yarn install --frozen-lockfile --production",
            "bun": "bun install --frozen-lockfile --production",
        }.get(service.package_manager, "npm ci --omit=dev")
    @staticmethod
    def _workspace_dockerfile(service: ServiceSpec) -> str:
        """One image for the whole workspace. Every service runs from it."""
        port = service.port or 3000
        install = service.install_command or "npm ci"
        build = f"RUN {service.build_command}" if service.build_command else "# The workspace has no build script."
        build_env = generator_class()._build_env_docker(service, 12)
        production = generator_class()._production_install(service)
        command = json.dumps(generator_class()._node_command(service))
        return textwrap.dedent(
            f"""
            # Written by the deployment agent.

            FROM node:20-alpine AS build
            WORKDIR /app
            COPY . .
            RUN {install}
            # Runtime values come from Secrets Manager.
            # These placeholders only keep the build parseable.
            {build_env}
            {build}
            # Keep what the build produced; swap the dependencies for runtime ones.
            RUN find . -name node_modules -type d -prune -exec rm -rf {{}} + \\
             && {production}

            FROM node:20-alpine AS runtime
            WORKDIR /app
            ENV NODE_ENV=production
            ENV PORT={port}

            # Not root. A container that is compromised should not also be
            # privileged inside its own filesystem.
            COPY --from=build --chown=node:node /app ./
            USER node
            EXPOSE {port}
            CMD {command}
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
                         contract: EnvironmentContract | None = None,
                         companions: list[ServiceSpec] | tuple = ()) -> dict:
        """The Fargate task definition, rendered by the workflow at deploy time.

        A workspace's other services are more containers in the same task. They
        share its network namespace, so the gateway still finds each one on the
        loopback port it defaults to, exactly as on a single machine."""
        port = service.port or 3000
        entries = generator_class()._runtime_secret_entries(contract)
        secrets = [
            {"name": entry.name, "valueFrom": f"__RUNTIME_SECRET_ARN__:{entry.name}::"}
            for entry in entries
        ]
        logging = {
            "logDriver": "awslogs",
            "options": {
                "awslogs-group": f"/deployment-agent/{plan.project_slug}",
                "awslogs-region": "__AWS_REGION__",
                "awslogs-stream-prefix": "app",
            },
        }
        environment = [
            {"name": "NODE_ENV", "value": "production"},
            {"name": "PORT", "value": str(port)},
            {"name": "HOSTNAME", "value": "0.0.0.0"},
        ]
        if service.framework != "nextjs":
            # What the gateway listens on; see _workspace_patches.
            environment.append({"name": "HOST", "value": "0.0.0.0"})
        containers = [
            {
                "name": f"{plan.project_slug}-app",
                "image": "__IMAGE__",
                "essential": True,
                "portMappings": [{"containerPort": port, "protocol": "tcp"}],
                "environment": environment,
                "secrets": secrets,
                "logConfiguration": logging,
            }
        ]
        for companion in companions:
            containers.append({
                "name": f"{plan.project_slug}-{companion.name}",
                "image": "__IMAGE__",
                # A service that stops takes the task with it, and ECS starts a
                # new one, as systemd restarts it on EC2.
                "essential": True,
                "command": generator_class()._node_command(companion),
                "workingDirectory": f"/app/{companion.root}" if companion.root else "/app",
                # No PORT: the one public port belongs to the gateway.
                "environment": [{"name": "NODE_ENV", "value": "production"}],
                "secrets": secrets,
                "logConfiguration": logging,
            })
        return {
            "family": f"{plan.project_slug}-task",
            "networkMode": "awsvpc",
            "requiresCompatibilities": ["FARGATE"],
            "cpu": "256",
            # Room for a Node.js process per service, not one.
            "memory": "1024" if companions else "512",
            "executionRoleArn": "__EXECUTION_ROLE_ARN__",
            "taskRoleArn": "__TASK_ROLE_ARN__",
            "containerDefinitions": containers,
        }
    @staticmethod
    def _release_script(service: ServiceSpec, contract: EnvironmentContract | None = None,
                        companions: list[ServiceSpec] | tuple = ()) -> str:
        """The script SSM Run Command executes on the instance for each release."""
        contract = contract or EnvironmentContract([])
        secret_names = [entry.name for entry in generator_class()._runtime_secret_entries(contract)]

        allowed = json.dumps(secret_names)
        units = [*(f"app-{companion.name}" for companion in companions), "nextjs"]
        restart = " ".join(units)
        journal = " ".join(f"-u {unit}" for unit in units)
        companion_checks = "\n".join(
            f'  curl -fsS --max-time 3 "http://127.0.0.1:{c.port}{c.health_path}" >/dev/null || return 1'
            for c in companions)
        return textwrap.dedent(
            f"""
            #!/usr/bin/env bash
            # Deployment Agent release script. Runs on the EC2 instance via SSM.
            # Usage: BUCKET=... SHA=... SECRET_ID=... release.sh
            set -euo pipefail
            umask 077

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

            __COMPANION_UNITS__
            echo "==> Restarting service"
            systemctl restart {restart}

            echo "==> Waiting for health check"
            all_services_healthy() {{
              curl -fsS --max-time 5 "http://127.0.0.1:$PORT$HEALTH_PATH" >/dev/null || return 1
            __COMPANION_CHECKS__
              return 0
            }}
            for attempt in $(seq 1 30); do
              if all_services_healthy; then
                echo "Health check passed on attempt $attempt"
                # Keep the five most recent releases so rollback has somewhere to go.
                ls -1dt "$RELEASES"/*/ 2>/dev/null | tail -n +6 | xargs -r rm -rf
                echo "$SHA" > "$SHARED/current-sha"
                exit 0
              fi
              sleep 2
            done

            echo "Health check failed; dumping recent service logs" >&2
            journalctl {journal} -n 50 --no-pager >&2 || true
            exit 1
            """
        ).lstrip().replace("__COMPANION_UNITS__\n", generator_class()._companion_units(companions)).replace("__COMPANION_CHECKS__", companion_checks)
    @staticmethod
    def _companion_units(companions: list[ServiceSpec] | tuple) -> str:
        """systemd units for the services that run beside the gateway.

        Every release writes them, not only the first boot, so a service added
        later gets one too. PartOf ties each to nextjs.service: restarting the
        main unit, which is all rollback does, restarts them with it."""
        if not companions:
            return ""
        blocks = ['echo "==> Installing the services that run beside the gateway"']
        for companion in companions:
            directory = f"/opt/app/current/{companion.root}" if companion.root else "/opt/app/current"
            entry = generator_class()._node_command(companion)[-1]
            blocks.append(textwrap.dedent(
                f"""
                # Override the gateway port only for this internal service.
                grep -vE '^(PORT|SERVICE_PORT|HOSTNAME)=' /opt/app/shared/.env > /opt/app/shared/{companion.name}.env || true
                printf 'PORT={companion.port}\\nSERVICE_PORT={companion.port}\\nHOSTNAME=127.0.0.1\\n' >> /opt/app/shared/{companion.name}.env
                chown root:nextjs /opt/app/shared/{companion.name}.env
                chmod 0640 /opt/app/shared/{companion.name}.env
                cat > /etc/systemd/system/app-{companion.name}.service <<'UNIT'
                [Unit]
                Description={companion.name}
                After=network-online.target
                Wants=network-online.target
                PartOf=nextjs.service

                [Service]
                Type=simple
                User=nextjs
                Group=nextjs
                WorkingDirectory={directory}
                EnvironmentFile=/opt/app/shared/{companion.name}.env
                ExecStart=/usr/bin/node {directory}/{entry}
                Restart=always
                RestartSec=5
                NoNewPrivileges=true
                PrivateTmp=true
                ProtectSystem=strict
                ProtectHome=true
                ReadWritePaths=/opt/app /var/log/app
                StandardOutput=append:/var/log/app/app.log
                StandardError=append:/var/log/app/app.log

                [Install]
                WantedBy=multi-user.target
                UNIT
                """
            ).strip())
        names = " ".join(f"app-{companion.name}" for companion in companions)
        blocks.append(f"systemctl daemon-reload\nsystemctl enable {names}")
        return "\n".join(blocks) + "\n\n"
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
        toolchain = generator_class()._toolchain(service)
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
