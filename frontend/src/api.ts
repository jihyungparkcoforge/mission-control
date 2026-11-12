export type Verdict = "go" | "no_go";
export type Status = "processing" | "pending_approval" | "review_failed" | "error" | "approved" | "rejected";

export interface Limit { label: string; unit: string; min: number | null; max: number | null }
export type Limits = Record<"wind_knots" | "temp_c" | "fuel_pct", Limit>;
export interface AppConfig { demo_mode: boolean; model: string; limits: Limits; cost_basis?: string }

export interface Violation { field: string; value: number; limit: string; message: string }
export interface CheckResult { flagged: boolean; findings: string[] }

export interface TraceStep {
  id: number;
  run: number;
  step: string;
  model: string;
  status: "running" | "ok" | "error";
  input_tokens: number;
  output_tokens: number;
  cost_usd: string;
  started_at: number;
  ended_at: number | null;
  output: unknown;
  error: string | null;
}

export interface Report {
  id: number;
  created_at: number;
  name: string;
  station: string;
  wind_knots: number;
  temp_c: number;
  fuel_pct: number;
  note: string;
  verdict: Verdict;
  violations: Violation[];
  status: Status;
  subsystem: string | null;
  model_severity: string | null;
  final_severity: string | null;
  brief_by_minutes: number | null;
  brief_by_at: number | null;
  classification_error: string | null;
  classification: { subsystem: string; severity?: string; rationale?: string } | null;
  checks: Record<"check_injection" | "check_missing" | "check_tone", CheckResult> | null;
  injection_flag: boolean;
  needs_review: boolean;
  error_message: string | null;
  briefing: { summary: string; recommended_actions: string[] } | null;
  review_rounds: number;
  review_feedback: string | null;
  decided_by: string | null;
  decided_at: number | null;
  decision_reason: string | null;
  run_count: number;
  trace?: TraceStep[];
  total_cost_usd?: string;
}

export interface NewReport {
  name: string;
  station: string;
  wind_knots: number;
  temp_c: number;
  fuel_pct: number;
  note: string;
}

export class ApiError extends Error {}

async function call<T>(path: string, init: RequestInit = {}, fdToken?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (fdToken) headers["X-FD-Token"] = fdToken;
  const res = await fetch(path, { ...init, headers });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(body.message ?? body.detail ?? `Request failed (${res.status})`);
  return body as T;
}

export const api = {
  config: () => call<AppConfig>("/api/config"),
  list: () => call<Report[]>("/api/reports"),
  get: (id: number) => call<Report>(`/api/reports/${id}`),
  file: (r: NewReport) => call<Report>("/api/reports", { method: "POST", body: JSON.stringify(r) }),
  approve: (id: number, token: string, approver: string, acknowledge_injection: boolean) =>
    call<Report>(`/api/reports/${id}/approve`,
      { method: "POST", body: JSON.stringify({ approver, acknowledge_injection }) }, token),
  reject: (id: number, token: string, approver: string, reason: string) =>
    call<Report>(`/api/reports/${id}/reject`,
      { method: "POST", body: JSON.stringify({ approver, reason }) }, token),
  regenerate: (id: number, token: string) =>
    call<Report>(`/api/reports/${id}/regenerate`, { method: "POST" }, token),
  rerun: (id: number, token: string) => call<Report>(`/api/reports/${id}/rerun`, { method: "POST" }, token),
};

export function usd(v: string | number | undefined): string {
  if (v === undefined) return "-";
  const n = Number(v);
  return `$${n.toFixed(n > 0 && n < 0.01 ? 5 : 4)}`;
}
