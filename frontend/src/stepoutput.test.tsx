import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import StepOutput from "./StepOutput";
import { step } from "./testFixtures";

const show = (name: string, output: unknown) => render(<StepOutput step={step(1, name, { output })} />);

describe("StepOutput renders each step as UI, never raw JSON", () => {
  it("limits check", () => {
    show("limits_check", { verdict: "no_go", violations: [{ field: "wind_knots", value: 31, limit: "<= 25",
      message: "Wind 31 kn exceeds the 25 kn maximum" }] });
    expect(screen.getByText("NO-GO")).toBeInTheDocument();
    expect(screen.getByText("1 violation")).toBeInTheDocument();
    expect(screen.getByText("Wind 31 kn exceeds the 25 kn maximum")).toBeInTheDocument();
  });

  it("limits check with no violations", () => {
    show("limits_check", { verdict: "go", violations: [] });
    expect(screen.getByText("GO")).toBeInTheDocument();
    expect(screen.getByText("0 violations")).toBeInTheDocument();
  });

  it("brief-by, including fallback and violation raise", () => {
    show("brief_by", { model_severity: "low", has_violation: true, final_severity: "high", brief_by_minutes: 5 });
    expect(screen.getByText("high · raised by violation")).toBeInTheDocument();
    expect(screen.getByText("5 min")).toBeInTheDocument();
  });

  it("brief-by after a classification fallback", () => {
    show("brief_by", { model_severity: null, has_violation: false, final_severity: "high", brief_by_minutes: 5 });
    expect(screen.getByText("— (fallback)")).toBeInTheDocument();
  });

  it("classification", () => {
    show("classify", { subsystem: "communications", severity: "medium", rationale: "telemetry dropout" });
    expect(screen.getByText("communications")).toBeInTheDocument();
    expect(screen.getByText("telemetry dropout")).toBeInTheDocument();
  });

  it("checks: flagged and clear", () => {
    const { unmount } = show("check_injection", { flagged: true, findings: ["'ignore previous instructions'"] });
    expect(screen.getByText("Flagged")).toBeInTheDocument();
    expect(screen.getByText("'ignore previous instructions'")).toBeInTheDocument();
    unmount();
    show("check_tone", { flagged: false, findings: [] });
    expect(screen.getByText("Clear")).toBeInTheDocument();
    expect(screen.getByText("Nothing found.")).toBeInTheDocument();
  });

  it("draft and review rounds", () => {
    const { unmount } = show("draft_2", { summary: "Valve slow to close.", recommended_actions: ["Cycle V-12"] });
    expect(screen.getByText("Valve slow to close.")).toBeInTheDocument();
    expect(screen.getByText("Cycle V-12")).toBeInTheDocument();
    unmount();
    show("review_2", { passed: false, feedback: "Remove invented cause" });
    expect(screen.getByText("Sent back")).toBeInTheDocument();
    expect(screen.getByText("Remove invented cause")).toBeInTheDocument();
  });

  it("review passed", () => {
    show("review_1", { passed: true, feedback: "ok" });
    expect(screen.getByText("Passed")).toBeInTheDocument();
  });

  it("unknown step falls back to labelled fields", () => {
    show("future_step", { alpha: 1, beta: { nested: true } });
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText('{"nested":true}')).toBeInTheDocument();
  });

  it("renders nothing without output", () => {
    const { container } = render(<StepOutput step={step(1, "classify", { output: null })} />);
    expect(container).toBeEmptyDOMElement();
  });
});
