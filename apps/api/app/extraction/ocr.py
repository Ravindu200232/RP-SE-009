"""Image OCR via pytesseract, falling back to easyocr.

Tesseract needs the native binary on PATH; easyocr is a heavier pure-python
fallback. When neither is available we return setup guidance.
"""
from __future__ import annotations

from typing import Any


def extract_image_text(data: bytes, filename: str = "upload.png") -> dict[str, Any]:
    # Preferred: pytesseract (needs the Tesseract binary)
    try:
        import io

        import pytesseract
        from PIL import Image

        img = Image.open(io.BytesIO(data))
        text = (pytesseract.image_to_string(img) or "").strip()
        return {"text": text, "engine": "tesseract"}
    except Exception:  # noqa: BLE001
        pass

    # Fallback: easyocr (pulls torch; optional)
    try:
        import numpy as np  # type: ignore
        import easyocr  # type: ignore
        from PIL import Image
        import io

        reader = easyocr.Reader(["en"], gpu=False)
        img = np.array(Image.open(io.BytesIO(data)).convert("RGB"))
        lines = reader.readtext(img, detail=0)
        return {"text": "\n".join(lines).strip(), "engine": "easyocr"}
    except Exception as exc:  # noqa: BLE001
        return {
            "text": "",
            "engine": "none",
            "error": (
                "OCR unavailable. Install Tesseract + `pip install pytesseract pillow`, "
                "or `pip install easyocr`. "
                f"({exc})"
            ),
        }
