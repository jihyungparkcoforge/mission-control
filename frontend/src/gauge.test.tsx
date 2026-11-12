import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Report, Violation } from "./api";
import { domainFor, GaugeTooltip, limitText, overshoot, ticksFor } from "./LimitGauge";
import ReportDetail from "./ReportDetail";
import { CLEAN, LIMITS } from "./testFixtures";

const v = (field: string, message: string): Violation => ({ field, value: 0, limit: "", message });

function renderReadings(wind: number, temp: number, fuel: number, violations: Violation[]) {
  const r: Report = { ...CLEAN, wind_knots: wind, temp_c: temp, fuel_pct: fuel, violations,
                      verdict: violations.length ? "no_go" : "go" };
  render(<ReportDetail r={r} limits={LIMITS} token="" onChange={vi.fn()} />);
}

const state = (field: string) => screen.getByTestId(`gauge-${field}`).getAttribute("data-state");

describe("Launch-limit gauges", () => {
  it("puts readings exactly on each limit inside the band", () => {
    renderReadings(25, 4, 98, []);
    expect(state("wind_knots")).toBe("in");
    expect(state("temp_c")).toBe("in");
    expect(state("fuel_pct")).toBe("in");
    expect(screen.getAllByText("In limits")).toHaveLength(3);
    // the reading is a stock Recharts scatter point
    const wind = screen.getByTestId("gauge-wind_knots");
    expect(wind.querySelector(".recharts-scatter-symbol")).not.toBeNull();
  });

  it("marks readings just past the limit as out, with the overshoot as text", () => {
    renderReadings(25.1, 3.9, 100.1, [
      v("wind_knots", "Wind 25.1 kn exceeds the 25 kn maximum"),
      v("temp_c", "Temperature 3.9 C is below the 4 C minimum"),
      v("fuel_pct", "Fuel 100.1% is outside the 98-100% range"),
    ]);
    for (const f of ["wind_knots", "temp_c", "fuel_pct"]) expect(state(f)).toBe("out");
    const wind = screen.getByTestId("gauge-wind_knots");
    expect(within(wind).getByText("Out of limits")).toBeInTheDocument();
    expect(within(wind).getByText(/\+0\.1 kn over/)).toBeInTheDocument();
    expect(within(screen.getByTestId("gauge-temp_c")).getByText(/−0\.1 °C under/)).toBeInTheDocument();
  });

  it("takes in/out from the server's violations, never re-judging in the browser", () => {
    // value is over the drawn band but the server reported no violation -> shown as in
    renderReadings(30, 10, 99, []);
    expect(state("wind_knots")).toBe("in");
  });

  it("describes each track for screen readers and shows limit text", () => {
    renderReadings(31, 15, 99, [v("wind_knots", "Wind 31 kn exceeds the 25 kn maximum")]);
    expect(screen.getByRole("img", { name: /Wind 31 kn, outside limit ≤ 25 kn/ })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Fuel 99 %, within limit 98–100 %/ })).toBeInTheDocument();
    expect(screen.getByText("limit ≥ 4 °C")).toBeInTheDocument();
  });

  it("falls back to a text list when limits are not loaded", () => {
    const r = { ...CLEAN, violations: [v("wind_knots", "Wind 40 kn exceeds the 25 kn maximum")] };
    render(<ReportDetail r={r} token="" onChange={vi.fn()} />);
    expect(screen.queryByTestId("gauge-wind_knots")).not.toBeInTheDocument();
    expect(screen.getByText("Wind 40 kn exceeds the 25 kn maximum")).toBeInTheDocument();
  });
});

describe("gauge helpers", () => {
  it("widens the axis to keep extreme readings on screen", () => {
    expect(domainFor("wind_knots", 10)).toEqual([0, 40]);
    const [, hi] = domainFor("wind_knots", 120);
    expect(hi).toBeGreaterThan(120);
    const [lo] = domainFor("temp_c", -40);
    expect(lo).toBeLessThan(-40);
  });

  it("puts axis ticks on round steps", () => {
    expect(ticksFor([0, 40])).toEqual([0, 10, 20, 30, 40]);
    expect(ticksFor([94, 102])).toEqual([94, 96, 98, 100, 102]);
  });

  it("formats limits and overshoot", () => {
    expect(limitText(LIMITS.wind_knots)).toBe("≤ 25 kn");
    expect(limitText(LIMITS.temp_c)).toBe("≥ 4 °C");
    expect(limitText(LIMITS.fuel_pct)).toBe("98–100 %");
    expect(overshoot(LIMITS.fuel_pct, 97)).toBe(-1);
    expect(overshoot(LIMITS.fuel_pct, 99)).toBe(0);
    expect(overshoot(LIMITS.wind_knots, 30)).toBe(5);
  });
});

describe("GaugeTooltip", () => {
  it("shows reading, limit and overshoot on hover only", () => {
    const { rerender, container } = render(<GaugeTooltip active={false} limit={LIMITS.wind_knots} value={31} out />);
    expect(container).toBeEmptyDOMElement();
    rerender(<GaugeTooltip active limit={LIMITS.wind_knots} value={31} out />);
    expect(screen.getByText("Wind: 31 kn")).toBeInTheDocument();
    expect(screen.getByText("+6 kn over")).toBeInTheDocument();
    rerender(<GaugeTooltip active limit={LIMITS.temp_c} value={3} out />);
    expect(screen.getByText("−1 °C under")).toBeInTheDocument();
    rerender(<GaugeTooltip active limit={LIMITS.fuel_pct} value={99} out={false} />);
    expect(screen.getByText("within limit")).toBeInTheDocument();
  });
});
