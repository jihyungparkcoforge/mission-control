import { useState } from "react";
import { Button } from "@astryxdesign/core/Button";
import { Dialog, DialogHeader } from "@astryxdesign/core/Dialog";
import { VStack } from "@astryxdesign/core/VStack";
import { Text } from "@astryxdesign/core/Text";
import { TraceStep, usd } from "./api";
import StatusMark from "./StatusMark";
import StepOutput from "./StepOutput";

const LABELS: Record<string, string> = {
  limits_check: "Launch limits",
  brief_by: "Brief-by time",
  brief_by_raised: "Brief-by raised (code)",
  classify: "Classification",
  check_injection: "Hidden instructions",
  injection_rules: "Instruction rules (code)",
  check_missing: "Missing details",
  check_tone: "Panic tone",
};

export function stepLabel(step: string): string {
  const m = step.match(/^(draft|review|verdict_check)_(\d+)$/);
  if (m) {
    const name = { draft: "Draft briefing", review: "Review draft", verdict_check: "Verdict check (code)" }[m[1]];
    return `${name} — round ${m[2]}`;
  }
  return LABELS[step] ?? step;
}

const STATUS = {
  ok: { tone: "good", label: "OK" },
  error: { tone: "bad", label: "Error" },
  running: { tone: "warn", label: "Running" },
} as const;

export function formatDuration(seconds: number): string {
  const ms = Math.round(seconds * 1000);
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

/** Model · tokens · cost · time in a fixed 4-column grid, so every card lines up. */
function Metrics({ step }: { step: TraceStep }) {
  const isCode = step.model === "code";
  const ms = step.ended_at ? formatDuration(step.ended_at - step.started_at) : "—";
  const cells: [string, string, string?][] = [
    ["Model", isCode ? "plain code" : step.model],
    ["Tokens", isCode ? "—" : `${step.input_tokens} in / ${step.output_tokens} out`, "tokens"],
    ["Cost", isCode ? "—" : usd(step.cost_usd)],
    ["Time", ms],
  ];
  return (
    <dl className="tc-metrics">
      {cells.map(([k, v, id]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd data-testid={id} title={v}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Body({ step }: { step: TraceStep }) {
  return (
    <VStack gap={2}>
      {step.error && <Text color="accent">{step.error}</Text>}
      <StepOutput step={step} />
    </VStack>
  );
}

export default function TraceCard({ step }: { step: TraceStep }) {
  const [open, setOpen] = useState(false);
  const status = STATUS[step.status];
  const hasBody = step.output != null || Boolean(step.error);
  const label = stepLabel(step.step);
  return (
    <li data-testid="trace-card" className={`trace-card is-${step.status}`}>
      <div className="tc-head">
        <span className="tc-title" title={label}>{label}</span>
        <StatusMark tone={status.tone} strong width={78} label={status.label} />
      </div>
      <Metrics step={step} />
      <div className="tc-body">{hasBody && <Body step={step} />}</div>
      <div className="tc-foot">
        {hasBody && <Button size="sm" variant="ghost" width={96} label="Details" onClick={() => setOpen(true)} />}
      </div>
      {open && (
        <Dialog isOpen={open} onOpenChange={setOpen} width={560} padding={5}>
          <VStack gap={4}>
            <DialogHeader title={label} onOpenChange={setOpen} />
            <Metrics step={step} />
            <Body step={step} />
          </VStack>
        </Dialog>
      )}
    </li>
  );
}
