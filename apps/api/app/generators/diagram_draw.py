"""Native (offline) diagram rendering for the PDF.

Draws the seven diagram types directly from the SRS data using ReportLab vector
graphics, so the PDF always contains real diagram *images* — no mermaid-cli,
Chromium, or network required. The Mermaid sources are still produced for the
web UI / .mmd files; these drawings are the print representation.
"""
from __future__ import annotations

import math
from typing import Optional

from reportlab.graphics.shapes import Drawing, Group, Line, Polygon, Rect, String
from reportlab.lib import colors
from reportlab.pdfbase.pdfmetrics import stringWidth

PRIMARY = colors.HexColor("#4F46E5")
INK = colors.HexColor("#0F172A")
MUTED = colors.HexColor("#64748B")
LINE = colors.HexColor("#CBD5E1")
SOFT = colors.HexColor("#F1F5F9")
INDIGO_BG = colors.HexColor("#EEF2FF")
GREEN_BG = colors.HexColor("#F0FDF4")
GREEN = colors.HexColor("#16A34A")
ORANGE_BG = colors.HexColor("#FFF7ED")
ORANGE = colors.HexColor("#EA580C")
SLATE_BG = colors.HexColor("#F8FAFC")

F = "Helvetica"
FB = "Helvetica-Bold"


def _fit(text: str, font: str, size: float, maxw: float) -> str:
    text = str(text)
    if stringWidth(text, font, size) <= maxw:
        return text
    while text and stringWidth(text + "…", font, size) > maxw:
        text = text[:-1]
    return text + "…"


def _box(g: Group, x, y, w, h, fill=colors.white, stroke=LINE, sw=1.0):
    g.add(Rect(x, y, w, h, rx=5, ry=5, fillColor=fill, strokeColor=stroke, strokeWidth=sw))


def _txt(g: Group, x, y, s, size=8, font=F, color=INK, anchor="start"):
    g.add(String(x, y, s, fontName=font, fontSize=size, fillColor=color, textAnchor=anchor))


def _node(g: Group, cx, cy, w, h, label, fill, stroke, color=INK, size=8):
    _box(g, cx - w / 2, cy - h / 2, w, h, fill, stroke)
    _txt(g, cx, cy - size / 2 + 1, _fit(label, FB, size, w - 8), size, FB, color, "middle")


def _arrow(g: Group, x1, y1, x2, y2, color=MUTED, dashed=False, label=None):
    ln = Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=1)
    if dashed:
        ln.strokeDashArray = [3, 2]
    g.add(ln)
    ang = math.atan2(y2 - y1, x2 - x1)
    a = 6
    g.add(Polygon(points=[
        x2, y2,
        x2 - a * math.cos(ang - 0.45), y2 - a * math.sin(ang - 0.45),
        x2 - a * math.cos(ang + 0.45), y2 - a * math.sin(ang + 0.45),
    ], fillColor=color, strokeColor=color))
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        _txt(g, mx, my + 2, _fit(label, F, 6.5, abs(x2 - x1) or 60), 6.5, F, MUTED, "middle")


# ── ERD ──────────────────────────────────────────────────────
def _erd(doc, W):
    db = doc.get("database_design", {})
    tables = db.get("tables", [])[:15]
    cols = 3 if len(tables) > 6 else 2
    pad = 10
    cw = (W - (cols + 1) * pad) / cols
    row_h, line_h, title_h = [], 11, 16

    boxes = []  # (table, x, y, w, h)
    # First pass: compute per-table heights and grid placement
    heights = [title_h + min(len(t.get("fields", [])), 7) * line_h + 6 for t in tables]
    y = 0
    i = 0
    centers = {}
    placed = []
    while i < len(tables):
        rown = tables[i:i + cols]
        rowh = max(heights[i:i + cols])
        for j, t in enumerate(rown):
            x = pad + j * (cw + pad)
            placed.append((t, x, y, cw, heights[i + j]))
        y += rowh + pad
        i += cols
    total_h = y + pad
    # Build with top-down coordinates flipped (drawing origin bottom-left)
    d = Drawing(W, total_h)
    g = Group()
    name_to_center = {}
    for (t, x, yt, w, h) in placed:
        Y = total_h - yt - h  # flip
        _box(g, x, Y, w, h, colors.white, PRIMARY, 1.1)
        _box(g, x, Y + h - title_h, w, title_h, INDIGO_BG, PRIMARY, 1.1)
        _txt(g, x + 5, Y + h - 11, _fit(t["table_name"], FB, 8, w - 10), 8, FB, PRIMARY)
        fy = Y + h - title_h - 10
        for fld in (t.get("fields", []) or [])[:7]:
            mark = "PK" if fld.get("primary_key") else ("FK" if fld.get("type") == "foreign_key" else ("UK" if fld.get("unique") else ""))
            label = f"{fld.get('name', '')}: {fld.get('type', '')}"
            _txt(g, x + 6, fy, _fit(label, F, 7, w - 26), 7, F, INK)
            if mark:
                _txt(g, x + w - 5, fy, mark, 6, FB, MUTED, "end")
            fy -= line_h
        name_to_center[t["table_name"]] = (x + w / 2, Y + h / 2, x, Y, w, h)
    # relationship connectors (light)
    names = set(name_to_center)
    for rel in db.get("relationships", []):
        a = str(rel.get("from", "")).split(".")[0]
        b = str(rel.get("to", "")).split(".")[0]
        if a in names and b in names and a != b:
            ax, ay, *_ = name_to_center[a]
            bx, by, *_ = name_to_center[b]
            g.add(Line(ax, ay, bx, by, strokeColor=LINE, strokeWidth=0.7))
    d.add(g)
    return d


# ── Use case ─────────────────────────────────────────────────
def _use_case(doc, W):
    roles = doc.get("roles", [])[:6]
    modules = [m for m in doc.get("main_modules", []) if m.lower() != "settings"][:7]
    H = max(len(roles), len(modules)) * 34 + 30
    d = Drawing(W, H)
    g = Group()
    aw, ah = 95, 24
    sys_x, sys_w = 150, W - 160
    _box(g, sys_x, 10, sys_w, H - 20, SLATE_BG, MUTED, 1)
    _txt(g, sys_x + 8, H - 20, _fit(doc.get("project_name", "System"), FB, 8, sys_w - 16), 8, FB, MUTED)
    uc_centers = []
    for i, m in enumerate(modules):
        cy = H - 40 - i * ((H - 60) / max(len(modules), 1))
        cx = sys_x + sys_w / 2
        _node(g, cx, cy, sys_w - 40, 20, m, colors.white, PRIMARY, INK, 7.5)
        uc_centers.append((cx, cy))
    for i, r in enumerate(roles):
        cy = H - 30 - i * ((H - 40) / max(len(roles), 1))
        _node(g, 12 + aw / 2, cy, aw, ah, r.get("role_name", "Actor"), INDIGO_BG, PRIMARY, INK, 7.5)
        if uc_centers:
            tx, ty = uc_centers[i % len(uc_centers)]
            _arrow(g, 12 + aw, cy, sys_x, ty, LINE)
    d.add(g)
    return d


# ── System context ───────────────────────────────────────────
def _context(doc, W):
    roles = doc.get("roles", [])[:5]
    integ = doc.get("integration_requirements", [])[:4]
    H = max(len(roles), len(integ)) * 40 + 70
    d = Drawing(W, H)
    g = Group()
    cx, cy = W / 2, H / 2
    _node(g, cx, cy, 150, 40, _fit(doc.get("project_name", "System"), FB, 8, 140), INDIGO_BG, PRIMARY, PRIMARY, 8)
    for i, r in enumerate(roles):
        ry = H - 30 - i * ((H - 50) / max(len(roles), 1))
        _node(g, 70, ry, 110, 22, r.get("role_name", "User"), GREEN_BG, GREEN, INK, 7)
        _arrow(g, 125, ry, cx - 75, cy + 8, LINE)
    for i, ig in enumerate(integ):
        iy = H - 30 - i * ((H - 50) / max(len(integ), 1))
        _node(g, W - 70, iy, 120, 22, ig.get("name", "External"), ORANGE_BG, ORANGE, INK, 7)
        _arrow(g, cx + 75, cy + 8, W - 130, iy, LINE)
    _node(g, cx, 22, 110, 22, "Database", SOFT, MUTED, INK, 7)
    _arrow(g, cx, cy - 20, cx, 33, LINE)
    d.add(g)
    return d


# ── Component (layered) ──────────────────────────────────────
def _component(doc, W):
    modules = [m for m in doc.get("main_modules", []) if m.lower() != "settings"][:8]
    bands = [
        ("Client Layer", ["Web SPA / PWA", "Mobile (PWA)"], INDIGO_BG, PRIMARY),
        ("API Gateway", ["REST API + Auth"], SOFT, MUTED),
        ("Domain Services", [f"{m}" for m in modules], colors.white, PRIMARY),
        ("Data Layer", ["Primary DB", "Cache", "Message Queue"], SOFT, MUTED),
    ]
    bh, gap = 56, 16
    H = len(bands) * (bh + gap) + 10
    d = Drawing(W, H)
    g = Group()
    y = H - 10
    centers = []
    for title, items, fill, stroke in bands:
        y -= bh
        _box(g, 6, y, W - 12, bh, SLATE_BG, LINE, 0.8)
        _txt(g, 12, y + bh - 12, title, 7.5, FB, MUTED)
        n = len(items)
        iw = min(110, (W - 24) / max(n, 1) - 8)
        for j, it in enumerate(items):
            cx = 16 + iw / 2 + j * ((W - 32) / max(n, 1))
            _node(g, cx, y + 22, iw, 22, it, fill, stroke, INK, 6.8)
        centers.append(y + bh / 2)
        y -= gap
    for k in range(len(centers) - 1):
        _arrow(g, W / 2, centers[k] - bh / 2 + 4, W / 2, centers[k + 1] + bh / 2 - 4, MUTED)
    d.add(g)
    return d


# ── Deployment ───────────────────────────────────────────────
def _deployment(doc, W):
    has_pay = any(i.get("type") == "payment" for i in doc.get("integration_requirements", []))
    tiers = [
        ("Edge", ["Browser / Mobile", "CDN"]),
        ("Web Tier", ["Next.js #1", "Next.js #2"]),
        ("API Tier", ["API #1", "API #2"]),
        ("Data Tier", ["DB Primary", "DB Replica", "Redis", "Object Store"]),
    ]
    colw = (W - 30) / len(tiers)
    H = 200
    d = Drawing(W, H)
    g = Group()
    col_mid = []
    for i, (title, nodes) in enumerate(tiers):
        x = 10 + i * colw
        _txt(g, x + colw / 2 - 10, H - 12, title, 7.5, FB, MUTED, "middle")
        ny = H - 40
        for nlabel in nodes:
            _node(g, x + colw / 2 - 8, ny, colw - 24, 22, nlabel, colors.white, PRIMARY, INK, 6.8)
            ny -= 30
        col_mid.append((x + colw / 2 - 8, H - 40))
    for i in range(len(col_mid) - 1):
        x1, y1 = col_mid[i]
        x2, y2 = col_mid[i + 1]
        _arrow(g, x1 + (colw - 24) / 2, y1, x2 - (colw - 24) / 2, y2, MUTED)
    if has_pay:
        _node(g, W - 60, 24, 100, 20, "Payment Gateway", ORANGE_BG, ORANGE, INK, 6.8)
    d.add(g)
    return d


# ── Activity ─────────────────────────────────────────────────
def _activity(doc, W):
    wf = (doc.get("business_workflows") or [{}])[0]
    steps = (wf.get("steps", []) or ["Start", "Process", "Save", "Notify", "End"])[:8]
    H = (len(steps) + 2) * 46 + 10
    d = Drawing(W, H)
    g = Group()
    cx = W / 2
    y = H - 24
    _node(g, cx, y, 80, 22, "Start", GREEN_BG, GREEN, INK, 7.5)
    prev = y - 11
    for s in steps:
        y -= 46
        low = s.lower()
        if any(k in low for k in ("pay", "approve", "verify", "check", "confirm", "valid")):
            pts = [cx, y + 16, cx + 90, y, cx, y - 16, cx - 90, y]
            g.add(Polygon(points=pts, fillColor=ORANGE_BG, strokeColor=ORANGE, strokeWidth=1))
            _txt(g, cx, y - 2, _fit(s + "?", FB, 7, 150), 7, FB, INK, "middle")
        else:
            _node(g, cx, y, W - 120, 24, s, colors.white, PRIMARY, INK, 7.5)
        _arrow(g, cx, prev, cx, y + 16, MUTED)
        prev = y - 13
    y -= 46
    _node(g, cx, y, 80, 22, "End", SOFT, MUTED, INK, 7.5)
    _arrow(g, cx, prev, cx, y + 11, MUTED)
    d.add(g)
    return d


# ── Sequence ─────────────────────────────────────────────────
def _sequence(doc, W):
    wf = (doc.get("business_workflows") or [{}])[0]
    steps = (wf.get("steps", []) or ["Submit", "Validate", "Persist", "Respond"])[:7]
    parts = ["User", "Web App", "API", "Database", "Notifier"]
    n = len(parts)
    colw = W / n
    xs = [colw * (i + 0.5) for i in range(n)]
    H = 60 + len(steps) * 30 + 20
    d = Drawing(W, H)
    g = Group()
    for i, p in enumerate(parts):
        _node(g, xs[i], H - 22, colw - 16, 22, p, INDIGO_BG, PRIMARY, INK, 7)
        ln = Line(xs[i], H - 34, xs[i], 16, strokeColor=LINE, strokeWidth=0.8)
        ln.strokeDashArray = [3, 3]
        g.add(ln)
    y = H - 50
    seq = [(0, 1), (1, 2), (2, 3), (3, 2), (2, 4), (2, 1), (1, 0)]
    for i, s in enumerate(steps):
        a, b = seq[i % len(seq)]
        _arrow(g, xs[a], y, xs[b], y, PRIMARY if a < b else MUTED, label=_fit(s, F, 6.5, colw * 1.4))
        y -= 30
    d.add(g)
    return d


_RENDERERS = {
    "erd": _erd, "use_case": _use_case, "system_context": _context,
    "component": _component, "deployment": _deployment, "activity": _activity,
    "sequence": _sequence,
}


def render_native(kind: str, doc: dict, width: float) -> Optional[Drawing]:
    """Return a ReportLab Drawing for the diagram kind, or None on failure."""
    fn = _RENDERERS.get(kind)
    if not fn:
        return None
    try:
        return fn(doc, width)
    except Exception:  # noqa: BLE001 - fall back to source text in the PDF
        return None
