"""Public Ollama client composed from small chat and catalogue responsibilities."""
import requests
# Source: llm_settings.py — imported helper(s) come from this file.
from agents.core.llm.llm_settings import *
# Source: chat_requests.py — imported helper(s) come from this file.
from agents.core.llm.chat_requests import OllamaChatMixin
# Source: model_catalog.py — imported helper(s) come from this file.
from agents.core.llm.model_catalog import OllamaCatalogMixin


class OllamaClient(OllamaChatMixin, OllamaCatalogMixin):
    # Prepares OllamaClient with the services and starting state it needs before it begins work.
    def __init__(self, host: str = None, api_key: str = None):
        """Prepare this helper with the state it needs."""
        # From: agents/core/llm/llm_settings.py
        self.host = (host or get_local_host()).rstrip("/")
        self._api_key = api_key
        self._tags_cache = None
        self._tags_ok = False
        self._me_cache = None
        self._cloud_tags_cache = None
        self._show_cache = {}

    # Returns the configured cloud API key without exposing it in logs.
    @property
    def api_key(self) -> str:

        """Return the configured cloud API key without exposing it in logs."""
        # From: agents/core/llm/llm_settings.py
        return self._api_key if self._api_key is not None else get_api_key()

    # Returns the address and headers needed for this model.
    def route(self, model: str):
        """Return the address and headers needed for this model."""
        headers = {"Content-Type": "application/json"}
        # From: agents/core/llm/llm_settings.py
        if is_cloud_model(model) and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            return CLOUD_HOST, headers
        return self.host, headers

# Creates the shared LLM client used by helpers that do not receive one explicitly.
def _default_client() -> "OllamaClient":
    """Create the shared LLM client used by helpers that do not receive one explicitly."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = OllamaClient()
    return _CLIENT


# Share the server's configured client with module helpers.
def set_default_client(client: "OllamaClient"):
    """Share the server's configured client with module helpers."""
    global _CLIENT
    _CLIENT = client
