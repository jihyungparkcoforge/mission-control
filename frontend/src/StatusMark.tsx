/*
 * Status shown as a small shape + plain text — no pill, no filled background.
 * Shape carries the meaning as well as colour (CVD-safe): good ●, bad ◆, warn ▲, info/neutral ■.
 * Pass `width` wherever the same slot shows different statuses so it never resizes with its label.
 */
export type Tone = "good" | "bad" | "warn" | "info" | "neutral";

export default function StatusMark({ tone, label, width, strong = false }: {
  tone: Tone; label: string; width?: number; strong?: boolean;
}) {
  return (
    <span className={`status-mark tone-${tone}${strong ? " strong" : ""}`} style={width ? { width } : undefined}
      data-tone={tone}>
      <span className="status-glyph" aria-hidden="true" />
      <span className="status-label">{label}</span>
    </span>
  );
}
