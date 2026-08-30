# Public UI request handler composed from small HTTP responsibilities.
class UIHandler(ResponseHelpersMixin, RequestRouterMixin, ApiGetMixin, ApiPostMixin, ProxyRoutesMixin, SimpleHTTPRequestHandler):
    """Route AgentForge UI, API, SRS, deployment and preview requests."""
    protocol_version = "HTTP/1.1"
    _raw = b""
