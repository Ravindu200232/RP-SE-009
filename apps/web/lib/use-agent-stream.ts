"use client";

import { useEffect, useRef, useState } from "react";
import type { AgentEvent } from "@agentforge/shared";
import { api } from "./api";

/** Subscribe to the live agent event stream (SSE) for a project. */
export function useAgentStream(projectId: string | null) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [latest, setLatest] = useState<AgentEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const srcRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!projectId) return;
    const es = new EventSource(api.eventStreamUrl(projectId));
    srcRef.current = es;
    es.addEventListener("agent", (e) => {
      try {
        const ev = JSON.parse((e as MessageEvent).data) as AgentEvent;
        setEvents((prev) => (prev.some((p) => p.id === ev.id) ? prev : [...prev, ev]));
        setLatest(ev);
      } catch {
        /* ignore malformed */
      }
    });
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    return () => {
      es.close();
      srcRef.current = null;
    };
  }, [projectId]);

  return { events, latest, connected };
}
