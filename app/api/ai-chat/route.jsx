import { ollamaChat, readOllamaStream } from '@/configs/AiModel';
import Prompt from '@/data/Prompt';

export async function POST(req) {
    const { prompt } = await req.json();

    try {
        const ollamaResponse = await ollamaChat({
            messages: [{ role: 'user', content: prompt }],
            system: Prompt.CHAT_PROMPT,
            temperature: 0.7,
            stream: true,
        });

        const encoder = new TextEncoder();
        const stream = new ReadableStream({
            async start(controller) {
                try {
                    let fullText = '';
                    for await (const chunk of readOllamaStream(ollamaResponse)) {
                        const content = chunk?.message?.content ?? '';
                        if (content) {
                            fullText += content;
                            controller.enqueue(encoder.encode(
                                `data: ${JSON.stringify({ chunk: content })}\n\n`
                            ));
                        }
                        if (chunk?.done) break;
                    }
                    controller.enqueue(encoder.encode(
                        `data: ${JSON.stringify({ result: fullText, done: true })}\n\n`
                    ));
                    controller.close();
                } catch (e) {
                    controller.enqueue(encoder.encode(
                        `data: ${JSON.stringify({ error: e.message || 'AI chat failed', done: true })}\n\n`
                    ));
                    controller.close();
                }
            },
        });

        return new Response(stream, {
            headers: {
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
            },
        });
    } catch (e) {
        return new Response(JSON.stringify({ error: e.message || 'AI chat failed' }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
        });
    }
}
