import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import TracePanel from "./TracePanel";
import { step } from "./testFixtures";

const RUN1 = [
  step(1, "limits_check", { model: "code", output: { verdict: "go", violations: [] } }),
  step(2, "classify", { output: { subsystem: "propulsion", severity: "low", rationale: "valve" } }),
  step(3, "brief_by", { model: "code", output: { model_severity: "low", has_violation: false, final_severity: "low", brief_by_minutes: 30 } }),
  step(4, "check_injection", { output: { flagged: false, findings: [] } }),
  step(5, "check_missing", { output: { flagged: false, findings: [] } }),
  step(6, "check_tone", { output: { flagged: false, findings: [] } }),
  step(11, "injection_rules", { model: "code", output: { flagged: true, findings: ['override of prior instructions: "ignore all previous instructions"'] } }),
  step(7, "draft_1", { output: { summary: "first", recommended_actions: [] } }),
  step(8, "review_1", { output: { passed: false, feedback: "too vague" } }),
  step(9, "draft_2", { output: { summary: "second", recommended_actions: [] } }),
  step(10, "review_2", { output: { passed: true, feedback: "ok" } }),
  step(12, "verdict_check_1", { model: "code", output: { consistent: false, problem: "x" } }),
  step(13, "verdict_check_2", { model: "code", output: { consistent: true, problem: null } }),
];

describe("TracePanel", () => {
  it("groups steps the way the pipeline runs", () => {
    render(<TracePanel trace={RUN1} />);
    const sections = [...document.querySelectorAll<HTMLElement>("ol.trace")].map((ol) => within(ol).getAllByTestId("trace-card").length);
    expect(sections).toEqual([3, 4, 3, 3]);          // rounds now include the code verdict check            // limits+classify+brief-by · 3 checks + code rules · round 1 · round 2
    expect(screen.getByText(/3 model checks ran concurrently/)).toBeInTheDocument();
    expect(screen.getByText("Instruction rules (code)")).toBeInTheDocument();
    expect(screen.getByText("Draft & review — round 2 of 3")).toBeInTheDocument();
  });

  it("shows the latest run first and folds earlier runs", () => {
    const run2 = [step(20, "draft_1", { run: 2, output: { summary: "regen", recommended_actions: [] } }),
                  step(21, "review_1", { run: 2, output: { passed: true, feedback: "ok" } })];
    render(<TracePanel trace={[...RUN1, ...run2]} />);
    expect(screen.getByText("Run 2 (latest)")).toBeInTheDocument();
    expect(screen.getByText("Run 1").closest("details")).not.toHaveAttribute("open");
  });

  it("puts unknown steps in an Other section and handles an empty trace", () => {
    const { unmount } = render(<TracePanel trace={[step(1, "future_step", { output: { a: 1 } })]} />);
    expect(screen.getByText("Other")).toBeInTheDocument();
    unmount();
    render(<TracePanel trace={[]} />);
    expect(screen.getByText("No steps yet.")).toBeInTheDocument();
  });

  it("opens full step details in a dialog", async () => {
    render(<TracePanel trace={[step(8, "review_1", { output: { passed: false, feedback: "too vague" } })]} />);
    const u = userEvent.setup();
    await u.click(screen.getByRole("button", { name: "Details" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Review draft — round 1")).toBeInTheDocument();
    expect(within(dialog).getByText("too vague")).toBeInTheDocument();
  });

  it("cards without output have no Details button", () => {
    render(<TracePanel trace={[step(1, "classify", { status: "running", ended_at: null })]} />);
    expect(screen.queryByRole("button", { name: "Details" })).not.toBeInTheDocument();
    expect(screen.getByText("—", { selector: "dd" })).toBeInTheDocument();   // no time yet
  });
});
