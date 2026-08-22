"""In-app AWS onboarding: SSO device flow, quota preflight, permission preflight.

The point of this module is that the operator never leaves the dashboard and
never types a credential. The SSO device flow yields short-lived credentials
that live only in the in-memory vault; the browser only ever sees a verification
URL, a user code, and the resulting account/role names.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .credentials import CREDENTIAL_VAULT
from .security import redact_text


CLIENT_NAME = "deployment-agent"
CLIENT_TYPE = "public"
SSO_SCOPES = ["sso:account:access"]


QUOTA_CHECKS = (
    {
        "key": "vpc",
        "label": "VPCs per Region",
        "service_code": "vpc",
        "quota_code": "L-F678F1CE",
        "needed": 1,
    },
    {
        "key": "eip",
        "label": "Elastic IPs per Region",
        "service_code": "ec2",
        "quota_code": "L-0263D0A3",
        "needed": 1,
    },
    {
        "key": "vcpu",
        "label": "Running On-Demand Standard instances (vCPU)",
        "service_code": "ec2",
        "quota_code": "L-1216C47A",
        "needed": 2,
    },
)


ECS_QUOTA_CHECKS = (
    {
        "key": "vpc",
        "label": "VPCs per Region",
        "service_code": "vpc",
        "quota_code": "L-F678F1CE",
        "needed": 1,
    },
    {
        "key": "fargate_vcpu",
        "label": "Fargate On-Demand vCPU",
        "service_code": "fargate",
        "quota_code": "L-3032A538",
        "needed": 1,
    },
    {
        "key": "alb",
        "label": "Application Load Balancers per Region",
        "service_code": "elasticloadbalancing",
        "quota_code": "L-53DA6B97",
        "needed": 1,
    },
)


REQUIRED_ACTIONS = (
    "sts:GetCallerIdentity",
    "cloudformation:CreateChangeSet",
    "cloudformation:ExecuteChangeSet",
    "cloudformation:DescribeChangeSet",
    "cloudformation:DescribeStacks",
    "cloudformation:DescribeStackEvents",
    "cloudformation:DeleteStack",
    "ec2:DescribeVpcs",
    "ec2:DescribeSubnets",
    "ec2:DescribeInstances",
    "ec2:CreateVpc",
    "ec2:CreateSubnet",
    "ec2:CreateInternetGateway",
    "ec2:CreateSecurityGroup",
    "ec2:AuthorizeSecurityGroupIngress",
    "ec2:AllocateAddress",
    "ec2:AssociateAddress",
    "ec2:RunInstances",
    "ec2:CreateTags",
    "iam:CreateRole",
    "iam:PutRolePolicy",
    "iam:AttachRolePolicy",
    "iam:CreateInstanceProfile",
    "iam:AddRoleToInstanceProfile",
    "iam:PassRole",
    "iam:CreateOpenIDConnectProvider",
    "iam:ListOpenIDConnectProviders",
    "s3:CreateBucket",
    "s3:PutEncryptionConfiguration",
    "s3:PutBucketVersioning",
    "s3:PutBucketPublicAccessBlock",
    "s3:PutLifecycleConfiguration",
    "secretsmanager:CreateSecret",
    "secretsmanager:PutSecretValue",
    "logs:CreateLogGroup",
    "logs:PutRetentionPolicy",
    "logs:FilterLogEvents",

    "ssm:GetParameters",
    "ssm:SendCommand",
    "ssm:GetCommandInvocation",
    "ssm:ListCommandInvocations",
)


_SHARED_ACTIONS = (
    "sts:GetCallerIdentity",
    "cloudformation:CreateChangeSet",
    "cloudformation:ExecuteChangeSet",
    "cloudformation:DescribeChangeSet",
    "cloudformation:DescribeStacks",
    "cloudformation:DescribeStackEvents",
    "cloudformation:DeleteStack",
    "ec2:DescribeVpcs",
    "ec2:DescribeSubnets",
    "ec2:CreateVpc",
    "ec2:CreateSubnet",
    "ec2:CreateInternetGateway",
    "ec2:CreateSecurityGroup",
    "ec2:AuthorizeSecurityGroupIngress",
    "ec2:CreateTags",
    "iam:CreateRole",
    "iam:PutRolePolicy",
    "iam:AttachRolePolicy",
    "iam:PassRole",
    "iam:CreateOpenIDConnectProvider",
    "iam:ListOpenIDConnectProviders",
    "secretsmanager:CreateSecret",
    "secretsmanager:PutSecretValue",
    "logs:CreateLogGroup",
    "logs:PutRetentionPolicy",
    "logs:FilterLogEvents",
)


ECS_REQUIRED_ACTIONS = _SHARED_ACTIONS + (
    "ecr:CreateRepository",
    "ecr:DescribeRepositories",
    "ecr:GetAuthorizationToken",
    "ecr:PutLifecyclePolicy",
    "ecr:ListImages",
    "ecr:BatchDeleteImage",
    "ecr:DeleteRepository",
    "ecs:CreateCluster",
    "ecs:CreateService",
    "ecs:RegisterTaskDefinition",
    "ecs:UpdateService",
    "ecs:DescribeServices",
    "ecs:DescribeClusters",
    "ecs:DeleteService",
    "ecs:DeleteCluster",
    "elasticloadbalancing:CreateLoadBalancer",
    "elasticloadbalancing:CreateTargetGroup",
    "elasticloadbalancing:CreateListener",
    "elasticloadbalancing:DescribeLoadBalancers",
    "elasticloadbalancing:DeleteLoadBalancer",
)


def actions_for(target) -> tuple[str, ...]:
    """The IAM actions a preflight should simulate for this target.

    Target-blind before this: an ECS run was told its account was ready on the
    strength of `ec2:RunInstances`, then failed ten minutes into a
    CloudFormation apply at the first `ecr:CreateRepository`.
    """
    from deployment_agent.models import DeploymentTarget

    if target == DeploymentTarget.AWS_ECS:
        return ECS_REQUIRED_ACTIONS
    if target == DeploymentTarget.VERCEL:
        return ()
    return REQUIRED_ACTIONS


def quotas_for(target) -> tuple[dict[str, Any], ...]:
    """The service quotas this target consumes."""
    from deployment_agent.models import DeploymentTarget

    if target == DeploymentTarget.AWS_ECS:
        return ECS_QUOTA_CHECKS
    if target == DeploymentTarget.VERCEL:
        return ()
    return QUOTA_CHECKS


def _boto3():
    try:
        import boto3
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("boto3 is not installed. Run setup.ps1.") from exc
    return boto3


def _unsigned_client(service: str, region: str):
    """sso-oidc and sso device-flow calls are unauthenticated by design."""
    from botocore import UNSIGNED
    from botocore.config import Config

    return _boto3().client(service, region_name=region, config=Config(signature_version=UNSIGNED))


@dataclass
class SsoFlow:
    flow_id: str
    region: str
    start_url: str
    client_id: str = ""
    client_secret: str = ""
    device_code: str = ""
    interval: int = 5
    expires_at: float = 0.0
    token_reference: str = ""
    created_at: float = field(default_factory=time.time)


class SsoDeviceFlowManager:
    """Drives the AWS IAM Identity Center device authorization flow.

    Secrets (client secret, access token, role credentials) are held in the
    credential vault and referenced by opaque handles; nothing sensitive is
    returned to the browser.
    """

    def __init__(self, ttl_seconds: int = 900):
        self.ttl_seconds = ttl_seconds
        self._flows: dict[str, SsoFlow] = {}
        self._lock = threading.RLock()

    def start(self, start_url: str, region: str) -> dict[str, Any]:
        start_url = str(start_url or "").strip()
        region = str(region or "").strip()
        if not start_url.startswith("https://"):
            raise ValueError("An IAM Identity Center start URL beginning with https:// is required")
        if not region:
            raise ValueError("An AWS region is required")
        oidc = _unsigned_client("sso-oidc", region)
        registration = oidc.register_client(clientName=CLIENT_NAME, clientType=CLIENT_TYPE, scopes=SSO_SCOPES)
        authorization = oidc.start_device_authorization(
            clientId=registration["clientId"],
            clientSecret=registration["clientSecret"],
            startUrl=start_url,
        )
        import secrets as _secrets

        flow = SsoFlow(
            flow_id="sso_" + _secrets.token_urlsafe(18),
            region=region,
            start_url=start_url,
            client_id=registration["clientId"],
            client_secret=registration["clientSecret"],
            device_code=authorization["deviceCode"],
            interval=int(authorization.get("interval", 5)) or 5,
            expires_at=time.time() + int(authorization.get("expiresIn", 600)),
        )
        with self._lock:
            self._prune_locked()
            self._flows[flow.flow_id] = flow
        return {
            "flow_id": flow.flow_id,
            "verification_uri_complete": authorization.get("verificationUriComplete", ""),
            "verification_uri": authorization.get("verificationUri", ""),
            "user_code": authorization.get("userCode", ""),
            "interval": flow.interval,
            "expires_in": int(authorization.get("expiresIn", 600)),
        }

    def poll(self, flow_id: str) -> dict[str, Any]:
        """One non-blocking poll. The UI calls this on the interval AWS gave us."""
        flow = self._flow(flow_id)
        if flow.token_reference:
            return {"status": "complete", "accounts": self.list_accounts(flow_id)}
        if time.time() > flow.expires_at:
            raise ValueError("The AWS sign-in request expired; start the connection again")
        oidc = _unsigned_client("sso-oidc", flow.region)
        try:
            token = oidc.create_token(
                clientId=flow.client_id,
                clientSecret=flow.client_secret,
                grantType="urn:ietf:params:oauth:grant-type:device_code",
                deviceCode=flow.device_code,
            )
        except Exception as exc:
            name = type(exc).__name__

            if "AuthorizationPending" in name or "SlowDown" in name:
                return {"status": "pending"}
            if "ExpiredToken" in name:
                raise ValueError("The AWS sign-in request expired; start the connection again") from exc
            raise ValueError(redact_text(str(exc))) from exc
        reference = CREDENTIAL_VAULT.put(credentials={"access_token": token["accessToken"]})
        with self._lock:
            flow.token_reference = reference
        return {"status": "complete", "accounts": self.list_accounts(flow_id)}

    def list_accounts(self, flow_id: str) -> list[dict[str, str]]:
        flow = self._flow(flow_id)
        token = self._access_token(flow)
        sso = _unsigned_client("sso", flow.region)
        accounts: list[dict[str, str]] = []
        paginator = sso.get_paginator("list_accounts")
        for page in paginator.paginate(accessToken=token):
            for item in page.get("accountList", []):
                accounts.append(
                    {
                        "account_id": item.get("accountId", ""),
                        "account_name": item.get("accountName", ""),
                        "email": item.get("emailAddress", ""),
                    }
                )
        return sorted(accounts, key=lambda item: item["account_name"].lower())

    def list_roles(self, flow_id: str, account_id: str) -> list[str]:
        flow = self._flow(flow_id)
        token = self._access_token(flow)
        sso = _unsigned_client("sso", flow.region)
        roles: list[str] = []
        paginator = sso.get_paginator("list_account_roles")
        for page in paginator.paginate(accessToken=token, accountId=str(account_id)):
            roles.extend(item.get("roleName", "") for item in page.get("roleList", []))
        return sorted(name for name in roles if name)

    def select(self, flow_id: str, account_id: str, role_name: str) -> dict[str, Any]:
        """Exchange the SSO token for role credentials and vault them."""
        flow = self._flow(flow_id)
        token = self._access_token(flow)
        sso = _unsigned_client("sso", flow.region)
        role = sso.get_role_credentials(
            roleName=str(role_name), accountId=str(account_id), accessToken=token
        )["roleCredentials"]
        reference = CREDENTIAL_VAULT.put(
            credentials={
                "aws_access_key_id": role["accessKeyId"],
                "aws_secret_access_key": role["secretAccessKey"],
                "aws_session_token": role["sessionToken"],
                "region": flow.region,
            }
        )
        return {
            "credential_reference": reference,
            "account_id": str(account_id),
            "role_name": str(role_name),
            "region": flow.region,

            "expires_at": int(role.get("expiration", 0)) // 1000,
        }

    def start_url(self, flow_id: str) -> str:
        return self._flow(flow_id).start_url

    def forget(self, flow_id: str) -> None:
        with self._lock:
            flow = self._flows.pop(flow_id, None)
        if flow and flow.token_reference:
            CREDENTIAL_VAULT.clear(flow.token_reference)

    def _flow(self, flow_id: str) -> SsoFlow:
        with self._lock:
            self._prune_locked()
            flow = self._flows.get(str(flow_id))
        if not flow:
            raise ValueError("The AWS sign-in session expired; start the connection again")
        return flow

    def _access_token(self, flow: SsoFlow) -> str:
        if not flow.token_reference:
            raise ValueError("AWS sign-in has not completed yet")
        return CREDENTIAL_VAULT.get(flow.token_reference).credentials["access_token"]

    def _prune_locked(self) -> None:
        cutoff = time.time() - self.ttl_seconds
        for flow_id, flow in list(self._flows.items()):
            if flow.created_at < cutoff:
                self._flows.pop(flow_id, None)
                if flow.token_reference:
                    CREDENTIAL_VAULT.clear(flow.token_reference)


def session_from_reference(credential_reference: str, region: str = ""):
    """Build a boto3 session from vaulted short-lived credentials."""
    bundle = CREDENTIAL_VAULT.get(credential_reference)
    values = bundle.credentials
    return _boto3().Session(
        aws_access_key_id=values.get("aws_access_key_id"),
        aws_secret_access_key=values.get("aws_secret_access_key"),
        aws_session_token=values.get("aws_session_token"),
        region_name=region or values.get("region") or None,
    )


def persist_sso_profile(
    profile_name: str,
    start_url: str,
    region: str,
    account_id: str,
    role_name: str,
    deployment_region: str = "",
) -> str:
    """Write an sso-session profile to ~/.aws/config, exactly as `aws configure sso` does.

    Only non-secret routing information is written: start URL, region, account
    id and role name. Tokens stay in the AWS CLI's own cache. This exists so
    monitoring can refresh credentials after the vaulted hour expires; it is
    opt-in because it modifies the user's AWS config file.
    """
    import configparser
    from pathlib import Path

    profile_name = str(profile_name or "deployment-agent").strip() or "deployment-agent"
    config_path = Path.home() / ".aws" / "config"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    parser = configparser.ConfigParser()
    if config_path.is_file():
        parser.read(config_path, encoding="utf-8")
    session_section = f"sso-session {profile_name}"
    profile_section = f"profile {profile_name}"
    for section in (session_section, profile_section):
        if not parser.has_section(section):
            parser.add_section(section)
    parser[session_section]["sso_start_url"] = start_url
    parser[session_section]["sso_region"] = region
    parser[session_section]["sso_registration_scopes"] = "sso:account:access"
    parser[profile_section]["sso_session"] = profile_name
    parser[profile_section]["sso_account_id"] = str(account_id)
    parser[profile_section]["sso_role_name"] = str(role_name)

    parser[profile_section]["region"] = deployment_region or region

    parser.remove_option(profile_section, "login_session")
    with config_path.open("w", encoding="utf-8") as handle:
        parser.write(handle)
    return profile_name


def check_quotas(session, target=None) -> list[dict[str, Any]]:
    """Compare the quotas this target's stack consumes against current usage.

    `target` defaults to None so the existing call sites keep meaning EC2.
    """
    checks = quotas_for(target) if target is not None else QUOTA_CHECKS
    if not checks:
        return []
    quotas = session.client("service-quotas")
    ec2 = session.client("ec2")
    usage: dict[str, int | None] = {"vpc": None, "eip": None, "vcpu": None}
    try:
        usage["vpc"] = len(ec2.describe_vpcs().get("Vpcs", []))
    except Exception:
        pass
    try:
        usage["eip"] = len(ec2.describe_addresses().get("Addresses", []))
    except Exception:
        pass

    results: list[dict[str, Any]] = []
    for check in checks:
        entry: dict[str, Any] = {
            "key": check["key"],
            "label": check["label"],
            "service_code": check["service_code"],
            "quota_code": check["quota_code"],
            "needed": check["needed"],
            "limit": None,
            "used": usage.get(check["key"]),
            "status": "unknown",
            "message": "",
        }
        try:
            value = quotas.get_service_quota(
                ServiceCode=check["service_code"], QuotaCode=check["quota_code"]
            )["Quota"]["Value"]
            entry["limit"] = int(value)
        except Exception as exc:
            entry["message"] = redact_text(str(exc))
            results.append(entry)
            continue
        limit = entry["limit"] or 0
        used = entry["used"]
        if limit < check["needed"]:
            entry["status"] = "failed"
            entry["message"] = f"Quota is {limit}; the deployment needs at least {check['needed']}."
        elif used is not None and (limit - used) < check["needed"]:
            entry["status"] = "failed"
            entry["message"] = f"{used} of {limit} already in use; no headroom for this deployment."
        else:
            entry["status"] = "passed"
        results.append(entry)
    return results


def request_quota_increase(session, service_code: str, quota_code: str, desired: float) -> dict[str, Any]:
    response = session.client("service-quotas").request_service_quota_increase(
        ServiceCode=str(service_code), QuotaCode=str(quota_code), DesiredValue=float(desired)
    )
    request = response.get("RequestedQuota", {})
    return {
        "id": request.get("Id", ""),
        "status": request.get("Status", ""),
        "desired": request.get("DesiredValue"),
        "quota_code": request.get("QuotaCode", ""),
    }


def check_permissions(session, actions: tuple[str, ...] = REQUIRED_ACTIONS) -> dict[str, Any]:
    """Ask IAM whether the signed-in principal may perform each required action.

    SimulatePrincipalPolicy is itself an IAM permission; when it is denied the
    result is reported as unknown rather than as a deployment blocker, because a
    principal can be fully authorized to deploy yet unable to introspect itself.
    """
    identity = session.client("sts").get_caller_identity()
    arn = identity.get("Arn", "")

    source = arn
    if ":assumed-role/" in arn:
        account = identity.get("Account", "")
        role_name = arn.split(":assumed-role/")[1].split("/")[0]
        source = f"arn:aws:iam::{account}:role/{role_name}"
    allowed: list[str] = []
    denied: list[str] = []
    try:
        iam = session.client("iam")
        for index in range(0, len(actions), 25):
            batch = list(actions[index : index + 25])
            response = iam.simulate_principal_policy(PolicySourceArn=source, ActionNames=batch)
            for item in response.get("EvaluationResults", []):
                name = item.get("EvalActionName", "")
                if item.get("EvalDecision") == "allowed":
                    allowed.append(name)
                else:
                    denied.append(name)
    except Exception as exc:
        return {
            "status": "unknown",
            "principal": source,
            "allowed": [],
            "denied": [],
            "message": redact_text(
                "Permission simulation is unavailable for this identity "
                f"({type(exc).__name__}); deployment will surface any missing permission directly."
            ),
        }
    return {
        "status": "passed" if not denied else "failed",
        "principal": source,
        "allowed": sorted(allowed),
        "denied": sorted(denied),
        "message": "" if not denied else f"{len(denied)} required action(s) are denied for this identity.",
    }


def bootstrap_role_template(trusted_principal_arn: str = "") -> str:
    """CloudFormation an administrator applies once to grant deploy permissions.

    Emitted so an operator without IAM rights can hand a reviewable template to
    whoever does, instead of a prose list of permissions.
    """
    import textwrap

    principal = str(trusted_principal_arn or "").strip()
    header = textwrap.dedent(
        """
        AWSTemplateFormatVersion: '2010-09-09'
        Description: Deployment Agent bootstrap permissions role

        Parameters:
          TrustedPrincipalArn:
            Type: String
            Default: __PRINCIPAL__
            Description: IAM principal (user or role) allowed to assume this deployment role

        Resources:
          DeploymentAgentRole:
            Type: AWS::IAM::Role
            Properties:
              RoleName: deployment-agent-bootstrap
              AssumeRolePolicyDocument:
                Version: '2012-10-17'
                Statement:
                  - Effect: Allow
                    Principal: {AWS: !Ref TrustedPrincipalArn}
                    Action: 'sts:AssumeRole'
              Policies:
                - PolicyName: DeploymentAgentBootstrap
                  PolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Resource: '*'
                        Action:
        __ACTIONS__

        Outputs:
          RoleArn:
            Value: !GetAtt DeploymentAgentRole.Arn
        """
    ).lstrip()
    actions = "\n".join(f"                          - {name}" for name in sorted(REQUIRED_ACTIONS))
    return header.replace("__ACTIONS__", actions).replace("__PRINCIPAL__", principal or "''")
