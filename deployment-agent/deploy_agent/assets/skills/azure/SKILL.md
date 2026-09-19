---
name: azure
description: Deploy and diagnose this project's azure delivery using its selected account and recorded identities.
---

Use the owner's service principal, subscription and isolated Azure CLI configuration. Preserve the recorded resource group, App Service plan and webapp name on redeploy. Use the interview location and SKU; do not escalate sizes on failure. Build before zip delivery with azure/webapps-deploy. Next.js standalone packaging must include .next/static and public beside server.js. Configure the startup command and runtime variables on App Service. Read webapp state and deployment logs, repair source and validate before retry. Never delete a resource group, modify unrelated apps, broaden role assignments or rotate databases during repair.

Reference: https://learn.microsoft.com/en-us/azure/app-service/deploy-github-actions and https://learn.microsoft.com/en-us/cli/azure/webapp
