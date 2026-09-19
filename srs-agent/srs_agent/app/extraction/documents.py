"""Read a document or an archive, using nothing but the standard library.

Word, PowerPoint and Excel files are zip archives of XML, and a zip is a zip,
so none of this needs a dependency. Without it every one of these formats was
decoded as if it were plain text: a specification written in Word reached the
model as a page of zip bytes, which is worse than not attaching it at all,
because the model reads it anyway and believes what it finds.
"""
from __future__ import annotations

import html
import io
import re
import zipfile
from typing import Any, Callable

# Which parts of each Office format carry the words.
OFFICE_PART = {
    ".docx": ("word/document.xml",),
    ".pptx": ("ppt/slides/slide",),
    ".xlsx": ("xl/sharedStrings.xml",),
}
DOCUMENT_EXT = tuple(OFFICE_PART) + (".rtf", ".doc")

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")

# What is worth quoting out of an archive rather than only naming.
ARCHIVE_TEXT_EXT = (".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".yaml", ".yml",
                    ".html", ".htm", ".css", ".js", ".jsx", ".ts", ".tsx", ".py", ".sql",
                    ".env", ".ini", ".toml", ".xml", ".svg")
ARCHIVE_TEXT_BUDGET = 24_000
ARCHIVE_LIST_MAX = 120


def _suffix(filename: str) -> str:
    name = str(filename or "").lower()
    return "." + name.rsplit(".", 1)[-1] if "." in name else ""


def _xml_words(xml: str) -> str:
    """The readable text out of one Office XML part."""
    xml = re.sub(r"</w:p>|</a:p>|</w:tr>", "\n", xml)
    xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
    xml = re.sub(r"</si>|</row>", "\n", xml)
    xml = re.sub(r"<[^>]+>", "", xml)
    return html.unescape(xml)


def _rtf_words(data: bytes) -> str:
    body = data.decode("utf-8", "ignore")
    body = re.sub(r"\\'[0-9a-f]{2}|\\[a-z]+-?\d*\s?|[{}]", " ", body)
    return re.sub(r"[ \t]{2,}", " ", body).strip()


def read_document(data: bytes, filename: str = "upload") -> dict[str, Any]:
    """The words in a .docx, .pptx, .xlsx or .rtf. Never raises."""
    suffix = _suffix(filename)
    if suffix == ".rtf":
        text = _rtf_words(data)
        return {"text": text, "engine": "rtf"} if text else {
            "text": "", "engine": "rtf", "warning": "nothing readable was found in this file"}
    if suffix == ".doc":
        return {"text": "", "engine": "none",
                "warning": "this is the old binary Word format; save it as .docx or a PDF "
                           "and attach that instead"}
    if suffix not in OFFICE_PART:
        return {"text": "", "engine": "none", "error": f"{suffix or filename} is not a document"}

    wanted = OFFICE_PART[suffix]
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = [name for name in archive.namelist()
                     if any(name.startswith(part) for part in wanted)]
            # slide2 before slide10, which sorting the strings does not do.
            names.sort(key=lambda name: (len(name), name))
            parts = []
            for name in names:
                try:
                    parts.append(_xml_words(archive.read(name).decode("utf-8", "ignore")))
                except (KeyError, OSError):
                    continue
    except (zipfile.BadZipFile, OSError) as error:
        return {"text": "", "engine": "zip",
                "error": f"{suffix[1:]} could not be opened ({error})"}

    text = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip()
    if not text:
        return {"text": "", "engine": "zip",
                "warning": f"nothing readable was found in this {suffix[1:]}"}
    return {"text": text, "engine": "zip", "parts": len(parts)}


def read_archive(data: bytes, filename: str = "upload.zip",
                 save_image: Callable[[str, bytes], str] | None = None) -> dict[str, Any]:
    """What is inside a zip: its listing, the text in it, and its pictures.

    A zip is how a pile of things arrives - a design export, a data dump, last
    year's site. Naming every entry says what was given; quoting the text files
    says what they contain. `save_image`, when a caller provides one, is handed
    each picture and returns the path it put it at, so the pictures become
    something that can be pointed to rather than something merely mentioned.
    """
    lines: list[str] = []
    quoted: list[str] = []
    saved: list[str] = []
    budget = ARCHIVE_TEXT_BUDGET
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = [item for item in archive.infolist() if not item.is_dir()]
            for item in entries[:ARCHIVE_LIST_MAX]:
                lines.append(f"- {item.filename} ({item.file_size} bytes)")
            if len(entries) > ARCHIVE_LIST_MAX:
                lines.append(f"- … and {len(entries) - ARCHIVE_LIST_MAX} more")

            for item in entries:
                lower = item.filename.lower()
                if lower.endswith(ARCHIVE_TEXT_EXT) and budget > 0:
                    try:
                        body = archive.read(item).decode("utf-8", "ignore").strip()
                    except (KeyError, OSError):
                        continue
                    if not body:
                        continue
                    body = body[:budget]
                    budget -= len(body)
                    quoted.append(f"#### {item.filename}\n{body}")
                elif lower.endswith(IMAGE_EXT) and save_image is not None:
                    try:
                        where = save_image(item.filename, archive.read(item))
                    except (KeyError, OSError, ValueError):
                        continue
                    if where:
                        saved.append(f"- {where} (was {item.filename})")
    except (zipfile.BadZipFile, OSError) as error:
        return {"text": "", "engine": "zip",
                "error": f"the archive could not be opened ({error})"}

    parts = ["It contains:", *lines]
    if saved:
        parts += ["", "Its pictures are now in the project at these exact paths:", *saved]
    if quoted:
        parts += ["", *quoted]
    return {"text": "\n".join(parts).strip(), "engine": "zip",
            "entries": len(lines), "images": len(saved)}


def read_text(data: bytes, filename: str = "upload") -> dict[str, Any]:
    """Decode a file that claims to be text, and say so when it is not.

    Everything unrecognised used to be decoded regardless, so a binary arrived
    as a page of replacement characters the model would then try to interpret.
    A file that cannot be read is worth one honest sentence instead.
    """
    if b"\x00" in data[:4096]:
        return {"text": "", "engine": "raw",
                "warning": f"{filename} is not a text file, so nothing was read from it"}
    try:
        return {"text": data.decode("utf-8"), "engine": "raw"}
    except UnicodeDecodeError:
        decoded = data.decode("utf-8", "ignore")
        sample = decoded[:4000]
        printable = sum(1 for ch in sample if ch.isprintable() or ch.isspace())
        if not decoded.strip() or printable < len(sample) * 0.8:
            return {"text": "", "engine": "raw",
                    "warning": f"{filename} could not be read as text"}
        return {"text": decoded, "engine": "raw",
                "warning": f"{filename} was not valid UTF-8; unreadable bytes were dropped"}
