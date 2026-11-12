import {
  CartesianGrid, ComposedChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Scatter, Tooltip, XAxis,
  YAxis, ZAxis,
} from "recharts";
import { Text } from "@astryxdesign/core/Text";
import { Limit, Limits, Report } from "./api";
import StatusMark from "./StatusMark";

/*
 * Dot chart per reading, built only from stock Recharts parts (no hand-drawn shapes):
 * GO range = ReferenceArea, limits = labelled ReferenceLine, reading = Scatter point + value label.
 * Status colours are the fixed, validated status pair. Red/green fails CVD separation
 * (deutan ΔE ≈ 4), so in/out never rides on colour alone: the point's position vs the band,
 * the "In/Out of limits" status text and the overshoot text carry it too.
 * In/out comes from the server's code-computed violations — the UI never re-judges a reading.
 */
const GOOD = "#0ca30c";
const CRITICAL = "#d03b3b";
const MUTED = "#898781";
const GRID = "#2c2c2a";
const AXIS = "#383835";

type Field = "wind_knots" | "temp_c" | "fuel_pct";
const FIELDS: Field[] = ["wind_knots", "temp_c", "fuel_pct"];

// Display window only (how much axis to show around the band); never used to judge.
const VIEW: Record<Field, [number, number]> = { wind_knots: [0, 40], temp_c: [-10, 30], fuel_pct: [94, 102] };

const fmt = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1));

function niceStep(span: number): number {
  const raw = span / 6;
  const mag = 10 ** Math.floor(Math.log10(raw));
  return [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw)!;
}

/** Axis window: the display view, widened (to round steps) so extreme readings stay on screen. */
export function domainFor(field: Field, value: number): [number, number] {
  let [lo, hi] = VIEW[field];
  if (value >= lo && value <= hi) return [lo, hi];
  lo = Math.min(lo, value);
  hi = Math.max(hi, value);
  const step = niceStep(hi - lo);
  return [Math.floor(lo / step) * step - (value === lo ? step : 0), Math.ceil(hi / step) * step + (value === hi ? step : 0)];
}

export function ticksFor([lo, hi]: [number, number]): number[] {
  const step = niceStep(hi - lo);
  const out: number[] = [];
  for (let t = Math.ceil(lo / step) * step; t <= hi + 1e-9; t += step) out.push(Number(t.toFixed(6)));
  return out;
}

export function limitText(l: Limit): string {
  if (l.min !== null && l.max !== null) return `${fmt(l.min)}–${fmt(l.max)} ${l.unit}`;
  if (l.max !== null) return `≤ ${fmt(l.max)} ${l.unit}`;
  return `≥ ${fmt(l.min!)} ${l.unit}`;
}

/** Distance outside the band (0 when inside). */
export function overshoot(l: Limit, v: number): number {
  if (l.max !== null && v > l.max) return v - l.max;
  if (l.min !== null && v < l.min) return v - l.min;
  return 0;
}

export function GaugeTooltip({ active, limit, value, out }: { active?: boolean; limit: Limit; value: number; out: boolean }) {
  if (!active) return null;
  const delta = overshoot(limit, value);
  return (
    <div className="gauge-tip">
      <Text weight="semibold" display="block">{limit.label}: {fmt(value)} {limit.unit}</Text>
      <Text type="supporting" display="block">limit {limitText(limit)}</Text>
      <Text type="supporting" display="block">
        {out ? `${delta > 0 ? "+" : "−"}${fmt(Math.abs(delta))} ${limit.unit} ${delta > 0 ? "over" : "under"}` : "within limit"}
      </Text>
    </div>
  );
}

function GaugeChart({ field, limit, value, out }: { field: Field; limit: Limit; value: number; out: boolean }) {
  const domain = domainFor(field, value);
  const [lo, hi] = domain;
  const bandLo = limit.min ?? lo;
  const bandHi = limit.max ?? hi;
  const summary = `${limit.label} ${fmt(value)} ${limit.unit}, ${out ? "outside" : "within"} limit ${limitText(limit)}`;
  const zone = { y1: -0.55, y2: 0.55, ifOverflow: "hidden" as const };

  return (
    <div role="img" aria-label={summary} className="gauge-chart">
      <ResponsiveContainer width="100%" height={78} initialDimension={{ width: 520, height: 78 }}>
        <ComposedChart data={[{ x: value, y: 0 }]} margin={{ top: 18, right: 14, bottom: 0, left: 14 }}>
          <CartesianGrid horizontal={false} stroke={GRID} />
          <XAxis type="number" dataKey="x" domain={domain} ticks={ticksFor(domain)} allowDataOverflow
            tickLine={false} axisLine={{ stroke: AXIS }} tick={{ fill: MUTED, fontSize: 11 }} tickFormatter={fmt} />
          <YAxis type="number" dataKey="y" domain={[-1, 1]} hide />
          <ReferenceArea x1={bandLo} x2={bandHi} {...zone} fill={GOOD} fillOpacity={0.16} />
          {[limit.min, limit.max].filter((v): v is number => v !== null).map((v) => (
            <ReferenceLine key={v} x={v} stroke={GOOD} strokeWidth={1}
              label={{ value: `${fmt(v)} ${limit.unit}`, position: "top", fill: MUTED, fontSize: 11 }} />
          ))}
          <ZAxis range={[110, 110]} />
          <Scatter dataKey="y" fill={out ? CRITICAL : GOOD} isAnimationActive={false} />
          <Tooltip cursor={false} isAnimationActive={false}
            content={({ active }) => <GaugeTooltip active={active} limit={limit} value={value} out={out} />} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function LimitGauges({ r, limits }: { r: Report; limits: Limits }) {
  return (
    <div className="gauges" aria-label="Launch readings against limits">
      <div className="gauge-legend" aria-hidden="true">
        <span><i className="lg-band" />GO range</span>
        <span><i className="lg-line" />limit</span>
        <span><i className="lg-dot" />reading</span>
      </div>
      {FIELDS.map((field) => {
        const limit = limits[field];
        const value = r[field];
        const violation = r.violations.find((v) => v.field === field);
        const out = Boolean(violation);
        const delta = overshoot(limit, value);
        return (
          <div className="gauge-row" key={field} data-testid={`gauge-${field}`} data-state={out ? "out" : "in"}>
            <div className="gauge-label">
              <Text type="supporting" display="block">{limit.label}</Text>
              <Text size="2xl" weight="bold" hasTabularNumbers display="block">
                {fmt(value)}<span className="gauge-unit">{limit.unit}</span>
              </Text>
              <Text type="supporting" display="block">limit {limitText(limit)}</Text>
            </div>
            <GaugeChart field={field} limit={limit} value={value} out={out} />
            <div className="gauge-status">
              <StatusMark tone={out ? "bad" : "good"} strong label={out ? "Out of limits" : "In limits"} />
              {out && delta !== 0 && (
                <Text weight="semibold" hasTabularNumbers display="block">
                  {delta > 0 ? "+" : "−"}{fmt(Math.abs(delta))} {limit.unit} {delta > 0 ? "over" : "under"}
                </Text>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
