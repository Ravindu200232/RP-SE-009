"""Regression check for the in-app AWS SSO -> deployment session bridge."""
from __future__ import annotations

import time

from deploy_agent.deployment_agent.aws_onboarding import (
    active_sso_identities,
    credential_reference_for_profile,
    profile_status,
    remember_sso_selection,
    session_for_profile,
)
from deploy_agent.deployment_agent.credentials import CREDENTIAL_VAULT


def main() -> None:
    profile = "contract-test-profile"
    reference = CREDENTIAL_VAULT.put(
        credentials={
            "aws_access_key_id": "ASIATESTONLY",
            "aws_secret_access_key": "test-secret-not-real",
            "aws_session_token": "test-session-not-real",
            "region": "us-east-1",
        }
    )
    remember_sso_selection(
        profile,
        {
            "credential_reference": reference,
            "account_id": "000000000000",
            "role_name": "ContractRole",
            "region": "us-east-1",
            "expires_at": int(time.time()) + 600,
        },
    )

    assert credential_reference_for_profile(profile) == reference
    assert active_sso_identities()[profile]["role_name"] == "ContractRole"
    assert profile_status(profile, "us-east-1")["authenticated"] is True

    credentials = session_for_profile(profile, "us-east-1").get_credentials()
    assert credentials is not None
    assert credentials.get_frozen_credentials().access_key == "ASIATESTONLY"

    CREDENTIAL_VAULT.clear(reference)
    assert credential_reference_for_profile(profile) == ""
    print("AWS in-app SSO session bridge: OK")


if __name__ == "__main__":
    main()
