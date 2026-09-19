"""The pictures in a request, as pictures.

An attachment reaches the agent twice over: as a file in `.agentforge/uploads/`
that its tools can open, and as a line in the brief naming that path. Neither
gets the image itself to the model - a tool read returns bytes it cannot look
at, and the brief carries someone else's description of it.

This reads the paths already named in the brief and hands the bytes to the model
turn, so a screenshot of a broken page is seen rather than recounted. Nothing new
is threaded through the socket, the job or the pipeline: the files are on disk
already and the brief already says where.
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

# Kept small deliberately. Every image is tokens in every later turn of the
# conversation, so a folder of screenshots would crowd out the code.
MAX_IMAGES = 6
MAX_PDF_PAGES = 3
MAX_BYTES = 5_000_000

PICTURES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
UPLOAD_PATH = re.compile(r"\.agentforge/(?:uploads|images)/([^\s`\"'<>)\]]+)")


def _as_base64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _pdf_pages(path: Path) -> list[str]:
    """The first few pages of a PDF, drawn, so a scan is readable at all."""
    try:
        import pymupdf
    except ImportError:
        try:
            import fitz as pymupdf          # the older name
        except ImportError:
            return []
    out = []
    try:
        with pymupdf.open(str(path)) as document:
            for index in range(min(len(document), MAX_PDF_PAGES)):
                pixels = document.load_page(index).get_pixmap(dpi=120)
                out.append(_as_base64(pixels.tobytes("png")))
    except Exception:                                           # noqa: BLE001
        return []
    return out


def images_in(brief: str, root: Path) -> list[str]:
    """Every attached picture the brief names, base64, ready for the model turn."""
    root = Path(root)
    seen, out = set(), []
    for name in UPLOAD_PATH.findall(str(brief or "")):
        if len(out) >= MAX_IMAGES:
            break
        for folder in ("uploads", "images"):
            path = (root / ".agentforge" / folder / Path(name).name)
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            suffix = path.suffix.lower()
            try:
                if suffix in PICTURES and path.stat().st_size <= MAX_BYTES:
                    out.append(_as_base64(path.read_bytes()))
                elif suffix == ".pdf":
                    out.extend(_pdf_pages(path)[:MAX_IMAGES - len(out)])
            except OSError:
                continue
            break
    return out[:MAX_IMAGES]
