"use client";

const AGENT2_API_BASE = process.env.NEXT_PUBLIC_AGENT2_API_BASE || "http://127.0.0.1:8102";

async function parseResponse(response) {
  const text = await response.text();
  const data = text ? JSON.parse(text) : {};
  if (!response.ok) {
    const message = data.detail || data.error || "Agent 2 request failed.";
    throw new Error(message);
  }
  return data;
}

export async function getAgent2Health() {
  const response = await fetch(`${AGENT2_API_BASE}/health`, { cache: "no-store" });
  return parseResponse(response);
}

export async function startAgent2Build({ srsJson, model }) {
  const response = await fetch(`${AGENT2_API_BASE}/api/v1/build/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ srs_json: srsJson, model: model || null }),
  });
  return parseResponse(response);
}

export async function getAgent2Build(buildId) {
  const response = await fetch(`${AGENT2_API_BASE}/api/v1/build/${buildId}`, { cache: "no-store" });
  return parseResponse(response);
}

export async function getAgent2BuildFile(buildId, path) {
  const url = `${AGENT2_API_BASE}/api/v1/build/${buildId}/file?path=${encodeURIComponent(path)}`;
  const response = await fetch(url, { cache: "no-store" });
  return parseResponse(response);
}

export async function planSandboxSrs({ srsJson, model }) {
  const response = await fetch(`${AGENT2_API_BASE}/api/v1/sandbox/plan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ srs_json: srsJson, model: model || null }),
  });
  return parseResponse(response);
}

export async function generateSandbox({ srsJson, model }) {
  const response = await fetch(`${AGENT2_API_BASE}/api/v1/sandbox/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ srs_json: srsJson, model: model || null }),
  });
  return parseResponse(response);
}

export async function getSandbox(sandboxId, { includeHtml = true } = {}) {
  const url = `${AGENT2_API_BASE}/api/v1/sandbox/${sandboxId}?include_html=${includeHtml ? "true" : "false"}`;
  const response = await fetch(url, { cache: "no-store" });
  return parseResponse(response);
}

export async function refineSandbox(sandboxId, instruction) {
  const response = await fetch(`${AGENT2_API_BASE}/api/v1/sandbox/${sandboxId}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction }),
  });
  return parseResponse(response);
}

export async function repairSandbox(sandboxId, { errorMessage, errorStack }) {
  const response = await fetch(`${AGENT2_API_BASE}/api/v1/sandbox/${sandboxId}/repair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ error_message: errorMessage, error_stack: errorStack || null }),
  });
  return parseResponse(response);
}

export function getSandboxPreviewUrl(sandboxId, version) {
  const v = version != null ? `?v=${version}` : "";
  return `${AGENT2_API_BASE}/api/v1/sandbox/${sandboxId}/preview${v}`;
}

export function getAgent2ApiBase() {
  return AGENT2_API_BASE;
}
