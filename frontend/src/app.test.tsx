import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { CLEAN, jsonResponse, LIMITS, REPORT } from "./testFixtures";

beforeEach(() => { localStorage.clear(); window.location.hash = ""; });
afterEach(() => vi.restoreAllMocks());

function routeFetch(routes: Record<string, () => Response | Promise<Response>>) {
  return vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const key = `${init?.method ?? "GET"} ${String(input)}`;
    const handler = routes[key];
    if (!handler) throw new Error(`unexpected fetch ${key}`);
    return handler();
  });
}

describe("App", () => {
  it("shows demo banner, lists reports, and opens a report's detail", async () => {
    routeFetch({
      "GET /api/config": () => jsonResponse(200, { demo_mode: true, model: "fake-model", limits: LIMITS }),
      "GET /api/reports": () => jsonResponse(200, [REPORT, CLEAN]),
      "GET /api/reports/7": () => jsonResponse(200, REPORT),
    });
    render(<App />);
    expect(await screen.findByText(/DEMO MODE/)).toBeInTheDocument();
    expect(screen.getAllByText(/Select a report/).length).toBeGreaterThan(0);
    expect(await screen.findByText(/#7 PROP-2/)).toBeInTheDocument();
    expect(screen.getByText(/Model: fake-model/)).toBeInTheDocument();

    await userEvent.setup().click(screen.getByText(/#7 PROP-2/));
    expect(await screen.findByRole("tab", { name: "Briefing" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("tab", { name: /Trace/ }));
    expect(screen.getAllByTestId("trace-card")).toHaveLength(REPORT.trace!.length);
    await userEvent.setup().click(screen.getByRole("tab", { name: "Briefing" }));
    expect(await screen.findByTestId("gauge-wind_knots")).toBeInTheDocument();   // limits from /api/config
    expect(document.querySelector(".astryx-badge")).toBeNull();   // no pill badges anywhere on the console
  });

  it("hides the demo banner with a real model and shows an empty list", async () => {
    routeFetch({
      "GET /api/config": () => jsonResponse(200, { demo_mode: false, model: "gpt-6-astra" }),
      "GET /api/reports": () => jsonResponse(200, []),
    });
    render(<App />);
    expect(await screen.findByText("No reports filed yet.")).toBeInTheDocument();
    expect(await screen.findByText(/Model: gpt-6-astra/)).toBeInTheDocument();
    expect(screen.queryByText(/DEMO MODE/)).not.toBeInTheDocument();
  });

  it("shows a server error when the API is unreachable", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Failed to fetch"));
    render(<App />);
    expect(await screen.findByText(/Cannot reach server: Failed to fetch/)).toBeInTheDocument();
  });

  it("selects a newly filed report and takes the FD token in the decision area", async () => {
    routeFetch({
      "GET /api/config": () => jsonResponse(200, { demo_mode: true, model: "fake-model" }),
      "GET /api/reports": () => jsonResponse(200, [CLEAN]),
      "GET /api/reports/8": () => jsonResponse(200, CLEAN),
      "POST /api/reports": () => jsonResponse(201, CLEAN),
    });
    render(<App />);
    const u = userEvent.setup();
    await u.type(screen.getByLabelText("Name"), "Ana");
    await u.type(screen.getByLabelText("Station"), "PROP-2");
    await u.type(screen.getByLabelText("Wind (kn)"), "10");
    await u.type(screen.getByLabelText("Temp (°C)"), "10");
    await u.type(screen.getByLabelText("Fuel (%)"), "99");
    await u.type(screen.getByLabelText("Note"), "Valve slow");
    await u.click(screen.getByRole("button", { name: "File report" }));
    // the FD token is asked for inside the decision area, and only taken on Unlock
    const tokenInput = await screen.findByPlaceholderText("Flight Director only");
    expect(screen.getByRole("button", { name: "Unlock" })).toHaveAttribute("aria-disabled", "true");
    await u.type(tokenInput, "fd");
    expect(localStorage.getItem("fd-token")).toBeNull();
    await u.click(screen.getByRole("button", { name: "Unlock" }));
    expect(localStorage.getItem("fd-token")).toBe("fd");
    expect(await screen.findByRole("button", { name: "Approve briefing" })).toBeInTheDocument();
  });

  it("replaces the detail after an FD action", async () => {
    localStorage.setItem("fd-token", "fd");
    localStorage.setItem("fd-name", "FD Kim");
    const approved = { ...CLEAN, status: "approved", decided_by: "FD Kim" };
    let current = CLEAN;
    routeFetch({
      "GET /api/config": () => jsonResponse(200, { demo_mode: true, model: "fake-model" }),
      "GET /api/reports": () => jsonResponse(200, [current]),
      "GET /api/reports/8": () => jsonResponse(200, current),
      "POST /api/reports/8/approve": () => { current = approved as typeof CLEAN; return jsonResponse(200, approved); },
    });
    render(<App />);
    const u = userEvent.setup();
    await u.click(await screen.findByText(/#8 PROP-2/));
    await u.click(await screen.findByRole("button", { name: "Approve briefing" }));
    await waitFor(() => expect(screen.getByText("Approved")).toBeInTheDocument());
    expect(screen.getByText(/by FD Kim/)).toBeInTheDocument();
  });

  it("opens the report named in the URL and records new selections there", async () => {
    window.location.hash = "#report-7";
    routeFetch({
      "GET /api/config": () => jsonResponse(200, { demo_mode: true, model: "fake-model" }),
      "GET /api/reports": () => jsonResponse(200, [REPORT, CLEAN]),
      "GET /api/reports/7": () => jsonResponse(200, REPORT),
      "GET /api/reports/8": () => jsonResponse(200, CLEAN),
    });
    render(<App />);
    expect(await screen.findByRole("tab", { name: "Briefing" })).toBeInTheDocument();
    await userEvent.setup().click(screen.getByText(/#8 PROP-2/));
    expect(window.location.hash).toBe("#report-8");
  });
});

it("report list verdicts use one fixed width for GO and NO-GO", async () => {
  routeFetch({
    "GET /api/config": () => jsonResponse(200, { demo_mode: false, model: "m" }),
    "GET /api/reports": () => jsonResponse(200, [REPORT, CLEAN]),
  });
  render(<App />);
  await screen.findByText(/#7 PROP-2/);
  const marks = [...document.querySelectorAll<HTMLElement>(".report-list .status-mark[data-tone]")]
    .filter((m) => m.textContent === "GO" || m.textContent === "NO-GO");
  expect(marks.map((m) => m.style.width)).toEqual(["68px", "68px"]);
});
