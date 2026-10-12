/** One place that knows how to talk to the server. */
export async function request(path, { method = 'GET', body, signal } = {}) {
  const response = await fetch('/api' + path, {
    method,
    headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  const text = await response.text();
  // A server that errors can answer JSON or, if it crashed before the handler, HTML.
  let payload = null;
  try { payload = text ? JSON.parse(text) : null; } catch { payload = null; }
  if (!response.ok) {
    const error = new Error(payload?.error ?? ('Request failed (' + response.status + ')'));
    error.status = response.status;
    throw error;
  }
  return payload;
}

/** Money is stored in the smallest unit and formatted in exactly one place. */
export function formatPrice(cents) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((cents ?? 0) / 100);
}
