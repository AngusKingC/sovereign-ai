"use client";
import { useEffect, useRef, useState, useCallback } from "react";

interface UseWebSocketOptions {
  onMessage?: (data: string) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (err: Event) => void;
  enabled?: boolean;
  maxRetries?: number;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const { enabled = true, maxRetries = 10 } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const retryCountRef = useRef(0);
  const reconnectTimerRef = useRef<NodeJS.Timeout | undefined>(undefined);

  // Rev2 H3 fix — store callbacks in refs to avoid reconnect storms.
  // Inline arrow functions passed as onMessage/onOpen/etc would otherwise
  // change identity on every render, causing the useEffect to clean up
  // and reconnect the WebSocket on every render. Refs stabilize identity.
  const onMessageRef = useRef(options.onMessage);
  const onOpenRef = useRef(options.onOpen);
  const onCloseRef = useRef(options.onClose);
  const onErrorRef = useRef(options.onError);

  useEffect(() => {
    onMessageRef.current = options.onMessage;
    onOpenRef.current = options.onOpen;
    onCloseRef.current = options.onClose;
    onErrorRef.current = options.onError;
  }); // Update refs every render, but don't trigger WebSocket reconnect

  const send = useCallback((data: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;

    const connect = () => {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        retryCountRef.current = 0;
        onOpenRef.current?.();
      };

      ws.onmessage = (event) => {
        onMessageRef.current?.(event.data);
      };

      ws.onerror = (event) => {
        setError(new Error("WebSocket error"));
        onErrorRef.current?.(event);
      };

      ws.onclose = () => {
        setIsConnected(false);
        onCloseRef.current?.();
        if (retryCountRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retryCountRef.current), 30000);
          retryCountRef.current++;
          reconnectTimerRef.current = setTimeout(connect, delay);
        }
      };
    };

    connect();

    return () => {
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
    };
  }, [url, enabled, maxRetries]); // Rev2 H3 fix — callbacks omitted from deps (stored in refs)

  return { isConnected, error, send };
}
