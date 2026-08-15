import { useEffect, useRef, useCallback, useState } from 'react';
import { useAuth } from '../features/auth/hooks/useAuth';

type WsEvent = { event: string; data: any };
type EventHandler = (data: any) => void;

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:3001';

export function useWebSocket() {
  const { token } = useAuth() as any;
  const ws = useRef<WebSocket | null>(null);
  const handlers = useRef<Map<string, Set<EventHandler>>>(new Map());
  const [connected, setConnected] = useState(false);

  const subscribe = useCallback((event: string, handler: EventHandler) => {
    if (!handlers.current.has(event)) handlers.current.set(event, new Set());
    handlers.current.get(event)!.add(handler);
    return () => handlers.current.get(event)?.delete(handler);
  }, []);

  const connect = useCallback(() => {
    if (!token || ws.current?.readyState === WebSocket.OPEN) return;
    const sock = new WebSocket(`${WS_BASE}?token=${token}`);

    sock.onopen = () => {
      setConnected(true);
      sock.send(JSON.stringify({ type: 'ping' }));
    };

    sock.onmessage = (e) => {
      try {
        const msg: WsEvent = JSON.parse(e.data);
        handlers.current.get(msg.event)?.forEach(h => h(msg.data));
        handlers.current.get('*')?.forEach(h => h(msg));
      } catch {}
    };

    sock.onclose = () => {
      setConnected(false);
      // Reconnect after 3s
      setTimeout(connect, 3000);
    };

    sock.onerror = () => sock.close();
    ws.current = sock;
  }, [token]);

  useEffect(() => {
    connect();
    return () => {
      ws.current?.close();
    };
  }, [connect]);

  return { connected, subscribe };
}
