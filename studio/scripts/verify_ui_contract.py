"""Fast source checks for the Studio integration contracts."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def text(path):
    return (ROOT / path).read_text(encoding="utf-8")


required = {
    "feature approval": ("app/page.jsx", "setPendingAsk({ payload"),
    "prompt review": ("app/page.jsx", "<TunePrompt"),
    "preview activity drawer": ("components/PreviewConsoleDrawer.jsx", "<Activity className="),
    "preview terminal drawer": ("components/PreviewConsoleDrawer.jsx", "<SquareTerminal className="),
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
    "preview drawer mounted": ("components/PreviewPane.jsx", "<PreviewConsoleDrawer"),
    "sequential E2E overlay": ("components/LiveE2EOverlay.jsx", "Live browser test"),
    "parallel QA view": ("components/testing/TestingResult.jsx", "E2ELiveLanes"),
    "SRS file intake": ("components/srs/Attachments.jsx", "PDF / image"),
    "messenger SRS interview": ("components/srs/Interview.jsx", "srs-messenger"),
    "SRS plan review": ("components/srs/PlanReview.jsx", "Product blueprint"),
    "deployment workspace": ("components/deploy/DeployPanel.jsx", "Deploy"),
    "AWS Console browser login": ("components/deploy/DeployAccounts.jsx", "tool: 'aws-console-login'"),
    "isolated AWS Console profile": ("components/deploy/DeployAccounts.jsx", "const AWS_CONSOLE_PROFILE = 'agentforge-console'"),
    "sidebar model picker": ("components/Sidebar.jsx", 'label="Model"'),
}

forbidden = {
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
