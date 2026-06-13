"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ClientAction, PhaseStatePayload } from "./protocol";
import { wsUrl } from "./api";

export type ConnStatus = "connecting" | "open" | "reconnecting" | "closed";

interface GameChannel {
  state: PhaseStatePayload | null;
  status: ConnStatus;
  send: (action: ClientAction) => void;
}

/**
 * Owns the WebSocket for one room. Reconnect is automatic with backoff; on
 * reconnect the server replays the current phase_state from its checkpoint,
 * so the UI needs no special "resume" handling beyond rendering what arrives.
 */
export function useGame(room: string, token: string | null): GameChannel {
  const [state, setState] = useState<PhaseStatePayload | null>(null);
  const [status, setStatus] = useState<ConnStatus>("connecting");
  const wsRef = useRef<WebSocket | null>(null);
  const retryRef = useRef(0);
  const closedRef = useRef(false);

  useEffect(() => {
    if (!token) return;
    closedRef.current = false;

    function connect() {
      setStatus(retryRef.current === 0 ? "connecting" : "reconnecting");
      const ws = new WebSocket(wsUrl(room, token!));
      wsRef.current = ws;

      ws.onopen = () => {
        retryRef.current = 0;
        setStatus("open");
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as { type: string; payload: unknown };
        if (msg.type === "phase_state") {
          setState(msg.payload as PhaseStatePayload);
        }
      };
      ws.onclose = () => {
        if (closedRef.current) return;
        const delay = Math.min(1000 * 2 ** retryRef.current, 8000);
        retryRef.current += 1;
        setStatus("reconnecting");
        setTimeout(connect, delay);
      };
      ws.onerror = () => ws.close();
    }

    connect();
    return () => {
      closedRef.current = true;
      wsRef.current?.close();
      setStatus("closed");
    };
  }, [room, token]);

  const send = useCallback((action: ClientAction) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "action", payload: action }));
    }
  }, []);

  return { state, status, send };
}
