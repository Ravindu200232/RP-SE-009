/**
 * Minimal streaming client for local Ollama.
 *
 * The builder is intentionally local-Ollama only on this machine (deepseek-r1:8b,
 * a reasoning model). We talk to Ollama's native /api/chat endpoint directly
 * (NDJSON stream) so the UI can show live thinking/content while the artifact
 * parser receives raw deltas — Ollama separates thinking from content, so the
 * <think> reasoning never leaks into a generated file.
 */

import { Agent } from 'undici';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

const OLLAMA_DISPATCHER = new Agent({ headersTimeout: 0, bodyTimeout: 0 });

export const OLLAMA_BASE_URL =
  process.env.OLLAMA_BASE_URL?.replace(/\/$/, '') || 'http://127.0.0.1:11434';
export const OLLAMA_MODEL = process.env.OLLAMA_MODEL || 'deepseek-r1:8b';
export const OLLAMA_CODE_MODEL = process.env.OLLAMA_CODE_MODEL || OLLAMA_MODEL;

type ContextProfile = 'fast' | 'balanced' | 'large' | 'huge';

// deepseek-r1:8b's ARCHITECTURAL max context is 128K (131072) — it is a
// Llama-3.1-8B distill. There is NO 256K (that was gemma4:12b). More importantly,
// 128K is NOT usable on a 12GB GPU: its q8_0 KV cache alone is ~8GB PER parallel
// slot, so with NUM_PARALLEL=2 it needs ~20GB and spills massively to CPU (the
// exact cause of the "GPU only 32%, very slow" problem). 32K fits 100% on the
// GPU (KV ~2GB/slot) and is plenty — planning sees a ~20K-token SRS digest and a
// code step sees only one page's spec. So keep contexts at/around 32K here.
export const DEEPSEEK_MAX_CTX = 131072; // 128K — hard ceiling, never exceed.

function contextProfile(): ContextProfile {
  const raw = (process.env.OLLAMA_CONTEXT_PROFILE || '').trim().toLowerCase();
  return raw === 'fast' || raw === 'balanced' || raw === 'huge' ? raw : 'large';
}

function defaultPlanCtx(): number {
  switch (contextProfile()) {
    case 'fast':
      return 32768;
    case 'balanced':
      return 65536;
    case 'huge': // 128K — the model max; only viable if VRAM allows (it won't at parallel=2).
      return DEEPSEEK_MAX_CTX;
    default:
      return 32768;
  }
}

function defaultCodeCtx(): number {
  switch (contextProfile()) {
    case 'fast':
      return 24576;
    case 'balanced':
      return 32768;
    case 'huge':
      return 65536;
    default:
      return 32768;
  }
}

// deepseek-r1:8b tops out at 128K context, but the RTX 3060 12GB is only fast
// when the KV cache fits fully in VRAM. Planning + build steps both use ~32K,
// which is 100%-GPU on this card; the SRS is digested and each code step only
// needs one page's spec + the manifest, so 32K loses no quality.
export const OLLAMA_NUM_CTX = Number(process.env.OLLAMA_NUM_CTX || defaultPlanCtx());
export const OLLAMA_CODE_CTX = Number(process.env.OLLAMA_CODE_CTX || defaultCodeCtx());

function sameModelFamily(a: string, b: string): boolean {
  return a === b || a.split(':')[0] === b.split(':')[0];
}

export interface OllamaStatus {
  provider: 'ollama';
  reachable: boolean;
  model: string;
  modelInstalled: boolean;
  codeModel: string;
  codeModelInstalled: boolean;
  models: string[];
  endpoint?: string;
  error?: string;
}

function statusSignal(ms = 5000): AbortSignal | undefined {
  return typeof AbortSignal !== 'undefined' && 'timeout' in AbortSignal
    ? AbortSignal.timeout(ms)
    : undefined;
}

/** Check that Ollama is up and the configured Gemma model is pulled. */
export async function checkOllama(): Promise<OllamaStatus> {
  try {
    const res = await fetch(`${OLLAMA_BASE_URL}/api/tags`, {
      cache: 'no-store',
      signal: statusSignal(),
      // @ts-expect-error Node/undici fetch extension.
      dispatcher: OLLAMA_DISPATCHER,
    });
    if (!res.ok) {
      return {
        provider: 'ollama',
        reachable: false,
        model: OLLAMA_MODEL,
        modelInstalled: false,
        codeModel: OLLAMA_CODE_MODEL,
        codeModelInstalled: false,
        models: [],
        endpoint: OLLAMA_BASE_URL,
        error: `Ollama responded ${res.status}`,
      };
    }

    const data = (await res.json()) as { models?: Array<{ name: string }> };
    const models = (data.models ?? []).map((m) => m.name);
    const modelInstalled = models.some((m) => sameModelFamily(m, OLLAMA_MODEL));
    const codeModelInstalled = models.some((m) => sameModelFamily(m, OLLAMA_CODE_MODEL));
    return {
      provider: 'ollama',
      reachable: true,
      model: OLLAMA_MODEL,
      modelInstalled,
      codeModel: OLLAMA_CODE_MODEL,
      codeModelInstalled,
      models,
      endpoint: OLLAMA_BASE_URL,
    };
  } catch (err) {
    return {
      provider: 'ollama',
      reachable: false,
      model: OLLAMA_MODEL,
      modelInstalled: false,
      codeModel: OLLAMA_CODE_MODEL,
      codeModelInstalled: false,
      models: [],
      endpoint: OLLAMA_BASE_URL,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

/**
 * Stream a chat completion from Ollama, yielding visible content deltas.
 * Gemma thinking deltas are routed to `onThinking` when Ollama exposes them.
 */
export async function* streamOllamaChat(
  messages: ChatMessage[],
  options: {
    signal?: AbortSignal;
    temperature?: number;
    think?: boolean;
    model?: string;
    context?: 'plan' | 'code';
    numCtx?: number;
    onThinking?: (text: string) => void;
  } = {},
): AsyncGenerator<string> {
  const selectedModel = options.model ?? OLLAMA_MODEL;
  const think =
    options.think ??
    (sameModelFamily(selectedModel, OLLAMA_MODEL) && process.env.OLLAMA_THINK !== 'false');
  const rawNumCtx =
    options.numCtx && Number.isFinite(options.numCtx)
      ? Math.max(8192, Math.floor(options.numCtx))
      : options.context === 'code' ||
          (options.context == null &&
            options.model != null &&
            sameModelFamily(selectedModel, OLLAMA_CODE_MODEL))
        ? OLLAMA_CODE_CTX
        : OLLAMA_NUM_CTX;
  // Never request more than deepseek-r1:8b's 128K ceiling — a larger num_ctx is
  // silently clamped by the model anyway and only bloats the KV cache toward a
  // CPU spill.
  const numCtx = Math.min(DEEPSEEK_MAX_CTX, rawNumCtx);

  const res = await fetch(`${OLLAMA_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal: options.signal,
    // @ts-expect-error Node/undici fetch extension.
    dispatcher: OLLAMA_DISPATCHER,
    body: JSON.stringify({
      model: selectedModel,
      messages,
      stream: true,
      think,
      keep_alive: -1,
      options: {
        num_ctx: numCtx,
        // deepseek-r1 falls into endless repetition at very low temperature —
        // DeepSeek's own guidance is temp 0.5-0.7 (0.6) with top_p 0.95. Using
        // those defaults keeps the reasoning model from wedging the watchdog.
        temperature: options.temperature ?? Number(process.env.OLLAMA_TEMPERATURE || 0.6),
        top_p: Number(process.env.OLLAMA_TOP_P || 0.95),
        num_batch: Number(process.env.OLLAMA_NUM_BATCH || 1024),
      },
    }),
  });

  if (!res.ok || !res.body) {
    const text = await res.text().catch(() => '');
    throw new Error(`Ollama request failed (${res.status}): ${text}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let newlineIndex: number;
    while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, newlineIndex).trim();
      buffer = buffer.slice(newlineIndex + 1);
      if (!line) continue;

      let json: {
        message?: { content?: string; thinking?: string };
        done?: boolean;
        error?: string;
      };
      try {
        json = JSON.parse(line);
      } catch {
        continue;
      }

      if (json.error) throw new Error(`Ollama error: ${json.error}`);
      if (json.message?.thinking && options.onThinking) {
        options.onThinking(json.message.thinking);
      }
      if (json.message?.content) yield json.message.content;
      if (json.done) return;
    }
  }
}
