import { Text } from "@astryxdesign/core/Text";
import { TraceStep } from "./api";
import TraceCard from "./TraceCard";

/*
 * The trace grouped the way the pipeline runs: code + classification, the three concurrent
 * checks, then each draft/review round on its own row. Latest run first; earlier runs folded.
 */
const STAGE1 = ["limits_check", "classify", "brief_by"];
const CHECKS = ["check_injection", "injection_rules", "check_missing", "check_tone", "brief_by_raised"];

function Section({ title, note, steps }: { title: string; note?: string; steps: TraceStep[] }) {
  if (!steps.length) return null;
  return (
    <section className="trace-section">
      <div className="trace-section-head">
        <Text weight="semibold">{title}</Text>
        {note && <Text type="supporting">{note}</Text>}
      </div>
      <ol className="trace">{steps.map((t) => <TraceCard key={t.id} step={t} />)}</ol>
    </section>
  );
}

function Run({ steps }: { steps: TraceStep[] }) {
  const byName = (names: string[]) =>
    names.map((n) => steps.find((s) => s.step === n)).filter((s): s is TraceStep => Boolean(s));
  const rounds = [...new Set(steps.map((s) => s.step.match(/^(?:draft|review)_(\d+)$/)?.[1]).filter(Boolean))]
    .map(Number).sort((a, b) => a - b);
  const known = new Set([...STAGE1, ...CHECKS, ...rounds.flatMap((n) => [`draft_${n}`, `review_${n}`, `verdict_check_${n}`])]);
  return (
    <>
      <Section title="Limits & classification" note="limits and brief-by are plain code" steps={byName(STAGE1)} />
      <Section title="Checks" note="3 model checks ran concurrently · code rules backstop hidden instructions" steps={byName(CHECKS)} />
      {rounds.map((n) => (
        <Section key={n} title={`Draft & review — round ${n} of 3`} steps={byName([`draft_${n}`, `review_${n}`, `verdict_check_${n}`])} />
      ))}
      <Section title="Other" steps={steps.filter((s) => !known.has(s.step))} />
    </>
  );
}

export default function TracePanel({ trace }: { trace: TraceStep[] }) {
  const runs = [...new Set(trace.map((t) => t.run))].sort((a, b) => b - a);
  if (!runs.length) return <Text type="supporting">No steps yet.</Text>;
  const [latest, ...earlier] = runs;
  return (
    <div className="trace-panel">
      {runs.length > 1 && <Text type="supporting">Run {latest} (latest)</Text>}
      <Run steps={trace.filter((t) => t.run === latest)} />
      {earlier.map((run) => (
        <details key={run} className="trace-earlier">
          <summary><Text type="supporting">Run {run}</Text></summary>
          <Run steps={trace.filter((t) => t.run === run)} />
        </details>
      ))}
    </div>
  );
}
