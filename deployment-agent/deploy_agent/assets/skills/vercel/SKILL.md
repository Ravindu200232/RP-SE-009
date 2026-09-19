---
name: vercel
description: Deploy and diagnose this project's vercel delivery using its selected account and recorded identities.
---

Use the selected scope and recorded project identity. Link with vercel link --yes --project <name> --scope <scope> when a scope is supplied. Supply authentication from owner credentials, never generated files. Pull production settings, build with vercel build --prod, then deploy with vercel deploy --prebuilt --prod. Read failing build output and repair the isolated project before retry. Reuse the existing project on redeploy. Check the live homepage and health endpoint before marking success. Never remove a project, change DNS, or change teams during repair.

Reference: https://vercel.com/docs/cli/deploy and https://vercel.com/docs/cli/global-options
