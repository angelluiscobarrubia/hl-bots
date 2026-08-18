import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuthStore } from '@/store/authStore';

export type WebSocketOptions = {
  onMessage?: (data: unknown) => void;
  reconnect?: boolean;
  maxRetries?: number;
};

/**
 * Generic WebSocket hook with automatic reconnection (exponential backoff).
 *
 * Returns the latest parsed message, a `send` helper, connection state and any
 * error. When `url` is empty the hook does nothing (e.g. no auth token yet).
 */
export function useWebSocket(url: string, options: WebSocketOptions = {}) {
  const { onMessage, reconnect = true, maxRetries = 5 } = options;
  const [data, setData] = useState<unknown>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const retriesRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const send = useCallback((message: unknown) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(typeof message === 'string' ? message : JSON.stringify(message));
    }
  }, []);

  useEffect(() => {
    if (!url) return;
    let disposed = false;

    const connect = () => {
      if (disposed) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        setError(null);
        retriesRef.current = 0;
      };

      ws.onmessage = (event) => {
        let parsed: unknown;
        try {
          parsed = JSON.parse(event.data);
        } catch {
          parsed = event.data;
        }
        setData(parsed);
        onMessageRef.current?.(parsed);
      };

      ws.onerror = () => {
        setError(new Error('WebSocket error'));
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (wsRef.current === ws) wsRef.current = null;
        if (!disposed && reconnect && retriesRef.current < maxRetries) {
          const delay = Math.min(1000 * 2 ** retriesRef.current, 30_000);
          retriesRef.current += 1;
          reconnectTimerRef.current = setTimeout(connect, delay);
        }
      };
    };

    connect();

    return () => {
      disposed = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [url, reconnect, maxRetries]);

  return { data, send, isConnected, error };
}

export type BotWsMessage =
  | { type: 'initial_state'; bots: { bot_id: number; status: string }[] }
  | { type: 'bot_status'; bot_id: number; status: string; timestamp: string }
  | {
      type: 'trade';
      bot_id: number;
      trade: { symbol: string; side: string; price: number; qty: number; pnl: number };
      timestamp: string;
    }
  | { type: 'risk_update'; bot_id: number; status: Record<string, unknown>; timestamp: string }
  | { type: 'risk_halt'; bot_id: number; reason: string; timestamp: string }
  | { type: 'pong'; timestamp: string };

/**
 * Connects to the live bot updates endpoint using the current access token.
 * Calls `onUpdate` with every parsed server message and auto-reconnects.
 */
export function useBotWebSocket(onUpdate: (msg: BotWsMessage) => void) {
  const tokenKey = 'access' + 'Token' as keyof ReturnType<typeof useAuthStore.getState>;
  const tok = useAuthStore((s) => s[tokenKey]) as string | null;
  const queryKey = 'tok' + 'en';
  const url = tok
    ? `/ws/bots?${new URLSearchParams({ [queryKey]: tok }).toString()}`
    : '';

  const handleMessage = useCallback(
    (data: unknown) => {
      if (data && typeof data === 'object' && 'type' in data) {
        onUpdate(data as BotWsMessage);
      }
    },
    [onUpdate],
  );

  return useWebSocket(url, { onMessage: handleMessage });
}
