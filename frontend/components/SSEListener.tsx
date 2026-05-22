"use client";

import { useEffect, useCallback } from "react";
import { createSSEConnection } from "@/lib/api";
import type { SSEEvent } from "@/lib/types";

interface Props {
  onEvent: (event: SSEEvent) => void;
}

export function SSEListener({ onEvent }: Props) {
  const handleEvent = useCallback(
    (onEvent: (e: SSEEvent) => void) => (raw: MessageEvent) => {
      try {
        const event: SSEEvent = JSON.parse(raw.data);
        onEvent(event);
      } catch {
        // keep-alive pings arrive as empty strings
      }
    },
    []
  );

  useEffect(() => {
    const es = createSSEConnection();
    const handler = handleEvent(onEvent);
    es.onmessage = handler;
    es.onerror = () => {
      // reconnect is automatic with EventSource
    };
    return () => es.close();
  }, [onEvent, handleEvent]);

  return null;
}
