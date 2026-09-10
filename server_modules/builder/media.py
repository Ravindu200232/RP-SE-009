# Optional image flow: validate -> generate or copy -> inspect -> publish.
BROWSER_CONSOLE_MAX = 6000


def _browser_console(msg: dict) -> str:
    """Return the latest bounded preview-console evidence for a prompt."""
    text = str(msg.get("console") or "").strip()
    if len(text) <= BROWSER_CONSOLE_MAX:
        return text
    return "…\n" + text[-BROWSER_CONSOLE_MAX:]


def _think_flag(msg: dict):
    """Preserve the UI thinking switch as an Ollama tri-state."""
    v = msg.get("think")
    return None if v is None else bool(v)


def _find_fooocus_config() -> str:
    """Find a portable Fooocus config instead of assuming a drive path."""
    inside = ("Fooocus/config.txt", "config.txt", "fooocus_config.json")
    for root in _FOOOCUS_ROOTS:
        try:
            if not root.exists():
                continue
            for folder in sorted(root.glob("Fooocus*")):
                for rel in inside:
                    candidate = folder / rel
                    if candidate.is_file():
                        return str(candidate)
                nested = folder / folder.name
                for rel in inside:
                    candidate = nested / rel
                    if candidate.is_file():
                        return str(candidate)
        except OSError:
            continue
    return ""


_FOOOCUS_ROOTS = (
    [Path(f"{d}:/") for d in "CDEFG"]
    + [Path.home() / p for p in
       ("", "Downloads", "Documents", "Desktop", "Documents/GitHub",
        "OneDrive/Documents", "OneDrive/Documents/GitHub", "OneDrive/Desktop")]
)


_FOOOCUS_LAUNCHERS = ("run_4gb.bat", "run.bat", "run_anime.bat",
                      "run_realistic.bat", "run.sh")


def _fooocus_folders() -> list:
    """Return likely launcher folders, preferring the configured install."""
    settings = load_settings()
    out = []
    config = str(settings.get("image_config", FOOOCUS_CONFIG)).strip()
    if config:
        here = Path(config).parent
        out += [here, *list(here.parents)[:3]]
    for root in _FOOOCUS_ROOTS:
        try:
            if root.exists():
                for folder in sorted(root.glob("Fooocus*")):
                    here = folder
                    for _ in range(4):
                        out.append(here)
                        here = here / folder.name
        except OSError:
            continue
    return out


def _fooocus_launcher() -> str:
    """The script that starts Fooocus on this machine, or ""."""
    explicit = str(load_settings().get("image_launcher", "")).strip()
    if explicit and Path(explicit).is_file():
        return explicit

    folders = _fooocus_folders()
    for name in _FOOOCUS_LAUNCHERS:
        for folder in folders:
            candidate = folder / name
            try:
                if candidate.is_file():
                    return str(candidate)
            except OSError:
                continue
    return ""


def start_fooocus() -> str:
    """Launch Fooocus detached; return an empty string or the failure reason."""
    script = _fooocus_launcher()
    if not script:
        return ("no Fooocus install was found — start it yourself, or set "
                "image_launcher in Settings to its run script")
    folder = Path(script).parent
    try:
        if os.name == "nt":
            subprocess.Popen(["cmd", "/c", "start", "", Path(script).name],
                             cwd=str(folder), shell=False,
                             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
        else:
            subprocess.Popen(["/bin/sh", str(script)], cwd=str(folder),
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,
                             start_new_session=True)
    except OSError as e:
        return f"could not start {Path(script).name}: {e}"
    elog("INFO", f"   🎨 Starting Fooocus — {script}")
    return ""


FOOOCUS_CONFIG = _find_fooocus_config()


def image_agent(callbacks: dict = None) -> ImageAgent:
    """The configured Fooocus, whether or not it is switched on."""
    s = load_settings()
    return ImageAgent(host=str(s.get("image_host", "")).strip(),
                      config_path=str(s.get("image_config", FOOOCUS_CONFIG)),
                      callbacks=callbacks or _analyzer_callbacks(),
                      enabled=bool(s.get("image_enabled", False)))


def _image_settings() -> dict:
    s = load_settings()
    return {
        "image_enabled": bool(s.get("image_enabled", False)),
        "image_host": str(s.get("image_host", "")),
        "image_config": str(s.get("image_config", FOOOCUS_CONFIG)),
        "image_launcher": str(s.get("image_launcher", "")),
        "lan_access": bool(s.get("lan_access", False)),
    }


UPLOAD_IMAGE_MAX = 7_500_000
UPLOAD_IMAGE_SIDE = 2048


def _safe_stem(raw: str, fallback: str = "upload") -> str:
    """Reduce a browser-supplied name to one safe path stem."""
    stem = Path(str(raw or "").replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")
    return (Path(stem).stem or fallback)[:60]


def save_uploaded_image(raw_b64: str, out: Path) -> str:
    """Validate and re-encode a browser upload as bounded PNG data."""
    raw = str(raw_b64 or "")
    if raw.lstrip().startswith("data:") and "," in raw[:64]:
        raw = raw.split(",", 1)[1]  # a browser data: URL
    if not raw.strip():
        return "no image was sent"
    try:
        blob = base64.b64decode(raw, validate=False)
    except Exception as e:                                      # noqa: BLE001
        return f"that is not valid base64 ({e})"
    if not blob:
        return "the image was empty"
    if len(blob) > UPLOAD_IMAGE_MAX:
        return f"the image is larger than {UPLOAD_IMAGE_MAX // 1_000_000} MB"

    try:
        from PIL import Image
    except Exception:                                           # noqa: BLE001
        # No Pillow: only a file that is already a PNG.
        if blob[:8] != b"\x89PNG\r\n\x1a\n":
            return "Pillow is not installed, so only PNG files can be uploaded"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(blob)
        return ""

    try:
        img = Image.open(io.BytesIO(blob))
        img.load()
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        img.thumbnail((UPLOAD_IMAGE_SIDE, UPLOAD_IMAGE_SIDE))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    except Exception as e:                                      # noqa: BLE001
        return f"that file could not be read as an image ({e})"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(buf.getvalue())
    return ""


IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac")
ATTACH_TEXT_CAP = 6000

# Documents and archives are read by the same package that reads PDFs, so
# there is one implementation of each format and the specification agent gets
# it too.
DOCUMENT_EXT = (".docx", ".pptx", ".xlsx", ".rtf", ".doc")


def _keep_picture(proj_dir: Path | None):
    """Hand an archive somewhere to put the pictures it is carrying.

    A picture the build is told about has to exist at the path it is given, so
    this only exists once there is a project to put one in.
    """
    if proj_dir is None:
        return None

    def keep(name: str, blob: bytes) -> str:
        stem = _safe_stem(name, "picture")
        out = proj_dir / "public" / "generated" / f"{stem}.png"
        if save_uploaded_image(base64.b64encode(blob).decode("ascii"), out):
            return ""
        return f"/generated/{stem}.png"

    return keep


def read_attachment(filename: str, data_b64: str, proj_dir: Path = None) -> dict:
    """Convert one image, PDF, audio, or text attachment into prompt context."""
    name = str(filename or "upload")
    lower = name.lower()
    out = {"kind": "file", "text": "", "url": "", "note": ""}

    try:
        if lower.endswith(IMAGE_EXT):
            out["kind"] = "image"
            stem = _safe_stem(name, "attached")
            where = ((proj_dir / "public" / "generated") if proj_dir
                     else (LOGS_DIR / "images")) / f"{stem}.png"
            why = save_uploaded_image(data_b64, where)
            if why:
                out["note"] = why
                return out
            out["url"] = f"/generated/{stem}.png"

            from srs_agent.app.extraction import read_image
            res = asyncio.run(read_image(base64.b64decode(_strip_data_url(data_b64)), name))
            out["text"] = (res.get("text") or "").strip()
            out["note"] = res.get("warning") or res.get("error") or ""
            return out

        raw = base64.b64decode(_strip_data_url(data_b64))

        if lower.endswith(".pdf"):
            out["kind"] = "pdf"
            from srs_agent.app.extraction import read_pdf
            res = asyncio.run(read_pdf(raw, name))
        elif lower.endswith(AUDIO_EXT):
            out["kind"] = "audio"
            from srs_agent.app.extraction import transcribe_audio
            res = transcribe_audio(raw, name)
        elif lower.endswith(DOCUMENT_EXT):
            out["kind"] = "document"
            from srs_agent.app.extraction import read_document
            res = read_document(raw, name)
        elif lower.endswith(".zip"):
            out["kind"] = "archive"
            from srs_agent.app.extraction import read_archive
            res = read_archive(raw, name, save_image=_keep_picture(proj_dir))
        else:
            out["kind"] = "text"
            from srs_agent.app.extraction import read_text
            res = read_text(raw, name)

        out["text"] = (res.get("text") or "").strip()
        out["note"] = res.get("warning") or res.get("error") or ""
    except Exception as e:                                      # noqa: BLE001
        log.warning(f"attachment {name}: {e}")
        out["note"] = f"{name} could not be read ({e})"
    return out


def _strip_data_url(raw: str) -> str:
    raw = str(raw or "")
    if raw.lstrip().startswith("data:") and "," in raw[:64]:
        return raw.split(",", 1)[1]
    return raw


# Where a chosen file waits between being picked on the home screen and there
# being a project to read it into. Hidden, so nothing lists it as a project.
STAGE_ROOT = ".attachments"


def _stage_dir(token: str) -> Path | None:
    stem = _safe_stem(token, "")
    return (PROD_DIR / STAGE_ROOT / stem) if stem else None


def stage_attachment(token: str, filename: str, data_b64: str,
                     purpose: str = "") -> dict:
    """Hold one file for the build that is about to start.

    The home screen accepts a PDF or a picture before any project exists, and
    until now only the specification agent could read one: pressing Build threw
    them away, so a request that said "the menu is in this PDF" was built from a
    sentence with no menu in it.

    The bytes come here over HTTP rather than travelling in the build message,
    which goes over the WebSocket and is refused above a megabyte - a limit an
    ordinary scanned PDF passes without trying.
    """
    stage = _stage_dir(token)
    if stage is None:
        return {"error": "an attachment needs a build to belong to"}
    name = str(filename or "upload")
    try:
        blob = base64.b64decode(_strip_data_url(data_b64), validate=False)
    except Exception as e:                                      # noqa: BLE001
        return {"error": f"that is not valid base64 ({e})"}
    if not blob:
        return {"error": f"{name} was empty"}

    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name.replace("\\", "/")).name).strip("-.")
    safe = safe[:80] or "upload"
    try:
        stage.mkdir(parents=True, exist_ok=True)
        (stage / safe).write_bytes(blob)
        purpose = " ".join(str(purpose or "").split())[:300]
        if purpose:
            (stage / f"{safe}.purpose").write_text(purpose, encoding="utf-8")
    except OSError as e:
        return {"error": f"{name} could not be held ({e})"}
    return {"ok": True, "name": safe, "bytes": len(blob)}


def read_staged_attachments(token: str, proj_dir: Path) -> str:
    """Read everything staged for this build, as prose for its brief.

    Read here rather than in the browser because this is the first moment there
    is a project: a picture the build is told to use has to exist at the path it
    is given, and only now is that path known.

    The stage is emptied afterwards. It held a copy; the project has its own.
    """
    stage = _stage_dir(token)
    if stage is None or not stage.is_dir():
        return ""

    parts = []
    for fp in sorted(stage.iterdir()):
        if not fp.is_file() or fp.suffix == ".purpose":
            continue
        got = read_attachment(fp.name, base64.b64encode(fp.read_bytes()).decode("ascii"),
                              proj_dir)
        text = (got.get("text") or "").strip()[:ATTACH_TEXT_CAP]
        note = str(got.get("note") or "").strip()
        purpose = ""
        wanted = fp.with_suffix(fp.suffix + ".purpose")
        if wanted.is_file():
            purpose = wanted.read_text(encoding="utf-8").strip()

        if got.get("kind") == "image" and got.get("url"):
            said = (f"### {fp.name} - a picture, already saved at {got['url']}\n"
                    f"It is on disk at that exact path. Use it in an `<img>` where "
                    f"the request calls for it; do not invent another path and do "
                    f"not leave a placeholder.")
        else:
            what = {"pdf": "a document", "document": "a document",
                    "audio": "a recording, transcribed",
                    "archive": "an archive, listed and read",
                    "text": "a file"}.get(got.get("kind"), "a file")
            said = f"### {fp.name} - {what}"
        if purpose:
            said += f"\nWhat they said it is for: {purpose}"
        if text:
            said += f"\n{text}"
        if note:
            said += f"\n({note})"
        parts.append(said)
        elog("INFO", f"   📎 read {fp.name}"
                     + (f" — {len(text)} characters" if text else " — nothing could be read"))

    shutil.rmtree(stage, ignore_errors=True)
    if not parts:
        return ""
    return ("\n\n## What they attached to the request\n\n"
            + "\n\n".join(parts))


INLINE_BUDGET = 6_000_000
PREVIEW_SIDE = 900


def preview_uri(out: Path) -> str:
    """Create a bounded PNG data URI without changing the source file."""
    try:
        raw = out.read_bytes()
    except OSError as e:
        log.debug(f"inline {out}: {e}")
        return ""

    if len(raw) <= INLINE_BUDGET:
        return "data:image/png;base64," + base64.b64encode(raw).decode()

    try:
        from PIL import Image

        img = Image.open(io.BytesIO(raw))
        img.load()
        img.thumbnail((PREVIEW_SIDE, PREVIEW_SIDE))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
    except Exception as e:                                      # noqa: BLE001
        log.debug(f"preview {out}: {e}")
        return ""
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _image_wishes(proj_dir: Path) -> list:
    """Read requested image kinds from the adopted SRS interview."""
    try:
        doc = json.loads((proj_dir / ".agentforge" / "srs" / "interview.json")
                         .read_text(encoding="utf-8"))
    except Exception:
        return []
    for answer in doc.get("answers") or []:
        if answer.get("question_id") != "image_kinds":
            continue
        value = answer.get("value")
        items = value if isinstance(value, list) else [value]
        return [str(v).replace("_", " ").strip() for v in items if str(v)]
    return []


def _image_brief_line(proj_dir: Path, requirement: str = "") -> str:
    """Tell planning exactly when generated image paths are safe to use."""
    agent = image_agent()
    wishes = _image_wishes(proj_dir)
    if requirement and not wishes and not feature_image_requested(requirement):
        return ("\n\nNO PICTURES WERE ASKED FOR in this request. Omit the "
                "`## Images` heading, leave `\"images\"` empty in the JSON, and "
                "do not write an <img> pointing at `/generated/…`. Use Tailwind "
                "gradients, inline SVG or emoji where a picture would go.\n")
    if not agent.enabled or not agent.available():
        return ("\n\nIMAGE GENERATION IS OFF for this build. Omit the "
                "`## Images` heading, leave `\"images\"` empty in the JSON, and "
                "do not write an <img> pointing at `/generated/…` — nothing "
                "will draw it and every one of them would 404. Use Tailwind "
                "gradients, inline SVG or emoji where a picture would go.\n")

    line = ("\n\nIMAGE GENERATION IS ON for this build. Every picture you list "
            "under `## Images` is drawn by a local image model into "
            "`public/generated/<key>.png` before the app first runs, so the "
            "tags you write for them point at real files. This app is not one "
            "of the ones that should omit the heading.")
    if wishes:
        line += (" The customer was asked which artwork they wanted and "
                 "answered: " + ", ".join(wishes) + ". Cover every one of "
                 "them, with a key per seeded record wherever the answer is a "
                 "photograph of a thing the app stores, so the seed can point "
                 "each row at its own picture.")
    else:
        line += (" List every picture the app is better for having — a photo "
                 "per seeded record that would carry one, a login backdrop, a "
                 "hero where the app has a public page.")
    return line + "\n"



def check_seed_duplicates(proj_dir: Path) -> list:
    """Report duplicate non-auth seed rows from the live project database."""
    try:
        from pymongo import MongoClient
    except ImportError:
        return []
    name = proj_dir.name
    try:
        db = MongoClient(MONGO.uri_for(name),
                         serverSelectionTimeoutMS=5000)[db_name_for(name)]
        collections = [c for c in db.list_collection_names()
                       if c not in ("user", "session", "account",
                                    "verification", "jwks")]
    except Exception as e:
        log.debug(f"seed duplicate check: {e}")
        return []

    out = []
    for coll in collections:
        try:

            sample = db[coll].find_one()
            if not sample:
                continue
            keys = [k for k in sample
                    if k not in ("_id", "createdAt", "updatedAt", "date")]
            if not keys:
                continue
            dupes = list(db[coll].aggregate([
                {"$group": {"_id": {k: f"${k}" for k in keys},
                            "n": {"$sum": 1}}},
                {"$match": {"n": {"$gt": 1}}},
                {"$sort": {"n": -1}},
                {"$limit": 3},
            ], maxTimeMS=8000))
        except Exception as e:
            log.debug(f"seed duplicates in {coll}: {e}")
            continue
        if dupes:
            worst = dupes[0]["n"]
            total = db[coll].count_documents({})
            out.append(f"{coll}: {total} row(s), and the seed's data is "
                       f"repeated up to {worst} times — every restart writes "
                       f"it again")
    return out


# --------------------------------------------------------------------------
# Filling in pictures the code asks for
# --------------------------------------------------------------------------
_GEN_IMG_RE = re.compile(r"/generated/([A-Za-z0-9._-]+)\.(?:png|jpg|jpeg|webp)")
_IMG_TAG_RE = re.compile(r"<(?:Image|img)\b[^>]*?>", re.S | re.I)
_ALT_RE = re.compile(r"""\balt\s*=\s*["'{]\s*([^"'}]{3,120})""")

IMAGE_STYLE = ("photographic, natural light, shallow depth of field, "
               "no text, no watermark, no people looking at the camera")

_IMAGE_SOURCE_EXT = (".jsx", ".js", ".css")
_IMAGE_SKIP_DIRS = {"node_modules", ".next", ".git", "public", ".agentforge", ".agent"}


def _wanted_images(proj_dir: Path) -> dict:
    """Every `/generated/<name>.png` the code references, with its alt text.

    Read from the files on disk rather than from a build-time plan, so a
    picture added by a later edit is filled in the same way as one planned at
    the start.
    """
    wanted: dict[str, tuple[str, str]] = {}
    for path in proj_dir.rglob("*"):
        if not path.is_file() or path.suffix not in _IMAGE_SOURCE_EXT:
            continue
        if any(part in _IMAGE_SKIP_DIRS for part in path.relative_to(proj_dir).parts):
            continue
        try:
            body = path.read_text("utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(proj_dir).as_posix()
        for tag in _IMG_TAG_RE.findall(body):
            alt = _ALT_RE.search(tag)
            for name in _GEN_IMG_RE.findall(tag):
                wanted.setdefault(name, (alt.group(1).strip() if alt else "", rel))
        for name in _GEN_IMG_RE.findall(body):
            wanted.setdefault(name, ("", rel))
    return wanted


def fill_missing_images(proj_dir: Path, why: str = "the build") -> int:
    """Draw any referenced picture that is not on disk yet.

    A missing file behind an `<img>` is a broken page, and the browser
    journeys will report it as one, so this runs before verification rather
    than being left to whoever notices the empty box.
    """
    wanted = _wanted_images(Path(proj_dir))
    if not wanted:
        return 0
    out_dir = Path(proj_dir) / "public" / "generated"
    missing = {name: meta for name, meta in wanted.items()
               if not (out_dir / f"{name}.png").is_file()}
    if not missing:
        return 0

    agent = image_agent()
    if not agent.enabled or not agent.available():
        elog("INFO", f"   🖼 {len(missing)} picture(s) referenced by {why} were not drawn "
                     "— image generation is off or no Fooocus is answering")
        return 0

    made = 0
    for index, (name, (alt, rel)) in enumerate(sorted(missing.items()), start=1):
        subject = alt or name.replace("-", " ").replace("_", " ")
        eprog(f"Picture {index}/{len(missing)}…", 78)
        if agent.generate(f"{subject}, {IMAGE_STYLE}", out_dir / f"{name}.png",
                          aspect="landscape"):
            made += 1
        else:
            log.info(f"image {name} referenced by {rel} could not be drawn")
    elog("INFO" if made else "WARN", f"   🎨 {made}/{len(missing)} picture(s) drawn for {why}")
    return made
