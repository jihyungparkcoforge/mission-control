import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import FileReportForm from "./FileReportForm";
import ReportDetail from "./ReportDetail";
import { findAlertWith, mockFetch, REPORT } from "./testFixtures";

afterEach(() => vi.restoreAllMocks());


describe("FileReportForm", () => {
  it("sends all six fields with numeric readings", async () => {
    const fetchSpy = mockFetch(201, { id: 1 });
    const onFiled = vi.fn();
    render(<FileReportForm onFiled={onFiled} />);
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Name"), "Ana Ortiz");
    await u.type(screen.getByLabelText("Station"), "PROP-2");
    await u.type(screen.getByLabelText("Wind (kn)"), "25");
    await u.type(screen.getByLabelText("Temp (°C)"), "4");
    await u.type(screen.getByLabelText("Fuel (%)"), "98.5");
    await u.type(screen.getByLabelText("Note"), "Valve V-12 slow to close");
    await u.click(screen.getByRole("button", { name: "File report" }));

    expect(fetchSpy).toHaveBeenCalledOnce();
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/reports");
    expect(JSON.parse(init!.body as string)).toEqual({
      name: "Ana Ortiz", station: "PROP-2", wind_knots: 25, temp_c: 4, fuel_pct: 98.5,
      note: "Valve V-12 slow to close",
    });
    expect(onFiled).toHaveBeenCalled();
  });

  it("shows the server's clear rejection message", async () => {
    mockFetch(422, { message: "Invalid input - wind_knots: Input should be a valid number" });
    render(<FileReportForm onFiled={vi.fn()} />);
    await userEvent.setup().click(screen.getByRole("button", { name: "File report" }));
    expect(await findAlertWith("wind_knots: Input should be a valid number")).toBeInTheDocument();
  });
});

describe("ReportDetail", () => {
  it("renders one trace card per step with its tokens", async () => {
    render(<ReportDetail r={REPORT} token="" onChange={vi.fn()} />);
    expect(screen.queryByTestId("trace-card")).not.toBeInTheDocument();   // trace lives in its own tab
    await userEvent.setup().click(screen.getByRole("tab", { name: /Trace/ }));
    const cards = screen.getAllByTestId("trace-card");
    expect(cards).toHaveLength(REPORT.trace!.length);
    const classify = cards[1];
    expect(within(classify).getByText("Classification")).toBeInTheDocument();
    expect(within(classify).getByTestId("tokens")).toHaveTextContent("102 in / 22 out");
    expect(within(cards[0]).getByText("plain code")).toBeInTheDocument();
    expect(within(cards[6]).getByText("Invalid model reply")).toBeInTheDocument();
    expect(screen.getByTestId("report-cost")).toHaveTextContent("$0.0120");
  });

  it("shows the code verdict and the hidden-instruction warning", () => {
    render(<ReportDetail r={REPORT} token="" onChange={vi.fn()} />);
    expect(screen.getAllByText("NO-GO")[0]).toBeInTheDocument();
    expect(screen.getByText(/Hidden instructions detected/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve briefing" })).not.toBeInTheDocument(); // no FD token
  });

  it("requires acknowledgement before approving a flagged briefing", async () => {
    render(<ReportDetail r={REPORT} token="fd" onChange={vi.fn()} />);
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Flight Director name"), "FD Kim");
    const approve = screen.getByRole("button", { name: "Approve briefing" });
    expect(approve).toHaveAttribute("aria-disabled", "true");   // Astryx uses aria-disabled
    await u.click(screen.getByRole("checkbox"));
    expect(approve).not.toHaveAttribute("aria-disabled");
  });
});
