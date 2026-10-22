import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fixtureSnapshot } from "./fixtures";
import { acceptSnapshot, initialStreamState, streamReducer } from "./state";
import { StatusBar } from "./components/StatusBar";
import type { ForecastSnapshot } from "./types";

describe("snapshot stream state", () => {
  it("rejects older snapshots while preserving frozen axes", () => {
    const current = fixtureSnapshot;
    const older = { ...fixtureSnapshot, forecast_id: "BTC-99", origin_time: "2026-10-21T07:59:59Z" };
    expect(acceptSnapshot(current, older)).toBe(current);
    expect(acceptSnapshot(undefined, current)?.intervals).toEqual(fixtureSnapshot.intervals);
  });

  it("tracks reconnect attempts and successful recovery", () => {
    const disconnected = streamReducer(initialStreamState, { type: "disconnected" });
    expect(disconnected.connection).toBe("RECONNECTING");
    expect(disconnected.reconnectAttempts).toBe(1);
    const connected = streamReducer(disconnected, { type: "connected" });
    expect(connected.connection).toBe("CONNECTED");
    expect(connected.reconnectAttempts).toBe(0);
  });
});

describe("status visibility", () => {
  it("shows mode, age, model and degraded states without hiding flags", () => {
    const stale: ForecastSnapshot = {
      ...fixtureSnapshot,
      source: { ...fixtureSnapshot.source, mode: "DEGRADED" as const, stale: true },
      quality_flags: ["STALE", "MARKET_CLOSED"],
    };
    render(<StatusBar snapshot={stale} connection="CONNECTED" />);
    expect(screen.getByText("DEGRADED")).toBeVisible();
    expect(screen.getByText("STALE")).toBeVisible();
    expect(screen.getByText("MARKET_CLOSED")).toBeVisible();
    expect(screen.getByText(/1.25s/)).toBeVisible();
    expect(screen.getByText(/bootstrap-v1/)).toBeVisible();
  });
});
