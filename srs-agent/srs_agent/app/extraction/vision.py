"""Reading an image with the model, with OCR alongside it.

Tesseract and a vision model are good at different things, and neither
replaces the other. OCR is exact, instant and free, and it is the right tool
for the thing customers most often send: a typed price list, an invoice, a
printed form. A vision model is the right tool for everything OCR cannot do —
a photo of a shelf, a handwritten note, a screenshot whose *layout* carries
the meaning — because it describes what the picture shows rather than which
glyphs are in it.

The picture goes to the model. That is the whole point of letting somebody
attach one: OCR returns the glyphs on a photo of a shelf and understands
nothing about it, and a customer who photographs their shelf is telling us
what they sell. So both readers run, concurrently, and the model's reading
leads — with OCR appended, because it is the exact one for a price or a code
that a model may paraphrase.

OCR is still the fallback that matters: it needs no model and no network, so
an intake with Ollama stopped keeps working on typed documents instead of
rejecting them.
"""
from __future__ import annotations

import asyncio
import base64
import re
from typing import Any

from ..llm import LLMUnavailable, get_llm
from .ocr import extract_image_text

_SYS = (
    "You are reading an image a non-technical customer attached while "
    "describing an app they want built. Reply in plain text, no markdown.\n"
    "1. Transcribe every piece of text in the image, exactly, keeping the "
    "line order and any prices, codes or units.\n"
    "2. Then, in one or two sentences, say what the image shows and what it "
    "tells you about their business.\n"
    "If the image has no text at all, skip straight to the description."
)


MIN_OCR_WORDS = 4
MIN_OCR_LETTERS = 12


def ocr_is_usable(text: str) -> bool:
    letters = len(re.findall(r"[^\W\d_]", text or "", flags=re.UNICODE))
    words = len(re.findall(r"[^\W\d_]{2,}", text or "", flags=re.UNICODE))
    return letters >= MIN_OCR_LETTERS and words >= MIN_OCR_WORDS


async def describe_image(data: bytes, filename: str = "image.png") -> dict[str, Any]:
    """Ask the model to read the image. Never raises."""
    try:
        text = await get_llm().complete_text(
            system=_SYS,
            user=f"The attached image is called {filename}. Read it now.",
            images=[base64.b64encode(data).decode("ascii")],
            label="vision_read",
        )
    except LLMUnavailable as exc:
        return {"text": "", "engine": "none",
                "error": f"Vision model unavailable. ({exc})"}
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "engine": "none",
                "error": f"Vision read failed. ({exc})"}
    return {"text": (text or "").strip(), "engine": "vision"}


async def _ocr(data: bytes, filename: str) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(extract_image_text, data, filename)
    except Exception as exc:  # noqa: BLE001
        return {"text": "", "engine": "none", "error": f"OCR crashed. ({exc})"}


async def read_image(data: bytes, filename: str = "image.png") -> dict[str, Any]:
    """Show the image to the model, keeping OCR's exact reading alongside it."""

    seen, ocr = await asyncio.gather(describe_image(data, filename),
                                     _ocr(data, filename))

    described = (seen.get("text") or "").strip()
    read = (ocr.get("text") or "").strip()

    if described:
        if ocr_is_usable(read):
            return {"text": f"{described}\n\nText read from the image:\n{read}",
                    "engine": "vision+tesseract"}
        return {"text": described, "engine": "vision"}

    # No model — the exact reader is all there is, and for a typed document
    # that is enough to carry on with.
    if read:
        # The raw failure goes in `model_error`, not `warning`. `warning` is
        # what the router hands the customer as the note beside their file, and
        # `LLMUnavailable` stringifies to the label, the base URL, every model
        # tried and the underlying httpx exception — a wall of text on an
        # upload that in fact read perfectly well.
        return {**ocr,
                "warning": "Read by OCR only — the vision model did not answer.",
                "model_error": seen.get("error") or ""}

    return {"text": "", "engine": "none",
            "error": seen.get("error") or ocr.get("error") or "Image could not be read."}


__all__ = ["read_image", "describe_image", "ocr_is_usable"]
