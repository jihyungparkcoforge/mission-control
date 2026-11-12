import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, usd } from "./api";
import TraceCard, { stepLabel } from "./TraceCard";
import { mockFetch, step } from "./testFixtures";

afterEach(() => vi.restoreAllMocks());

describe("TraceCard", () => {
  it("labels draft/review rounds and unknown steps", () => {
    expect(stepLabel("draft_2")).toBe("Draft briefing — round 2");
    expect(stepLabel("review_3")).toBe("Review draft — round 3");
    expect(stepLabel("verdict_check_2")).toBe("Verdict check (code) — round 2");
    expect(stepLabel("brief_by")).toBe("Brief-by time");
    expect(stepLabel("something_new")).toBe("something_new");
  });

  it("shows a running step without duration", () => {
    render(<TraceCard step={step(1, "check_tone", { status: "running", ended_at: null })} />);
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.queryByText(/ ms$/)).not.toBeInTheDocument();
  });

  it("shows structured output, string output, duration and cost", () => {
    const { rerender } = render(
      <TraceCard step={step(1, "classify", { output: { subsystem: "propulsion" }, started_at: 1, ended_at: 1.25 })} />);
    expect(screen.getByText("250 ms")).toBeInTheDocument();
    expect(screen.getByText("$0.00200")).toBeInTheDocument();
    expect(screen.getByText("propulsion")).toBeInTheDocument();         // rendered as UI, not JSON
    expect(screen.queryByText(/"subsystem"/)).not.toBeInTheDocument();
    rerender(<TraceCard step={step(1, "classify", { status: "error", output: "not json", error: "Invalid model reply" })} />);
    expect(screen.getByText("Show rejected model reply")).toBeInTheDocument();   // raw only behind a disclosure
    expect(screen.getByText("not json")).toBeInTheDocument();
    expect(screen.getByText("Error")).toBeInTheDocument();
  });
});

describe("usd", () => {
  it("formats costs", () => {
    expect(usd(undefined)).toBe("-");
    expect(usd("0")).toBe("$0.0000");
    expect(usd("0.00006")).toBe("$0.00006");
    expect(usd("0.0123")).toBe("$0.0123");
  });
});

describe("api client", () => {
  it("sends the FD token only on FD calls", async () => {
    const f = mockFetch(200, {});
    await api.get(1);
    expect((f.mock.calls[0][1]!.headers as Record<string, string>)["X-FD-Token"]).toBeUndefined();
    await api.regenerate(1, "tok");
    expect(f.mock.calls[1][0]).toBe("/api/reports/1/regenerate");
    expect((f.mock.calls[1][1]!.headers as Record<string, string>)["X-FD-Token"]).toBe("tok");
  });

  it("uses message, then detail, then status code for errors", async () => {
    mockFetch(422, { message: "Invalid input - name" });
    await expect(api.list()).rejects.toThrow("Invalid input - name");
    vi.restoreAllMocks();
    mockFetch(409, { detail: "Only a pending briefing can be approved" });
    await expect(api.approve(1, "t", "FD", false)).rejects.toThrow("Only a pending briefing");
    vi.restoreAllMocks();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("<html>bad gateway</html>", { status: 502 }));
    const err = await api.config().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toBe("Request failed (502)");
  });
});

describe("fixed-size status slots", () => {
  it("trace status keeps the same width for OK, Error and Running", () => {
    const widths = (["ok", "error", "running"] as const).map((s) => {
      const { container, unmount } = render(<TraceCard step={step(1, "classify", { status: s })} />);
      const w = (container.querySelector(".status-mark") as HTMLElement).style.width;
      unmount();
      return w;
    });
    expect(new Set(widths)).toEqual(new Set(["78px"]));
  });

  it("status marks never render as filled pills", () => {
    render(<TraceCard step={step(1, "classify", { status: "error" })} />);
    expect(document.querySelector(".astryx-badge")).toBeNull();
  });
});
