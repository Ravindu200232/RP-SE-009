"""Headless Fooocus batch caller.

RUN WITH FOOOCUS'S EMBEDDED PYTHON (it has the matching `websockets` lib):
    <fooocus>/python_embeded/python.exe fooocus_caller.py jobs.json

jobs.json = {"jobs": [{"prompt": str, "aspect": "landscape"|"portrait", "out": "abs/path.jpg"}]}

Speaks the gradio 3.41 WS queue protocol against the running Fooocus UI
(127.0.0.1:7865): per job it fires the generate chain's two real steps with one
session_hash — the args-builder dependency (the one with the most inputs, ->
state) and then the streaming generator dependency (state -> ... gallery).
Defaults for all other inputs are read live from /config, so this stays valid
across minor Fooocus versions. Final gallery file paths are local; images are
copied to each job's `out`. Prints one JSON status line per job.
"""
import asyncio
import json
import random
import re
import shutil
import sys
import urllib.request

HOST = "127.0.0.1:7865"


def load_config():
    with urllib.request.urlopen(f"http://{HOST}/config", timeout=10) as r:
        return json.loads(r.read())


def resolve(cfg):
    """Find the two deps of the generate chain + input override positions."""
    deps = cfg["dependencies"]
    comps = {c["id"]: c for c in cfg["components"]}
    build_i = max(range(len(deps)), key=lambda i: len(deps[i]["inputs"]))
    build = deps[build_i]
    btn_targets = set(build.get("targets") or [])
    gen_i = next(
        i for i, d in enumerate(deps)
        if i != build_i
        and set(d.get("targets") or []) & btn_targets
        and d.get("trigger") == "then"
        and len(d["inputs"]) == 1
        and any(comps.get(o, {}).get("type") == "gallery" for o in d["outputs"])
    )

    defaults, slots = [], {}
    for n, cid in enumerate(build["inputs"]):
        c = comps.get(cid, {})
        p = c.get("props", {}) or {}
        if c.get("type") == "state":
            defaults.append(None)
            continue
        defaults.append(p.get("value", None))
        label = str(p.get("label") or p.get("elem_id") or "")
        if label == "positive_prompt":
            slots["prompt"] = n
        elif label == "Negative Prompt":
            slots["negative"] = n
        elif label == "Performance":
            slots["performance"] = n
        elif label == "Aspect Ratios":
            slots["aspect"] = n
            slots["aspect_choices"] = [
                (ch[0] if isinstance(ch, list) else ch) for ch in (p.get("choices") or [])
            ]
        elif label == "Image Number":
            slots["count"] = n
        elif label == "Output Format":
            slots["format"] = n
        elif label == "Seed":
            slots["seed"] = n
    return build_i, gen_i, defaults, slots


def pick_aspect(choices, want):
    target = {"portrait": "896×1152", "square": "1024×1024"}.get(want, "1152×896")
    for ch in choices:
        if target in str(ch):
            return ch
    return None  # keep default


async def run_dep(ws_url, fn_index, data, session_hash, collect_stream=False):
    import websockets
    final = None
    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024, open_timeout=15) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            m = msg.get("msg")
            if m == "send_hash":
                await ws.send(json.dumps({"fn_index": fn_index, "session_hash": session_hash}))
            elif m == "send_data":
                await ws.send(json.dumps({
                    "data": data, "event_data": None,
                    "fn_index": fn_index, "session_hash": session_hash,
                }))
            elif m == "process_completed":
                final = msg.get("output") or {}
                break
    return final


def harvest_files(output):
    """Pull local image file paths out of a completed output payload."""
    found = []

    def walk(x):
        if isinstance(x, dict):
            name = x.get("name")
            if x.get("is_file") and isinstance(name, str) and re.search(r"\.(png|jpe?g|webp)$", name, re.I):
                found.append(name)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(output.get("data"))
    return found


async def run_job(job, build_i, gen_i, defaults, slots):
    session = "fc" + str(random.randint(10**8, 10**9))
    args = list(defaults)
    args[slots["prompt"]] = job["prompt"]
    if "negative" in slots:
        args[slots["negative"]] = "text, watermark, logo, signature, low quality, blurry, deformed, cartoon"
    if "count" in slots:
        args[slots["count"]] = 1
    if "format" in slots:
        args[slots["format"]] = "jpeg"
    if "seed" in slots:
        args[slots["seed"]] = str(random.randint(1, 2**31))
    if "aspect" in slots:
        ch = pick_aspect(slots.get("aspect_choices") or [], job.get("aspect", "landscape"))
        if ch:
            args[slots["aspect"]] = ch

    ws_url = f"ws://{HOST}/queue/join"
    await run_dep(ws_url, build_i, args, session)              # build AsyncTask -> state
    out = await run_dep(ws_url, gen_i, [None], session)        # run generation (state input)
    files = harvest_files(out or {})
    if not files:
        return {"out": job["out"], "ok": False, "err": "no image in output"}
    shutil.copyfile(files[-1], job["out"])
    return {"out": job["out"], "ok": True, "src": files[-1]}


async def main():
    jobs_path = sys.argv[1]
    with open(jobs_path, encoding="utf-8") as f:
        jobs = json.load(f)["jobs"]
    cfg = load_config()
    build_i, gen_i, defaults, slots = resolve(cfg)
    print(json.dumps({"resolved": {"build": build_i, "gen": gen_i,
                                   "slots": {k: v for k, v in slots.items() if k != "aspect_choices"}}}), flush=True)
    for job in jobs:
        try:
            res = await asyncio.wait_for(run_job(job, build_i, gen_i, defaults, slots), timeout=420)
        except Exception as e:  # noqa: BLE001 - report and continue with next image
            res = {"out": job.get("out"), "ok": False, "err": str(e)[:200]}
        print(json.dumps(res), flush=True)
    try:
        import os
        os.remove(jobs_path)  # signals "batch finished" to anything watching
    except OSError:
        pass


if __name__ == "__main__":
    asyncio.run(main())
