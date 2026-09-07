/**
 * One place that knows how to talk to the gateway.
 *
 * Relative URLs only: the gateway serves this bundle from its own origin, so
 * an absolute localhost URL would work in development and break everywhere
 * else.
 */
export async function fetchProducts(query = '') {
  const response = await fetch('/api/products' + (query ? '?q=' + encodeURIComponent(query) : ''));
  if (!response.ok) throw new Error('Could not load products (' + response.status + ')');
  const body = await response.json();
  return body.products ?? [];
}

/** Money is stored in cents and formatted once, here. */
export function formatPrice(cents) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format((cents ?? 0) / 100);
}
