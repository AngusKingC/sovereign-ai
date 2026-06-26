"use client";
import { useEffect, useRef, useState, useCallback } from "react";

interface UseSSEOptions {
  url: string;
  onMessage: (data: unknown) => void;
  enabled?: boolean;
  maxRetries?: number;
}

const MAX_BACKOFF = 30_000;
const BASE_BACKOFF = 1_000;
const DEFAULT_MAX_RETRIES = 10;

export function useSSE({
  url,
  onMessage,
  enabled = true,
  maxRetries = DEFAULT_MAX_RETRIES,
}: UseSSEOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const backoffRef = useRef(BASE_BACKOFF);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);

  // Keep ref current without re-running effect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connect = useCallback(() => {
    if (retryCountRef.current >= maxRetries) {
      setError(new Error(`SSE max retries (${maxRetries}) exceeded — stopping`));
      return;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const es = new EventSource(url, { withCredentials: true });
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
      backoffRef.current = BASE_BACKOFF;
      retryCountRef.current = 0;
    };

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessageRef.current(data);
      } catch (e) {
        setError(e instanceof Error ? e : new Error("Failed to parse SSE data"));
      }
    };

    es.onerror = () => {
      setIsConnected(false);
      es.close();

      retryCountRef.current += 1;
      if (retryCountRef.current >= maxRetries) {
        setError(new Error(`SSE max retries (${maxRetries}) exceeded — stopping`));
        return;
      }

      const delay = Math.min(backoffRef.current * 2, MAX_BACKOFF);
      backoffRef.current = delay;

      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = setTimeout(() => connect(), delay);
    };
  }, [url, maxRetries]);

  useEffect(() => {
    if (!enabled) return;

    connect();

    return () => {
      if (eventSourceRef.current) eventSourceRef.current.close();
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
    };
  }, [connect, enabled]);

  return { isConnected, error };
}
