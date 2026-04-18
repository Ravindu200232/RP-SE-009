/**
 * Bug Memory Service — ChromaDB-backed learning system
 *
 * Stores bug patterns + fix outcomes so the system learns what works and what doesn't.
 * On each new bug, queries ChromaDB for similar past bugs and injects that knowledge
 * into the AI fix prompt so the AI doesn't repeat failed approaches.
 *
 * Falls back to a local JSON file if ChromaDB is not running.
 *
 * ChromaDB setup:
 *   pip install chromadb
 *   chroma run --path ./chroma-data --port 8001
 *
 * Set CHROMADB_URL=http://localhost:8001 in your env (defaults to 8001).
 * Set OLLAMA_EMBED_MODEL=nomic-embed-text for embeddings (defaults to nomic-embed-text).
 */

import { readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const CHROMA_URL = process.env.CHROMADB_URL || 'http://localhost:8001';
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
const EMBED_MODEL = process.env.OLLAMA_EMBED_MODEL || 'nomic-embed-text';
const FALLBACK_PATH = path.join(process.cwd(), 'bug-memory-store.json');
const COLLECTION_NAME = 'ai_builder_bug_fixes';
const SIMILARITY_THRESHOLD = 0.55; // cosine similarity cutoff for "similar enough"

let chromaAvailable = null;
let collectionId = null;

// ── Helpers ───────────────────────────────────────────────────────────────────

function truncate(text, maxChars = 1500) {
    return String(text || '').slice(0, maxChars);
}

// ── Ollama embeddings ─────────────────────────────────────────────────────────

async function getEmbedding(text) {
    try {
        const res = await fetch(`${OLLAMA_BASE_URL}/api/embeddings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: EMBED_MODEL, prompt: truncate(text) }),
            signal: AbortSignal.timeout(12000),
        });
        if (!res.ok) return null;
        const data = await res.json();
        return Array.isArray(data.embedding) && data.embedding.length ? data.embedding : null;
    } catch (_) {
        return null;
    }
}

// ── ChromaDB REST client ──────────────────────────────────────────────────────

async function chromaFetch(method, endpoint, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
        signal: AbortSignal.timeout(6000),
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(`${CHROMA_URL}${endpoint}`, opts);
    if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`ChromaDB ${method} ${endpoint} → ${res.status}: ${text.slice(0, 200)}`);
    }
    return res.json();
}

async function checkChromaAvailable() {
    if (chromaAvailable !== null) return chromaAvailable;
    try {
        await chromaFetch('GET', '/api/v1/heartbeat');
        chromaAvailable = true;
    } catch (_) {
        chromaAvailable = false;
    }
    return chromaAvailable;
}

async function getCollectionId() {
    if (collectionId) return collectionId;
    try {
        const col = await chromaFetch('POST', '/api/v1/collections', {
            name: COLLECTION_NAME,
            get_or_create: true,
            metadata: { description: 'AI builder bug fix learning memory' },
        });
        collectionId = col.id;
    } catch (_) {
        try {
            const col = await chromaFetch('GET', `/api/v1/collections/${COLLECTION_NAME}`);
            collectionId = col.id;
        } catch (__) {
            throw new Error('Cannot get ChromaDB collection');
        }
    }
    return collectionId;
}

// ── Cosine similarity (JSON fallback) ────────────────────────────────────────

function cosineSim(a, b) {
    if (!Array.isArray(a) || !Array.isArray(b) || !a.length || a.length !== b.length) return 0;
    let dot = 0, magA = 0, magB = 0;
    for (let i = 0; i < a.length; i++) {
        dot += a[i] * b[i];
        magA += a[i] * a[i];
        magB += b[i] * b[i];
    }
    const denom = Math.sqrt(magA) * Math.sqrt(magB);
    return denom === 0 ? 0 : dot / denom;
}

// Simple keyword overlap for when embeddings are unavailable
function keywordSim(textA, textB) {
    const wordsOf = (t) => new Set(String(t).toLowerCase().split(/\W+/).filter(w => w.length > 3));
    const aWords = wordsOf(textA);
    const bWords = wordsOf(textB);
    let overlap = 0;
    for (const w of aWords) if (bWords.has(w)) overlap++;
    return overlap / Math.max(aWords.size, 1);
}

// ── JSON fallback store ───────────────────────────────────────────────────────

async function jsonLoad() {
    try {
        const raw = await readFile(FALLBACK_PATH, 'utf8');
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed.entries) ? parsed : { entries: [] };
    } catch (_) {
        return { entries: [] };
    }
}

async function jsonSave(store) {
    await writeFile(FALLBACK_PATH, JSON.stringify(store, null, 2), 'utf8').catch(() => {});
}

async function jsonQuery(bugText, topK) {
    const store = await jsonLoad();
    if (!store.entries.length) return [];
    const queryEmbed = await getEmbedding(bugText);

    const scored = store.entries.map(entry => {
        const sim = queryEmbed && entry.embedding?.length
            ? cosineSim(queryEmbed, entry.embedding)
            : keywordSim(bugText, entry.bugText);
        return { ...entry.meta, similarity: sim };
    });

    return scored
        .sort((a, b) => b.similarity - a.similarity)
        .slice(0, topK)
        .filter(r => r.similarity > 0.1);
}

// ── Public API ────────────────────────────────────────────────────────────────

/**
 * Store a bug fix attempt in ChromaDB (or JSON fallback).
 *
 * @param {object} opts
 * @param {string}  opts.bugText     - Error/bug text
 * @param {string}  opts.method      - Strategy name used (e.g. "standard", "full-rewrite")
 * @param {'success'|'fail'} opts.outcome
 * @param {string}  opts.phase       - "backend-fix" | "api-test" | "live-fix"
 * @param {number}  opts.round
 * @param {string}  [opts.fixSummary] - Brief description of what was changed
 */
export async function storeBugFix({ bugText, method, outcome, phase, round, fixSummary = '' }) {
    if (!bugText?.trim()) return;
    const id = `fix-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const meta = {
        method: String(method),
        outcome: String(outcome),
        phase: String(phase),
        round: String(round),
        timestamp: new Date().toISOString(),
        fixSummary: truncate(fixSummary, 400),
    };

    if (await checkChromaAvailable()) {
        try {
            const embedding = await getEmbedding(bugText);
            const cid = await getCollectionId();
            const body = {
                ids: [id],
                documents: [truncate(bugText)],
                metadatas: [meta],
            };
            if (embedding) body.embeddings = [embedding];
            await chromaFetch('POST', `/api/v1/collections/${cid}/add`, body);
            return;
        } catch (err) {
            console.warn('[BugMemory] ChromaDB store failed, using JSON fallback:', err.message);
            chromaAvailable = false; // circuit-breaker until next startup
        }
    }

    // JSON fallback
    const store = await jsonLoad();
    const embedding = await getEmbedding(bugText);
    store.entries.push({ id, bugText: truncate(bugText), embedding: embedding || [], meta });
    if (store.entries.length > 600) store.entries = store.entries.slice(-600);
    await jsonSave(store);
}

/**
 * Query ChromaDB (or JSON) for similar past bugs.
 *
 * @param {string} bugText
 * @param {number} topK
 * @returns {Array<{ method, outcome, phase, fixSummary, similarity? }>}
 */
export async function queryBug(bugText, topK = 6) {
    if (!bugText?.trim()) return [];

    if (await checkChromaAvailable()) {
        try {
            const embedding = await getEmbedding(bugText);
            const cid = await getCollectionId();
            const body = {
                n_results: topK,
                include: ['metadatas', 'distances'],
            };
            if (embedding) {
                body.query_embeddings = [embedding];
            } else {
                body.query_texts = [truncate(bugText)];
            }
            const results = await chromaFetch('POST', `/api/v1/collections/${cid}/query`, body);
            const metas = results.metadatas?.[0] || [];
            const distances = results.distances?.[0] || [];
            return metas.map((m, i) => ({
                ...m,
                similarity: Math.max(0, 1 - (distances[i] || 1)),
            }));
        } catch (err) {
            console.warn('[BugMemory] ChromaDB query failed:', err.message);
            chromaAvailable = false;
        }
    }

    return jsonQuery(bugText, topK);
}

/**
 * Get fix methods that previously FAILED for a similar bug.
 * Helps the AI avoid repeating the same failed approach.
 *
 * @returns {string[]} - list of failed method names
 */
export async function getFailedMethods(bugText) {
    const similar = await queryBug(bugText, 8);
    return [...new Set(
        similar
            .filter(r => r.outcome === 'fail' && (r.similarity ?? 0) >= SIMILARITY_THRESHOLD)
            .map(r => r.method)
            .filter(Boolean)
    )];
}

/**
 * Get the best known fix approach for a similar bug.
 *
 * @returns {{ method, fixSummary } | null}
 */
export async function getBestKnownFix(bugText) {
    const similar = await queryBug(bugText, 8);
    return similar
        .filter(r => r.outcome === 'success' && (r.similarity ?? 0) >= SIMILARITY_THRESHOLD)
        .sort((a, b) => (b.similarity ?? 0) - (a.similarity ?? 0))[0] || null;
}

/**
 * Build a memory context string for injection into AI prompts.
 * Tells the AI what worked and what failed for similar bugs.
 *
 * @param {string} bugText
 * @returns {string} - human-readable memory context block
 */
export async function buildMemoryContext(bugText) {
    try {
        const similar = await queryBug(bugText, 6);
        if (!similar.length) return '';

        const relevant = similar.filter(r => (r.similarity ?? 0) >= SIMILARITY_THRESHOLD);
        if (!relevant.length) return '';

        const successes = relevant.filter(r => r.outcome === 'success');
        const failures = relevant.filter(r => r.outcome === 'fail');
        const lines = ['[BUG FIX MEMORY — from past similar bugs]'];

        if (successes.length) {
            lines.push('What WORKED for similar bugs:');
            successes.slice(0, 3).forEach(r => {
                const summary = r.fixSummary ? ` — ${r.fixSummary}` : '';
                lines.push(`  ✓ Method "${r.method}" in ${r.phase}${summary}`);
            });
        }

        if (failures.length) {
            const failedMethods = [...new Set(failures.map(r => r.method))];
            lines.push(`What did NOT work: ${failedMethods.join(', ')}`);
            lines.push('IMPORTANT: Do NOT use these failed methods again. Try a completely different approach.');
        }

        return lines.join('\n');
    } catch (_) {
        return '';
    }
}
