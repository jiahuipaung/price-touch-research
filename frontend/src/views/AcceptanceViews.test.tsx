import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DataQuality } from "./DataQuality";
import { Methodology } from "./Methodology";
import { Research } from "./Research";

describe("acceptance views", () => {
  it("shows calibration metrics, filters, regimes and coverage disclosure", () => {
    render(<Research />);
    expect(screen.getByText("Brier score")).toBeVisible();
    expect(screen.getByText("Reliability diagram")).toBeVisible();
    expect(screen.getByLabelText("Regime filter")).toBeVisible();
    expect(screen.getByText(/LOW.*MEDIUM.*HIGH.*SHOCK/)).toBeVisible();
    expect(screen.getByText(/COMPACT_DEMO_NOT_FULL_CYCLE/)).toBeVisible();
    expect(screen.getByText(/checksum/i)).toBeVisible();
  });

  it("shows quality counters and a fault timeline", () => {
    render(<DataQuality />);
    expect(screen.getByText("Duplicate events")).toBeVisible();
    expect(screen.getByText("Too-late events")).toBeVisible();
    expect(screen.getByText("Gap / reconnect timeline")).toBeVisible();
  });

  it("states the exact event, half-open boundaries, assumptions and limits", () => {
    render(<Methodology />);
    expect(screen.getByText(/任一时刻.*成交价.*价格区间/)).toBeVisible();
    expect(screen.getByText(/\[lower, upper\)/)).toBeVisible();
    expect(screen.getByText("Assumptions")).toBeVisible();
    expect(screen.getByText("Limitations")).toBeVisible();
  });
});
