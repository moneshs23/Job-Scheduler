import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

interface RealtimeEvent {
  type: string;
  data: Record<string, unknown>;
}

const JOB_EVENT_TYPES = new Set([
  "job.started",
  "job.completed",
  "job.retry",
  "job.dead_letter",
  "job.queued",
]);

export function useRealtime() {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<RealtimeEvent | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/api/v1/ws`;
    let cancelled = false;
    let socket: WebSocket;

    const connect = () => {
      socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) setTimeout(connect, 2000);
      };
      socket.onmessage = (event) => {
        try {
          const parsed: RealtimeEvent = JSON.parse(event.data);
          setLastEvent(parsed);
          if (JOB_EVENT_TYPES.has(parsed.type)) {
            queryClient.invalidateQueries({ queryKey: ["jobs"] });
            queryClient.invalidateQueries({ queryKey: ["queue-metrics"] });
            queryClient.invalidateQueries({ queryKey: ["dashboard-overview"] });
            queryClient.invalidateQueries({ queryKey: ["dead-letters"] });
          }
        } catch {
          /* ignore malformed frames */
        }
      };
    };

    connect();
    return () => {
      cancelled = true;
      socketRef.current?.close();
    };
  }, [queryClient]);

  return { connected, lastEvent };
}
