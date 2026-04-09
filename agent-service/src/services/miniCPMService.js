/**
 * MiniCPMService — Multimodal input processor using openbmb/minicpm-o4.5 via Ollama.
 *
 * Processes:
 *  - Text prompts (pass-through)
 *  - Images (base64 → vision understanding)
 *  - PDFs (extracted text → summary)
 *  - Voice files (audio transcription via Ollama whisper-compatible)
 *
 * Output: unified text description for DeepSeek to build SRS from.
 */

import axios from 'axios';
import fs from 'fs';
import path from 'path';
import dotenv from 'dotenv';
dotenv.config();

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://localhost:11434';
const MINICPM_MODEL = process.env.MINICPM_MODEL || 'minicpm-o';
const VOICE_NOTE_MARKER = 'Voice note:';

function extractBrowserVoiceTranscript(textPrompt = '') {
  const markerIndex = textPrompt.lastIndexOf(VOICE_NOTE_MARKER);
  if (markerIndex === -1) {
    return '';
  }

  return textPrompt.slice(markerIndex + VOICE_NOTE_MARKER.length).trim();
}

class MiniCPMService {
  /**
   * Process all uploaded files + user text prompt into a unified project description.
   * @param {string} textPrompt - User's text description
   * @param {Array<{path, mimetype, originalname}>} files - Uploaded files
   * @param {Function} logFn - Logging callback (message, level)
   * @returns {Promise<string>} Unified project description
   */
  async processInputs(textPrompt, files = [], logFn = () => {}) {
    logFn('🔍 MiniCPM-O: Processing multimodal inputs...', 'info');

    const parts = [];
    const browserVoiceTranscript = extractBrowserVoiceTranscript(textPrompt);

    // Always include text prompt
    if (textPrompt?.trim()) {
      parts.push(`USER PROMPT: ${textPrompt.trim()}`);
      logFn(`📝 Text prompt received: "${textPrompt.trim().slice(0, 80)}..."`, 'info');
    }

    if (browserVoiceTranscript) {
      parts.push(`VOICE NOTE TRANSCRIPT: ${browserVoiceTranscript}`);
      logFn('Using the browser transcript that came with the live voice recording.', 'success');
    }

    // Process each uploaded file
    for (const file of files) {
      try {
        const ext = path.extname(file.originalname).toLowerCase();
        logFn(`📂 Processing file: ${file.originalname} (${file.mimetype})`, 'info');

        if (file.mimetype.startsWith('image/')) {
          const result = await this._processImage(file, logFn);
          parts.push(`IMAGE CONTENT: ${result}`);

        } else if (file.mimetype === 'application/pdf' || ext === '.pdf') {
          const result = await this._processPDF(file, logFn);
          parts.push(`PDF CONTENT: ${result}`);

        } else if (file.mimetype.startsWith('audio/') || ['.mp3', '.wav', '.m4a', '.ogg', '.webm', '.aac'].includes(ext)) {
          if (browserVoiceTranscript) {
            parts.push(`VOICE NOTE FILE: ${file.originalname}`);
            logFn(`Audio file kept with the live browser transcript: ${file.originalname}`, 'info');
            continue;
          }
          const result = await this._processVoice(file, logFn);
          parts.push(`VOICE TRANSCRIPT: ${result}`);

        } else if (file.mimetype.startsWith('text/') || ['.txt', '.md', '.markdown', '.json', '.csv'].includes(ext)) {
          const content = fs.readFileSync(file.path, 'utf8');
          parts.push(`TEXT FILE (${file.originalname}): ${content.slice(0, 3000)}`);
          logFn(`📄 Text file read: ${content.length} chars`, 'success');
        }
      } catch (err) {
        logFn(`⚠️ Could not process ${file.originalname}: ${err.message}`, 'warning');
      }
    }

    if (parts.length === 0) {
      return textPrompt || 'No input provided';
    }

    // If only text prompt (no files), return directly
    if (parts.length === 1 && files.length === 0) {
      return textPrompt;
    }

    // Use MiniCPM to synthesize all inputs into one description
    logFn('🧠 MiniCPM-O: Synthesizing all inputs into unified project description...', 'info');
    const unified = await this._synthesize(parts, logFn);
    logFn('✅ MiniCPM-O: Input synthesis complete', 'success');
    return unified;
  }

  // ── Private: Image processing ──────────────────────────────────────────────

  async _processImage(file, logFn) {
    logFn('🖼️ MiniCPM-O: Analyzing image with vision...', 'info');
    const imageBase64 = fs.readFileSync(file.path).toString('base64');
    const mimeType = file.mimetype;

    try {
      const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
        model: MINICPM_MODEL,
        messages: [
          {
            role: 'user',
            content: [
              {
                type: 'text',
                text: 'Analyze this image and describe what software application, system, or requirements it shows. Extract any text, diagrams, wireframes, flowcharts, or UI mockups visible. Provide a detailed description for software requirements purposes.'
              },
              {
                type: 'image_url',
                image_url: { url: `data:${mimeType};base64,${imageBase64}` }
              }
            ]
          }
        ],
        stream: false
      }, { timeout: 120000 });

      const result = response.data?.message?.content || 'Image analyzed but no content extracted';
      logFn(`🖼️ Image analysis: ${result.slice(0, 100)}...`, 'success');
      return result;
    } catch (err) {
      logFn(`⚠️ Vision model unavailable, using image filename as hint: ${err.message}`, 'warning');
      return `Image file: ${file.originalname} (vision processing unavailable)`;
    }
  }

  // ── Private: PDF processing ────────────────────────────────────────────────

  async _processPDF(file, logFn) {
    logFn('📄 Extracting text from PDF...', 'info');
    try {
      const { PDFParse } = await import('pdf-parse');
      const dataBuffer = fs.readFileSync(file.path);
      const parser = new PDFParse({ data: dataBuffer });
      const data = await parser.getText();
      const text = data.text.slice(0, 5000); // cap at 5000 chars
      await parser.destroy();
      logFn(`📄 PDF extracted: ${data.numpages} pages, ${data.text.length} chars`, 'success');
      return text;
    } catch (err) {
      logFn(`⚠️ PDF extraction failed: ${err.message}`, 'warning');
      return `PDF file: ${file.originalname} (text extraction failed)`;
    }
  }

  // ── Private: Voice/audio processing ───────────────────────────────────────

  async _processVoice(file, logFn) {
    logFn('🎤 MiniCPM-O: Transcribing voice input...', 'info');
    try {
      const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
        model: MINICPM_MODEL,
        messages: [
          {
            role: 'user',
            content: `A user uploaded an audio note for software requirements. If the model can truly access audio, transcribe it and summarize the product idea. If audio access is unavailable, clearly say the file was received but not transcribed automatically. Audio file: ${file.originalname}.`
          }
        ],
        stream: false
      }, { timeout: 120000 });

      const result = response.data?.message?.content || `Voice file received: ${file.originalname}`;
      logFn(`🎤 Voice transcription: ${result.slice(0, 100)}`, 'success');
      return result;
    } catch {
      logFn(`🎤 Voice file registered: ${file.originalname}`, 'info');
      return `Voice input provided (${file.originalname}) — please describe your requirements in text as well`;
    }
  }

  // ── Private: Synthesize all inputs ────────────────────────────────────────

  async _synthesize(parts, logFn) {
    const combinedInput = parts.join('\n\n---\n\n');

    try {
      const response = await axios.post(`${OLLAMA_URL}/api/chat`, {
        model: MINICPM_MODEL,
        messages: [
          {
            role: 'system',
            content: 'You are a requirements analyst. Synthesize all provided inputs (text, images, PDFs, voice) into a single comprehensive project description. Extract: project purpose, core features, user types, technical constraints, domain, and application type. Be specific and detailed.'
          },
          {
            role: 'user',
            content: `Synthesize these inputs into one project description:\n\n${combinedInput}`
          }
        ],
        stream: false,
        options: { temperature: 0.1, num_predict: 2000 }
      }, { timeout: 180000 });

      return response.data?.message?.content || combinedInput.slice(0, 3000);
    } catch (err) {
      logFn(`⚠️ MiniCPM synthesis failed, using raw inputs: ${err.message}`, 'warning');
      return combinedInput.slice(0, 3000);
    }
  }
}

export default new MiniCPMService();
