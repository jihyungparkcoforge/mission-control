import { useCallback, useEffect, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Card } from "@astryxdesign/core/Card";
import { EmptyState } from "@astryxdesign/core/EmptyState";
import { Text } from "@astryxdesign/core/Text";
import { VStack } from "@astryxdesign/core/VStack";
import { api, AppConfig, Report } from "./api";
import FileReportForm from "./FileReportForm";
import ReportDetail from "./ReportDetail";
import ReportList from "./ReportList";

const POLL_MS = 1500;

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  // The selected report lives in the URL (#report-7) so a briefing can be linked and survives reload.
  const [selected, setSelectedState] = useState<number | null>(() => {
    const m = window.location.hash.match(/^#report-(\d+)$/);
    return m ? Number(m[1]) : null;
  });
  const setSelected = useCallback((id: number) => {
    window.location.hash = `report-${id}`;
    setSelectedState(id);
  }, []);
  const [detail, setDetail] = useState<Report | null>(null);
  const [token, setToken] = useState(localStorage.getItem("fd-token") ?? "");
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setReports(await api.list());
      if (selected !== null) setDetail(await api.get(selected));
      setLoadError(null);
    } catch (e) {
      setLoadError((e as Error).message);
    }
  }, [selected]);

  useEffect(() => { api.config().then(setConfig).catch(() => {}); }, []);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  const saveToken = (v: string) => { setToken(v); localStorage.setItem("fd-token", v); };

  return (
    <div className="app">
      {config?.demo_mode && (
        <Banner status="warning" container="section"
          title="DEMO MODE — no OPENAI_API_KEY set. Model steps use a deterministic fake, not real AI." />
      )}
      {loadError && (
        <div className="page-pad">
          <Banner status="error" title={`Cannot reach server: ${loadError}`} />
        </div>
      )}
      <main>
        <VStack gap={3}>
          <FileReportForm onFiled={(r) => { setSelected(r.id); setDetail(r); refresh(); }} />
          <ReportList reports={reports} selected={selected} onSelect={setSelected} />
        </VStack>
        <div>
          {detail ? (
            <ReportDetail r={detail} limits={config?.limits} token={token} onTokenChange={saveToken}
              onChange={(r) => { setDetail(r); refresh(); }} />
          ) : (
            <Card padding={6}>
              <EmptyState title="No report selected"
                description="Select a report to see its verdict, briefing, cost, and trace." />
            </Card>
          )}
        </div>
      </main>
      <footer className="app-footer">
        <Text type="supporting">
          Model: {config?.model ?? "…"} · verdicts are computed by code, never by a model · only a Flight Director can approve
        </Text>
      </footer>
    </div>
  );
}
