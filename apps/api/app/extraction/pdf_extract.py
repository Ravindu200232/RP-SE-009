"""PDF text extraction via pdfplumber, falling back to pypdf.

Both are optional (see requirements-extract.txt). When neither is installed
we return a structured note instead of crashing the intake flow.
"""
from __future__ import annotations

from typing import Any


def extract_pdf_text(data: bytes, filename: str = "upload.pdf") -> dict[str, Any]:
    # Preferred: pdfplumber (better layout fidelity)
    try:
        import io

        import pdfplumber

        text_parts: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
        text = "\n\n".join(p for p in text_parts if p).strip()
        if text:
            return {"text": text, "engine": "pdfplumber", "pages": len(text_parts)}
    except Exception:  # noqa: BLE001 - try the next engine
        pass

    # Fallback: pypdf
    try:
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n\n".join((page.extract_text() or "") for page in reader.pages).strip()
        return {"text": text, "engine": "pypdf", "pages": len(reader.pages)}
    except Exception as exc:  # noqa: BLE001
        return {
            "text": "",
            "engine": "none",
            "error": (
                "PDF text extraction unavailable. Install extras: "
                "`pip install pdfplumber pypdf`. "
                f"({exc})"
            ),
        }
