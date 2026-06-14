"""Local image generation for prototypes via a running Fooocus UI (RTX/SDXL).

The pipeline launches image generation as a SUBPROCESS at the start of code
generation and collects it at the end — pages take far longer than images, so
the photos cost ~zero extra wall time. If Fooocus isn't running (or anything
fails) the prototype still works: every <img> in the generated pages carries an
onError hide, so missing photos degrade to the clean no-image design.

Images land at output/<project_id>/assets/{hero,feature,about,auth,contact}.jpg
which is exactly the path set the page prompts are told about (themes.py).
"""
import json
import os
import re
import subprocess
import urllib.request

FOOOCUS_DIR = os.getenv("FOOOCUS_DIR", r"D:\Fooocus_win64_2-5-0\Fooocus_win64_2-5-0")
FOOOCUS_HOST = "127.0.0.1:7865"
_CALLER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fooocus_caller.py")

_FILLER = re.compile(r"\b(management|system|app|application|platform|portal|admin|tool|software|online|the|a|an)\b", re.I)


def alive(timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(f"http://{FOOOCUS_HOST}/config", timeout=timeout):
            return True
    except Exception:
        return False


_fooocus_proc = None
_GEN_ACTIVE = False        # True while a background image batch is generating
_ACTIVE_CALLER = None      # the Popen of the image caller currently on the GPU


def image_gen_active() -> bool:
    """True when a background image batch is actively running (used by the GPU
    handoff so LLM code edits can briefly pause Fooocus)."""
    return _GEN_ACTIVE


def fooocus_server_pid() -> int:
    """PID of the running Fooocus server (the process holding SDXL on the GPU):
    the one we launched, else whoever is listening on :7865."""
    if _fooocus_proc is not None and _fooocus_proc.poll() is None:
        return _fooocus_proc.pid
    try:
        import psutil
        for c in psutil.net_connections(kind="inet"):
            if c.laddr and c.laddr.port == 7865 and c.status == psutil.CONN_LISTEN and c.pid:
                return c.pid
    except Exception:
        pass
    return 0


def active_caller_pid() -> int:
    p = _ACTIVE_CALLER
    return p.pid if (p is not None and p.poll() is None) else 0


def ensure_fooocus(wait_s: int = 260) -> bool:
    """Self-healing image runtime: if Fooocus isn't up, launch it (its gradio UI
    on :7865) and wait until it answers. Like ensure_ollama() for the LLM, this
    means the user never has to start Fooocus by hand. Returns False (and the
    caller ships imageless) if it can't be started in time."""
    if alive():
        return True
    global _fooocus_proc
    embedded = os.path.join(FOOOCUS_DIR, "python_embeded", "python.exe")
    launch = os.path.join(FOOOCUS_DIR, "Fooocus", "launch.py")
    if not (os.path.exists(embedded) and os.path.exists(launch)):
        return False
    if _fooocus_proc is not None and _fooocus_proc.poll() is None:
        pass  # already launching from a previous call - just keep waiting below
    else:
        _unload_llm()  # free the GPU's VRAM before SDXL loads
        try:
            _fooocus_proc = subprocess.Popen(
                [embedded, "-s", launch, "--port", "7865"],
                cwd=FOOOCUS_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT,
            )
        except Exception:
            return False
    import time as _t
    for _ in range(max(1, wait_s // 3)):
        _t.sleep(3)
        if alive():
            return True
    return False


def _unload_llm():
    """Free the LLM's VRAM before image generation. Fooocus (SDXL) and Ollama
    share one 12GB GPU: if both load at once the LLM splits 50/50 onto the CPU
    and everything crawls. The prototype is already finished when images start,
    so the LLM isn't needed; it reloads (fully on GPU) on the next generation."""
    model = os.getenv("AI_DESIGNER_MODEL", "qwen2.5-coder:7b")
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=json.dumps({"model": model, "keep_alive": 0}).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception:
        pass  # best effort - image gen still works, just slower


def _domain_subject(app_name: str, user_prompt: str) -> str:
    """'Hospital Management System' -> 'hospital'; falls back to prompt words."""
    base = _FILLER.sub(" ", app_name or "")
    base = re.sub(r"[^A-Za-z ]", " ", base)
    words = [w for w in base.split() if len(w) > 2]
    if not words:
        base = _FILLER.sub(" ", (user_prompt or "")[:80])
        words = [w for w in re.sub(r"[^A-Za-z ]", " ", base).split() if len(w) > 2][:3]
    return " ".join(words[:3]).lower() or "modern business"


def build_jobs(out_dir: str, app_name: str, user_prompt: str) -> list:
    subject = _domain_subject(app_name, user_prompt)
    # Absolute paths: the caller runs as a separate process, so relative output
    # paths would silently depend on ITS cwd.
    assets = os.path.abspath(os.path.join(out_dir, "assets"))
    os.makedirs(assets, exist_ok=True)
    style = "professional photography, natural light, high detail, photorealistic"

    def job(fname, prompt, aspect="landscape"):
        return {"prompt": prompt, "aspect": aspect,
                "out": os.path.join(assets, fname).replace("\\", "/")}

    return [
        job("logo.jpg",     f"minimal flat vector logo mark for a {subject} brand, simple bold geometric icon, centered, clean solid background, no text", "square"),
        job("hero.jpg",     f"modern {subject} environment, clean bright interior, {style}"),
        job("feature.jpg",  f"{subject} professionals working with modern technology, candid, {style}"),
        job("about.jpg",    f"friendly professional team at a {subject} workplace, collaboration, {style}"),
        job("auth.jpg",     f"atmospheric architectural detail of a modern {subject} building, dramatic soft light, {style}", "portrait"),
        job("contact.jpg",  f"welcoming {subject} reception front desk area, {style}"),
        job("gallery1.jpg", f"detail close-up of {subject} equipment or product, shallow depth of field, {style}"),
        job("gallery2.jpg", f"{subject} customers having a great experience, candid moment, {style}"),
        job("gallery3.jpg", f"wide angle of a busy {subject} space, atmosphere, {style}"),
        job("banner.jpg",   f"cinematic panoramic {subject} scene, golden hour light, {style}"),
    ]


# ---- V2 (Next.js apps): 13 DISTINCT image slots -> <project>/public/assets ----
V2_NAMES = ["logo.jpg", "hero.jpg", "banner.jpg", "auth.jpg", "contact.jpg",
            "feature1.jpg", "feature2.jpg", "about1.jpg", "about2.jpg",
            "gallery1.jpg", "gallery2.jpg", "gallery3.jpg", "cta.jpg"]

def build_jobs_v2(project_dir: str, app_name: str, user_prompt: str) -> list:
    subject = _domain_subject(app_name, user_prompt)
    assets = os.path.abspath(os.path.join(project_dir, "public", "assets"))
    os.makedirs(assets, exist_ok=True)
    style = "professional photography, natural light, high detail, photorealistic"

    def job(fname, prompt, aspect="landscape"):
        return {"prompt": prompt, "aspect": aspect,
                "out": os.path.join(assets, fname).replace("\\", "/")}

    return [
        job("logo.jpg",     f"minimal flat vector logo mark for a {subject} brand, simple bold geometric icon, centered, clean solid background, no text", "square"),
        job("hero.jpg",     f"modern {subject} environment, clean bright interior, {style}"),
        job("banner.jpg",   f"cinematic panoramic {subject} scene, golden hour light, {style}"),
        job("auth.jpg",     f"atmospheric architectural detail of a modern {subject} building, dramatic soft light, {style}", "portrait"),
        job("contact.jpg",  f"welcoming {subject} reception front desk area, {style}"),
        job("feature1.jpg", f"{subject} professionals working with modern technology, candid, {style}"),
        job("feature2.jpg", f"close-up of {subject} tools and equipment in use, shallow depth of field, {style}"),
        job("about1.jpg",   f"friendly professional team at a {subject} workplace, collaboration, {style}"),
        job("about2.jpg",   f"portrait of a smiling {subject} professional at work, environmental portrait, {style}", "portrait"),
        job("gallery1.jpg", f"detail close-up of {subject} products or service moment, {style}"),
        job("gallery2.jpg", f"{subject} customers having a great experience, candid moment, {style}"),
        job("gallery3.jpg", f"wide angle of a busy {subject} space, atmosphere, {style}"),
        job("cta.jpg",      f"inspiring {subject} success moment, celebratory, warm tones, {style}"),
    ]


def _run_one_job(out_path: str, prompt: str, aspect: str, timeout: int) -> bool:
    """Generate ONE image in its OWN caller process (Fooocus must already be up).
    Isolated + timed out, so a single slow/hung image can't block the others."""
    embedded = os.path.join(FOOOCUS_DIR, "python_embeded", "python.exe")
    if not (os.path.exists(embedded) and os.path.exists(_CALLER)):
        return False
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    job = {"prompt": prompt, "aspect": aspect, "out": out_path.replace("\\", "/")}
    jobs_path = os.path.join(os.path.dirname(out_path), "_one_" + os.path.basename(out_path) + ".json")
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump({"jobs": [job]}, f)
    global _ACTIVE_CALLER
    try:
        p = subprocess.Popen([embedded, _CALLER, jobs_path], cwd=os.path.dirname(_CALLER),
                             stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        _ACTIVE_CALLER = p
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            p.kill()
        except Exception:
            pass
    except Exception:
        return False
    finally:
        _ACTIVE_CALLER = None
    return os.path.exists(out_path) and os.path.getsize(out_path) > 2000


def generate_one(out_path: str, prompt: str, aspect: str = "landscape", timeout: int = 240) -> bool:
    """Single image to out_path (Select-Element image regen)."""
    if not ensure_fooocus():
        return False
    _unload_llm()
    style = "professional photography, natural light, high detail, photorealistic"
    return _run_one_job(out_path, f"{prompt}, {style}", aspect, timeout)


def generate_all_bg(project_dir: str, app_name: str, user_prompt: str) -> int:
    """Generate the full image set ONE IMAGE AT A TIME (each isolated + capped),
    so the run NEVER fully fails - whatever lands is used, missing ones auto-hide.
    Returns how many images were produced. Meant to run in a background thread."""
    if os.getenv("AI_DESIGNER_FAST"):
        return 0
    if not ensure_fooocus():
        return 0
    _unload_llm()
    try:
        jobs = build_jobs_v2(project_dir, app_name, user_prompt)
    except Exception:
        return 0
    global _GEN_ACTIVE
    _GEN_ACTIVE = True
    done = 0
    try:
        for j in jobs:
            try:
                if _run_one_job(j["out"], j["prompt"], j.get("aspect", "landscape"), 150):
                    done += 1
            except Exception:
                continue
    finally:
        _GEN_ACTIVE = False
    return done


def start_v2(project_dir: str, app_name: str, user_prompt: str):
    """V2: generate the 13 slots into <project>/public/assets (fire after pages;
    caller decides whether to block). Returns process handle or None."""
    if os.getenv("AI_DESIGNER_FAST"):  # validation runs: skip the slow GPU step
        return None
    if not alive() and not ensure_fooocus():   # auto-start Fooocus if it's down
        return None
    embedded = os.path.join(FOOOCUS_DIR, "python_embeded", "python.exe")
    if not (os.path.exists(embedded) and os.path.exists(_CALLER)):
        return None
    _unload_llm()
    jobs = build_jobs_v2(project_dir, app_name, user_prompt)
    assets = os.path.abspath(os.path.join(project_dir, "public", "assets"))
    jobs_path = os.path.join(assets, "_jobs.json")
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump({"jobs": jobs}, f)
    log = open(os.path.join(assets, "_imglog.txt"), "w", encoding="utf-8")
    proc = subprocess.Popen([embedded, _CALLER, jobs_path],
                            stdout=log, stderr=subprocess.STDOUT, text=True,
                            cwd=os.path.dirname(_CALLER))
    log.close()
    return proc


def finish_v2(proc, project_dir: str, timeout: int = 600) -> str:
    if proc is None:
        return "Images: Fooocus not running - app ships with the clean no-image design."
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return "Images: generation timed out; partial set kept (missing ones auto-hide)."
    assets = os.path.join(project_dir, "public", "assets")
    have = [n for n in V2_NAMES if os.path.exists(os.path.join(assets, n))]
    return f"Images: generated {len(have)}/{len(V2_NAMES)} images ({', '.join(have) or 'none'})."


def start(out_dir: str, app_name: str, user_prompt: str):
    """Kick off image generation in the background. Returns the process handle
    or None when Fooocus is unavailable (callers just skip images then)."""
    if not alive():
        return None
    embedded = os.path.join(FOOOCUS_DIR, "python_embeded", "python.exe")
    if not (os.path.exists(embedded) and os.path.exists(_CALLER)):
        return None
    _unload_llm()  # hand the whole GPU to Fooocus for round 2
    jobs = build_jobs(out_dir, app_name, user_prompt)
    assets = os.path.abspath(os.path.join(out_dir, "assets"))
    jobs_path = os.path.join(assets, "_jobs.json")
    with open(jobs_path, "w", encoding="utf-8") as f:
        json.dump({"jobs": jobs}, f)
    # Log to a file (not a pipe): nothing reads stdout until finish(), and a
    # file leaves a diagnosable trace when generation fails.
    log = open(os.path.join(assets, "_imglog.txt"), "w", encoding="utf-8")
    proc = subprocess.Popen(
        [embedded, _CALLER, jobs_path],
        stdout=log, stderr=subprocess.STDOUT, text=True,
        cwd=os.path.dirname(_CALLER),
    )
    # The child owns its inherited copy of the handle; close ours immediately so
    # fire-and-forget callers don't leak a file handle per generation.
    log.close()
    return proc


def finish(proc, out_dir: str, timeout: int = 1200) -> str:
    """Wait for the image subprocess and report what landed."""
    if proc is None:
        return "Images: Fooocus not running - prototype uses the clean no-image design."
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        return "Images: generation timed out; partial set kept (missing ones auto-hide)."
    names = ["logo.jpg", "hero.jpg", "feature.jpg", "about.jpg", "auth.jpg", "contact.jpg",
             "gallery1.jpg", "gallery2.jpg", "gallery3.jpg", "banner.jpg"]
    have = [n for n in names if os.path.exists(os.path.join(out_dir, "assets", n))]
    return f"Images: generated {len(have)}/10 local images via Fooocus ({', '.join(have) or 'none'})."
