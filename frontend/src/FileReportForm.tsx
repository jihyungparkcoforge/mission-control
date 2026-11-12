import { FormEvent, useState } from "react";
import { Banner } from "@astryxdesign/core/Banner";
import { Button } from "@astryxdesign/core/Button";
import { Card } from "@astryxdesign/core/Card";
import { Heading } from "@astryxdesign/core/Heading";
import { HStack } from "@astryxdesign/core/HStack";
import { NumberInput } from "@astryxdesign/core/NumberInput";
import { TextArea } from "@astryxdesign/core/TextArea";
import { TextInput } from "@astryxdesign/core/TextInput";
import { VStack } from "@astryxdesign/core/VStack";
import { api, NewReport, Report } from "./api";

interface Fields {
  name: string;
  station: string;
  wind_knots: number | null;
  temp_c: number | null;
  fuel_pct: number | null;
  note: string;
}
const EMPTY: Fields = { name: "", station: "", wind_knots: null, temp_c: null, fuel_pct: null, note: "" };

export default function FileReportForm({ onFiled }: { onFiled: (r: Report) => void }) {
  const [f, setF] = useState<Fields>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Fields>(k: K) => (v: Fields[K]) => setF((prev) => ({ ...prev, [k]: v }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      // Validation is enforced by the server (empty number -> null -> 422); its message is shown verbatim.
      const r = await api.file(f as unknown as NewReport);
      setF(EMPTY);
      onFiled(r);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card padding={4}>
      <form onSubmit={submit} noValidate aria-label="File anomaly report">
        <VStack gap={3}>
          <Heading level={2}>File anomaly report</Heading>
          <HStack gap={2}>
            <TextInput label="Name" value={f.name} onChange={set("name")} />
            <TextInput label="Station" value={f.station} onChange={set("station")} placeholder="e.g. PROP-2" />
          </HStack>
          <HStack gap={2}>
            <NumberInput label="Wind (kn)" value={f.wind_knots} hasClear onChange={set("wind_knots")} />
            <NumberInput label="Temp (°C)" value={f.temp_c} hasClear onChange={set("temp_c")} />
            <NumberInput label="Fuel (%)" value={f.fuel_pct} hasClear onChange={set("fuel_pct")} />
          </HStack>
          <TextArea label="Note" value={f.note} onChange={set("note")} rows={4}
            description="Limits: wind ≤ 25 kn · temp ≥ 4 °C · fuel 98–100 %" />
          {error && <Banner status="error" title="Report rejected" description={error} role="alert" />}
          <Button type="submit" variant="primary" label={busy ? "Filing…" : "File report"} isLoading={busy} />
        </VStack>
      </form>
    </Card>
  );
}
