import { EventEmitter } from "events";
import type { ProgressEvent } from "@/types";

interface GlobalWithBus {
  _agent3EventBus?: EventEmitter;
}

const g = global as GlobalWithBus;
if (!g._agent3EventBus) {
  g._agent3EventBus = new EventEmitter();
  g._agent3EventBus.setMaxListeners(200);
}

export const eventBus = g._agent3EventBus!;

export function emitProgress(runId: string, event: ProgressEvent): void {
  eventBus.emit(`run:${runId}`, event);
}

export function subscribeToRun(
  runId: string,
  callback: (event: ProgressEvent) => void
): () => void {
  eventBus.on(`run:${runId}`, callback);
  return () => eventBus.off(`run:${runId}`, callback);
}

export function buildEvent(
  type: ProgressEvent["type"],
  partial: Omit<ProgressEvent, "type" | "timestamp">
): ProgressEvent {
  return { type, timestamp: new Date().toISOString(), ...partial };
}
