// Ollama client helper — default to local coder models
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
const MODEL = process.env.OLLAMA_MODEL || 'qwen2.5-coder:7b';
const BACKEND_GEN_MODEL  = process.env.OLLAMA_MODEL_BACKEND_GEN  || MODEL;
const BACKEND_FIX_MODEL  = process.env.OLLAMA_MODEL_BACKEND_FIX  || MODEL;
const API_TEST_MODEL     = process.env.OLLAMA_MODEL_API_TEST      || MODEL;
const FRONTEND_GEN_MODEL = process.env.OLLAMA_MODEL_FRONTEND      || MODEL;
const FRONTEND_FIX_MODEL = process.env.OLLAMA_MODEL_FRONTEND_FIX  || MODEL;
const FALLBACK_MODEL     = process.env.OLLAMA_MODEL_FALLBACK       || 'codellama:7b';

async function requestOllamaChat(body) {
    return fetch(`${OLLAMA_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
}

/**
 * Send a chat request to Ollama and return the raw Response (supports streaming).
 * @param {object} opts
 * @param {Array<{role:string,content:string}>} opts.messages
 * @param {string}  [opts.system]       - optional system prompt prepended to messages
 * @param {number}  [opts.temperature]  - default 0.7
 * @param {boolean} [opts.stream]       - default true
 * @param {string}  [opts.format]       - e.g. "json" to force JSON output
 */
export async function ollamaChat({ messages, system, temperature = 0.7, stream = true, format, model = MODEL }) {
    const fullMessages = system
        ? [{ role: 'system', content: system }, ...messages]
        : messages;

    const buildBody = (selectedModel) => ({
        model: selectedModel,
        messages: fullMessages,
        stream,
        options: { temperature },
        ...(format ? { format } : {}),
    });

    const modelsToTry = [model];
    if (FALLBACK_MODEL && FALLBACK_MODEL !== model) {
        modelsToTry.push(FALLBACK_MODEL);
    }

    let lastError = null;
    for (const selectedModel of modelsToTry) {
        try {
            const response = await requestOllamaChat(buildBody(selectedModel));
            if (!response.ok) {
                const errText = await response.text();
                lastError = new Error(`Ollama API error (${response.status}) for model ${selectedModel}: ${errText}`);
                continue;
            }

            return response;
        } catch (error) {
            lastError = new Error(
                `Ollama fetch failed for model ${selectedModel} at ${OLLAMA_BASE_URL}/api/chat: ${error.message}`
            );
        }
    }

    throw lastError || new Error(`Ollama request failed for models ${modelsToTry.join(', ')}`);
}

/**
 * Async generator that yields parsed Ollama NDJSON chunks from a streaming response.
 * Each yielded object has shape: { message: { role, content }, done: boolean }
 */
export async function* readOllamaStream(response) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            try {
                yield JSON.parse(trimmed);
            } catch (_) {}
        }
    }

    if (buffer.trim()) {
        try { yield JSON.parse(buffer.trim()); } catch (_) {}
    }
}

export { OLLAMA_BASE_URL, MODEL, BACKEND_GEN_MODEL, BACKEND_FIX_MODEL, API_TEST_MODEL, FRONTEND_GEN_MODEL, FRONTEND_FIX_MODEL, FALLBACK_MODEL };





