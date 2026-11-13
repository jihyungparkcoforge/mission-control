import { HStack } from "@astryxdesign/core/HStack";
import { MetadataList, MetadataListItem } from "@astryxdesign/core/MetadataList";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { TraceStep, Violation } from "./api";
import StatusMark from "./StatusMark";

/*
 * Renders each pipeline step's result as readable UI instead of raw JSON.
 * The only raw text ever shown is a model reply that FAILED schema validation, kept
 * behind a disclosure because it is the evidence for the error.
 */

type Obj = Record<string, unknown>;
const isObj = (o: unknown): o is Obj => typeof o === "object" && o !== null && !Array.isArray(o);

function Findings({ items, empty }: { items: string[]; empty: string }) {
  if (!items.length) return <Text type="supporting">{empty}</Text>;
  return <ul className="plain-list">{items.map((f, i) => <li key={i}><Text>{f}</Text></li>)}</ul>;
}

function LimitsOutput({ o }: { o: Obj }) {
  const violations = (o.violations as Violation[]) ?? [];
  return (
    <VStack gap={1}>
      <HStack gap={2} align="center">
        <StatusMark tone={o.verdict === "go" ? "good" : "bad"} strong label={o.verdict === "go" ? "GO" : "NO-GO"} />
        <Text type="supporting">{violations.length} violation{violations.length === 1 ? "" : "s"}</Text>
      </HStack>
      {violations.length > 0 && <Findings items={violations.map((v) => v.message)} empty="" />}
    </VStack>
  );
}

function BriefByOutput({ o }: { o: Obj }) {
  const raised = (o.has_violation || o.injection_flagged) && o.model_severity !== "high";
  const why = o.injection_flagged ? "hidden instructions" : "violation";
  return (
    <MetadataList columns={2}>
      <MetadataListItem label="Model severity"><Text>{(o.model_severity as string) ?? "— (fallback)"}</Text></MetadataListItem>
      <MetadataListItem label="Final severity">
        <Text weight="semibold">{o.final_severity as string}{raised ? ` · raised by ${why}` : ""}</Text>
      </MetadataListItem>
      <MetadataListItem label="Brief within"><Text weight="semibold">{o.brief_by_minutes as number} min</Text></MetadataListItem>
      {Boolean(o.injection_flagged) && (
        <MetadataListItem label="Rule">
          <Text type="supporting">Extra rule beyond the brief: hidden instructions raise the briefing to high</Text>
        </MetadataListItem>
      )}
    </MetadataList>
  );
}

function ClassifyOutput({ o }: { o: Obj }) {
  return (
    <VStack gap={1}>
      <MetadataList columns={2}>
        <MetadataListItem label="Subsystem"><Text weight="semibold">{o.subsystem as string}</Text></MetadataListItem>
        <MetadataListItem label="Severity"><Text weight="semibold">{o.severity as string}</Text></MetadataListItem>
      </MetadataList>
      {typeof o.rationale === "string" && <Text type="supporting">{o.rationale}</Text>}
    </VStack>
  );
}

function CheckOutput({ o }: { o: Obj }) {
  const flagged = Boolean(o.flagged);
  return (
    <VStack gap={1} align="start">
      <StatusMark tone={flagged ? "warn" : "good"} strong label={flagged ? "Flagged" : "Clear"} />
      <Findings items={(o.findings as string[]) ?? []} empty="Nothing found." />
    </VStack>
  );
}

function DraftOutput({ o }: { o: Obj }) {
  const actions = (o.recommended_actions as string[]) ?? [];
  return (
    <VStack gap={1}>
      <Text>{o.summary as string}</Text>
      {actions.length > 0 && <Findings items={actions} empty="" />}
    </VStack>
  );
}

function ReviewOutput({ o }: { o: Obj }) {
  return (
    <VStack gap={1} align="start">
      <StatusMark tone={o.passed ? "good" : "bad"} strong label={o.passed ? "Passed" : "Sent back"} />
      <Text type="supporting">{o.feedback as string}</Text>
    </VStack>
  );
}

function VerdictCheckOutput({ o }: { o: Obj }) {
  return (
    <VStack gap={1} align="start">
      <StatusMark tone={o.consistent ? "good" : "bad"} strong label={o.consistent ? "Matches the code verdict" : "Contradicts the code verdict"} />
      {typeof o.problem === "string" && <Text type="supporting">{o.problem}</Text>}
    </VStack>
  );
}

export default function StepOutput({ step }: { step: TraceStep }) {
  const out = step.output;
  if (out == null) return null;
  if (!isObj(out)) {
    // a reply the schema rejected: show it only on request, as evidence
    return (
      <details>
        <summary><Text type="supporting">Show rejected model reply</Text></summary>
        <pre className="mono note">{String(out)}</pre>
      </details>
    );
  }
  const kind = step.step.replace(/_\d+$/, "");
  switch (kind) {
    case "limits_check": return <LimitsOutput o={out} />;
    case "brief_by":
    case "brief_by_raised": return <BriefByOutput o={out} />;
    case "classify": return <ClassifyOutput o={out} />;
    case "check_injection":
    case "injection_rules":
    case "check_missing":
    case "check_tone": return <CheckOutput o={out} />;
    case "draft": return <DraftOutput o={out} />;
    case "review": return <ReviewOutput o={out} />;
    case "verdict_check": return <VerdictCheckOutput o={out} />;
    default:
      return (
        <MetadataList columns={1}>
          {Object.entries(out).map(([k, v]) => (
            <MetadataListItem key={k} label={k}><Text>{typeof v === "object" ? JSON.stringify(v) : String(v)}</Text></MetadataListItem>
          ))}
        </MetadataList>
      );
  }
}
