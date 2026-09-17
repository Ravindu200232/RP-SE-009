# The customer's own pictures: kept once, described once, copied where needed.
#
# Nothing in this system draws artwork, so every real photograph on a finished
# page arrives here - uploaded on the design screen, captioned by the person who
# knows what it is for. One folder holds the files and one manifest holds what
# each is for; `images.md` is written from that manifest so the designer and the
# builder read the same description, and the files are copied into the drawing
# and into the built app's `public/` so an `<img>` resolves in both.
#
# Imported rather than leaned on: every other name here is defined by an earlier
# runtime part, but this one arrives with a part loaded after this file.
from server_modules.services.project_state import atomic_json

SITE_IMAGE_DIRNAME = "images"
SITE_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".avif", ".ico")
SITE_IMAGE_BRIEF = "images.md"
SITE_IMAGE_MANIFEST = "manifest.json"
# What the pages reference. Relative, because the drawing is served from its own
# folder and the built app from `public/` - an absolute path would be right in
# exactly one of them.
SITE_IMAGE_WEB_DIR = "images"


def _site_dir(proj_dir: Path) -> Path:
    return proj_dir / ".agentforge" / SITE_IMAGE_DIRNAME


# Where pictures wait when there is no project yet. The design screen runs
# between an approved specification and the first build, so the only identity
# that exists at that moment is the specification's - the same staging folder
# the interview already writes to, and the same one `adopt_srs` reads when the
# project is finally created.
SITE_IMAGE_STAGE = "site-images"


def _site_folder(owner: str):
    """(folder, error) for whichever of the two things this name refers to.

    A built project owns its pictures under `.agentforge/images`. Before that
    exists the name is a specification id, and they wait in its staging folder.
    Both are addressed the same way by the studio, which knows only that it has
    an id and some files.
    """
    name = str(owner or "").strip()
    if not name:
        return None, "a project or specification is required"
    if (PROD_DIR / name).is_dir():
        _, proj_dir, error = _owned_dir(PROD_DIR, name, "project name", "project")
        return (None, error) if error else (_site_dir(proj_dir), "")
    staging = PROD_DIR / ".srs" / name
    if staging.is_dir() and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        return staging / SITE_IMAGE_STAGE, ""
    return None, f"no such project: {name}"


def adopt_site_images(srs_id: str, proj_dir: Path) -> int:
    """Move pictures chosen on the design screen into the project they built.

    Copied, not moved: building twice from one specification has to keep
    working, exactly as the staged specification itself does.
    """
    staging = PROD_DIR / ".srs" / str(srs_id or "") / SITE_IMAGE_STAGE
    if not staging.is_dir():
        return 0
    target = _site_dir(proj_dir)
    moved = 0
    try:
        target.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            if item.is_file():
                shutil.copy2(item, target / item.name)
                moved += 1
    except OSError as e:                                        # noqa: BLE001
        log.debug(f"adopt site images {srs_id}: {e}")
    return moved


def adopt_wireframes(srs_id: str, proj_dir: Path) -> int:
    """Put the page layouts where the drawing pass can read them.

    Adopted to `.agentforge/wireframes/` rather than left under the copied
    specification, because that is the one folder both agents are allowed to
    read and the one the brief can name without qualification.
    """
    staging = PROD_DIR / ".srs" / str(srs_id or "") / "wireframes"
    if not staging.is_dir():
        return 0
    target = proj_dir / ".agentforge" / "wireframes"
    copied = 0
    try:
        target.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            if item.is_file() and item.suffix.lower() == ".json":
                shutil.copy2(item, target / item.name)
                copied += 1
    except OSError as e:                                        # noqa: BLE001
        log.debug(f"adopt wireframes {srs_id}: {e}")
    return copied


def read_project_wireframes(project: str) -> dict:
    """The page layouts a built project adopted, for its own SRS tab."""
    _, proj_dir, error = _owned_dir(PROD_DIR, project, "project name", "project")
    if error:
        return {"pages": [], "journeys": [], "error": error}
    path = proj_dir / ".agentforge" / "wireframes" / "wireframes.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        return {"pages": [], "journeys": []}


def wireframe_brief(proj_dir: Path) -> str:
    """The line that tells a drawing pass the layouts already exist."""
    path = proj_dir / ".agentforge" / "wireframes" / "wireframes.json"
    try:
        pages = (json.loads(path.read_text(encoding="utf-8")) or {}).get("pages") or []
    except Exception:                                           # noqa: BLE001
        return ""
    if not pages:
        return ""
    routes = ", ".join(str(p.get("route")) for p in pages[:14])
    return (f"\n\nWIREFRAMES EXIST for {len(pages)} page(s): {routes}. Read "
            f"`.agentforge/wireframes/wireframes.json` before drawing. Each page lists its "
            f"blocks on a 0-100 grid - kind, label, x, y, w, h - which is where the customer "
            f"expects things to sit. Follow that arrangement; a page marked \"edited\": true "
            f"was positioned by hand, so match it closely. The wireframes carry no colour and "
            f"no navigation by design - take the layout from them and the look from the theme.\n")


def _site_rows(folder: Path) -> list:
    """What is on disk, in the order it was added, with its caption."""
    try:
        saved = json.loads((folder / SITE_IMAGE_MANIFEST).read_text(encoding="utf-8"))
    except Exception:                                           # noqa: BLE001
        saved = []
    captions = {str(row.get("file")): str(row.get("purpose") or "")
                for row in saved if isinstance(row, dict) and row.get("file")}
    order = [str(row.get("file")) for row in saved if isinstance(row, dict)]
    # The folder is the truth about which files exist; the manifest is the truth
    # about what they are for. A file deleted by hand should stop being listed,
    # and one dropped in by hand should still show up - uncaptioned.
    on_disk = sorted(item.name for item in folder.glob("*")
                     if item.is_file() and item.suffix.lower() in SITE_IMAGE_EXT)
    ranked = sorted(on_disk, key=lambda name: (order.index(name) if name in order else len(order), name))
    return [{"file": name, "purpose": captions.get(name, "")} for name in ranked]


def _save_site_rows(folder: Path, rows: list) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    atomic_json(folder / SITE_IMAGE_MANIFEST, rows)


def _site_answer(folder: Path, owner: str) -> dict:
    """The list, with the brief rewritten so disk and description never drift."""
    write_site_images_md_in(folder)
    return {"ok": True, "project": owner, "images": _site_rows(folder)}


def site_image_list(owner: str) -> dict:
    folder, error = _site_folder(owner)
    return {"error": error} if error else _site_answer(folder, owner)


def site_image_save(owner: str, filename: str, data_b64: str, purpose: str = "") -> dict:
    """Keep one uploaded picture under its own name and extension.

    The name is kept - not renamed to a hash or forced to PNG - because the
    caption the customer writes refers to it, and because a photograph
    re-encoded as PNG grows several times over for no gain. Only the extension
    is trusted from the name, and only from a short list.
    """
    folder, error = _site_folder(owner)
    if error:
        return {"error": error}
    raw = Path(str(filename or "").replace("\\", "/")).name
    suffix = Path(raw).suffix.lower()
    if suffix not in SITE_IMAGE_EXT:
        return {"error": f"{suffix or 'that'} files cannot be used as page images"}
    stem = _safe_stem(raw, "image")
    try:
        blob = base64.b64decode(_strip_data_url(data_b64), validate=False)
    except Exception as e:                                      # noqa: BLE001
        return {"error": f"that is not valid base64 ({e})"}
    if not blob:
        return {"error": f"{raw} was empty"}
    if len(blob) > UPLOAD_IMAGE_MAX:
        return {"error": f"{raw} is larger than {UPLOAD_IMAGE_MAX // 1_000_000} MB"}

    folder.mkdir(parents=True, exist_ok=True)
    name = f"{stem}{suffix}"
    count = 2
    while (folder / name).is_file() and count < 100:
        name = f"{stem}-{count}{suffix}"
        count += 1
    try:
        (folder / name).write_bytes(blob)
    except OSError as e:
        return {"error": f"{raw} could not be saved ({e})"}

    rows = _site_rows(folder)
    _caption(rows, name, purpose)
    _save_site_rows(folder, rows)
    return {**_site_answer(folder, owner), "file": name}


def _caption(rows: list, name: str, purpose: str) -> bool:
    """Write one row's caption, tidied. True when the row was there to write to."""
    found = False
    for row in rows:
        if row["file"] == name:
            row["purpose"] = " ".join(str(purpose or "").split())[:400]
            found = True
    return found


def site_image_describe(owner: str, file: str, purpose: str) -> dict:
    """Record what one picture is for."""
    folder, error = _site_folder(owner)
    if error:
        return {"error": error}
    name = Path(str(file or "").replace("\\", "/")).name
    rows = _site_rows(folder)
    if not _caption(rows, name, purpose):
        return {"error": f"{name} is not one of this project's images"}
    _save_site_rows(folder, rows)
    return _site_answer(folder, owner)


def site_image_drop(owner: str, file: str) -> dict:
    folder, error = _site_folder(owner)
    if error:
        return {"error": error}
    name = Path(str(file or "").replace("\\", "/")).name
    target = (folder / name).resolve()
    try:
        target.relative_to(folder.resolve())
    except ValueError:
        return {"error": f"{name} is not one of this project's images"}
    target.unlink(missing_ok=True)
    _save_site_rows(folder, [row for row in _site_rows(folder) if row["file"] != name])
    return _site_answer(folder, owner)


def read_site_image(owner: str, file: str) -> tuple:
    """(bytes, content type) for one stored picture, for the studio to show."""
    resolved, error = _site_folder(owner)
    if error:
        raise FileNotFoundError(error)
    folder = resolved.resolve()
    target = (folder / Path(str(file or "").replace("\\", "/")).name).resolve()
    try:
        target.relative_to(folder)
    except ValueError:
        raise ValueError(f"{file} is outside this project's images") from None
    if target.suffix.lower() not in SITE_IMAGE_EXT or not target.is_file():
        raise FileNotFoundError(f"{file} is not a stored image")
    kinds = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".webp": "image/webp", ".gif": "image/gif", ".svg": "image/svg+xml",
             ".avif": "image/avif", ".ico": "image/x-icon"}
    return target.read_bytes(), kinds[target.suffix.lower()]


def write_site_images_md(proj_dir: Path) -> str:
    """The brief for a built project's own picture folder."""
    return write_site_images_md_in(_site_dir(proj_dir))


def write_site_images_md_in(folder: Path) -> str:
    """The brief both agents read: what each file is, and where it lives.

    Written from the manifest rather than passed through a prompt, so the
    caption the customer typed reaches the drawing and the build unchanged, and
    so a picture nobody explained is still listed - as unexplained, which is
    something the agent can ask about rather than silently ignore.
    """
    rows = _site_rows(folder)
    if not rows:
        # The last picture was removed: the brief describing them has to go too,
        # or an agent reads a table of files that are no longer there.
        if folder.is_dir():
            (folder / SITE_IMAGE_BRIEF).unlink(missing_ok=True)
        return ""
    lines = [
        "# Site images",
        "",
        f"{len(rows)} picture{'' if len(rows) == 1 else 's'} the customer supplied for this "
        "product. They are real files, already on disk.",
        "",
        f"Reference them as `{SITE_IMAGE_WEB_DIR}/<file name>` - relative, so the same markup "
        "works in the drawing and in the built app. Do not rename them, do not invent others, "
        "and do not replace one with a placeholder or a stock URL.",
        "",
        "| File | What it is for |",
        "| --- | --- |",
    ]
    for row in rows:
        purpose = row["purpose"] or "_not stated - ask before choosing a place for it_"
        lines.append(f"| `{SITE_IMAGE_WEB_DIR}/{row['file']}` | {purpose} |")
    lines.append("")
    lines.append("A picture with no stated use may be left out rather than placed at a guess.")
    lines.append("")
    text = "\n".join(lines)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / SITE_IMAGE_BRIEF).write_text(text, encoding="utf-8")
    return text


def publish_site_images(proj_dir: Path) -> int:
    """Copy the stored pictures to every place a page can actually load them.

    The drawing is served from its own folder and the built app from `public/`,
    so a file that exists in only one of them is a broken image in the other.
    Copied rather than linked: a build is archived, downloaded and deployed as a
    directory, and a symlink does not survive any of that.
    """
    folder = _site_dir(proj_dir)
    rows = _site_rows(folder)
    if not rows:
        return 0

    targets = [proj_dir / ".agentforge" / "prototype" / SITE_IMAGE_WEB_DIR]
    # Where the built app serves static files from depends on what was
    # scaffolded, and on a first build nothing has been scaffolded yet - so
    # publish to every static root that exists and to `public/` regardless,
    # which is the static root for Next.js, Vite and CRA alike. Call this again
    # once the scaffold is on disk to catch a client that appeared in between.
    for static_root in (proj_dir / "public", proj_dir / "client" / "public",
                        proj_dir / "packages" / "client" / "public"):
        if static_root.is_dir() or static_root == proj_dir / "public":
            targets.append(static_root / SITE_IMAGE_WEB_DIR)

    copied = 0
    for target in targets:
        try:
            target.mkdir(parents=True, exist_ok=True)
            for row in rows:
                source = folder / row["file"]
                if source.is_file():
                    shutil.copy2(source, target / row["file"])
                    copied += 1
        except OSError as e:                                    # noqa: BLE001
            log.debug(f"site images -> {target}: {e}")
    return copied


def site_images_brief(proj_dir: Path) -> str:
    """The pictures line for an agent's prompt, or "" when there are none."""
    rows = _site_rows(_site_dir(proj_dir))
    if not rows:
        return ""
    named = ", ".join(f"{SITE_IMAGE_WEB_DIR}/{row['file']}" for row in rows[:12])
    more = f" and {len(rows) - 12} more" if len(rows) > 12 else ""
    return (f"\n\nTHE CUSTOMER SUPPLIED {len(rows)} PICTURE(S) for this product: {named}{more}. "
            f"Read `.agentforge/{SITE_IMAGE_DIRNAME}/{SITE_IMAGE_BRIEF}` for what each one is "
            f"for, and use them where it says. Never swap one for a stock photo, a gradient or "
            f"a placeholder, and never rename one.\n"
            f"The files are kept in `.agentforge/{SITE_IMAGE_DIRNAME}/` and copied into "
            f"`public/{SITE_IMAGE_WEB_DIR}/` and into the drawing. If the stack you scaffold "
            f"serves static files from somewhere else, copy them there too before you reference "
            f"them - an `<img>` pointing at a file the dev server cannot reach is a broken page, "
            f"not a styling detail.\n")
