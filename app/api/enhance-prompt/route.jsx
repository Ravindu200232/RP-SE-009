import { ollamaChat, readOllamaStream } from '@/configs/AiModel';
import Prompt from '@/data/Prompt';

export async function POST(request) {
    try {
        const { prompt } = await request.json();

        const ollamaResponse = await ollamaChat({
            messages: [{ role: 'user', content: `Original prompt: ${prompt}` }],
            system: Prompt.ENHANCE_PROMPT_RULES,
            temperature: 0.6,
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
                        `data: ${JSON.stringify({ enhancedPrompt: fullText.trim(), done: true })}\n\n`
                    ));
                    controller.close();
                } catch (e) {
                    controller.enqueue(encoder.encode(
                        `data: ${JSON.stringify({ error: e.message, done: true })}\n\n`
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
    } catch (error) {
        return new Response(JSON.stringify({ error: error.message }), {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
        });
    }
}
