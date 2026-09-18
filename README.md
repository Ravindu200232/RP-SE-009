# AgentForge installer

`AgentForge-Setup-2.0.1.exe` — the Windows installer for AgentForge.

This branch holds the installer and nothing else. The project that builds it
lives outside this repository, so the application's history and a 78 MB binary
never sit in the same commits.

## What it does on first run

It checks the machine, installs only what is missing, and shows each step as it
goes:

| Tool | Why |
| --- | --- |
| Node.js, npm | the Studio and its packages |
| Python 3.11+ | the agents and their packages |
| Git | fetching the application |
| Ollama | serves the models |
| GitHub CLI | signing in, and the repository a deployment pushes to |
| Vercel CLI, Netlify CLI | signing in to those from the Deploy screen |
| MongoDB | the local database |

Then it fetches the application from this repository's latest release
(`agentforge-app.zip`) into `%LOCALAPPDATA%\AgentForgepp`, installs the
Python and Studio packages, and registers the Ollama cloud models listed in
`ollama-models.txt` — skipping any the machine already has.

The application is fetched rather than carried, so a fix to the app does not
mean handing everyone a new installer.

## A private repository

The release asset needs a token to read. The installer uses `gh auth token` if
the GitHub CLI is signed in, or `AGENTFORGE_GITHUB_TOKEN` from the environment,
and says which to do if it has neither.
