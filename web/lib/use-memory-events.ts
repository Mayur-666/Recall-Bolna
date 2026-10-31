"use client";

import { useEffect, useRef } from "react";

import type { MemoryEvent } from "@/lib/types";

/**
 * Live updates for the signed-in user's memories (server-sent events): a conversation started
 * processing, finished with the memories it produced, or failed. EventSource reconnects on its own.
 */
export function useMemoryEvents(onEvent: (e: MemoryEvent) => void) {
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    const source = new EventSource("/api/v1/memories/events");
    source.onmessage = (msg) => {
      try {
        handler.current(JSON.parse(msg.data) as MemoryEvent);
      } catch {
        /* ignore malformed frames */
      }
    };
    return () => source.close();
  }, []);
}
