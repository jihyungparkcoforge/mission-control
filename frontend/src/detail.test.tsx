import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Report } from "./api";
import ReportDetail from "./ReportDetail";
import { CLEAN, findAlertWith, mockFetch, REPORT } from "./testFixtures";

beforeEach(() => localStorage.clear());
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

const NOW = 1_700_000_000;

function renderAt(r: Report, token = "", nowSec = NOW) {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(nowSec * 1000);
  const onChange = vi.fn();
  render(<ReportDetail r={r} token={token} onChange={onChange} />);
  vi.useRealTimers();
  return onChange;
}

describe("ReportDetail display", () => {
  it("shows brief-by deadline and time left", () => {
    renderAt({ ...CLEAN, brief_by_at: NOW + 125 });
    expect(screen.getByText("2:05")).toBeInTheDocument();                 // big countdown tile
    expect(screen.getByText(/· 15 min$/)).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();               // severity tile
  });

  it("marks an overdue briefing", () => {
    renderAt({ ...CLEAN, brief_by_at: NOW - 61 });
    expect(screen.getByText("−2 min")).toBeInTheDocument();
    expect(screen.getByText(/^overdue · was due/)).toBeInTheDocument();
  });

  it("hides the countdown once decided and shows who decided", () => {
    renderAt({ ...CLEAN, status: "rejected", decided_by: "FD Kim", decision_reason: "vague", brief_by_at: NOW + 60 });
    expect(screen.getByText("Done")).toBeInTheDocument();                 // no countdown once decided
    expect(screen.getByText(/by FD Kim/)).toBeInTheDocument();
    expect(screen.getByText(/“vague”/)).toBeInTheDocument();
  });

  it("shows pending state while processing", () => {
    renderAt({ ...CLEAN, status: "processing", brief_by_at: null, brief_by_minutes: null, briefing: null,
               subsystem: null, final_severity: null, model_severity: null, checks: null, trace: undefined,
               total_cost_usd: undefined });
    expect(screen.getByText("pending classification")).toBeInTheDocument();
    expect(screen.getByText("Drafting…")).toBeInTheDocument();
  });

  it("shows classification fallback, pipeline error, and no briefing", async () => {
    renderAt({ ...CLEAN, status: "error", classification_error: "Invalid model reply", subsystem: "unclassified",
               model_severity: null, final_severity: "high", briefing: null,
               error_message: "Briefing withheld: the report could not be fully verified." });
    expect(screen.getByText(/Classification failed — safe default used/)).toBeInTheDocument();
    expect(await findAlertWith("Briefing withheld")).toBeInTheDocument();
    expect(screen.getByText("No briefing.")).toBeInTheDocument();
  });

  it("explains a review failure and lists recommended actions and check findings", () => {
    renderAt({ ...CLEAN, status: "review_failed", review_rounds: 3, review_feedback: "invented a cause" });
    expect(screen.getByText(/after 3 rounds — it cannot be approved/)).toBeInTheDocument();
    expect(screen.getByText("Last feedback: invented a cause")).toBeInTheDocument();
    expect(screen.getByText("Recheck valve V-12")).toBeInTheDocument();
    expect(screen.getByText(/No time given/)).toBeInTheDocument();      // missing-details finding
    expect(screen.getByText("Panic tone: flagged")).toBeInTheDocument();
    expect(screen.getByText("Hidden instructions: clear")).toBeInTheDocument();
  });

  it("notes when a violation raised the model's severity", () => {
    renderAt(REPORT);
    expect(screen.getByText(/raised by violation/)).toBeInTheDocument();
    expect(screen.getByText("Wind 30 kn exceeds the 25 kn maximum")).toBeInTheDocument();
  });
});

describe("Flight Director actions", () => {
  it("shows nothing to do for an approved report", () => {
    renderAt({ ...CLEAN, status: "approved" }, "fd");
    expect(screen.queryByLabelText("Flight Director name")).not.toBeInTheDocument();
  });

  it("approves with the token and remembers the FD name", async () => {
    const fetchSpy = mockFetch(200, { ...CLEAN, status: "approved" });
    const onChange = renderAt(CLEAN, "fd");
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Flight Director name"), "FD Kim");
    await u.click(screen.getByRole("button", { name: "Approve briefing" }));
    const [url, init] = fetchSpy.mock.calls[0];
    expect(url).toBe("/api/reports/8/approve");
    expect((init!.headers as Record<string, string>)["X-FD-Token"]).toBe("fd");
    expect(JSON.parse(init!.body as string)).toEqual({ approver: "FD Kim", acknowledge_injection: false });
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ status: "approved" }));
    expect(localStorage.getItem("fd-name")).toBe("FD Kim");
  });

  it("rejects with a reason", async () => {
    const fetchSpy = mockFetch(200, { ...CLEAN, status: "rejected" });
    renderAt(CLEAN, "fd");
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Flight Director name"), "FD");
    await u.type(screen.getByPlaceholderText("reason (optional)"), "too vague");
    await u.click(screen.getByRole("button", { name: "Reject" }));
    expect(fetchSpy.mock.calls[0][0]).toBe("/api/reports/8/reject");
    expect(JSON.parse(fetchSpy.mock.calls[0][1]!.body as string)).toEqual({ approver: "FD", reason: "too vague" });
  });

  it("regenerates a review-failed briefing (no approve button)", async () => {
    const fetchSpy = mockFetch(200, { ...CLEAN, status: "processing" });
    renderAt({ ...CLEAN, status: "review_failed" }, "fd");
    expect(screen.queryByRole("button", { name: "Approve briefing" })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Regenerate briefing" }));
    expect(fetchSpy.mock.calls[0][0]).toBe("/api/reports/8/regenerate");
  });

  it("re-runs a report in error", async () => {
    const fetchSpy = mockFetch(200, { ...CLEAN, status: "processing" });
    renderAt({ ...CLEAN, status: "error" }, "fd");
    await userEvent.setup().click(screen.getByRole("button", { name: "Re-run pipeline" }));
    expect(fetchSpy.mock.calls[0][0]).toBe("/api/reports/8/rerun");
  });

  it("shows the server's refusal", async () => {
    mockFetch(403, { detail: "Invalid Flight Director token" });
    const onChange = renderAt({ ...CLEAN, status: "error" }, "wrong");
    await userEvent.setup().click(screen.getByRole("button", { name: "Re-run pipeline" }));
    expect(await findAlertWith("Invalid Flight Director token")).toBeInTheDocument();
    expect(onChange).not.toHaveBeenCalled();
  });

  it("sends the injection acknowledgement", async () => {
    const fetchSpy = mockFetch(200, { ...REPORT, status: "approved" });
    renderAt(REPORT, "fd");
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Flight Director name"), "FD");
    await u.click(screen.getByRole("checkbox"));
    await u.click(screen.getByRole("button", { name: "Approve briefing" }));
    expect(JSON.parse(fetchSpy.mock.calls[0][1]!.body as string).acknowledge_injection).toBe(true);
  });
});
