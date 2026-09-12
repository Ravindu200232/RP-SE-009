"""Real photographs in a drawing, not the photo service's stand-in.

A drawing asks LoremFlickr for a photograph of its subject by tags, with a lock
so it stays the same one: `https://loremflickr.com/800/600/bedroom,hotel?lock=12`.
When no photograph carries every tag - or none is big enough for the size asked
for - LoremFlickr does not fail. It sends its one default picture. Every miss on
every page is then the same photograph, which is what gets reported as "the
same image on every page". On two drawings, 5 of 48 addresses came back as it,
the home page's hero among them.

Nothing in an address says whether it will miss, and the same address can miss
once and land the next time, so each one is asked. A miss is exchanged for the
nearest picture that returns a photograph - any of the tags instead of all of
them, then fewer tags - and one photograph turning up for two different
pictures is moved to another lock, so a page does not show it twice. An address
that cannot be checked is left as it was.

A picture is its tags and its lock, not its size: a room's card and its detail
page ask for the same picture at two sizes, and both are mended the same way so
they stay the same photograph.
"""
from __future__ import annotations

import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ADDRESS = re.compile(r"https?://loremflickr\.com/(\d+)/(\d+)/([A-Za-z0-9_,\-]+)"
                     r"(/any|/all)?(?:\?lock=(\d+))?")
TEXT = {".html", ".htm", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".json", ".css"}
SKIP = {"node_modules", "dist", "build", "coverage", "out"}
STAND_IN = "defaultImage"
# However slow the service is, a drawing is not held up longer than this.
BUDGET_SECONDS = 120
MAX_BYTES = 2_000_000
OTHER_LOCKS = 4


def _http_probe(address: str) -> str:
    """'photo:<id>' for a real photograph, 'stand-in' for the default one, '' if unknown."""
    for attempt in range(2):
        try:
            answer = requests.head(address, allow_redirects=False, timeout=15)
        except requests.RequestException:
            answer = None
        if answer is not None and answer.is_redirect:
            where = answer.headers.get("Location", "")
            if STAND_IN in where:
                return "stand-in"
            parts = where.rsplit("/", 1)[-1].split("_")
            return "photo:" + (parts[1] if len(parts) > 1 else where)
        if attempt == 0:
            time.sleep(1)
    return ""


def _files(root: Path):
    """The text files under a drawing or an app that could carry a picture address."""
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        for name in names:
            path = Path(folder) / name
            if path.suffix.lower() not in TEXT:
                continue
            try:
                if path.stat().st_size <= MAX_BYTES:
                    yield path
            except OSError:
                continue


def _picture(match) -> tuple:
    """What makes two addresses the same picture: its tags, how they match, its lock."""
    _, _, tags, mode, lock = match.groups()
    return (tags, "" if mode == "/all" else (mode or ""), lock or "")


def _address(picture: tuple, width, height) -> str:
    tags, mode, lock = picture
    return (f"https://loremflickr.com/{width}/{height}/{tags}{mode}"
            + (f"?lock={lock}" if lock else ""))


def _nearer(picture: tuple) -> list:
    """Pictures near one that missed, the most like it first: any tag, fewer tags, one."""
    tags, mode, lock = picture
    parts = [tag for tag in tags.split(",") if tag]
    out = []
    if len(parts) > 1 and mode != "/any":
        out.append((",".join(parts), "/any", lock))
    if len(parts) > 2:
        out.append((",".join(parts[:2]), "", lock))
    out += [(tag, "", lock) for tag in parts]
    return [other for other in dict.fromkeys(out) if other != picture]


def repair(root, probe=None) -> list:
    """Replace every stand-in, and every photograph shown for two pictures, under `root`.

    Returns (old, new) for each address that changed. Hidden folders and
    installed packages are not read, so pointed at a project this is its own
    source; pointed at `.agentforge/prototype` it is the drawing.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    texts = {}
    for path in _files(root):
        try:
            texts[path] = path.read_bytes().decode("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    order = []
    for text in texts.values():
        for match in ADDRESS.finditer(text):
            if match.group(0) not in order:
                order.append(match.group(0))
    if not order:
        return []

    # Each picture, and the sizes it is asked for at, in the order they appear.
    pictures = {}
    for address in order:
        match = ADDRESS.fullmatch(address)
        pictures.setdefault(_picture(match), []).append((match.group(1), match.group(2), address))

    probe = probe or _http_probe
    deadline = time.monotonic() + BUDGET_SECONDS

    def ask(address):
        return probe(address) if time.monotonic() < deadline else ""

    with ThreadPoolExecutor(8) as pool:
        found = dict(zip(order, pool.map(ask, order)))

    def at_every_size(picture, sizes):
        """This picture's addresses at these sizes - if every one is a photograph."""
        addresses = [_address(picture, width, height) for width, height, _ in sizes]
        for address in addresses:
            if address not in found:
                found[address] = ask(address)
            if not found[address].startswith("photo:"):
                return None
        return addresses

    chosen = {}
    for picture, sizes in pictures.items():
        if not any(found[address] == "stand-in" for _, _, address in sizes):
            continue
        for other in _nearer(picture):
            addresses = at_every_size(other, sizes)
            if addresses:
                chosen.update((old, new) for (_, _, old), new in zip(sizes, addresses))
                pictures[picture] = [(w, h, old) for w, h, old in sizes]
                break

    # One photograph behind two different pictures is shown twice. The first
    # keeps it; the later picture is moved to another lock, at every size.
    owner = {}
    for picture, sizes in pictures.items():
        photos = {found.get(chosen.get(old, old), "") for _, _, old in sizes}
        photos = {photo for photo in photos if photo.startswith("photo:")}
        now = _picture(ADDRESS.fullmatch(chosen.get(sizes[0][2], sizes[0][2])))
        if any(owner.get(photo, picture) != picture for photo in photos) and now[2]:
            for step in range(1, OTHER_LOCKS + 1):
                moved = (now[0], now[1], str(int(now[2]) + 17 * step))
                addresses = at_every_size(moved, sizes)
                if addresses and not any(owner.get(found[a], picture) != picture
                                         for a in addresses):
                    chosen.update((old, new) for (_, _, old), new in zip(sizes, addresses))
                    photos = {found[a] for a in addresses}
                    break
        for photo in photos:
            owner.setdefault(photo, picture)

    if not chosen:
        return []
    for path, text in texts.items():
        new = ADDRESS.sub(lambda m: chosen.get(m.group(0), m.group(0)), text)
        if new != text:
            path.write_bytes(new.encode("utf-8"))
    return list(chosen.items())
