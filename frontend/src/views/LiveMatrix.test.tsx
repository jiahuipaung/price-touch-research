import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { fixtureSnapshot } from "../fixtures";
import { LiveMatrix } from "./LiveMatrix";

describe("LiveMatrix", () => {
  it("renders fixed dimensions and inspects all probability variants and bounds", () => {
    render(<LiveMatrix snapshot={fixtureSnapshot} />);
    expect(screen.getAllByTestId("matrix-cell")).toHaveLength(6);
    fireEvent.click(screen.getAllByTestId("matrix-cell")[0]);
    expect(screen.getAllByText(/6680000.*6690000/)).toHaveLength(2);
    expect(screen.getByText(/100000000000.*105000000000/)).toBeVisible();
    expect(screen.getByText("10.00%")).toBeVisible();
    expect(screen.getByText("11.00%")).toBeVisible();
    expect(screen.getByText("9.00%")).toBeVisible();
    expect(screen.getByText("UNCALIBRATED")).toBeVisible();
  });

  it("validates an odd interval count and exposes asset selection", () => {
    render(<LiveMatrix snapshot={fixtureSnapshot} />);
    expect(screen.getByLabelText("资产")).toHaveValue("BTC");
    fireEvent.change(screen.getByLabelText("区间数量"), { target: { value: "4" } });
    expect(screen.getByRole("alert")).toHaveTextContent("奇数");
  });
});
