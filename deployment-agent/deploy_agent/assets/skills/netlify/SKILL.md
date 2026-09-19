---
name: netlify
description: Deploy and diagnose this project's netlify delivery using its selected account and recorded identities.
---

Use the owner's NETLIFY_AUTH_TOKEN and recorded site ID. Create a site only for the selected team/name when no site exists. Next.js uses the maintained Netlify adapter; keep .next as the publish directory and the package-manager build command. Use netlify deploy --build --prod --site <id>; inspect CLI and failed deploy logs before repairing source. Set runtime variables in the site environment, not client code or committed files. Redeploy the same site ID. Do not delete sites, alter DNS, or use anonymous deployments during repair.

Reference: https://docs.netlify.com/api-and-cli-guides/cli-guides/get-started-with-cli/ and https://docs.netlify.com/build/frameworks/framework-setup-guides/nextjs/overview/
