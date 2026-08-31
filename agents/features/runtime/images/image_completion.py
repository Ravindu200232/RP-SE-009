
_GEN_IMG_RE = re.compile(r"/generated/([A-Za-z0-9._-]+)\.(?:png|jpg|jpeg|webp)")

_GEN_IMG_TPL_RE = re.compile(
    r"/generated/\$\{([^}]{1,80})\}\.(?:png|jpg|jpeg|webp)")

_SEED_LABEL_RE = re.compile(r"\b(?:name|title|label)\s*:\s*['\"]([^'\"]{1,80})['\"]")

# Map seeded field values to labels from the same JS object literal.
def _seeded_values(arch, field: str) -> dict:
    """Map seeded field values to labels from the same JS object literal."""
    field_re = re.compile(r"\b" + re.escape(field) + r"\s*:\s*['\"]([^'\"]{1,80})['\"]")
    out = {}
    for rel, body in arch.files.items():
        if "seed" not in rel.lower() or not rel.endswith(".js"):
            continue
        for m in field_re.finditer(body):
            value = m.group(1).strip()
            if not value or "/" in value:
                continue
            # From: agents/data/database_server.py
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

IMAGE_STYLE = ("photographic, believable materials, natural commercial lighting, "
               "strong subject separation, composition matched to the UI crop, "
               "no text, no lettering, no watermark, no people looking at the camera")
_PLACEHOLDER_PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c63606060f80f0001040100b51c0c020000000049454e44ae426082")

# Generate image references added after the original build plan.
def _fill_missing_images(arch, proj_dir: Path, why: str = "an edit", *,
                         explicit_request: bool = False) -> int:
    """Generate image references added after the original build plan."""
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

                # From: agents/build/tester_common.py
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
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in missing:
        (out_dir / f"{name}.png").write_bytes(_PLACEHOLDER_PNG)

    # From: agents/features/runtime/images/image_service.py
    agent = image_agent()
    if explicit_request:
        agent.enabled = True
        # From: agents/features/image_generator.py
        # Only an address on this machine can be started from here. A remote
        # Fooocus has to be running already, and with no address configured
        # there is nothing to start it for.
        # From: agents/features/image_settings.py
        if not agent.available() and is_local_host(agent.host):
            # From: agents/features/runtime/images/image_service.py
            why_start = start_fooocus()
            if not why_start:
                agent._checked = None
                for _ in range(20):
                    # From: agents/features/image_generator.py
                    if agent.available():
                        break
                    time.sleep(1)
            else:
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⚠ Fooocus could not be started: {why_start}")
    # From: agents/features/image_generator.py
    if not agent.enabled or not agent.available():
        # From: agents/build/tester_common.py
        elog("WARN", f"   🖼 {len(missing)} picture(s) {why} added are not "
                     f"drawn — {agent.why_unavailable()}: "
                     f"{', '.join(sorted(missing))}")
        return 0

    idea = (arch.plan or {}).get("description") or (arch.plan or {}).get("title") or ""
    made = 0
    ephase({"phase": -21, "title": f"Drawing {len(missing)} picture(s)",
            "status": "active"})
    for name, (alt, rel) in sorted(missing.items()):

        subject = alt or name.replace("-", " ").replace("_", " ")
        prompt = f"{subject}; authentic domain-appropriate visual; {IMAGE_STYLE}"
        if idea:
            prompt = (f"{subject}; visually fit this application context: {idea[:180]}; "
                      f"avoid generic stock-photo clichés; {IMAGE_STYLE}")
        # From: agents/build/tester_common.py
        elog("INFO", f"   🎨 {name}.png — {subject[:70]}")
        try:
            # From: agents/features/image_generator.py
            if agent.generate(prompt, out_dir / f"{name}.png",
                              aspect="landscape"):
                made += 1
            else:
                # From: agents/build/tester_common.py
                elog("WARN", f"   ⚠ {name}.png could not be drawn")
        except Exception as e:
            # From: agents/build/tester_common.py
            elog("WARN", f"   ⚠ {name}.png failed: {e}")
            log.debug(f"fill image {name}", exc_info=True)
    ephase({"phase": -21, "title": f"Drawing {len(missing)} picture(s)",
            "status": "done", "written": made})
    # From: agents/build/tester_common.py
    elog("INFO" if made else "WARN",
         f"   🖼 {made}/{len(missing)} picture(s) drawn for {why}")
    return made

# Report duplicate non-auth seed rows from the live project database.
def check_seed_duplicates(proj_dir: Path) -> list:
    """Report duplicate non-auth seed rows from the live project database."""
    try:
        from pymongo import MongoClient
    except ImportError:
        return []
    name = proj_dir.name
    try:
        # From: agents/data/database_helpers.py
        # From: agents/data/database_records.py
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
