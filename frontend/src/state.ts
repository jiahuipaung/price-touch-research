import type { ForecastSnapshot } from "./types";

export type ConnectionState = "CONNECTING" | "CONNECTED" | "RECONNECTING";

export interface StreamState {
  connection: ConnectionState;
  reconnectAttempts: number;
  snapshot?: ForecastSnapshot;
}

export type StreamAction =
  | { type: "connected" }
  | { type: "disconnected" }
  | { type: "snapshot"; snapshot: ForecastSnapshot };

export const initialStreamState: StreamState = {
  connection: "CONNECTING",
  reconnectAttempts: 0,
};

export function acceptSnapshot(
  current: ForecastSnapshot | undefined,
  incoming: ForecastSnapshot,
): ForecastSnapshot | undefined {
  if (!current) return incoming;
  const currentOrigin = Date.parse(current.origin_time);
  const incomingOrigin = Date.parse(incoming.origin_time);
  return incomingOrigin > currentOrigin ? incoming : current;
}

export function streamReducer(state: StreamState, action: StreamAction): StreamState {
  if (action.type === "connected") {
    return { ...state, connection: "CONNECTED", reconnectAttempts: 0 };
  }
  if (action.type === "disconnected") {
    return {
      ...state,
      connection: "RECONNECTING",
      reconnectAttempts: state.reconnectAttempts + 1,
    };
  }
  return { ...state, snapshot: acceptSnapshot(state.snapshot, action.snapshot) };
}
