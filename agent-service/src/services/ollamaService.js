const axios = require('axios');
const Message = require('../models/Message');

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const DEFAULT_MODEL = process.env.OLLAMA_MODEL || 'qwen2.5:14b';
const MAX_NUM_CTX = Number.parseInt(process.env.OLLAMA_NUM_CTX || '12288', 10);
const MAX_NUM_PREDICT = Number.parseInt(process.env.OLLAMA_NUM_PREDICT || '6144', 10);
const MAX_HISTORY_MESSAGES = Number.parseInt(process.env.OLLAMA_HISTORY_MESSAGES || '10', 10);
const DEFAULT_TEMPERATURE = Number.parseFloat(process.env.OLLAMA_TEMPERATURE || '0.12');
const DEFAULT_REPEAT_PENALTY = Number.parseFloat(process.env.OLLAMA_REPEAT_PENALTY || '1.12');
const DEFAULT_REPEAT_LAST_N = Number.parseInt(process.env.OLLAMA_REPEAT_LAST_N || '96', 10);
const DEFAULT_TIMEOUT_MS = Number.parseInt(process.env.OLLAMA_TIMEOUT_MS || '900000', 10);

// Repetition detection — checked every N new tokens
const REPETITION_CHECK_EVERY = 80;   // check after every 80 new characters added
// Window sizes to scan (short phrases to medium paragraphs)
const REPETITION_WINDOWS = [30, 60, 100, 200];
const REPETITION_COUNT = 3;          // same chunk must appear 3x to declare loop

/**
 * Custom error that carries the partial streaming response generated before timeout.
 * callers (developerAgent) can extract files from partialResponse and continue.
 */
class OllamaTimeoutError extends Error {
  constructor(message, partialResponse) {
    super(message);
    this.name = 'OllamaTimeoutError';
    this.partialResponse = partialResponse || '';
    this.isTimeout = true;
  }
}

/**
 * OllamaService — wraps Ollama chat API with streaming support.
 * Saves every message to MongoDB so the agent can use history for error fixing.
 *
 * Bug fixes applied:
 *  [1] Double resolve() — only ONE of (parsed.done / stream end) resolves the promise
 *  [2] Double Message.create() — guarded by a `saved` flag
 *  [3] Repetition loop detection — stops early when AI starts doubling tokens
 *  [4] Response truncation — clips everything after the last ===END=== marker
 *  [5] Higher repeat_penalty (1.15) to reduce model repetition tendency
 *  [6] OllamaTimeoutError — carries partial response so callers can continue generation
 */
class OllamaService {
  constructor(io) {
    this.io = io;
  }

  resolveModel(context = {}) {
    return String(context.model || DEFAULT_MODEL);
  }

  resolveTimeoutMs(context = {}) {
    const seconds = Number.parseInt(String(context.timeoutSeconds || ''), 10);
    if (Number.isFinite(seconds) && seconds > 0) {
      return seconds * 1000;
    }
    return DEFAULT_TIMEOUT_MS;
  }

  buildOptions(phase = '') {
    const normalizedPhase = String(phase || '').toLowerCase();
    let numCtx = MAX_NUM_CTX;
    let numPredict = MAX_NUM_PREDICT;

    if (normalizedPhase.startsWith('plan')) {
      numCtx = Math.min(MAX_NUM_CTX, 6144);
      numPredict = Math.min(MAX_NUM_PREDICT, 2048);
    } else if (normalizedPhase.startsWith('pkg')) {
      numCtx = Math.min(MAX_NUM_CTX, 4096);
      numPredict = Math.min(MAX_NUM_PREDICT, 1536);
    } else if (normalizedPhase.startsWith('src_frontend')) {
      numCtx = Math.min(MAX_NUM_CTX, 12288);
      numPredict = Math.min(MAX_NUM_PREDICT, 8192);
    } else if (normalizedPhase.startsWith('src_')) {
      numCtx = Math.min(MAX_NUM_CTX, 12288);
      numPredict = Math.min(MAX_NUM_PREDICT, 6144);
    } else if (normalizedPhase.includes('analyze') || normalizedPhase.includes('repair') || normalizedPhase.includes('fix')) {
      numCtx = Math.min(MAX_NUM_CTX, 8192);
      numPredict = Math.min(MAX_NUM_PREDICT, 3072);
    }

    return {
      temperature: DEFAULT_TEMPERATURE,
      num_predict: numPredict,
      repeat_penalty: DEFAULT_REPEAT_PENALTY,
      repeat_last_n: DEFAULT_REPEAT_LAST_N,
      num_ctx: numCtx
    };
  }

  trimHistory(history = [], phase = '') {
    const normalizedPhase = String(phase || '').toLowerCase();
    const messageLimit = normalizedPhase.includes('analyze')
      ? Math.min(MAX_HISTORY_MESSAGES, 8)
      : MAX_HISTORY_MESSAGES;
    const charBudget = normalizedPhase.includes('analyze') ? 18000 : 24000;

    const selected = [];
    let totalChars = 0;

    for (let index = history.length - 1; index >= 0; index -= 1) {
      const message = history[index];
      const contentLength = (message?.content || '').length;

      if (selected.length >= messageLimit) {
        break;
      }

      if (selected.length > 0 && totalChars + contentLength > charBudget) {
        break;
      }

      selected.unshift(message);
      totalChars += contentLength;
    }

    return selected;
  }

  /** Check Ollama is reachable and model is available */
  async checkHealth(modelName = DEFAULT_MODEL) {
    try {
      const res = await axios.get(`${OLLAMA_URL}/api/tags`, { timeout: 5000 });
      const models = res.data.models || [];
      const available = models.map(m => m.name);
      const found = available.some(n => n === modelName || n.startsWith(String(modelName).split(':')[0]));
      return { ok: true, models: available, modelFound: found, selectedModel: modelName };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  }

  /**
   * Core streaming chat. Saves user messages and assistant response to DB.
   * @param {string} jobId
   * @param {Array}  messages  - [{role, content}]
   * @param {string} agent     - agent name for logging
   * @param {string} phase     - phase name for logging
   * @param {Function} onToken - callback(token) for streaming UI
   */
  async chat(jobId, messages, agent, phase, onToken, context = {}) {
    const model = this.resolveModel(context);
    const timeoutMs = this.resolveTimeoutMs(context);

    // Persist the last user message
    const lastMsg = messages[messages.length - 1];
    if (lastMsg.role === 'user') {
      await Message.create({
        jobId,
        role: 'user',
        content: lastMsg.content,
        agent,
        phase,
        workspaceId: context.workspaceId,
        threadId: context.threadId,
        generationId: context.generationId || jobId
      });
    }

    let fullResponse = '';
    let saved = false;               // ★ FIX [2]: guard against double save
    let resolved = false;            // ★ FIX [1]: guard against double resolve
    let loopDetected = false;        // ★ FIX [3]: repetition loop flag
    let lastRepetitionCheck = 0;     // track when we last ran the repetition check

    const saveAndResolve = (resolve) => {
      if (resolved) return;
      resolved = true;

      // ★ FIX [4]: truncate everything after the LAST ===END=== so looped
      // text ("IfIf you you need need...") is discarded before saving/returning
      const cleaned = this._truncateAfterLastEnd(fullResponse);

      if (!saved) {
        saved = true;
        Message.create({
          jobId,
          role: 'assistant',
          content: cleaned,
          agent,
          phase,
          workspaceId: context.workspaceId,
          threadId: context.threadId,
          generationId: context.generationId || jobId
        })
          .catch(console.error);
      }
      resolve(cleaned);
    };

    try {
      const requestConfig = {
        method: 'POST',
        url: `${OLLAMA_URL}/api/chat`,
        data: {
          model,
          messages: messages.map(({ role, content }) => ({ role, content })),
          stream: true,
          options: {
            temperature: 0.15,         // low temperature → less hallucination
            num_predict: 32768,
            repeat_penalty: 1.15,      // ★ FIX [5]: penalise repeated tokens
            repeat_last_n: 128,        // look back 128 tokens for repetition
            num_ctx: 32768             // full context window
          }
        },
        responseType: 'stream',
        timeout: timeoutMs
      };
      requestConfig.data.options = this.buildOptions(phase);
      const response = await axios(requestConfig);

      return await new Promise((resolve, reject) => {
        let buffer = '';

        response.data.on('data', (chunk) => {
          // If we already detected a loop and stopped early, discard further data
          if (loopDetected) return;

          buffer += chunk.toString();
          const lines = buffer.split('\n');
          buffer = lines.pop(); // keep incomplete last line

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const parsed = JSON.parse(line);
              const token = parsed?.message?.content || '';

              if (token) {
                fullResponse += token;

                // ★ FIX [3]: Repetition loop detection — multi-scale window check
                // Only run every REPETITION_CHECK_EVERY chars to avoid perf cost
                if (fullResponse.length - lastRepetitionCheck >= REPETITION_CHECK_EVERY &&
                    fullResponse.length > REPETITION_WINDOWS[REPETITION_WINDOWS.length - 1] * REPETITION_COUNT) {
                  lastRepetitionCheck = fullResponse.length;

                  if (this._isLooping(fullResponse)) {
                    loopDetected = true;
                    console.warn(`[OllamaService] Repetition loop detected for job ${jobId} — truncating response`);
                    this.io?.to(jobId).emit('log', {
                      level: 'warning',
                      agent: 'AI',
                      message: '⚠️ Repetition loop detected — truncating AI response at last valid ===END===',
                      timestamp: new Date().toISOString()
                    });
                    saveAndResolve(resolve);
                    return;
                  }
                }

                if (onToken) onToken(token);
                // Stream to connected UI clients
                if (this.io) {
                  this.io.to(jobId).emit('agent:token', { agent, token });
                }
              }

              // ★ FIX [1]: Only resolve on done — end event is backup only
              if (parsed.done) {
                saveAndResolve(resolve);
              }
            } catch {
              // skip malformed JSON chunks
            }
          }
        });

        response.data.on('error', (err) => {
          if (!resolved) reject(err);
        });

        // ★ FIX [1]: 'end' event fires after done — only save/resolve if not already done
        response.data.on('end', () => {
          if (!resolved) {
            if (fullResponse) {
              saveAndResolve(resolve);
            } else {
              reject(new Error('Empty response from Ollama'));
            }
          }
        });
      });
    } catch (err) {
      // ★ FIX [6]: On timeout, throw OllamaTimeoutError with whatever was generated so far.
      // This lets developerAgent extract partial files and continue with a second prompt.
      const isTimeout = err.code === 'ECONNABORTED' ||
                        err.code === 'ETIMEDOUT' ||
                        err.message?.includes('timeout') ||
                        err.message?.includes('ETIMEDOUT');
      if (isTimeout) {
        const partial = this._truncateAfterLastEnd(fullResponse);
        throw new OllamaTimeoutError(
          `Ollama generation timed out after ${Math.round(timeoutMs / 1000)}s`,
          partial
        );
      }
      const msg = err.code === 'ECONNREFUSED'
        ? `Cannot connect to Ollama at ${OLLAMA_URL}. Is Ollama running?`
        : `Ollama error: ${err.message}`;
      throw new Error(msg);
    }
  }

  /**
   * ★ FIX [3]: Multi-scale repetition loop detector.
   *
   * Checks at multiple window sizes (30, 60, 100, 200 chars).
   * For each window size W, takes the last W*REPETITION_COUNT chars from the
   * response and checks if any W-length substring appears REPETITION_COUNT times.
   *
   * Also catches the word-doubling pattern: "If If you you need need..."
   */
  _isLooping(text) {
    if (!text) return false;

    // --- Check 1: Multi-scale chunk repetition ---
    for (const windowSize of REPETITION_WINDOWS) {
      const scanLen = windowSize * REPETITION_COUNT;
      if (text.length < scanLen) continue;

      const tail = text.slice(-scanLen);
      const chunk = tail.slice(0, windowSize);

      // Count how many times this chunk appears in the tail
      let count = 0;
      let pos = 0;
      while ((pos = tail.indexOf(chunk, pos)) !== -1) {
        count++;
        pos += 1; // +1 not +windowSize to catch overlapping
      }
      if (count >= REPETITION_COUNT) return true;
    }

    // --- Check 2: Word doubling ("If If you you need need...") ---
    // Look at the last 400 chars and check word-pair doubling rate
    const tailWords = text.slice(-400).split(/\s+/).filter(w => w.length > 1);
    if (tailWords.length >= 10) {
      let doubles = 0;
      for (let i = 0; i < tailWords.length - 1; i++) {
        if (tailWords[i] === tailWords[i + 1]) doubles++;
      }
      // If >40% of adjacent word pairs are identical → word doubling loop
      if (doubles / (tailWords.length - 1) > 0.40) return true;
    }

    return false;
  }

  /**
   * ★ FIX [4]: Truncate response to everything up to and including the last
   * valid ===END=== marker. Discards any looped/repeated content that appears
   * after the model finishes its real output.
   *
   * Pattern we see when model loops:
   *   ===END===
   *   Would Would you you like like to to add add...  ← LOOPED JUNK
   *   === ===ENDEND======                             ← DOUBLED MARKER
   *
   * This clips at the FIRST ===END=== after the last real file block.
   */
  _truncateAfterLastEnd(response) {
    if (!response) return response;

    // Find the last clean ===END=== in the response
    const endMarker = '===END===';
    const lastIdx = response.lastIndexOf(endMarker);

    if (lastIdx === -1) {
      // No ===END=== found — check for partial/doubled markers and clean up
      return this._deduplicateTokens(response);
    }

    // Keep everything up to and including the last ===END===
    const truncated = response.slice(0, lastIdx + endMarker.length);
    return truncated;
  }

  /**
   * De-duplicate doubled tokens in AI response.
   * Handles patterns like: "IfIf youyou needneed" or "If If you you need need"
   *
   * This is a fallback for when the AI model starts doubling every token.
   */
  _deduplicateTokens(text) {
    if (!text) return text;

    // Detect "word word" doubling pattern (with space between)
    // If more than 30% of words are doubled, apply dedup
    const words = text.split(/\s+/);
    let doubledCount = 0;
    for (let i = 0; i < words.length - 1; i++) {
      if (words[i] === words[i + 1] && words[i].length > 1) doubledCount++;
    }

    if (doubledCount / words.length > 0.3) {
      // Remove every other duplicate word
      const deduped = [];
      for (let i = 0; i < words.length; i++) {
        if (i < words.length - 1 && words[i] === words[i + 1] && words[i].length > 1) {
          deduped.push(words[i]);
          i++; // skip the duplicate
        } else {
          deduped.push(words[i]);
        }
      }
      return deduped.join(' ');
    }

    return text;
  }

  /**
   * Generate with system prompt (no history).
   */
  async generate(jobId, userPrompt, systemPrompt, agent, phase, onToken, context = {}) {
    const messages = [
      { role: 'system', content: systemPrompt },
      { role: 'user', content: userPrompt }
    ];
    return this.chat(jobId, messages, agent, phase, onToken, context);
  }

  /**
   * Generate using full conversation history from DB.
   * Used for error fixing — the model has context of everything it generated.
   */
  async generateWithHistory(jobId, userPrompt, systemPrompt, agent, phase, onToken, context = {}) {
    const query = context.threadId ? { threadId: context.threadId } : { jobId };
    const history = await Message.find(query)
      .sort({ createdAt: 1 })
      .select('role content -_id')
      .lean();
    const trimmedHistory = this.trimHistory(history, phase);

    const messages = [
      { role: 'system', content: systemPrompt },
      ...trimmedHistory,
      { role: 'user', content: userPrompt }
    ];
    return this.chat(jobId, messages, agent, phase, onToken, context);
  }

  /** Get all messages for a job (conversation history) */
  async getHistory(jobId) {
    return Message.find({ jobId }).sort({ createdAt: 1 }).lean();
  }
}

module.exports = OllamaService;
module.exports.OllamaTimeoutError = OllamaTimeoutError;
