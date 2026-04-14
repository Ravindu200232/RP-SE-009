// Ollama client helper — replaces Google Gemini
const OLLAMA_BASE_URL = process.env.OLLAMA_BASE_URL || 'http://localhost:11434';
const MODEL = process.env.OLLAMA_MODEL || 'deepseek-v3.1:671b-cloud';

/**
 * Send a chat request to Ollama and return the raw Response (supports streaming).
 * @param {object} opts
 * @param {Array<{role:string,content:string}>} opts.messages
 * @param {string}  [opts.system]       - optional system prompt prepended to messages
 * @param {number}  [opts.temperature]  - default 0.7
 * @param {boolean} [opts.stream]       - default true
 * @param {string}  [opts.format]       - e.g. "json" to force JSON output
 */
export async function ollamaChat({ messages, system, temperature = 0.7, stream = true, format }) {
    const fullMessages = system
        ? [{ role: 'system', content: system }, ...messages]
        : messages;

    const body = {
        model: MODEL,
        messages: fullMessages,
        stream,
        options: { temperature },
        ...(format ? { format } : {}),
    };

    const response = await fetch(`${OLLAMA_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        const errText = await response.text();
        throw new Error(`Ollama API error (${response.status}): ${errText}`);
    }

    return response;
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

export { OLLAMA_BASE_URL, MODEL };
