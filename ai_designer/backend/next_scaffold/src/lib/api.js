'use client';
// Client data layer - the ONLY way generated pages talk to the backend.
// Wraps the generic CRUD API + mock auth; session lives in localStorage.

async function http(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error((data && data.error) || `Request failed (${res.status})`);
  return data;
}

export const api = {
  list: (entity) => http('GET', `/api/records/${encodeURIComponent(entity)}`),
  get: (entity, id) => http('GET', `/api/records/${encodeURIComponent(entity)}/${encodeURIComponent(id)}`),
  create: (entity, data) => http('POST', `/api/records/${encodeURIComponent(entity)}`, data),
  update: (entity, id, data) => http('PUT', `/api/records/${encodeURIComponent(entity)}/${encodeURIComponent(id)}`, data),
  remove: (entity, id) => http('DELETE', `/api/records/${encodeURIComponent(entity)}/${encodeURIComponent(id)}`),
};

export const auth = {
  async login(email, password) {
    const user = await http('POST', '/api/auth/login', { email, password });
    localStorage.setItem('session', JSON.stringify(user));
    return user;
  },
  async register(payload) {
    const user = await http('POST', '/api/auth/register', payload);
    localStorage.setItem('session', JSON.stringify(user));
    return user;
  },
  logout() {
    localStorage.removeItem('session');
  },
  currentUser() {
    try {
      return JSON.parse(localStorage.getItem('session'));
    } catch (e) {
      return null;
    }
  },
};
