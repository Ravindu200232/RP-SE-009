"use client";

const AGENT1_API_BASE = process.env.NEXT_PUBLIC_AGENT1_API_BASE || "http://127.0.0.1:8101";
const AGENT1_REQUEST_TIMEOUT_MS = Number(process.env.NEXT_PUBLIC_AGENT1_REQUEST_TIMEOUT_MS || 180000);

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), AGENT1_REQUEST_TIMEOUT_MS);

  try {
    return await fetch(url, {
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("Agent 1 build timed out. Check whether Ollama and the DeepSeek model are running, then try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

async function parseResponse(response) {
  const text = await response.text();
  let data = {};

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text };
    }
  }

  if (!response.ok) {
    throw new Error(data.detail || data.error || "Agent 1 request failed.");
  }

  return data;
}

export async function getAgent1Health() {
  const response = await fetchWithTimeout(`${AGENT1_API_BASE}/health`, { cache: "no-store" });
  return parseResponse(response);
}

export async function createAgent1Session(payload) {
  const response = await fetchWithTimeout(`${AGENT1_API_BASE}/api/v1/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function fetchAgent1Session(sessionId) {
  const response = await fetchWithTimeout(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}`, {
    cache: "no-store",
  });
  return parseResponse(response);
}

export async function submitAgent1Intake({ sessionId, message, browserTranscript = "", files = [] }) {
  const formData = new FormData();
  formData.append("message", message || "");
  formData.append("browser_transcript", browserTranscript || "");
  files.forEach((file) => formData.append("files", file));

  const response = await fetchWithTimeout(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/intake`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function submitAgent1Answers({ sessionId, answers }) {
  const response = await fetchWithTimeout(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  return parseResponse(response);
}

export async function sendAgent1Message({ sessionId, message }) {
  const response = await fetchWithTimeout(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  return parseResponse(response);
}

export async function generateAgent1Srs(sessionId) {
  const response = await fetchWithTimeout(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/generate-srs`, {
    method: "POST",
  });
  return parseResponse(response);
}

export function getAgent1ArtifactUrl(sessionId, artifactName) {
  return `${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/artifacts/${artifactName}`;
}

export function getAgent1ApiBase() {
  return AGENT1_API_BASE;
}
