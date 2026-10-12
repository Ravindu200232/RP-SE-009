/** Forward one request to an internal service. */
export function proxyTo(baseUrl) {
  return async function proxy(req, res) {
    const target = new URL(req.originalUrl.replace(/^\/api/, ''), baseUrl);
    const headers = { accept: req.get('accept') ?? 'application/json' };
    if (req.get('content-type')) headers['content-type'] = req.get('content-type');
    const hasBody = !['GET', 'HEAD'].includes(req.method);
    try {
      const response = await fetch(target, {
        method: req.method,
        headers,
        body: hasBody ? JSON.stringify(req.body ?? {}) : undefined,
      });
      const text = await response.text();
      res.status(response.status);
      const type = response.headers.get('content-type');
      if (type) res.type(type);
      res.send(text);
    } catch (error) {
      res.status(503).json({ error: 'Upstream service unavailable', service: baseUrl });
    }
  };
}
