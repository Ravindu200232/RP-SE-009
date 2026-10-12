import { vi } from 'vitest';

/** Replace `fetch` for a component or page test, so it runs without a server. */
export function stubFetch(routes = {}) {
  const log = [];
  const unhandled = [];
  const table = Object.entries(routes).map(([key, handler]) => {
    const [method, pattern] = key.split(' ');
    const regex = new RegExp(`^${pattern.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/:[A-Za-z0-9_]+/g, '[^/]+')}$`);
    return { method: method.toUpperCase(), regex, handler };
  });
  const fetchMock = vi.fn(async (input, init = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, 'http://localhost');
    const method = String(init.method ?? (typeof input === 'object' ? input.method : undefined) ?? 'GET').toUpperCase();
    let body;
    if (typeof init.body === 'string') {
      try { body = JSON.parse(init.body); } catch { body = init.body; }
    }
    const entry = { method, path: url.pathname, query: Object.fromEntries(url.searchParams), body };
    log.push(entry);
    const route = table.find((r) => r.method === method && r.regex.test(url.pathname));
    if (!route) {
      unhandled.push(entry);
      return answer(404, { error: 'This request was not stubbed' });
    }
    const out = typeof route.handler === 'function' ? await route.handler(entry) : route.handler;
    return out && typeof out === 'object' && 'status' in out && 'body' in out ? answer(out.status, out.body) : answer(200, out);
  });
  vi.stubGlobal('fetch', fetchMock);
  return { fetch: fetchMock, log, unhandled, calls: (method, path) => log.filter((e) => e.method === method.toUpperCase() && e.path === path) };
}

function answer(status, body) {
  return new Response(body === undefined || status === 204 ? null : JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });
}
