import { useEffect, useReducer } from "react";

import { initialStreamState, streamReducer } from "./state";
import type { ForecastSnapshot } from "./types";

const reconnectDelayMs = 1_000;

export function useSnapshotStream() {
  const [state, dispatch] = useReducer(streamReducer, initialStreamState);

  useEffect(() => {
    let socket: WebSocket | undefined;
    let reconnectTimer: number | undefined;
    let stopped = false;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${window.location.host}/ws/snapshots`);
      socket.onopen = () => dispatch({ type: "connected" });
      socket.onmessage = (message) => {
        const snapshot = JSON.parse(message.data as string) as ForecastSnapshot;
        dispatch({ type: "snapshot", snapshot });
      };
      socket.onclose = () => {
        if (stopped) return;
        dispatch({ type: "disconnected" });
        reconnectTimer = window.setTimeout(connect, reconnectDelayMs);
      };
    };

    fetch("/api/v1/snapshots?limit=1")
      .then((response) => (response.ok ? response.json() : []))
      .then((items: ForecastSnapshot[]) => {
        if (items.length) dispatch({ type: "snapshot", snapshot: items[0] });
      })
      .catch(() => undefined)
      .finally(connect);

    return () => {
      stopped = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);

  return state;
}
