from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import shutil
import subprocess
from typing import Callable


@dataclass(frozen=True)
class IntegrationStatus:
    provider: str
    connected: bool
    state: str
    message: str
    setup_url: str
    required_environment: list[str]
    command: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class IntegrationService:
    """Read-only integration diagnostics.

    Credentials are never returned to the frontend. A provider is considered
    connected only when the required local CLI session or environment variables
    are available to the Agent 4 backend process.
    """

    def statuses(self) -> dict:
        items = [
            self._github(),
            self._token_provider(
                provider="snyk",
                token_names=["SNYK_TOKEN"],
                setup_url="https://app.snyk.io/account",
                command="snyk auth",
            ),
            self._token_provider(
                provider="sonarcloud",
                token_names=["SONAR_TOKEN"],
                setup_url="https://sonarcloud.io/account/security",
            ),
            self._aws(),
            self._token_provider(
                provider="vercel",
                token_names=["VERCEL_TOKEN"],
                setup_url="https://vercel.com/account/tokens",
                command="vercel login",
            ),
        ]
        return {"items": [item.to_dict() for item in items]}

    def _github(self) -> IntegrationStatus:
        gh = shutil.which("gh")
        if not gh:
            return IntegrationStatus(
                provider="github",
                connected=False,
                state="CLI_MISSING",
                message="GitHub CLI is not installed on the backend machine.",
                setup_url="https://github.com/cli/cli#installation",
                required_environment=[],
                command="gh auth login --hostname github.com --git-protocol https --web",
            )

        try:
            result = subprocess.run(
                [gh, "auth", "status", "--hostname", "github.com"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return IntegrationStatus(
                provider="github",
                connected=False,
                state="CHECK_FAILED",
                message=f"Unable to check GitHub CLI authentication: {exc}",
                setup_url="https://github.com/login/device",
                required_environment=[],
                command="gh auth login --hostname github.com --git-protocol https --web",
            )

        connected = result.returncode == 0
        details = (result.stdout or result.stderr).strip()
        return IntegrationStatus(
            provider="github",
            connected=connected,
            state="CONNECTED" if connected else "AUTH_REQUIRED",
            message=details or ("GitHub CLI authenticated." if connected else "GitHub CLI authentication is required."),
            setup_url="https://github.com/login/device",
            required_environment=[],
            command="gh auth login --hostname github.com --git-protocol https --web",
        )

    def _aws(self) -> IntegrationStatus:
        required = ["AWS_ROLE_ARN or AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY", "AWS_REGION"]
        has_role = bool(os.getenv("AWS_ROLE_ARN"))
        has_keys = bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"))
        has_region = bool(os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"))
        connected = (has_role or has_keys) and has_region
        return IntegrationStatus(
            provider="aws",
            connected=connected,
            state="CONNECTED" if connected else "CONFIG_REQUIRED",
            message="AWS deployment credentials and region are configured." if connected else "Configure GitHub OIDC/AWS role credentials and AWS_REGION.",
            setup_url="https://console.aws.amazon.com/iam/home#/roles",
            required_environment=required,
            command="aws sts get-caller-identity",
        )

    def _token_provider(
        self,
        provider: str,
        token_names: list[str],
        setup_url: str,
        command: str = "",
    ) -> IntegrationStatus:
        connected = all(bool(os.getenv(name)) for name in token_names)
        return IntegrationStatus(
            provider=provider,
            connected=connected,
            state="CONNECTED" if connected else "TOKEN_REQUIRED",
            message=f"{provider.title()} credentials are configured." if connected else f"Add {', '.join(token_names)} to the backend or GitHub Actions secrets.",
            setup_url=setup_url,
            required_environment=token_names,
            command=command,
        )
