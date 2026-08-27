"""Render the AgentForge documentation set to PDF.

Five documents: the system as a whole, and one per component branch. They share
the palette and furniture of the SRS and the test report, because they land in
the same folder and looking like one product matters.

The content comes from `document/content/*.json`, which is written by research
over the actual source rather than by hand — so re-running this after the code
changes is a matter of re-running the research, not of editing prose here.

    python document/build_docs.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, Frame, KeepTogether, PageBreak, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = Path(__file__).resolve().parent

PRIMARY = colors.HexColor("#2563EB")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#E2E8F0")
SOFT = colors.HexColor("#F8FAFC")

REPO = "https://github.com/Ravindu200232/full-stack-ai-web-developer"

# The open-source projects the system stands on. Kept here rather than asked of
# a model: a wrong URL in a reference table is worse than no table.
REPOS = [
    ("Next.js", "vercel/next.js", "https://github.com/vercel/next.js",
     "The studio, and every application AgentForge generates."),
    ("React", "facebook/react", "https://github.com/facebook/react",
     "The studio's UI, and the generated apps' components."),
    ("Tailwind CSS", "tailwindlabs/tailwindcss", "https://github.com/tailwindlabs/tailwindcss",
     "Styling, in the studio and in generated apps."),
    ("Zustand", "pmndrs/zustand", "https://github.com/pmndrs/zustand",
     "The studio's client state."),
    ("Lucide", "lucide-icons/lucide", "https://github.com/lucide-icons/lucide",
     "Icons throughout the studio."),
    ("JSZip", "Stuk/jszip", "https://github.com/Stuk/jszip",
     "Packaging a generated project for download."),
    ("FastAPI", "fastapi/fastapi", "https://github.com/fastapi/fastapi",
     "The SRS agent's HTTP surface."),
    ("Uvicorn", "encode/uvicorn", "https://github.com/encode/uvicorn",
     "Serves the SRS app inside AgentForge's process."),
    ("Pydantic", "pydantic/pydantic", "https://github.com/pydantic/pydantic",
     "Request and document schemas in the SRS agent."),
    ("LangGraph", "langchain-ai/langgraph", "https://github.com/langchain-ai/langgraph",
     "The SRS agent's node graph: intake, classify, interview, plan, generate."),
    ("LangChain Core", "langchain-ai/langchain", "https://github.com/langchain-ai/langchain",
     "Message and tool primitives used by the graph."),
    ("Motor / PyMongo", "mongodb/motor", "https://github.com/mongodb/motor",
     "Async and sync MongoDB access."),
    ("MongoDB", "mongodb/mongo", "https://github.com/mongodb/mongo",
     "Storage for SRS projects, and the database every generated app uses."),
    ("Ollama", "ollama/ollama", "https://github.com/ollama/ollama",
     "Runs the language and vision models, locally or against a cloud host."),
    ("Playwright", "microsoft/playwright", "https://github.com/microsoft/playwright",
     "Screenshots for the pencil tool, and the end-to-end browser run."),
    ("Vitest", "vitest-dev/vitest", "https://github.com/vitest-dev/vitest",
     "The unit test runner the QA agent writes for and drives."),
    ("Lighthouse", "GoogleChrome/lighthouse", "https://github.com/GoogleChrome/lighthouse",
     "The performance, accessibility, best-practice and SEO pass."),
    ("ReportLab", "MrBitBucket/reportlab-mirror", "https://github.com/MrBitBucket/reportlab-mirror",
     "Every PDF in the product, including this one."),
    ("pypdf", "py-pdf/pypdf", "https://github.com/py-pdf/pypdf",
     "Reading the text layer of an attached PDF."),
    ("PyMuPDF", "pymupdf/PyMuPDF", "https://github.com/pymupdf/PyMuPDF",
     "Rasterising a scanned PDF page so the vision model can read it."),
    ("Pillow", "python-pillow/Pillow", "https://github.com/python-pillow/Pillow",
     "Image decoding, re-encoding and bounding for uploads."),
    ("Tesseract / pytesseract", "tesseract-ocr/tesseract",
     "https://github.com/tesseract-ocr/tesseract",
     "Exact text out of an attached picture, alongside the model's reading."),
    ("faster-whisper", "SYSTRAN/faster-whisper", "https://github.com/SYSTRAN/faster-whisper",
     "Transcribes an attached or recorded voice note."),
    ("Fooocus", "lllyasviel/Fooocus", "https://github.com/lllyasviel/Fooocus",
     "Generates the pictures and logos a generated app asks for."),
    ("boto3", "boto/boto3", "https://github.com/boto/boto3",
     "AWS: CloudFormation, EC2, ECS, and the credential chain."),
    ("Vercel CLI", "vercel/vercel", "https://github.com/vercel/vercel",
     "The other deployment target."),
    ("websockets", "python-websockets/websockets", "https://github.com/python-websockets/websockets",
     "The live log, phases and streaming file writes into the studio."),
    ("watchdog", "gorakhargosh/watchdog", "https://github.com/gorakhargosh/watchdog",
     "Watches generated projects on disk."),
    ("jsonschema", "python-jsonschema/jsonschema", "https://github.com/python-jsonschema/jsonschema",
     "Validates deployment manifests."),
    ("PyYAML", "yaml/pyyaml", "https://github.com/yaml/pyyaml",
     "Reads and writes the generated CI workflows."),
]

BRANCHES = [
    ("main", "The shared runtime: server.py, the studio shell, the launchers."),
    ("srs-review-and-revision", "The working branch where the whole system is developed."),
    ("srs-agent", "srs-agent/ and studio/components/srs/ — the interview and the SRS."),
    ("builder-agent", "agents/ — planning, generation, repair and the editing tools."),
    ("qa-agent", "qa_agent/ and studio/components/testing/ — tests, e2e, the report."),
    ("deployment-agent",
     "deployment-agent/ and studio/components/deploy/ — CI, AWS and Vercel."),
]


def styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("title", parent=base["Title"], fontSize=27, leading=31,
                                textColor=INK),
        "subtitle": ParagraphStyle("subtitle", fontSize=12.5, leading=17, textColor=MUTED,
                                   alignment=TA_CENTER),
        "h1": ParagraphStyle("h1", fontSize=16, leading=20, spaceBefore=15, spaceAfter=8,
                             textColor=PRIMARY, fontName="Helvetica-Bold"),
        "h2": ParagraphStyle("h2", fontSize=12.5, leading=16, spaceBefore=11, spaceAfter=4,
                             textColor=INK, fontName="Helvetica-Bold"),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontSize=9.8, leading=14.5,
                               textColor=INK, alignment=TA_JUSTIFY, spaceAfter=7),
        "small": ParagraphStyle("small", fontSize=8.5, leading=11.5, textColor=MUTED),
        "cell": ParagraphStyle("cell", fontSize=8.4, leading=11, textColor=INK),
        "cellb": ParagraphStyle("cellb", fontSize=8.4, leading=11, textColor=INK,
                                fontName="Helvetica-Bold"),
        "mono": ParagraphStyle("mono", fontSize=7.8, leading=10, fontName="Courier",
                               textColor=colors.HexColor("#334155")),
        "stage": ParagraphStyle("stage", fontSize=9.8, leading=14, textColor=INK,
                                leftIndent=16, spaceAfter=6),
    }


class Doc(BaseDocTemplate):
    def __init__(self, path, meta, **kw):
        super().__init__(str(path), pagesize=A4, topMargin=2.2 * cm, bottomMargin=1.8 * cm,
                         leftMargin=1.9 * cm, rightMargin=1.9 * cm, **kw)
        self.meta = meta
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=lambda c, d: None),
            PageTemplate(id="body", frames=[frame], onPage=self._chrome),
        ])

    def _chrome(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.setLineWidth(0.5)
        canvas.line(self.leftMargin, A4[1] - 1.5 * cm, A4[0] - self.rightMargin, A4[1] - 1.5 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(self.leftMargin, A4[1] - 1.35 * cm, self.meta["title"][:72])
        canvas.drawRightString(A4[0] - self.rightMargin, A4[1] - 1.35 * cm,
                               self.meta.get("branch", ""))
        canvas.line(self.leftMargin, 1.4 * cm, A4[0] - self.rightMargin, 1.4 * cm)
        canvas.drawString(self.leftMargin, 1.1 * cm, "AgentForge Studio · Documentation")
        canvas.drawRightString(A4[0] - self.rightMargin, 1.1 * cm, f"Page {doc.page}")
        canvas.restoreState()

    def afterFlowable(self, f):
        if isinstance(f, Paragraph):
            if f.style.name == "h1":
                self.notify("TOCEntry", (0, f.getPlainText(), self.page))
            elif f.style.name == "h2":
                self.notify("TOCEntry", (1, f.getPlainText(), self.page))


def esc(text) -> str:
    return (str("" if text is None else text)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def P(text, st, key="cell"):
    return Paragraph(esc(text), st[key])


def table(rows, widths, header=True):
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("FONTSIZE", (0, 0), (-1, -1), 8.4),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
                  ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                  ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")]
    t.setStyle(TableStyle(style))
    return t


def build(data: dict, out_path: Path) -> Path:
    st = styles()
    meta = {"title": data["title"], "branch": data.get("branch", "")}
    doc = Doc(out_path, meta)
    W = doc.width
    s: list = []

    # ------------------------------------------------------------- cover
    s += [
        Spacer(1, 3.6 * cm),
        Paragraph("AgentForge Studio",
                  ParagraphStyle("brand", fontSize=12, textColor=PRIMARY,
                                 alignment=TA_CENTER, fontName="Helvetica-Bold")),
        Spacer(1, 0.55 * cm),
        Paragraph(esc(data["title"]), st["title"]),
        Spacer(1, 0.35 * cm),
        Paragraph(esc(data["one_liner"]), st["subtitle"]),
        Spacer(1, 1.6 * cm),
        table([[P("Repository", st, "cellb"), P(REPO, st)],
               [P("Branch", st, "cellb"), P(data.get("branch", "main"), st)],
               [P("Scope", st, "cellb"), P(data.get("scope", "—"), st)],
               [P("Written", st, "cellb"), P(date.today().isoformat(), st)]],
              [W * 0.24, W * 0.76], header=False),
        PageBreak(),
    ]

    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("t1", fontSize=10.5, leading=16, spaceBefore=4,
                       fontName="Helvetica-Bold", textColor=INK),
        ParagraphStyle("t2", fontSize=9.5, leading=13, leftIndent=14, textColor=MUTED),
    ]
    s += [Paragraph("Contents", st["h1"]), toc, PageBreak()]

    n = [0]

    def h1(text):
        n[0] += 1
        s.append(Paragraph(f"{n[0]}. {esc(text)}", st["h1"]))

    # --------------------------------------------------------- overview
    h1("Overview")
    for para in str(data["overview"]).split("\n\n"):
        if para.strip():
            s.append(Paragraph(esc(para.strip()), st["body"]))

    # --------------------------------------------------------- features
    h1("What it does")
    rows = [[P("Feature", st, "cellb"), P("What it does", st, "cellb"),
             P("Where", st, "cellb")]]
    for f in data.get("features") or []:
        rows.append([P(f.get("name"), st), P(f.get("what"), st),
                     Paragraph(esc(f.get("where", "—")), st["mono"])])
    s.append(table(rows, [W * 0.22, W * 0.50, W * 0.28]))

    # ------------------------------------------------------------ stack
    s.append(PageBreak())
    h1("Technology and tools")
    rows = [[P("Technology", st, "cellb"), P("Version", st, "cellb"),
             P("What it does here", st, "cellb"), P("Why", st, "cellb")]]
    for t in data.get("stack") or []:
        rows.append([P(t.get("name"), st), P(t.get("version", "—"), st),
                     P(t.get("role"), st), P(t.get("why", "—"), st)])
    s.append(table(rows, [W * 0.18, W * 0.10, W * 0.36, W * 0.36]))

    # ----------------------------------------------------- how it works
    s.append(PageBreak())
    h1("How it works")
    for i, step in enumerate(data.get("how_it_works") or [], start=1):
        s.append(KeepTogether([
            Paragraph(f"{i}. {esc(step.get('stage'))}", st["h2"]),
            Paragraph(esc(step.get("detail")), st["stage"]),
        ]))

    # -------------------------------------------------------- key files
    s.append(PageBreak())
    h1("The code, file by file")
    rows = [[P("Path", st, "cellb"), P("What lives there", st, "cellb")]]
    for k in data.get("key_files") or []:
        rows.append([Paragraph(esc(k.get("path")), st["mono"]), P(k.get("does"), st)])
    s.append(table(rows, [W * 0.34, W * 0.66]))

    # -------------------------------------------------------- decisions
    s.append(PageBreak())
    h1("Why it is built this way")
    s.append(Paragraph(
        "Design decisions with their reasons. Where the source records the "
        "failure that forced a choice, that failure is given rather than a "
        "general principle.", st["body"]))
    rows = [[P("Decision", st, "cellb"), P("Why", st, "cellb")]]
    for d in data.get("decisions") or []:
        rows.append([P(d.get("decision"), st), P(d.get("why"), st)])
    s.append(table(rows, [W * 0.36, W * 0.64]))

    # -------------------------------------------------------- contracts
    if data.get("contracts"):
        s.append(PageBreak())
        h1("Interfaces")
        rows = [[P("Name", st, "cellb"), P("Shape", st, "cellb")]]
        for c in data["contracts"]:
            rows.append([Paragraph(esc(c.get("name")), st["mono"]),
                         P(c.get("shape", "—"), st)])
        s.append(table(rows, [W * 0.38, W * 0.62]))

    # ------------------------------------------- repositories (master)
    if data.get("include_repos"):
        s.append(PageBreak())
        h1("Repositories")
        s.append(Paragraph(
            "AgentForge itself, and the branch it keeps each component on. Each "
            "component branch holds only that subsystem's paths, so it can be "
            "read as one thing.", st["body"]))
        rows = [[P("Branch", st, "cellb"), P("What is on it", st, "cellb")]]
        for b, what in BRANCHES:
            rows.append([Paragraph(esc(b), st["mono"]), P(what, st)])
        s.append(table(rows, [W * 0.28, W * 0.72]))

        s.append(Spacer(1, 12))
        s.append(Paragraph("Open source it is built on", st["h2"]))
        s.append(Paragraph(
            "Every third-party project the system depends on at runtime, and "
            "what each one is used for here.", st["body"]))
        rows = [[P("Project", st, "cellb"), P("Repository", st, "cellb"),
                 P("Used here for", st, "cellb")]]
        for name, slug, url, why in REPOS:
            rows.append([P(name, st), Paragraph(esc(slug), st["mono"]), P(why, st)])
        s.append(table(rows, [W * 0.20, W * 0.28, W * 0.52]))
        s.append(Spacer(1, 8))
        s.append(Paragraph(
            "Repository addresses are github.com/&lt;slug&gt; for each row above.",
            st["small"]))

    doc.multiBuild(s)
    return out_path


def main() -> int:
    content = HERE / "content"
    if not content.is_dir():
        print(f"no content directory at {content}")
        return 1
    built = []
    for src in sorted(content.glob("*.json")):
        data = json.loads(src.read_text(encoding="utf-8"))
        out = HERE / f"{src.stem}.pdf"
        build(data, out)
        built.append((out.name, out.stat().st_size))
        print(f"  {out.name:44} {out.stat().st_size:>9,} bytes")
    print(f"\n{len(built)} document(s) in {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
