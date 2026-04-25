"use client";

const AGENT1_SESSION_KEY = "agentforge-agent1-session";

export function loadAgent1Session() {
  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.localStorage.getItem(AGENT1_SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveAgent1Session(session) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(AGENT1_SESSION_KEY, JSON.stringify(session));
}

export function clearAgent1Session() {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.removeItem(AGENT1_SESSION_KEY);
}
