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

# Fooocus reports a gallery file before that file is readable, so the fetch
# polls rather than deciding on its first attempt.
FETCH_TIMEOUT = 45
FETCH_POLL = 1.5
IMAGE_MAGIC = (b"\x89PNG", b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1",
               b"\xff\xd8\xff\xdb", b"RIFF")

