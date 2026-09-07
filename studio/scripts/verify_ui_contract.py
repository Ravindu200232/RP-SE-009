"""Fast source checks for the Studio integration contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


required = {
    "chat composer": ("components/AgentChat.jsx", "type: 'agent_update'"),
    "chat prompt review": ("components/AgentChat.jsx", "<TunePrompt"),
    "chat turns from the run": ("lib/chat.js", "export function chatTurns"),
    "chat answers a paused question": ("components/AgentChat.jsx", "answerQuestion(typed)"),
    "agent turns in the store": ("lib/store.js", "pushChat:"),
    "run context in the store": ("lib/store.js", "setRunStats:"),
    "status line at the foot of the chat": ("components/AgentChat.jsx", "function StatusLine"),
    "context window is a bar": ("components/AgentChat.jsx", "percent >= 90 ? 'bg-bad'"),
    "tokens and requests are shown": ("components/AgentChat.jsx", "{stats.requests} req"),
    "the engine reports what it spent": ("../builder-agent/builder_agent/loop.py", "used_"),
    "the plan is shown": ("components/AgentChat.jsx", "turn.kind === 'plan'"),
    "the design is shown": ("components/AgentChat.jsx", "function DesignCard"),
    "chat opens itself for a run": ("components/AgentChat.jsx", "if (busy) setOpen(true)"),
    "nothing is dropped from the stream": ("lib/chat.js", "usually the interesting one"),
    "one row per action": ("lib/chat.js", "Every action is its own row"),
    "the live step is animated": ("components/AgentChat.jsx", "live ? <Loader2"),
    "thinking is shown as thinking": ("components/AgentChat.jsx", "function Thinking"),
    "the engine reports thinking": ("../server_modules/builder/bridge.py", '"state": "thinking"'),
    "human activity mapper": ("lib/activity.js", "Creating the build plan"),
    "unit-test activity": ("lib/activity.js", "Creating unit tests"),
    "E2E activity": ("lib/activity.js", "Starting end-to-end testing"),
    "builder animation": ("components/BuildOverlay.jsx", "/__agentforge/builder-flow.gif"),
    "SRS planner animation": ("components/srs/SrsActivity.jsx", "/__agentforge/srs-planner.gif"),
    "builder paced feed": ("components/BuildOverlay.jsx", "}, 10000)"),
    "builder latest five": ("components/BuildOverlay.jsx", ".slice(-5)"),
    "builder white full view": ("components/BuildOverlay.jsx", 'overflow-y-auto bg-white'),
    "builder light color scope": ("components/BuildOverlay.jsx", 'data-theme="light"'),
    "builder unframed activity": ("components/BuildOverlay.jsx", 'section className="flex min-h-[560px] flex-col p-6"'),
    "builder unframed flow": ("components/BuildOverlay.jsx", 'section className="relative flex min-h-[560px] items-center justify-center overflow-hidden p-5"'),
    "chat is a column beside the work": ("app/page.jsx", "<AgentChat />"),
    "chat is not a drawer": ("components/AgentChat.jsx", "<aside className=\"flex w-["),
    "select tool": ("components/PreviewPane.jsx", "element_edit"),
    "pencil tool": ("components/PreviewPane.jsx", "pencil_edit"),
    "test evidence view": ("components/testing/TestingResult.jsx", "label: 'Evidence'"),
    "verification ledger rendered": ("components/testing/Evidence.jsx", "qa?.report?.evidence"),
    "sequential E2E overlay": ("components/LiveE2EOverlay.jsx", "Live browser test"),
    "parallel QA view": ("components/testing/TestingResult.jsx", "E2ELiveLanes"),
    "SRS file intake": ("components/srs/Attachments.jsx", "PDF / image"),
    "messenger SRS interview": ("components/srs/Interview.jsx", "srs-messenger"),
    "SRS plan review": ("components/srs/PlanReview.jsx", "Product blueprint"),
    "deployment workspace": ("components/deploy/DeployPanel.jsx", "Deploy"),
    "AWS Console browser login": ("components/deploy/DeployAccounts.jsx", "tool: 'aws-console-login'"),
    "isolated AWS Console profile": ("components/deploy/DeployAccounts.jsx", "const AWS_CONSOLE_PROFILE = 'agentforge-console'"),
    "sidebar model picker": ("components/Sidebar.jsx", 'label="Model"'),
    "sidebar collapses": ("components/Sidebar.jsx", "if (collapsed) {"),
}

forbidden = {
    # The terminal pane was replaced by the chat stream: raw backend lines
    # scrolled past faster than anyone could read them.
    "terminal drawer": ("components/PreviewPane.jsx", "PreviewConsoleDrawer"),
    "ask modal": ("app/page.jsx", "askOpen &&"),
    # A drawer covers the preview it is describing; the chat is a column now.
    "chat drawer": ("components/AgentChat.jsx", "absolute inset-x-4 bottom-3"),
    "chat inside the preview": ("components/PreviewPane.jsx", "AgentChat"),
    "team planner picker": ("components/Sidebar.jsx", 'label="Planner"'),
    "team design picker": ("components/Sidebar.jsx", 'label="Design"'),
    "team builder picker": ("components/Sidebar.jsx", 'label="Builder"'),
    "builder percentage bar": ("components/BuildOverlay.jsx", "Math.round(pct)"),
    "builder progress rail": ("components/BuildOverlay.jsx", "transition-[width]"),
    "raw warning card": ("components/BuildOverlay.jsx", "event.kind === 'warn'"),
    "builder activity card frame": ("components/BuildOverlay.jsx", "rounded-[22px] rounded-bl-[8px]"),
    "builder two-card shells": ("components/BuildOverlay.jsx", "rounded-[34px] border border-white/80 bg-white/72"),
    "builder decorative canvas gradient": ("components/BuildOverlay.jsx", "radial-gradient(circle_at_12%_10%"),
    "SRS activity card frame": ("components/srs/SrsActivity.jsx", "rounded-[21px] rounded-bl-[8px]"),
}

failed = []
for label, (path, needle) in required.items():
    if needle not in text(path):
        failed.append(f"{label}: missing {needle!r} in {path}")
for label, (path, needle) in forbidden.items():
    if needle in text(path):
        failed.append(f"{label}: unwanted {needle!r} remains in {path}")

if failed:
    raise SystemExit("\n".join(failed))
print(f"Studio UI contracts: {len(required) + len(forbidden)}/{len(required) + len(forbidden)} OK")
