"""Generate cached project images through a local or remote Fooocus Gradio UI."""
import base64
import json
import logging
import random
import re
import time
from pathlib import Path

import requests

log = logging.getLogger("images")


class _NoQueue(Exception):
    """This Gradio has no WebSocket queue — try the newer HTTP protocol."""


DEFAULT_HOSTS = ("http://127.0.0.1:7865", "http://127.0.0.1:7860")


PROMPT_LABEL = None
NEGATIVE_LABEL = "Negative Prompt"
ASPECT_LABEL = "Aspect Ratios"
COUNT_LABEL = "Image Number"
SEED_LABEL = "Seed"


SAFE_RE = re.compile(r"[^a-z0-9]+")

GENERATE_TIMEOUT = 600

# A Fooocus reached over a tunnel or a LAN answers its first request slower
# than one on this machine, and four seconds was short enough to report a
# working remote address as unreachable.
REACH_TIMEOUT = 10


# Say why an address did not answer in words a person can act on.
def reach_reason(exc) -> str:
    """Say why an address did not answer in words a person can act on."""
    name = type(exc).__name__
    if "Timeout" in name:
        return f"it did not answer within {REACH_TIMEOUT}s"
    if "SSL" in name:
        return "its certificate was refused"
    if name in ("MissingSchema", "InvalidSchema", "InvalidURL", "URLRequired"):
        return "that is not a usable web address"
    if "Connection" in name:
        return "nothing is listening there"
    return name


# Accept a pasted address that is missing its scheme or carries a stray slash.
def clean_host(raw: str) -> str:
    """Accept a pasted address that is missing its scheme or carries a stray slash."""
    host = str(raw or "").strip().rstrip("/")
    if host and not re.match(r"^https?://", host, re.I):
        host = "http://" + host
    return host


# Fooocus reports a gallery file before that file is readable, so the fetch
# polls rather than deciding on its first attempt.
FETCH_TIMEOUT = 45
FETCH_POLL = 1.5
IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1",
               b"\xff\xd8\xff\xdb", b"RIFF")

