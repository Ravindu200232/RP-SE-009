"""Extraction adapter tests (degrade gracefully without optional deps)."""
from pathlib import Path

from app.extraction import (
    build_brief,
    extract_image_text,
    extract_pdf_text,
    transcribe_audio,
)

SAMPLE_PDF = Path(__file__).resolve().parents[3] / "samples" / "stayease_ieee830.pdf"


def test_voice_returns_transcript_or_warning():
    res = transcribe_audio(b"\x00\x01\x02fakeaudio", "audio.webm")
    assert "text" in res
    # Either a real transcript or a clear setup warning (never a fake transcript).
    assert res.get("text") or res.get("warning") or res.get("engine") == "none"


def test_image_ocr_adapter_returns_dict():
    # 1x1 PNG; OCR yields empty text but must return a structured result.
    png = bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000002000154a24f5f0000000049454e44ae426082"
    )
    res = extract_image_text(png, "x.png")
    assert "text" in res and "engine" in res


def test_pdf_extraction_returns_dict():
    if not SAMPLE_PDF.exists():
        return
    res = extract_pdf_text(SAMPLE_PDF.read_bytes(), SAMPLE_PDF.name)
    assert "text" in res and "engine" in res
    if res["engine"] != "none":
        assert len(res["text"]) > 100  # real text extracted


def test_build_brief_merges_sources():
    brief = build_brief(
        "A hotel app",
        [{"mode": "pdf", "filename": "spec.pdf", "text": "Guests can book rooms."}],
    )
    assert "USER IDEA" in brief and "hotel app" in brief
    assert "PDF SOURCE" in brief and "book rooms" in brief
