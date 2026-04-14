import { ollamaChat, readOllamaStream } from '@/configs/AiModel';
import Prompt from '@/data/Prompt';

/* ─────────────────────────────────────────────────────────────────────────────
   UNIVERSAL AI OUTPUT PARSER
   Tries 5 different formats that AI models commonly produce:
   1. Our ===FRONTEND: /path=== delimiter format
   2. Markdown code blocks with filename:  ```js\n// /App.js\ncode\n```
   3. Markdown code blocks with path tag:  ```js:/App.js\ncode\n```
   4. Plain JSON  { "frontend": {...}, "files": {...} }
   5. Key-value file headers:  // FILE: /App.js\ncode
───────────────────────────────────────────────────────────────────────────── */
function parseAIOutput(text) {
    const result = { projectTitle: '', explanation: '', frontend: {}, backend: {} };

    // ── Helper ──────────────────────────────────────────────────────────────
    const addFrontend = (path, code) => {
        if (!path || !code?.trim()) return;
        const k = path.trim().startsWith('/') ? path.trim() : `/${path.trim()}`;
        // Skip non-source files
        if (k === '/index.js' || k === '/index.html' || k === '/package.json' ||
            k === '/vite.config.js' || k === '/tailwind.config.js') return;
        result.frontend[k] = { code: code.trim() };
    };
    const addBackend = (path, code) => {
        if (!path || !code?.trim()) return;
        const k = path.trim().startsWith('/') ? path.trim() : `/${path.trim()}`;
        result.backend[k] = { code: code.trim() };
    };

    // ── Parse META ──────────────────────────────────────────────────────────
    const metaMatch = text.match(/===META===([\s\S]*?)===ENDMETA===/i);
    if (metaMatch) {
        try {
            const m = JSON.parse(metaMatch[1].trim());
            result.projectTitle = m.projectTitle || m.title || '';
            result.explanation  = m.explanation  || m.description || '';
        } catch (_) {
            const t = metaMatch[1].match(/projectTitle["\s:]+([^\n",}]+)/i);
            if (t) result.projectTitle = t[1].trim().replace(/[",]/g, '');
        }
    }

    // ── Method 1: ===FRONTEND: /path=== … ===ENDFILE=== ────────────────────
    //   (flexible: allows spaces, handles \r\n, case-insensitive)
    {
        const re = /={2,3}\s*FRONTEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)(?===={2,3}\s*(?:FRONTEND|BACKEND|ENDFILE|META)\s*|$)/gi;
        let m;
        while ((m = re.exec(text)) !== null) addFrontend(m[1], m[2].replace(/===ENDFILE===/gi,'').trimEnd());

        const re2 = /={2,3}\s*BACKEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)(?===={2,3}\s*(?:FRONTEND|BACKEND|ENDFILE|META)\s*|$)/gi;
        while ((m = re2.exec(text)) !== null) addBackend(m[1], m[2].replace(/===ENDFILE===/gi,'').trimEnd());

        // Also match explicit ===ENDFILE===
        const re3 = /={2,3}\s*FRONTEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)={2,3}\s*ENDFILE\s*={2,3}/gi;
        while ((m = re3.exec(text)) !== null) addFrontend(m[1], m[2]);

        const re4 = /={2,3}\s*BACKEND\s*:\s*([^\n=\r]+?)\s*={2,3}\r?\n([\s\S]*?)={2,3}\s*ENDFILE\s*={2,3}/gi;
        while ((m = re4.exec(text)) !== null) addBackend(m[1], m[2]);
    }

    // ── Method 2: ```lang\n// /path.js\ncode\n``` ───────────────────────────
    if (Object.keys(result.frontend).length === 0) {
        const re = /```(?:jsx?|tsx?|javascript|typescript)?\r?\n([\s\S]*?)```/g;
        let m;
        while ((m = re.exec(text)) !== null) {
            const block = m[1];
            // First line must be a file path comment
            const firstLine = block.split('\n')[0].trim();
            const pathMatch = firstLine.match(/^\/\/\s*(\/[\w/.\-]+\.[a-z]+)/i)
                || firstLine.match(/^#\s*(\/[\w/.\-]+\.[a-z]+)/i)
                || firstLine.match(/^\/\*\s*(\/[\w/.\-]+\.[a-z]+)/i);
            if (pathMatch) {
                const code = block.split('\n').slice(1).join('\n');
                const path = pathMatch[1];
                const isBackend = path.includes('-service') || path.includes('gateway') || path.includes('/routes/') || path.includes('/models/');
                if (isBackend) addBackend(path, code);
                else addFrontend(path, code);
            }
        }
    }

    // ── Method 3: ```lang:/path.js\ncode\n``` ──────────────────────────────
    if (Object.keys(result.frontend).length === 0) {
        const re = /```(?:jsx?|tsx?|javascript)?:([^\n`\r]+)\r?\n([\s\S]*?)```/g;
        let m;
        while ((m = re.exec(text)) !== null) {
            const path = m[1].trim();
            const code = m[2];
            const isBackend = path.includes('-service') || path.includes('gateway') || path.includes('/routes/') || path.includes('/models/');
            if (isBackend) addBackend(path, code);
            else addFrontend(path, code);
        }
    }

    // ── Method 4: JSON { frontend:{}, backend:{}, files:{} } ───────────────
    if (Object.keys(result.frontend).length === 0) {
        try {
            const s = text.indexOf('{'), e = text.lastIndexOf('}');
            if (s !== -1 && e > s) {
                const parsed = JSON.parse(text.slice(s, e + 1));
                const fe = parsed.frontend || parsed.files || {};
                const be = parsed.backend  || {};
                Object.entries(fe).forEach(([p,v]) => addFrontend(p, v?.code || v));
                Object.entries(be).forEach(([p,v]) => addBackend(p,  v?.code || v));
                if (parsed.projectTitle) result.projectTitle = parsed.projectTitle;
            }
        } catch (_) {}
    }

    // ── Method 5: // FILE: /path.js header blocks ───────────────────────────
    if (Object.keys(result.frontend).length === 0) {
        const re = /\/\/\s*(?:FILE|File|file)\s*:\s*(\/[\w/.\-]+\.[a-z]+)\s*\r?\n([\s\S]*?)(?=\/\/\s*(?:FILE|File|file)\s*:|$)/g;
        let m;
        while ((m = re.exec(text)) !== null) addFrontend(m[1], m[2]);
    }

    // ── Extract projectTitle from text if still missing ─────────────────────
    if (!result.projectTitle) {
        const t = text.match(/(?:projectTitle|Project Title|title)\s*[":=]\s*["']?([^\n"',]+)/i);
        if (t) result.projectTitle = t[1].trim();
    }

    return result;
}

/* ─────────────────────────────────────────────────────────────────────────────
   COUNT PROGRESS — works across all delimiter styles
───────────────────────────────────────────────────────────────────────────── */
function countFilesInText(text) {
    // Count file START markers — works regardless of whether AI uses ===ENDFILE===
    const frontendStarts = (text.match(/===\s*FRONTEND\s*:/gi) || []).length;
    const backendStarts  = (text.match(/===\s*BACKEND\s*:/gi)  || []).length;
    const endfileCount   = (text.match(/===ENDFILE===/gi)      || []).length;
    const mdBlocks       = (text.match(/```(?:jsx?|tsx?)[:/\n]/gi) || []).length;
    return Math.max(frontendStarts + backendStarts, endfileCount, Math.floor(mdBlocks / 2));
}

/* ─────────────────────────────────────────────────────────────────────────────
   ROUTE HANDLER
───────────────────────────────────────────────────────────────────────────── */
export async function POST(req) {
    const { prompt } = await req.json();

    try {
        const ollamaResponse = await ollamaChat({
            messages: [{ role: 'user', content: prompt }],
            system: Prompt.CODE_GEN_PROMPT,
            temperature: 0.7,
            stream: true,
            // No format:'json' — let model write code naturally
        });

        const encoder = new TextEncoder();
        const stream  = new ReadableStream({
            async start(controller) {
                try {
                    let fullText  = '';
                    let prevCount = 0;

                    for await (const chunk of readOllamaStream(ollamaResponse)) {
                        const content = chunk?.message?.content ?? '';
                        if (content) {
                            fullText += content;
                            const newCount = countFilesInText(fullText);
                            const payload  = newCount !== prevCount
                                ? { chunk: content, filesFound: newCount }
                                : { chunk: content };
                            prevCount = newCount;
                            controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
                        }
                        if (chunk?.done) break;
                    }

                    // Log raw output for debugging
                    console.log(`\n📝 AI raw output (${fullText.length} chars, first 800):\n${fullText.slice(0, 800)}\n---`);

                    // Parse with universal parser
                    const parsedData    = parseAIOutput(fullText);
                    const frontendCount = Object.keys(parsedData.frontend).length;
                    const backendCount  = Object.keys(parsedData.backend).length;

                    if (frontendCount === 0) {
                        console.error('⚠️ All parsers failed. Full output:\n', fullText.slice(0, 1000));
                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({
                            error: `Generation failed — AI produced ${fullText.length} chars but no files were detected. Check server console.`,
                            raw: fullText.slice(0, 500),
                            done: true,
                        })}\n\n`));
                    } else {
                        console.log(`✅ Parsed: ${frontendCount} frontend + ${backendCount} backend files — "${parsedData.projectTitle}"`);
                        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ final: parsedData, done: true })}\n\n`));
                    }
                    controller.close();

                } catch (e) {
                    console.error('gen-ai-code stream error:', e);
                    controller.enqueue(encoder.encode(`data: ${JSON.stringify({ error: e.message || 'Generation failed', done: true })}\n\n`));
                    controller.close();
                }
            },
        });

        return new Response(stream, {
            headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive' },
        });

    } catch (e) {
        console.error('gen-ai-code route error:', e);
        return new Response(JSON.stringify({ error: e.message }), {
            status: 500, headers: { 'Content-Type': 'application/json' },
        });
    }
}
