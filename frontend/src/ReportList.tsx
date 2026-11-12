import { Card } from "@astryxdesign/core/Card";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Text } from "@astryxdesign/core/Text";
import { Report } from "./api";
import StatusMark, { Tone } from "./StatusMark";

export const STATUS_LABEL: Record<string, string> = {
  processing: "Processing",
  pending_approval: "Awaiting FD approval",
  review_failed: "Review failed",
  error: "Error",
  approved: "Approved",
  rejected: "Rejected",
};

export const STATUS_TONE: Record<string, Tone> = {
  processing: "info",
  pending_approval: "warn",
  review_failed: "bad",
  error: "bad",
  approved: "good",
  rejected: "neutral",
};

export default function ReportList({ reports, selected, onSelect }: {
  reports: Report[]; selected: number | null; onSelect: (id: number) => void;
}) {
  if (!reports.length) {
    return (
      <Card padding={4}>
        <EmptyState title="No reports filed yet." description="Filed reports appear here with their verdict." />
      </Card>
    );
  }
  return (
    <Card padding={1}>
      <ul className="report-list" aria-label="Reports">
        {reports.map((r) => (
          <li key={r.id}>
            <button className={r.id === selected ? "selected" : ""} onClick={() => onSelect(r.id)}>
              <StatusMark tone={r.verdict === "go" ? "good" : "bad"} strong width={68} label={r.verdict === "go" ? "GO" : "NO-GO"} />
              <span className="grow">
                <Text weight="medium" display="block">#{r.id} {r.station} · {r.name}</Text>
                <Text type="supporting" display="block">
                  {r.subsystem ?? "…"} · {r.final_severity ?? "…"} · {STATUS_LABEL[r.status]}
                </Text>
              </span>
              <span className="list-flag" title={r.injection_flag ? "Hidden instructions detected" : undefined}>
                {r.injection_flag && <><StatusMark tone="warn" label="" /><span className="sr-only">Hidden instructions detected</span></>}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </Card>
  );
}
