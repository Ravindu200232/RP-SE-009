# Optional image flow: validate -> generate or copy -> inspect -> publish.
BROWSER_CONSOLE_MAX = 6000

# Returns the latest bounded preview-console evidence for a prompt.
def _browser_console(msg: dict) -> str:
    """Return the latest bounded preview-console evidence for a prompt."""
    text = str(msg.get("console") or "").strip()
    if len(text) <= BROWSER_CONSOLE_MAX:
        return text
    return "…\n" + text[-BROWSER_CONSOLE_MAX:]

# Preserve the UI thinking switch as an Ollama tri-state.
def _think_flag(msg: dict):
    """Preserve the UI thinking switch as an Ollama tri-state."""
    v = msg.get("think")
    return None if v is None else bool(v)

# Finds a portable Fooocus config instead of assuming a drive path.
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

# Returns likely launcher folders, preferring the configured install.
def _fooocus_folders() -> list:
    """Return likely launcher folders, preferring the configured install."""
    # From: agents/core/llm/llm_settings.py
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

# The script that starts Fooocus on this machine, or "".
def _fooocus_launcher() -> str:
    """The script that starts Fooocus on this machine, or ""."""
    # From: agents/core/llm/llm_settings.py
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

# Launch Fooocus detached; return an empty string or the failure reason.
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
    # From: agents/build/tester_common.py
    elog("INFO", f"   🎨 Starting Fooocus — {script}")
    return ""

FOOOCUS_CONFIG = _find_fooocus_config()

# The configured Fooocus, whether or not it is switched on.
def image_agent(callbacks: dict = None) -> ImageAgent:
    """The configured Fooocus, whether or not it is switched on."""
    # From: agents/core/llm/llm_settings.py
    s = load_settings()
    # From: agents/features/image_generator.py
    # From: agents/pipeline/build/project_preview.py
    return ImageAgent(host=str(s.get("image_host", "")).strip(),
                      config_path=str(s.get("image_config", FOOOCUS_CONFIG)),
                      callbacks=callbacks or _analyzer_callbacks(),
                      enabled=bool(s.get("image_enabled", False)))

# Try one Fooocus address on demand so Settings can test before saving.
def probe_image_host(host: str = "") -> dict:
    """Try one Fooocus address on demand so Settings can test before saving.

    ``config_path`` is deliberately left empty: falling back to the Fooocus
    config file on this machine would let a remote address that answered
    nothing at all still report itself as ready.
    """
    # From: agents/core/llm/llm_settings.py
    s = load_settings()
    asked = str(host or "").strip()
    # From: agents/features/image_generator.py
    agent = ImageAgent(host=asked or str(s.get("image_host", "")).strip(),
                       config_path="", callbacks={}, enabled=True)
    out = agent.probe()
    out["asked"] = asked
    out["enabled"] = bool(s.get("image_enabled", False))
    return out

# Read the configured image service settings needed by image runtime work.
def _image_settings() -> dict:
    """Prepare the image settings value or state used by this focused pipeline step."""
    # From: agents/core/llm/llm_settings.py
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

# Reduce a browser-supplied name to one safe path stem.
def _safe_stem(raw: str, fallback: str = "upload") -> str:
    """Reduce a browser-supplied name to one safe path stem."""
    stem = Path(str(raw or "").replace("\\", "/")).name
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-.")
    return (Path(stem).stem or fallback)[:60]

# Validate and re-encode a browser upload as bounded PNG data.
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
