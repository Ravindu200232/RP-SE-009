---
name: github
description: Deploy and diagnose this project's github delivery using its selected account and recorded identities.
---

Use the selected repository and its default branch. Preserve existing origin and history. Create a repository only if none exists, using the interview name and visibility; do not silently append a name on auth or permission failure. Use gh repo view to confirm identity. Use gh run list and gh run view <id> --log-failed for the exact pushed commit. Read source before edits; fix all related failures together. Commit validated updates and push without force. Branch protection uses a PR and waits for merge. Never change repository visibility, delete repositories, or rewrite history to repair deployment.

Reference: https://cli.github.com/manual/gh_run_view and https://cli.github.com/manual/gh_repo_create
