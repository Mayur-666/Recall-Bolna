"use client";

import { useEffect, useState } from "react";

import type { CallEvent } from "@/lib/types";

/** Backend-observed events for one call (history replay + live), via server-sent events. */
export function useCallEvents(callSessionId: string | null) {
  const [events, setEvents] = useState<CallEvent[]>([]);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    setEvents([]);
    if (!callSessionId) return;
    const source = new EventSource(`/api/v1/calls/${callSessionId}/events`);
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // EventSource reconnects on its own
    source.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as CallEvent;
        // History is replayed on reconnect; de-duplicate by type + tool call id.
        setEvents((prev) => {
          const key = (e: CallEvent) => `${e.type}:${"tool_call_id" in e ? e.tool_call_id : ""}`;
          return prev.some((p) => key(p) === key(event)) ? prev : [...prev, event];
        });
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => source.close();
  }, [callSessionId]);

  return { events, connected };
}
