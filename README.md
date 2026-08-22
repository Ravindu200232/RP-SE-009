<div align="center">

<img src="assets/locode.png" alt="AgentForge Logo" width="100" />

# ⚡ AgentForge

**The first fully local AI app builder — powered entirely by your Ollama models.**

![License](https://img.shields.io/badge/license-MIT-22d3ee?style=flat-square)
![Python](https://img.shields.io/badge/python-3.9+-4ade80?style=flat-square&logo=python&logoColor=white)
![Node](https://img.shields.io/badge/node-20_LTS-4ade80?style=flat-square&logo=node.js&logoColor=white)
![Ollama](https://img.shields.io/badge/powered_by-Ollama-a78bfa?style=flat-square)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-22d3ee?style=flat-square)

*No cloud. No API keys. No subscriptions. Just your machine and your imagination.*

<br>

[![Download for macOS](https://img.shields.io/badge/⬇_Download_AgentForge-macOS_DMG-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/locode-dev/locode/releases/download/v1.0.0/AgentForge-v1.0.0-arm64.dmg)

**v1.0.0 · Apple Silicon (arm64)**

</div>

---

## ✨ What is AgentForge?

AgentForge is an open-source, fully local alternative to tools like Lovable or v0 — except the model runs on your machine using Ollama.

It takes an idea the whole way:

```
idea ──▶ SRS ──▶ build ──▶ test ──▶ deploy ──▶ monitor
```

1. **Specify.** An interview turns a one-line idea into a written SRS, with diagrams, exported as a PDF.
2. **Build.** A plan is written, then a complete **Next.js + Tailwind + MongoDB** application — routes, pages, database access and sign-in with Better Auth.
3. **Test.** Vitest unit tests and Playwright end-to-end flows are generated and run, and failures are fed back to a repair loop rather than reported at you.
4. **Deploy.** One button to **Vercel**, **AWS EC2** or **AWS ECS Fargate**. The infrastructure is generated as CloudFormation, the image is built in GitHub Actions, and nothing needs Docker installed locally.
5. **Watch.** A ten-tab dashboard over the running deployment: the pipeline with per-stage timings, the repository, CI/CD with the generated YAML, infrastructure, IAM and security, logs, live endpoint probes and the masked evidence bundle.

The model never leaves your machine. Deployment is the only step that talks to anyone else, and only to the accounts you connect.

---

## 🏗️ Features

| Feature | Description |
|---|---|
| 📄 **SRS from an interview** | A guided interview becomes a written specification with diagrams, exported as PDF, and hands straight over to the build |
| 🏗️ **Full Project Generation** | Complete Next.js + Tailwind + MongoDB projects, with sign-in wired up, from a plain-English description |
| 🧪 **Generated test suites** | Vitest unit tests and Playwright end-to-end flows, written against the app that was just built |
| 🚀 **One-button deployment** | Vercel, AWS EC2, or AWS ECS Fargate behind a load balancer — infrastructure as generated CloudFormation |
| 📊 **Deployment monitoring** | Ten tabs over the live deployment: pipeline timings, CI/CD, infrastructure, IAM, logs, endpoint probes and evidence |
| 🧹 **Cancel and delete** | Stop a deployment mid-flight, or destroy its cloud resources — the record is archived, never silently dropped |
| ✏️ **Smart Reprompt** | Three modes — patch (instant), modify (targeted), feature (new component) |
| 🧭 **Intent Classification** | Automatically routes your request: text/color tweaks skip the full rebuild cycle |
| 🔧 **Auto-Fix Pipeline** | Playwright + LLM catch and fix errors automatically |
| ➕ **Feature Injection** | Add new sections or features to existing projects via natural language |
| 📦 **ZIP Export** | Download your generated project as a ready-to-use ZIP |
| 👀 **Live Preview** | Real-time preview across desktop, tablet, and mobile |
| 📄 **Streaming Code Viewer** | Watch your code generate live, token by token |
| 💰 **Savings Calculator** | See how much you saved vs. ChatGPT, Claude API, and Lovable after every build |
| 💻 **Native macOS DMG** | Install and run as a native desktop app |

---

## 💻 Installation (macOS)

[![Download for macOS](https://img.shields.io/badge/⬇_Download_AgentForge-macOS_DMG-000000?style=for-the-badge&logo=apple&logoColor=white)](https://github.com/locode-dev/locode/releases/download/v1.0.0/AgentForge-v1.0.0-arm64.dmg)

1. Click the **Download** button above
2. Open [`AgentForge-v1.0.0-arm64.dmg`](https://github.com/locode-dev/locode/releases/download/v1.0.0/AgentForge-v1.0.0-arm64.dmg)
3. Drag **AgentForge** to your Applications folder
4. Make sure [Ollama](https://ollama.ai) is running with at least one model pulled
5. Open AgentForge and start building

> **First launch:** If macOS blocks the app ("Apple could not verify"):
> 1. Right-click (or Control-click) **AgentForge** in your Applications folder
> 2. Select **Open** from the menu
> 3. Click **Open** again in the warning dialog

Alternatively, go to **System Settings → Privacy & Security** and scroll down to click **Open Anyway**.

### 🧹 Full Uninstallation / Reset

To completely remove all AgentForge data (including generated projects and settings) on macOS:

```bash
rm -rf ~/Library/Application\ Support/agentforge*
```

*(You can also use the **Maintenance → Factory Reset** menu option inside the app.)*

---

## 🚀 Run from Source

### Prerequisites

- Python 3.9+
- Node.js 20 LTS
- [Ollama](https://ollama.ai) installed and running

### 1. Pull your preferred models

AgentForge works with any open-source model supported by [Ollama](https://ollama.ai). For the best results, use a code-specialised model for generation:

```bash
# Recommended setup
ollama pull llama3.1:8b          # Idea refinement (fast, low VRAM)
ollama pull qwen2.5-coder:14b    # React/Tailwind code generation (best quality)
```

You can mix and match — select different models for the **Refine** and **Build** stages inside the app. Any model in the Ollama library will work.

### 2. Clone and install

```bash
git clone https://github.com/locode-dev/locode
cd agentforge
npm install
pip3 install -r requirements.txt
```

### 3. Run

```bash
python3 server.py
```

### 4. Open in browser

```
http://localhost:7824
```

---

## ✏️ Reprompt Modes

Once an app is built, the toolbar gives you three ways to iterate:

| Tab | When to use | How it works |
|---|---|---|
| **Reprompt** | Change text, colors, layout, logic | Auto-classifies as `patch` (instant HMR) or `modify` (targeted rebuild) |
| **Feature** | Add a brand-new section or component | Always creates a new component matched to the existing visual style |
| **Fix Bugs** | Something looks broken | Runs the full auto-fix pipeline: npm build check → LLM fix → Playwright retest |

### Intent classification

The Reprompt tab automatically classifies your request so the right amount of work happens:

- **patch** — `"change the button color to blue"` → surgical file edit + Vite HMR. Done in ~2 seconds, no test loop.
- **modify** — `"redesign the hero section layout"` → targeted LLM rewrite of that component + Vite restart + test.
- **feature** — anything from the Feature tab → new component scaffolded and injected into App.jsx.

---

## 💰 Savings Calculator

After every build, AgentForge shows a popup comparing what the same token usage would have cost on paid APIs:

| Service | Pricing basis |
|---|---|
| ChatGPT (GPT-4o) | $5 input / $15 output per 1M tokens |
| Claude (Sonnet) | $3 input / $15 output per 1M tokens |
| Lovable | ~$40 per 1M tokens equivalent |
| **AgentForge** | **$0.00** |

A typical build uses 50k–150k tokens across the Refiner + Builder + Tester agents. The savings add up fast.

---

## 🏗 Architecture

```
agentforge/
├── server.py              # Main server — HTTP :7824, WebSocket :7825
├── agents/
│   ├── refiner.py         # Classifies idea, enriches spec via LLM
│   ├── builder.py         # Generates React + Tailwind + Vite project
│   └── tester.py          # Playwright browser tests + validation
├── ui/
│   └── index.html         # Frontend interface
├── electron/              # Electron wrapper for macOS DMG
├── production-ready/      # Generated project output directory
└── logs/                  # Run logs
```

### Agent Pipeline

```
User prompt
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Refiner  (refiner.py)                              │
│  • Keyword + LLM intent detection                   │
│  • Classifies site type (tool / game / app / saas…) │
│  • Produces detailed spec: description, features,   │
│    component details, color scheme, style           │
└────────────────────────┬────────────────────────────┘
                         │ enriched spec (JSON)
                         ▼
┌─────────────────────────────────────────────────────┐
│  Builder  (builder.py)                              │
│  • Generates App.jsx + all section components       │
│  • Streams each file live to the UI                 │
│  • Writes config (package.json, vite.config, CSS)   │
└────────────────────────┬────────────────────────────┘
                         │ project on disk
                         ▼
┌─────────────────────────────────────────────────────┐
│  Tester   (tester.py)                               │
│  • Waits for Vite dev server (port polling)         │
│  • Playwright headless Chromium: load, mount, check │
│  • Reports real JS errors only (filters HMR noise)  │
│  • On failure → Builder fix loop (up to MAX_FIX)    │
└─────────────────────────────────────────────────────┘
```

### Update Pipeline (Reprompt / Feature / Fix)

```
User reprompt
    │
    ▼
_classify_intent()          ← keyword-based, no LLM call
    │
    ├── patch   ──▶  _decide_targets() (existing only)
    │               _build_update_prompt() (surgical)
    │               write file → Vite HMR → done (~2s)
    │
    ├── modify  ──▶  _decide_targets() (existing only)
    │               _build_update_prompt() (preserve rest)
    │               write file → Vite restart → test loop
    │
    └── feature ──▶  _decide_targets() (may create new)
                    _build_update_prompt() (new component)
                    _inject_component_into_app()
                    Vite restart → test loop
```

---

## 👤 Author

**Ravindu B. Subasinghe**
Sri Lanka Institute of Information Technology (SLIIT)

---

## 📄 License

[MIT](LICENSE) — free to use, modify, and distribute.

---

<div align="center">

⚡ Built with Ollama · Next.js · MongoDB · Vitest · Playwright · CloudFormation · Electron

**Ravindu B. Subasinghe** — Sri Lanka Institute of Information Technology

</div>