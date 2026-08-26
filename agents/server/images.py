# Fooocus generation, uploads and image completion.
BROWSER_CONSOLE_MAX = 6000


def _browser_console(msg: dict) -> str:
    """
    What the preview's console had logged, as the client sent it.

    Trimmed here rather than trusted: the client already caps it, and the cap
    that matters is the one on the side that pastes the text into a prompt. An
    app in a render loop can log the same error thousands of times a second,
    and a repair prompt that arrives mostly full of console does not leave room
    for the file it is supposed to repair.

    The tail, not the head — the errors nearest the complaint are the ones from
    the thing that just failed.
    """
    text = str(msg.get("console") or "").strip()
    if len(text) <= BROWSER_CONSOLE_MAX:
        return text
    return "…\n" + text[-BROWSER_CONSOLE_MAX:]


def _think_flag(msg: dict):
    """
    The UI's thinking switch, as Ollama's tri-state.

    True and False are both instructions — `false` actively suppresses a
    reasoning model's thinking, which is the whole point of being able to turn
    it off. A request that carries no flag at all leaves the model's own
    default alone, so an older client keeps behaving exactly as it did.
    """
    v = msg.get("think")
    return None if v is None else bool(v)


def _find_fooocus_config() -> str:
    """Where Fooocus keeps its config, looked for rather than assumed.

    This was one absolute path with a drive letter in it, and the install has
    since moved from E: to D: to C:. Each time, the path in the source pointed
    at a drive that was not mounted — harmless, because it is only a fallback
    for reading model paths, but it is also never right for anybody else.

    Only used when `image_host` gives nothing away; the agent finds the running
    Fooocus on its own port regardless. Cheap enough to run at import: a
    handful of `is_file()` calls on paths that mostly do not exist.
    """
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
    """Every directory that might hold a Fooocus launcher, nearest first.

    `image_config` leads the list because that path is already known to point
    into a real install — walking up from `…/Fooocus/config.txt` reaches the
    launcher beside it without guessing where the folder is. The scan is the
    fallback for an install that was never configured.
    """
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
                    out += [folder, folder / folder.name]
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
    """
    Launch the local Fooocus. Returns "" on success, else why not.

    Detached and in its own window: it takes minutes to load a checkpoint the
    first time, prints its progress, and is the thing somebody needs to read
    when it fails. Nothing here waits for it — `/image-check` is what says
    whether it came up.
    """
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
    """A name from the browser, reduced to something that cannot leave the folder.

    Both the picture name and the project name are pasted straight into a path,
    so `../../` in either walks out of `public/generated` and writes wherever it
    likes. Taking the basename first and then keeping only safe characters means
    neither a separator nor a drive letter survives.
    """
    stem = Path(str(raw or "").replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")
    return (Path(stem).stem or fallback)[:60]


def save_uploaded_image(raw_b64: str, out: Path) -> str:
    """Write a browser upload to `out` as a real PNG. Returns "" or the reason.

    Re-encoded rather than saved as it arrived, because the file is copied
    byte-for-byte to `public/logo.png` at build time — a JPEG sitting at a .png
    path is a lie the rest of the pipeline has no reason to expect. Re-encoding
    also settles webp, bmp and animated gif, and is the point at which a corrupt
    upload is caught rather than becoming a broken image in the built app.
    """
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


def read_attachment(filename: str, data_b64: str, proj_dir: Path = None) -> dict:
    """Turn one attached file into something an editing prompt can carry.

    The three editing tools all take a single instruction string and hand it to
    a model, so the cheapest way to let somebody attach a document to one of
    them is to make the attachment *part of that string*. No edit path changes,
    no new websocket message, and the three tools cannot drift apart.

    A picture is the one case with two possible meanings — "put this on the
    page" and "make it look like this" — and guessing is worse than serving
    both: the file is saved into the project where an `<img>` can point at it,
    AND it is read, so the description goes into the prompt. Which one the user
    meant is in their own words, where the model can see it.

    The readers are the SRS agent's, already installed and already exercised by
    the intake: text layer first for a PDF and the vision model for the pages it
    cannot reach, faster-whisper for audio.
    """
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
        else:
            out["kind"] = "text"
            res = {"text": raw.decode("utf-8", "ignore")}

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


INLINE_BUDGET = 6_000_000
PREVIEW_SIDE = 900


def preview_uri(out: Path) -> str:
    """A data: URI for `out`, shrinking it rather than giving up when it is big.

    The caller shows this as the picture; there is no second source to fall back
    on, so returning "" means the screen says nothing was produced while every
    other field says something was. That branch used to be unreachable — Fooocus
    caps its aspects at about a megapixel, so a generated PNG never approached
    the budget — and an upload at 2048² makes it live: a photograph re-encodes
    to seven to nine megabytes whatever size the JPEG that carried it was.

    So the budget now governs how the preview is made, not whether there is one.
    The file on disk is untouched; it is the full-resolution picture the build
    copies. Only the copy travelling to the browser is scaled.
    """
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
    """The kinds of picture the customer asked for, from the adopted interview.

    `adopt_srs` copies `interview.json` next to the SRS, and it is the only
    artefact that still holds the answers verbatim — the SRS document itself
    reduces "tire photos, supplier logos, vehicle photos" to one adjective in
    `ui_ux_requirements.design_style`, which is not something a planner can
    turn into an image list.
    """
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


def _image_brief_line(proj_dir: Path) -> str:
    """
    What the planner is told about pictures — which until now was nothing.

    The plan is the only thing that decides whether an app has images:
    `run_image_stage` draws exactly what `plan["images"]` lists, and the
    planner's instructions end with "omit the heading entirely for an app with
    no pictures — an admin dashboard usually has none". A POS reads as an admin
    dashboard, so the heading was omitted, `plan["images"]` came back empty, and
    the image stage returned before it reached Fooocus.

    That happened with the switch on, Fooocus answering, and the customer
    having answered a question in the interview asking which artwork they
    wanted — tire photos, supplier logos, vehicle photos. Every layer worked
    and no picture was ever drawn, because the one component that decides was
    the only one never told any of it.

    The off branch matters as much: told nothing, a planner is equally free to
    write `<img src="/generated/hero.png">` for a build with no generator
    behind it, and every one of those tags is a 404 in the shipped app.
    """
    agent = image_agent()
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
    wishes = _image_wishes(proj_dir)
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


def run_image_stage(arch, proj_dir: Path) -> int:
    """
    Generate the pictures the plan asked for, into the project's public folder.

    Runs after the files are written and before the build check, for two
    reasons: the markup already references `/generated/<key>.png`, so the paths
    are settled; and a missing image is not a compile error, so nothing
    downstream has to wait on the GPU to find out whether the app builds.

    Every failure here is survivable. An app with a broken <img> is worth
    shipping; a build that died because a GPU was busy is not.
    """
    plan_images = (arch.plan or {}).get("images") or []
    if not plan_images:
        return 0
    agent = image_agent()
    if not agent.enabled:
        elog("INFO", f"   🖼 {len(plan_images)} image(s) planned — image "
                     f"generation is off, so the app ships with the tags in "
                     f"place and the files missing")
        return 0
    if not agent.available():
        elog("WARN", "   ⚠ No Fooocus is answering — the planned images are "
                     "skipped. Start it, or set its address in Settings.")
        return 0

    ephase({"phase": -21, "title": f"Generating {len(plan_images)} image(s)",
            "status": "active"})
    out_dir = proj_dir / "public" / "generated"
    made = 0
    for n, im in enumerate(plan_images, start=1):
        eprog(f"Image {n}/{len(plan_images)}…", 78)
        if agent.generate(im["prompt"], out_dir / f"{im['key']}.png",
                          aspect=im.get("aspect", "landscape")):
            made += 1
    ephase({"phase": -21, "title": f"Generating {len(plan_images)} image(s)",
            "status": "done", "written": made})
    elog("INFO" if made else "WARN",
         f"   🎨 {made}/{len(plan_images)} image(s) generated")
    return made


_GEN_IMG_RE = re.compile(r"/generated/([A-Za-z0-9._-]+)\.(?:png|jpg|jpeg|webp)")


_GEN_IMG_TPL_RE = re.compile(
    r"/generated/\$\{([^}]{1,80})\}\.(?:png|jpg|jpeg|webp)")


_SEED_LABEL_RE = re.compile(r"\b(?:name|title|label)\s*:\s*['\"]([^'\"]{1,80})['\"]")


def _seeded_values(arch, field: str) -> dict:
    """
    `{value: label}` for every literal `field: '…'` in the project's seed.

    The label is the `name`/`title`/`label` in the SAME object literal, found
    by walking out to the braces either side rather than by parsing
    JavaScript.

    The braces are the whole point. A fixed-size window around the match
    reaches back into the object before it, and `search` returns the first
    match it finds there — so every row was paired with its predecessor's
    name: `snake-plant` came back labelled "Fiddle Leaf Fig", and five plants
    would have been drawn as the wrong species. An empty label is harmless
    (the filename is used instead); a confidently wrong one is not.
    """
    field_re = re.compile(r"\b" + re.escape(field) + r"\s*:\s*['\"]([^'\"]{1,80})['\"]")
    out = {}
    for rel, body in arch.files.items():
        if "seed" not in rel.lower() or not rel.endswith(".js"):
            continue
        for m in field_re.finditer(body):
            value = m.group(1).strip()
            if not value or "/" in value:
                continue
            open_at = body.rfind("{", 0, m.start())
            close_at = body.find("}", m.end())
            span = body[(open_at + 1 if open_at != -1 else 0):
                        (close_at if close_at != -1 else len(body))]
            label = _SEED_LABEL_RE.search(span)
            out.setdefault(value, label.group(1).strip() if label else "")
    return out


_IMG_TAG_RE = re.compile(
    r"<(?:Image|img)\b[^>]*?>", re.S | re.I)
_ALT_RE = re.compile(r"""\balt\s*=\s*["'{]\s*([^"'}]{3,120})""")

IMAGE_STYLE = ("photographic, natural light, shallow depth of field, "
               "no text, no watermark, no people looking at the camera")


def _fill_missing_images(arch, proj_dir: Path, why: str = "an edit", *,
                         explicit_request: bool = False) -> int:
    """
    Draw any picture the app now asks for and does not have.

    An edit that adds a section usually adds a picture with it — the model
    writes `<img src="/generated/spa-suite.png" alt="a hotel spa suite" />`
    because that is what the markup needs, and then nothing draws it, so the
    page ships with a broken image. The build has an image stage, but it only
    reads `plan.images`, which is written once before any edit exists.

    So: after an edit, look at what the source references, compare it with
    what is on disk, and generate the difference. The alt text is the prompt —
    it is already a description of the picture, written by the model that
    decided the picture belonged there.

    Never fatal. An app with one missing image is worth serving; a failed edit
    because a GPU was busy is not.
    """
    wanted = {}
    for rel, body in arch.files.items():
        if not rel.endswith((".jsx", ".js", ".css")):
            continue
        for tag in _IMG_TAG_RE.findall(body):
            names = _GEN_IMG_RE.findall(tag)
            if not names:
                continue
            alt = _ALT_RE.search(tag)
            for name in names:
                wanted.setdefault(name, (alt.group(1).strip() if alt else "",
                                         rel))

        for name in _GEN_IMG_RE.findall(body):
            wanted.setdefault(name, ("", rel))

        for expr in _GEN_IMG_TPL_RE.findall(body):
            field = expr.strip().split(".")[-1].strip()
            if not field.isidentifier():
                continue
            rows = _seeded_values(arch, field)
            if not rows:

                elog("WARN", f"   🖼 {rel} builds its image path from "
                             f"`{expr.strip()}` and no seeded `{field}` values "
                             f"were found — those pictures cannot be drawn and "
                             f"the page will 404 on every one")
                continue
            for value, label in rows.items():
                wanted.setdefault(value, (label, rel))

    out_dir = proj_dir / "public" / "generated"
    missing = {n: v for n, v in wanted.items()
               if not (out_dir / f"{n}.png").is_file()}
    if not missing:
        return 0

    agent = image_agent()
    if explicit_request:
        agent.enabled = True
        if not agent.available():
            why_start = start_fooocus()
            if not why_start:
                agent._checked = None
                for _ in range(20):
                    if agent.available():
                        break
                    time.sleep(1)
            else:
                elog("WARN", f"   ⚠ Fooocus could not be started: {why_start}")
    if not agent.enabled or not agent.available():
        elog("WARN", f"   🖼 {len(missing)} picture(s) {why} added are not "
                     f"drawn — image generation is off or no Fooocus is "
                     f"answering: {', '.join(sorted(missing))}")
        return 0

    idea = (arch.plan or {}).get("description") or (arch.plan or {}).get("title") or ""
    made = 0
    ephase({"phase": -21, "title": f"Drawing {len(missing)} picture(s)",
            "status": "active"})
    for name, (alt, rel) in sorted(missing.items()):

        subject = alt or name.replace("-", " ").replace("_", " ")
        prompt = f"{subject}, {IMAGE_STYLE}"
        if idea:
            prompt = f"{subject}, for {idea[:80]}, {IMAGE_STYLE}"
        elog("INFO", f"   🎨 {name}.png — {subject[:70]}")
        try:
            if agent.generate(prompt, out_dir / f"{name}.png",
                              aspect="landscape"):
                made += 1
            else:
                elog("WARN", f"   ⚠ {name}.png could not be drawn")
        except Exception as e:
            elog("WARN", f"   ⚠ {name}.png failed: {e}")
            log.debug(f"fill image {name}", exc_info=True)
    ephase({"phase": -21, "title": f"Drawing {len(missing)} picture(s)",
            "status": "done", "written": made})
    elog("INFO" if made else "WARN",
         f"   🖼 {made}/{len(missing)} picture(s) drawn for {why}")
    return made


def check_seed_duplicates(proj_dir: Path) -> list:
    """
    Rows the seed wrote more than once, counted in the live database.

    `ensureSeeded()` runs on a cold start, so it runs again on every dev-server
    restart, and whether that is harmless depends entirely on whether the seed
    is idempotent. Two static attempts at deciding that from `lib/seed.js` were
    both wrong — the first reported thirty-one of forty-two projects including
    ones upserting on `{ email }`, the second missed six that were genuinely
    duplicating and flagged four that were not. The causes are too varied to
    read off the source: no guard, an unstable key, a key that is not unique,
    a seed that races itself.

    Counting is not a guess. A clinic seeded five pets and six appointments and
    the collection held eighty-four; a shop seeded a handful of reviews and
    held seventy-six. Whatever the reason, that is the bug the user sees — the
    same dog fourteen times on the ward board.
    """
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
