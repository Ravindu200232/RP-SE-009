"""Shared import setup for the repository-level tests."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

for source_root in (ROOT, ROOT / "srs-agent", ROOT / "deployment-agent"):
    value = str(source_root)
    if value not in sys.path:
        sys.path.insert(0, value)


# --------------------------------------------------------------------------
# Ollama test double
#
# The suite must not need a running daemon, and `is_cloud_model()` reaches the
# module-level default client, so a test that forgets to replace it would make
# a real HTTP call. `fake_ollama` swaps both the transport and that default.
# --------------------------------------------------------------------------
import contextlib
import json as _json
import os
from unittest import mock


class FakeResponse:
    """The slice of `requests.Response` the Ollama client actually uses."""

    def __init__(self, payload=None, status_code=200, lines=None):
        self._payload = payload if payload is not None else {}
        self.status_code = status_code
        self._lines = list(lines or [])
        self.text = _json.dumps(self._payload)

    def json(self):
        return self._payload

    def iter_lines(self):
        for line in self._lines:
            yield _json.dumps(line).encode("utf-8")

    def close(self):
        pass


class FakeDaemon:
    """
    A stand-in for the Ollama HTTP surface.

    Only the routes the client calls are implemented; anything else answers
    404 so an accidental new dependency shows up as a test failure rather than
    as a silent success.
    """

    def __init__(self, models=None, account=None, reachable=True,
                 context_length=None, pull_error=None, capabilities=None):
        self.models = [dict(m) for m in (models or [])]
        self.account = dict(account or {})
        self.reachable = reachable
        self.context_length = context_length
        self.pull_error = pull_error
        self.capabilities = list(capabilities or ["completion"])
        self.calls = []
        self.exceptions = mock.Mock(ReadTimeout=type("ReadTimeout", (Exception,), {}))

    def _record(self, method, url, body=None):
        self.calls.append((method, url.rsplit("/api/", 1)[-1], body))

    def hit(self, route):
        """How many times an `/api/<route>` endpoint was called."""
        return sum(1 for call in self.calls if call[1] == route)

    def get(self, url, **kwargs):
        self._record("GET", url)
        if not self.reachable:
            raise OSError("connection refused")
        if url.endswith("/api/tags"):
            return FakeResponse({"models": self.models})
        return FakeResponse({}, 404)

    def post(self, url, **kwargs):
        body = kwargs.get("json") or {}
        self._record("POST", url, body)
        if not self.reachable:
            raise OSError("connection refused")
        if url.endswith("/api/me"):
            if not self.account:
                return FakeResponse({}, 401)
            return FakeResponse(dict(self.account))
        if url.endswith("/api/show"):
            info = {}
            if self.context_length is not None:
                info["fake.context_length"] = self.context_length
            return FakeResponse({"capabilities": self.capabilities,
                                 "model_info": info})
        if url.endswith("/api/pull"):
            if self.pull_error:
                return FakeResponse(lines=[{"error": self.pull_error}])
            name = body.get("name", "")
            remote = "https://ollama.com" if self.proxies(name) else ""
            self.models.append({"name": name, "remote_host": remote})
            return FakeResponse(lines=[{"status": "pulling manifest"},
                                       {"status": "success"}])
        return FakeResponse({}, 404)

    def proxies(self, name):
        """Whether a freshly pulled name comes back as an ollama.com proxy."""
        return name.endswith(("-cloud", ":cloud")) or "gemma4" in name


def cloud_entry(name):
    """A `/api/tags` row for a model the daemon proxies to ollama.com."""
    return {"name": name, "remote_host": "https://ollama.com"}


def local_entry(name):
    """A `/api/tags` row for a model whose weights are on this machine."""
    return {"name": name, "remote_host": ""}


@contextlib.contextmanager
def fake_ollama(daemon, api_key="", host="http://localhost:11434"):
    """
    Run a block with the Ollama client wired to `daemon` and nothing else.

    The settings file and the two environment overrides are neutralised too,
    so a context-window assertion measures the code under test rather than
    whatever the developer happens to have configured.
    """
    from agents.core.llm import llm_client as oc

    previous = oc._CLIENT
    missing = ROOT / "test" / "results" / "__no_such_settings__.json"
    with mock.patch.object(oc, "requests", daemon), \
            mock.patch.object(oc, "SETTINGS_PATH", missing), \
            mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AGENTFORGE_NUM_CTX", None)
        os.environ.pop("OLLAMA_API_KEY", None)
        os.environ.pop("OLLAMA_HOST", None)
        client = oc.OllamaClient(host, api_key=api_key)
        oc.set_default_client(client)
        try:
            yield client
        finally:
            oc._CLIENT = previous
