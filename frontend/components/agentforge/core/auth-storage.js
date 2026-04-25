export const AUTH_CREDENTIALS_KEY = "exagentic.auth.credentials";
export const AUTH_SESSION_KEY = "exagentic.auth.session";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.localStorage !== "undefined";
}

function readJson(key) {
  if (!canUseStorage()) {
    return null;
  }

  try {
    const rawValue = window.localStorage.getItem(key);
    return rawValue ? JSON.parse(rawValue) : null;
  } catch {
    return null;
  }
}

function writeJson(key, value) {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.setItem(key, JSON.stringify(value));
}

export function loadStoredCredentials() {
  return readJson(AUTH_CREDENTIALS_KEY);
}

export function saveStoredCredentials({ email, password }) {
  writeJson(AUTH_CREDENTIALS_KEY, {
    email,
    password,
    savedAt: new Date().toISOString(),
  });
}

export function loadActiveSession() {
  return readJson(AUTH_SESSION_KEY);
}

export function saveActiveSession({ email }) {
  writeJson(AUTH_SESSION_KEY, {
    email,
    loginAt: new Date().toISOString(),
  });
}

export function clearActiveSession() {
  if (!canUseStorage()) {
    return;
  }

  window.localStorage.removeItem(AUTH_SESSION_KEY);
}
