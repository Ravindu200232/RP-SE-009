---
name: aws
description: Deploy and diagnose this project's aws delivery using its selected account and recorded identities.
---

Use the owner's selected AWS profile and region and project stack name. Read CloudFormation events, ECS service/task diagnostics or SSM release output for the exact deployment. Validate changed infrastructure before delivery. Keep GitHub OIDC subjects scoped to this repository/branch, SSM administration and least privilege. Preserve runtime secrets between releases. Honor the interview instance size and free tier preference; ask before a size increase. Change only project-managed infrastructure through the orchestrator. A failed stack or IAM permission is evidence, never authorization to delete resources, broaden IAM, open SSH, or change databases.

Reference: https://docs.aws.amazon.com/cli/latest/reference/cloudformation/deploy/

For a service workspace, run every detected companion with its own internal port and environment. Collect gateway, companion and database readiness evidence before calling the release healthy. A gateway-only 200 is insufficient. Keep public traffic on nginx/the gateway and internal services private. Diagnose proxy routing, forwarded cookies and failed upstream requests together before one repair. Preserve existing session/signing keys during redeploy. Never execute destructive development seeds in production or copy another project's database; production data initialization must be deliberate and idempotent. Treat an omitted Atlas database name as an isolation error and use the reviewed project's database identity.
