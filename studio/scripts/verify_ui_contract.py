"""Fast source checks for the Studio integration contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


required = {
    "chat composer": ("components/AgentChat.jsx", "'element_edit' : 'agent_update'"),
    "what you type is what is sent": ("components/AgentChat.jsx", "Say it, and it goes"),
    "chat turns from the run": ("lib/chat.js", "export function chatTurns"),
    "chat answers a paused question": ("components/AgentChat.jsx", "answerQuestion(typed)"),
    "the box stays open while the agent works": ("components/AgentChat.jsx", "queueUp(payload"),
    "what was typed during a run waits in the store": ("lib/store.js", "takeQueued:"),
    "and goes when the run ends": ("components/AgentChat.jsx", "takeQueued(project)"),
    "waiting messages are visible and droppable": ("components/AgentChat.jsx", "function Queued"),
    "a log line is read without its badge": ("lib/chat.js", "export function plainly"),
    "dev-server chatter is not conversation": ("lib/chat.js", "SERVER_READY"),
    "agent turns in the store": ("lib/store.js", "pushChat:"),
    "run context in the store": ("lib/store.js", "setRunStats:"),
    "status line at the foot of the chat": ("components/AgentChat.jsx", "function StatusLine"),
    "context window is a bar": ("components/AgentChat.jsx", "percent >= 90 ? 'bg-bad'"),
    "tokens and requests are shown": ("components/AgentChat.jsx", "{stats.requests} req"),
    "the engine reports what it spent": ("../builder-agent/builder_agent/loop.py", "used_"),
    "the plan is shown": ("components/AgentChat.jsx", "turn.kind === 'plan'"),
    "the design is shown": ("components/AgentChat.jsx", "function DesignCard"),
    "the plan can be accepted or revised": ("components/AgentDecision.jsx", "function PlanDecision"),
    "the plan is read, not dumped": ("components/AgentDecision.jsx", "<PlanReading"),
    "a plan is laid out as prose": ("components/PlanReading.jsx", "readPlan"),
    "the model is chosen where the build is configured": ("components/BuildSetup.jsx", "build-model"),
    "the design can be customised": ("components/AgentDecision.jsx", "function DesignDecision"),
    "the whole catalogue is offered": ("components/AgentDecision.jsx", 'label="Voice"'),
    "the screens are chosen too": ("components/AgentDecision.jsx", "togglePage"),
    "a design is the default, not the exception":
        ("../builder-agent/builder_agent/agent.py", "nobody writes those words"),
    "a decision has a deadline": ("components/AgentDecision.jsx", "function Countdown"),
    "answering one question does not close the next":
        ("components/AgentDecision.jsx", "store.approval?.id === id"),
    "nor does the resolution that follows it": ("lib/ws.js", "approval?.id === m.id"),
    "decisions reach the run": ("lib/api.js", "decide: (body)"),
    "the gate expires into the default": ("../builder-agent/builder_agent/approvals.py", "timedOut"),
    "a journey can pick from repeated controls": ("../builder-agent/builder_agent/browser.py", "def _pick"),
    "the browser streams what it sees": ("../builder-agent/builder_agent/browser.py", "startScreencast"),
    "it streams whenever it is open": ("../builder-agent/builder_agent/browser.py", "def _watch"),
    "the preview shows the agent's browser": ("components/AgentBrowser.jsx", "browserFrame"),
    "the browser is labelled as the agent's": ("components/AgentBrowser.jsx", "agent"),
    "a finished cast gives the preview back": ("components/AgentBrowser.jsx", "STALE_MS"),
    "frames reach the studio": ("lib/ws.js", "browser_frame"),
    "chat opens itself for a run": ("components/AgentChat.jsx", "if (busy) setOpen(true)"),
    "nothing is dropped from the stream": ("lib/chat.js", "usually the interesting one"),
    "one row per action": ("lib/chat.js", "Every action is its own row"),
    "the live step is animated": ("components/AgentChat.jsx", "live ? <Loader2"),
    "the last row is the live one": ("components/AgentChat.jsx", "live={busy && i === turns.length - 1}"),
    "thinking is shown as thinking": ("components/AgentChat.jsx", "function Thinking"),
    "thinking is actually rendered": ("components/AgentChat.jsx", "agentState === 'thinking' && <Thinking />"),
    "a frame never blocks the socket it arrives on":
        ("../builder-agent/builder_agent/browser.py", "def post"),
    "the engine reports thinking": ("../server_modules/builder/bridge.py", '"state": "thinking"'),
    "SRS planner animation": ("components/srs/SrsActivity.jsx", "/__agentforge/srs-planner.gif"),
    "a run can be stopped from the chat": ("components/AgentChat.jsx", "function CancelRun"),
    "each project keeps its own stream": ("lib/store.js", "streams: {}"),
    "a stream outlives the tab that watched it": ("lib/api.js", "saveStream:"),
    "one project's lines stay its own": ("lib/ws.js", "function meantForMe"),
    "and the server stamps them": ("../server_modules/core/bootstrap.py", "def stamp_owner"),
    "a run is refused the projects store": ("../server_modules/builder/pipeline.py", "def _workspace"),
    "a stream is handed back on the way in": ("lib/store.js", "function restored"),
    "the run knows which project it belongs to": ("lib/ws.js", "setBusyProject"),
    "a working project says so in the list": ("components/Sidebar.jsx", "s.busyProject === name"),
    "chat is a column beside the work": ("app/page.jsx", "<AgentChat />"),
    "chat is not a drawer": ("components/AgentChat.jsx", "<aside className=\"flex w-["),
    "select tool": ("components/PreviewPane.jsx", "attachPicker"),
    "pencil tool": ("components/PreviewPane.jsx", "pencilOn"),
    "what you point at is attached to the message":
        ("components/PreviewPane.jsx", "const attachShot"),
    "several things can be attached at once": ("lib/store.js", "addSelection:"),
    "the attachments are shown in the composer": ("components/AgentChat.jsx", "function Attached"),
    "the message carries them": ("components/AgentChat.jsx", "payload.shots"),
    "a drawing is photographed with its red line":
        ("../server_modules/services/shots.py", "def capture_drawing"),
    "an element is photographed on its own":
        ("../server_modules/services/shots.py", "def capture_element"),
    "the screenshots are read for the agent":
        ("../server_modules/builder/edits.py", "def _read_shots"),
    "one browser is kept warm between clicks":
        ("../server_modules/services/shots.py", "class _Warm"),
    "test evidence view": ("components/testing/TestingResult.jsx", "label: 'Evidence'"),
    "verification ledger rendered": ("components/testing/Evidence.jsx", "qa?.report?.evidence"),
    "a run adds to the suite instead of replacing it":
        ("../qa-agent/qa_agent/report.py", "def carry_unit"),
    "journeys nobody reran are still known":
        ("../qa-agent/qa_agent/report.py", "def carry_journeys"),
    "and the pane says how much was carried":
        ("components/testing/UnitTests.jsx", "v.carriedForward"),
    "documents and archives reach the model":
        ("../srs-agent/srs_agent/app/extraction/documents.py", "def read_document"),
    "the builder reads them too": ("../server_modules/builder/media.py", "DOCUMENT_EXT"),
    "and they can be chosen in the first place": ("lib/api.js", ".docx"),
    "E2E failures retain browser diagnostics":
        ("components/testing/EndToEnd.jsx", "Browser console & network evidence"),
    "sequential E2E overlay": ("components/LiveE2EOverlay.jsx", "Live browser test"),
    "parallel QA view": ("components/testing/TestingResult.jsx", "E2ELiveLanes"),
    "SRS file intake": ("components/srs/Attachments.jsx", "PDF / image"),
    "messenger SRS interview": ("components/srs/Interview.jsx", "srs-messenger"),
    "SRS plan review": ("components/srs/PlanReview.jsx", "Product blueprint"),
    "deployment workspace": ("components/deploy/DeployPanel.jsx", "Deploy"),
    "AWS Console browser login": ("components/deploy/DeployAccounts.jsx", "tool: 'aws-console-login'"),
    "isolated AWS Console profile": ("components/deploy/DeployAccounts.jsx", "const AWS_CONSOLE_PROFILE = 'agentforge-console'"),
    "the stack is chosen, not guessed": ("components/Home.jsx", "2. Choose the stack"),
    "the build is configured before it starts": ("components/BuildSetup.jsx", "Configure your build"),
    "and it asks for the stack": ("components/BuildSetup.jsx", "build-setup-stack"),
    "the design can still be customised": ("components/AgentDecision.jsx", "How should it look?"),
    "the chosen stack travels with the build": ("components/Home.jsx", "config?.stack || stack"),
    "the engine prefers a chosen stack": ("../server_modules/builder/pipeline.py", "stack or detect_stack"),
    "sidebar collapses": ("components/Sidebar.jsx", "if (collapsed) {"),
}

forbidden = {
    # Asked once, in the dialog that starts the build — not left in a sidebar
    # where it looks like a setting that applies to something already running.
    "a second model picker": ("components/Sidebar.jsx", 'label="Model"'),
    "build switches in the sidebar": ("components/Sidebar.jsx", "Build controls"),
    # One styling story: Tailwind in the scaffold, tokens from the contract.
    "a UI framework picker": ("components/BuildSetup.jsx", "UI_LIBRARIES"),
    "a provider block picker": ("components/AgentDecision.jsx", "Provider blocks"),
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
    "SRS activity card frame": ("components/srs/SrsActivity.jsx", "rounded-[21px] rounded-bl-[8px]"),
    # The build screen said in an animation what the chat stream already says
    # in words, and covered the browser while it did.
    "build screen": ("components/PreviewPane.jsx", "BuildOverlay"),
    "decorative build animation": ("components/PreviewPane.jsx", "builder-flow.gif"),
    # Pointing at something is one gesture with two shapes, not three tools
    # with three prompt boxes.
    "picture tool": ("components/PreviewPane.jsx", "image_edit"),
    # Being asked to approve a paraphrase of your own sentence is a step
    # between you and the agent, not a help.
    "a paraphrase to approve": ("components/AgentChat.jsx", "TunePrompt"),
    "a second prompt box beside the chat": ("components/PreviewPane.jsx", "Review request"),
}

missing = {
    # Deleted with the build screen they served.
    "the build screen": "components/BuildOverlay.jsx",
    "its activity mapper": "lib/activity.js",
    "its contract check": "scripts/verify_activity.mjs",
    "the rewording dialog": "components/TunePrompt.jsx",
}

failed = []
for label, (path, needle) in required.items():
    if needle not in text(path):
        failed.append(f"{label}: missing {needle!r} in {path}")
for label, (path, needle) in forbidden.items():
    if needle in text(path):
        failed.append(f"{label}: unwanted {needle!r} remains in {path}")
for label, path in missing.items():
    if (ROOT / path).exists():
        failed.append(f"{label}: {path} should have been removed")

if failed:
    raise SystemExit("\n".join(failed))
total = len(required) + len(forbidden) + len(missing)
print(f"Studio UI contracts: {total}/{total} OK")
