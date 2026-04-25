"use client";

const AGENT1_API_BASE = process.env.NEXT_PUBLIC_AGENT1_API_BASE || "http://127.0.0.1:8101";

async function parseResponse(response) {
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const message = data.detail || data.error || "Agent 1 request failed.";
    throw new Error(message);
  }

  return data;
}

export async function getAgent1Health() {
  const response = await fetch(`${AGENT1_API_BASE}/health`, { cache: "no-store" });
  return parseResponse(response);
}

export async function createAgent1Session(payload) {
  const response = await fetch(`${AGENT1_API_BASE}/api/v1/sessions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  return parseResponse(response);
}

export async function fetchAgent1Session(sessionId) {
  const response = await fetch(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}`, {
    cache: "no-store",
  });
  return parseResponse(response);
}

export async function submitAgent1Intake({ sessionId, message, browserTranscript = "", files = [] }) {
  const formData = new FormData();
  formData.append("message", message || "");
  formData.append("browser_transcript", browserTranscript || "");
  files.forEach((file) => formData.append("files", file));

  const response = await fetch(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/intake`, {
    method: "POST",
    body: formData,
  });
  return parseResponse(response);
}

export async function sendAgent1Message({ sessionId, message }) {
  const response = await fetch(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/message`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });
  return parseResponse(response);
}

export async function generateAgent1Srs(sessionId) {
  const response = await fetch(`${AGENT1_API_BASE}/api/v1/sessions/${sessionId}/generate-srs`, {
    method: "POST",
  });
  return parseResponse(response);
}

export function getAgent1ApiBase() {
  return AGENT1_API_BASE;
}
