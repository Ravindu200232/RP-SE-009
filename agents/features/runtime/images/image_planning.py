
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
AUDIO_EXT = (".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac")
ATTACH_TEXT_CAP = 6000

# Converts one image, PDF, audio, or text attachment into prompt context.
def read_attachment(filename: str, data_b64: str, proj_dir: Path = None) -> dict:
    """Convert one image, PDF, audio, or text attachment into prompt context."""
    name = str(filename or "upload")
    lower = name.lower()
    out = {"kind": "file", "text": "", "url": "", "note": ""}

    try:
        if lower.endswith(IMAGE_EXT):
            out["kind"] = "image"
            # From: agents/features/runtime/images/image_service.py
            stem = _safe_stem(name, "attached")
            where = ((proj_dir / "public" / "generated") if proj_dir
                     else (LOGS_DIR / "images")) / f"{stem}.png"
            # From: agents/features/runtime/images/image_service.py
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

# Cleans data url in the format expected by the next pipeline steps.
def _strip_data_url(raw: str) -> str:
    """Clean data url in the standard shape used by the rest of the pipeline."""
    raw = str(raw or "")
    if raw.lstrip().startswith("data:") and "," in raw[:64]:
        return raw.split(",", 1)[1]
    return raw

INLINE_BUDGET = 6_000_000
PREVIEW_SIDE = 900

# Creates a bounded PNG data URI without changing the source file.
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

_IMAGE_YES = {"true", "yes", "1"}


# Collect SRS/interview answers that can affect which images the app needs.
def _srs_answers(proj_dir: Path) -> list:
    """Prepare the srs answers value or state used by this focused pipeline step."""
    try:
        doc = json.loads((proj_dir / ".agentforge" / "srs" / "interview.json")
                         .read_text(encoding="utf-8"))
    except Exception:
        return []
    return doc.get("answers") or []


# Read requested image kinds from the adopted SRS interview. The interview asks two separate things: `images` is
# the yes/no, and `image_kinds` is the list of kinds — and it only asks the second one sometimes. Reading the
# kinds alone meant an interview that answered "yes, generate artwork" and was never asked which kinds looked
# identical to one that asked for no pictures at all, so the planner was told NO PICTURES WERE ASKED FOR and the
# build shipped with none.
def _image_wishes(proj_dir: Path) -> list:
    """Read requested image kinds from the adopted SRS interview.

    The interview asks two separate things: `images` is the yes/no, and
    `image_kinds` is the list of kinds — and it only asks the second one
    sometimes. Reading the kinds alone meant an interview that answered "yes,
    generate artwork" and was never asked which kinds looked identical to one
    that asked for no pictures at all, so the planner was told NO PICTURES WERE
    ASKED FOR and the build shipped with none.
    """
    answers = _srs_answers(proj_dir)
    for answer in answers:
        if answer.get("question_id") != "image_kinds":
            continue
        value = answer.get("value")
        items = value if isinstance(value, list) else [value]
        kinds = [str(v).replace("_", " ").strip() for v in items if str(v)]
        if kinds:
            return kinds
    spoken = _images_spoken(proj_dir)
    if spoken:
        # They were never offered the kinds list, but they described what they
        # wanted in their own words. Those words beat any list we could guess.
        return [spoken]
    if _images_wanted(proj_dir):
        # Asked for, but never asked which kinds. Say so plainly rather than
        # inventing a list the customer never chose.
        return ["the pictures this product needs"]
    return []


# What the customer typed next to the yes/no image question, if anything.
def _images_spoken(proj_dir: Path) -> str:
    """What the customer typed next to the yes/no image question, if anything."""
    if not _images_wanted(proj_dir):
        return ""
    for answer in _srs_answers(proj_dir):
        if answer.get("question_id") != "images":
            continue
        said = str(answer.get("raw_text") or answer.get("text") or "").strip()
        # A bare "true"/"yes" is the radio button echoing itself, not a wish.
        if said and said.strip().lower().strip(".") not in _IMAGE_YES:
            return said
    return ""


# Did the interview's yes/no image question say yes?.
def _images_wanted(proj_dir: Path) -> bool:
    """Did the interview's yes/no image question say yes?"""
    for answer in _srs_answers(proj_dir):
        if answer.get("question_id") != "images":
            continue
        value = answer.get("value")
        items = value if isinstance(value, list) else [value]
        return any(str(v).strip().lower() in _IMAGE_YES for v in items)
    return False

# Tell planning exactly when generated image paths are safe to use.
def _image_brief_line(proj_dir: Path, requirement: str = "") -> str:
    """Tell planning exactly when generated image paths are safe to use."""
    # From: agents/features/runtime/images/image_service.py
    agent = image_agent()
    wishes = _image_wishes(proj_dir)
    # From: agents/features/feature_prompts.py
    if requirement and not wishes and not feature_image_requested(requirement):
        return ("\n\nNO PICTURES WERE ASKED FOR in this request. Omit the "
                "`## Images` heading, leave `\"images\"` empty in the JSON, and "
                "do not write an <img> pointing at `/generated/…`. Use Tailwind "
                "gradients, inline SVG or emoji where a picture would go.\n")
    # From: agents/features/image_generator.py
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
            "of the ones that should omit the heading. "
            "The `images` array in the JSON has to come back with real entries "
            "— a plan that returns it empty while generation is on ships an "
            "app with nothing to look at, which is the single most common way "
            "these builds come out looking unfinished. Give every entry a "
            "`key` (lowercase, hyphenated, no extension), a `prompt` written "
            "as a photographer would brief a shoot for THIS business by name, "
            "and an `aspect` of landscape, portrait or square. Then use those "
            "keys: the page that needs the picture renders "
            "`/generated/<key>.png`, and a seeded row that owns one stores "
            "that path in its own field. A key nothing references is wasted "
            "GPU time, and an `<img>` pointing at a key you never listed "
            "is a 404.")
    if wishes:
        line += (" The customer was asked which artwork they wanted and "
                 "answered: " + ", ".join(wishes) + ". Cover every one of "
                 "them, with a key per seeded record wherever the answer is a "
                 "photograph of a thing the app stores, so the seed can point "
                 "each row at its own picture.")
    else:
        line += (" List only visuals that materially improve the real product experience. "
                 "Prefer a strong public hero, useful auth backdrop, and domain-appropriate "
                 "seeded item photos; do not force images into admin tables, utility screens, "
                 "or sections that are clearer without artwork.")
    return line + "\n"

# Generate planned images without making GPU failure fatal to the build.
def run_image_stage(arch, proj_dir: Path) -> int:
    """Generate planned images without making GPU failure fatal to the build."""
    plan_images = (arch.plan or {}).get("images") or []
    if not plan_images:
        return 0
    out_dir = proj_dir / "public" / "generated"; out_dir.mkdir(parents=True, exist_ok=True)
    for im in plan_images:
        target = out_dir / f"{im['key']}.png"
        if not target.exists(): target.write_bytes(_PLACEHOLDER_PNG)
    # From: agents/features/runtime/images/image_service.py
    agent = image_agent()
    if not agent.enabled:
        # From: agents/build/tester_common.py
        elog("INFO", f"   🖼 {len(plan_images)} image(s) planned — image "
                     f"generation is off, so instant placeholder files stay in "
                     f"place instead of broken image URLs")
        return 0
    # From: agents/features/image_generator.py
    if not agent.available():
        # From: agents/build/tester_common.py
        elog("WARN", "   ⚠ The planned images are skipped — "
                     f"{agent.why_unavailable()}")
        return 0

    ephase({"phase": -21, "title": f"Generating {len(plan_images)} image(s)",
            "status": "active"})
    made = 0
    for n, im in enumerate(plan_images, start=1):
        eprog(f"Image {n}/{len(plan_images)}…", 78)
        # From: agents/features/image_generator.py
        if agent.generate(im["prompt"], out_dir / f"{im['key']}.png",
                          aspect=im.get("aspect", "landscape")):
            made += 1
    ephase({"phase": -21, "title": f"Generating {len(plan_images)} image(s)",
            "status": "done", "written": made})
    # From: agents/build/tester_common.py
    elog("INFO" if made else "WARN",
         f"   🎨 {made}/{len(plan_images)} image(s) generated")
    return made
