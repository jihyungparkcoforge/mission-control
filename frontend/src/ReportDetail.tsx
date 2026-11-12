import { useEffect, useId, useState } from "react";
import { Tab, TabList } from "@astryxdesign/core/TabList";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { CheckboxInput } from "@astryxdesign/core/CheckboxInput";
import { Divider } from "@astryxdesign/core/Divider";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { Text } from "@astryxdesign/core/Text";
import { TextInput } from "@astryxdesign/core/TextInput";
import { VStack } from "@astryxdesign/core/VStack";
import { api, Limits, Report, usd } from "./api";
import LimitGauges from "./LimitGauge";
import { STATUS_LABEL, STATUS_TONE } from "./ReportList";
import TracePanel from "./TracePanel";
import StatusMark from "./StatusMark";

function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(Date.now() / 1000);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now() / 1000), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

/** One cell of the facts strip: small label, then value + muted supporting text on one line. */
function Tile({ label, value, sub, tone, testId }: {
  label: string; value: string; sub?: string; tone?: "bad"; testId?: string;
}) {
  return (
    <div className={`tile${tone ? ` tile-${tone}` : ""}`}>
      <div className="tile-label">{label}</div>
      <div className="tile-line">
        <span className="tile-value" data-testid={testId}>{value}</span>
        {sub && <span className="tile-sub" title={sub}>{sub}</span>}
      </div>
    </div>
  );
}

function BriefByTile({ r }: { r: Report }) {
  const now = useNow();
  if (!r.brief_by_at) return <Tile label="Brief in" value="…" sub="pending classification" />;
  const at = new Date(r.brief_by_at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
  const sub = `due ${at} · ${r.brief_by_minutes} min`;
  if (r.status === "approved" || r.status === "rejected") return <Tile label="Brief in" value="Done" sub={sub} />;
  const left = Math.round(r.brief_by_at - now);
  if (left < 0) return <Tile label="Brief in" value={`−${Math.ceil(-left / 60)} min`} sub={`overdue · was due ${at}`} tone="bad" />;
  return <Tile label="Brief in" value={`${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`} sub={sub} />;
}

const SUBSYSTEM_LABEL: Record<string, string> = {
  propulsion: "Propulsion", avionics: "Avionics", communications: "Comms", ground_support: "Ground",
  weather: "Weather", structures: "Structures", unclassified: "Unclassified",
};

const CHECK_LABELS = { check_injection: "Hidden instructions", check_missing: "Missing details", check_tone: "Panic tone" } as const;

function ChecksRow({ r }: { r: Report }) {
  const flaggedNotes = r.checks
    ? (["check_missing", "check_tone"] as const).filter((k) => r.checks![k].flagged && r.checks![k].findings.length)
    : [];
  return (
    <div className="checks-row">
      <div className="checks-marks">
        {(Object.keys(CHECK_LABELS) as (keyof typeof CHECK_LABELS)[]).map((k) => {
          const c = r.checks?.[k];
          return <StatusMark key={k} width={230} tone={!c ? "neutral" : c.flagged ? "warn" : "good"}
            label={`${CHECK_LABELS[k]}${!c ? " —" : c.flagged ? ": flagged" : ": clear"}`} />;
        })}
      </div>
      {flaggedNotes.map((k) => (
        <Text key={k} type="supporting" display="block">{CHECK_LABELS[k]}: {r.checks![k].findings.join("; ")}</Text>
      ))}
    </div>
  );
}

/** Holds the typed token locally and hands it up only on Unlock/Enter, so the form doesn't swap mid-typing. */
function TokenField({ onSubmit }: { onSubmit: (t: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <form className="token-field" onSubmit={(e) => { e.preventDefault(); if (value.trim()) onSubmit(value.trim()); }}>
      <HStack gap={2} align="end">
        <TextInput type="password" label="FD token" value={value} onChange={setValue} placeholder="Flight Director only" />
        <Button type="submit" width={96} label="Unlock" isDisabled={!value.trim()} />
      </HStack>
    </form>
  );
}

// Every FD action button is the same width, whatever its label.
const FD_BUTTON_W = 176;

function FdActions({ r, token, onChange, onTokenChange }: {
  r: Report; token: string; onChange: (r: Report) => void; onTokenChange?: (t: string) => void;
}) {
  const [approver, setApprover] = useState(localStorage.getItem("fd-name") ?? "");
  const [ack, setAck] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function act(fn: () => Promise<Report>) {
    setError(null);
    try {
      localStorage.setItem("fd-name", approver);
      onChange(await fn());
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const canApprove = r.status === "pending_approval";
  const canReject = r.status === "pending_approval" || r.status === "review_failed";
  const canRegenerate = r.status === "review_failed" || r.status === "rejected";
  const canRerun = r.status === "error";
  if (!canApprove && !canReject && !canRegenerate && !canRerun) return null;

  // The FD token is asked for here, where it is needed, not in a global header.
  if (!token) {
    return (
      <VStack gap={3}>
        <Divider />
        <Heading level={3}>Flight Director decision</Heading>
        {onTokenChange ? (
          <TokenField onSubmit={onTokenChange} />
        ) : (
          <Text type="supporting">Flight Director token required to act on this report.</Text>
        )}
      </VStack>
    );
  }

  return (
    <VStack gap={3}>
      <Divider />
      <Heading level={3}>Flight Director decision</Heading>
      <HStack gap={2} align="end" wrap="wrap">
        <TextInput label="Flight Director name" value={approver} onChange={setApprover} />
        {canReject && (
          <TextInput label="Reason" isOptional value={reason} onChange={setReason} placeholder="reason (optional)" />
        )}
      </HStack>
      {canApprove && r.injection_flag && (
        <CheckboxInput value={ack} onChange={setAck}
          label="I have read the original note; it contained hidden instructions that were ignored." />
      )}
      <HStack gap={2} wrap="wrap">
        {canApprove && (
          <Button variant="primary" width={FD_BUTTON_W} label="Approve briefing" isDisabled={!approver || (r.injection_flag && !ack)}
            onClick={() => act(() => api.approve(r.id, token, approver, ack))} />
        )}
        {canReject && (
          <Button variant="destructive" width={FD_BUTTON_W} label="Reject" isDisabled={!approver}
            onClick={() => act(() => api.reject(r.id, token, approver, reason))} />
        )}
        {canRegenerate && <Button width={FD_BUTTON_W} label="Regenerate briefing" onClick={() => act(() => api.regenerate(r.id, token))} />}
        {canRerun && <Button width={FD_BUTTON_W} label="Re-run pipeline" onClick={() => act(() => api.rerun(r.id, token))} />}
      </HStack>
      {error && <Banner status="error" title="Action refused" description={error} role="alert" />}
    </VStack>
  );
}

export default function ReportDetail({ r, limits, token, onChange, onTokenChange }: {
  r: Report; limits?: Limits; token: string; onChange: (r: Report) => void; onTokenChange?: (t: string) => void;
}) {
  const [tab, setTab] = useState("briefing");
  const panelId = useId();
  const go = r.verdict === "go";
  const raised = r.violations.length > 0 && r.model_severity !== null && r.model_severity !== "high";
  const steps = r.trace?.length ?? 0;
  const sevSub = r.model_severity === null && r.final_severity
    ? "safe default (classification failed)"
    : r.model_severity ? `model: ${r.model_severity}${raised ? " · raised by violation" : ""}` : undefined;
  return (
    <VStack gap={3}>
      <Card padding={4} variant={go ? "green" : "red"}>
        <HStack justify="between" align="center" gap={4} wrap="wrap">
          <Text type="display-1" weight="bold">{go ? "GO" : "NO-GO"}</Text>
          <HStack gap={2} align="center">
            <StatusMark tone={STATUS_TONE[r.status]} strong label={STATUS_LABEL[r.status]} />
            {r.decided_by && <Text>by {r.decided_by}</Text>}
            {r.decision_reason && <Text type="supporting">“{r.decision_reason}”</Text>}
          </HStack>
        </HStack>
      </Card>

      <div className="tiles">
        <BriefByTile r={r} />
        <Tile label="Severity" value={r.final_severity ?? "…"} sub={sevSub} />
        <Tile label="Subsystem" value={r.subsystem ? SUBSYSTEM_LABEL[r.subsystem] ?? r.subsystem : "…"} sub={r.station} />
      </div>
      <ChecksRow r={r} />

      {r.classification_error && (
        <Banner status="warning" title="Classification failed — safe default used (unclassified, high)."
          description={r.classification_error} />
      )}
      {r.error_message && <Banner status="error" title="Pipeline stopped" description={r.error_message} role="alert" />}
      {r.injection_flag && (
        <Banner status="warning" title="Hidden instructions detected — ignored, verdict unaffected. FD review required."
          description={<ul className="plain-list">{r.checks?.check_injection.findings.map((f, i) => <li key={i}>{f}</li>)}</ul>} />
      )}

      <TabList value={tab} onChange={setTab} hasDivider role="tablist" aria-label="Report sections">
        <Tab value="briefing" label="Briefing" panelId={`${panelId}-briefing`} />
        <Tab value="trace" label={`Trace · ${steps} steps`} panelId={`${panelId}-trace`} />
      </TabList>

      {tab === "briefing" ? (
        <div role="tabpanel" id={`${panelId}-briefing`}>
        <VStack gap={3}>
          {limits ? (
            <Card padding={4}>
              <VStack gap={2}>
                <Heading level={3}>Launch readings</Heading>
                <LimitGauges r={r} limits={limits} />
              </VStack>
            </Card>
          ) : r.violations.length > 0 && (
            <Banner status="error" title="Limit violations"
              description={<ul className="plain-list">{r.violations.map((v) => <li key={v.field}>{v.message}</li>)}</ul>} />
          )}

          <Card padding={4}>
            <VStack gap={3}>
              <HStack gap={2} align="center">
                <Heading level={3}>Briefing</Heading>
                {r.review_rounds > 0 && <Text type="supporting">review round {r.review_rounds} of 3</Text>}
              </HStack>
              {r.briefing ? (
                <>
                  <Text as="p" size="lg">{r.briefing.summary}</Text>
                  {r.briefing.recommended_actions.length > 0 && (
                    <ul className="actions">{r.briefing.recommended_actions.map((a, i) => <li key={i}><Text>{a}</Text></li>)}</ul>
                  )}
                  {r.status === "review_failed" && (
                    <Banner status="error" title="Reviewer did not pass this draft after 3 rounds — it cannot be approved."
                      description={`Last feedback: ${r.review_feedback}`} />
                  )}
                </>
              ) : (
                <Text type="supporting">{r.status === "processing" ? "Drafting…" : "No briefing."}</Text>
              )}
              <FdActions r={r} token={token} onChange={onChange} onTokenChange={onTokenChange} />
            </VStack>
          </Card>

          <Card padding={4} variant="muted">
            <details>
              <summary><Text weight="medium">Original report from {r.name} @ {r.station}</Text></summary>
              <pre className="mono note">{r.note}</pre>
            </details>
          </Card>
        </VStack>
        </div>
      ) : (
        <div role="tabpanel" id={`${panelId}-trace`}>
          <VStack gap={3}>
            {/* Cost is audit information, not decision information: it lives with the trace. */}
            <div className="trace-summary">
              <span>Report cost <strong data-testid="report-cost">{usd(r.total_cost_usd)}</strong></span>
              <span>{r.run_count} run{r.run_count === 1 ? "" : "s"}</span>
              <span>{steps} steps</span>
              <span>{r.trace?.filter((t) => t.model !== "code").length ?? 0} model calls</span>
            </div>
            <TracePanel trace={r.trace ?? []} />
          </VStack>
        </div>
      )}
    </VStack>
  );
}
