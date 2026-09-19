from __future__ import annotations

from .deployer_shared import *
from .deployer_shared import _PERSISTED_ACTIVE_STATES
from .deployer_core import DeploymentCoreMixin
from .deployer_prepare import DeploymentPrepareMixin
from .deployer_aws import DeploymentAwsMixin
from .deployer_git import DeploymentGitMixin
from .deployer_lifecycle import DeploymentLifecycleMixin
from .deployer_hosted import DeploymentHostedMixin
from deployment_agent import owner_credentials


class DeploymentAgent(DeploymentCoreMixin, DeploymentPrepareMixin, DeploymentAwsMixin, DeploymentGitMixin, DeploymentLifecycleMixin, DeploymentHostedMixin):
    def __init__(self, store: StateStore, emit: Callable[..., object]):
        self.store = store
        self.emit = emit
        # Whose accounts each run signs in with (owner_credentials.py).
        self._owners: dict[str, str] = {}
    def start_deployment(
        self,
        run_id: str,
        aws_profile: str,
        region: str,
        mongodb_uri: str,
        approved: bool,
        credential_reference: str = "",
        vercel_token: str = "",
        owner: str = "",
    ) -> None:
        _run, project_key = self._validate_request(run_id, mongodb_uri, approved)
        self._reserve_project(run_id, project_key)
        self._owners[run_id] = str(owner or "")
        threading.Thread(
            target=owner_credentials.carry(self._deploy_reserved, owner),
            args=(run_id, aws_profile, region, mongodb_uri, project_key, credential_reference, vercel_token),
            daemon=True,
        ).start()
