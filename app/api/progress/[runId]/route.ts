import { NextRequest } from "next/server";
import { subscribeToRun } from "@/server/event-bus";
import type { ProgressEvent } from "@/types";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;

  const encoder = new TextEncoder();
  let unsub: (() => void) | null = null;

  const stream = new ReadableStream({
    start(controller) {
      const send = (event: ProgressEvent) => {
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
          if (event.type === "complete" || event.type === "error") {
            if (unsub) unsub();
            controller.close();
          }
        } catch {
          // controller already closed
        }
      };

      unsub = subscribeToRun(runId, send);

      // Send initial heartbeat
      controller.enqueue(
        encoder.encode(
          `data: ${JSON.stringify({ type: "log", message: "SSE connected", timestamp: new Date().toISOString() })}\n\n`
        )
      );
    },
    cancel() {
      if (unsub) unsub();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
