import type { ReactNode } from "react";
import { Card, OverlayTrigger, Tooltip } from "react-bootstrap";

export const pct = (v: number | null | undefined) => (v == null ? "—" : `${Math.round(v * 100)}%`);
/** Same rule as the backend flags: compare whole percents, so "85% vs 85% target" is a pass. */
export const misses = (v: number | null | undefined, target: number) =>
  v != null && Math.round(v * 100) < Math.round(target * 100);

/** Validated palette (dataviz reference): slot 1 blue, slot 2 orange; status colors reserved for grades. */
export const C = {
  office: "#2a78d6",
  city: "#898781",
  received: "#2a78d6",
  resolved: "#eb6834",
  target: "#d03b3b",
  grid: "#e1e0d9",
  ink2: "#52514e",
};

const GRADE: Record<string, { label: string; icon: string; bg: string; fg: string }> = {
  good: { label: "Mahusay", icon: "check-circle-fill", bg: "#e7f6e7", fg: "#006300" },
  watch: { label: "Bantayan", icon: "eye-fill", bg: "#fff4d9", fg: "#7a5200" },
  attention: { label: "Kailangan ng aksyon", icon: "exclamation-triangle-fill", bg: "#fbe4e4", fg: "#9b1c1c" },
  insufficient: { label: "Kulang ang datos", icon: "dash-circle", bg: "#f0efec", fg: "#52514e" },
};

/** Status always shown with icon + label, never color alone. */
export function GradeChip({ grade }: { grade: string }) {
  const g = GRADE[grade] ?? GRADE.insufficient;
  return (
    <span className="badge rounded-pill fw-semibold" style={{ background: g.bg, color: g.fg }}>
      <i className={`bi bi-${g.icon} me-1`} aria-hidden />{g.label}
    </span>
  );
}

/** Rate vs its target: number + thin bar + target tick. */
export function RateCell({ value, target }: { value: number | null | undefined; target?: number }) {
  if (value == null) return <span className="text-secondary">—</span>;
  const miss = target != null && Math.round(value * 100) < Math.round(target * 100);
  return (
    <div style={{ minWidth: 84 }}>
      <div className={`fw-semibold ${miss ? "text-danger" : ""}`} style={{ fontVariantNumeric: "tabular-nums" }}>
        {miss && <i className="bi bi-arrow-down-short" aria-label="below target" />}{pct(value)}
      </div>
      <div className="position-relative" style={{ height: 4, background: C.grid, borderRadius: 2 }}>
        <div style={{ width: `${Math.min(100, value * 100)}%`, height: 4, borderRadius: 2, background: miss ? "#d03b3b" : C.office }} />
        {target != null && (
          <div title={`target ${pct(target)}`} style={{ position: "absolute", left: `${target * 100}%`, top: -3, width: 2, height: 10, background: "#0b0b0b" }} />
        )}
      </div>
    </div>
  );
}

export function KpiTile({ label, value, sub, tip, tone }: { label: string; value: ReactNode; sub?: ReactNode; tip?: string; tone?: "danger" }) {
  const body = (
    <Card className="h-100 border-0 shadow-sm">
      <Card.Body className="py-3">
        <div className="small text-secondary">{label}{tip && <i className="bi bi-info-circle ms-1" aria-hidden />}</div>
        <div className={`fs-3 fw-bold lh-sm ${tone === "danger" ? "text-danger" : ""}`}>{value}</div>
        {sub && <div className="small text-secondary">{sub}</div>}
      </Card.Body>
    </Card>
  );
  return tip ? <OverlayTrigger overlay={<Tooltip>{tip}</Tooltip>}>{body}</OverlayTrigger> : body;
}

export const PERIODS = [
  { key: "this_month", label: "Ngayong buwan" },
  { key: "last_month", label: "Nakaraang buwan" },
  { key: "quarter", label: "Quarter" },
  { key: "90d", label: "90 araw" },
  { key: "12m", label: "12 buwan" },
] as const;
