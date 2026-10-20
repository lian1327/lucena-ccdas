import { useMemo, useState } from "react";
import { Button, Table } from "react-bootstrap";

import type { ExecBarangay } from "@/api/types";

// Sequential blue ramp (validated reference palette), light → dark
const RAMP = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
const shade = (v: number, max: number) => (v <= 0 || max <= 0 ? RAMP[0] : RAMP[Math.min(RAMP.length - 1, 1 + Math.floor((v / max) * (RAMP.length - 2)))]);

type Cat = { code: string; name: string };

/** Barangay × issue: darker = more problems, compared within each issue column. Click a column to rank by it. */
export function BarangayHeatmap({ rows, cats }: { rows: ExecBarangay[]; cats: Cat[] }) {
  const [sortBy, setSortBy] = useState<string>("count");
  const [all, setAll] = useState(false);
  const max = useMemo(() => Object.fromEntries(cats.map((c) => [c.code, Math.max(5, ...rows.map((r) => r.cells[c.code] ?? 0))])), [rows, cats]);
  const sorted = useMemo(() => [...rows].sort((a, b) => {
    const va = sortBy === "count" ? a.count : sortBy === "per_1000" ? a.per_1000 ?? 0 : a.cells[sortBy] ?? 0;
    const vb = sortBy === "count" ? b.count : sortBy === "per_1000" ? b.per_1000 ?? 0 : b.cells[sortBy] ?? 0;
    return vb - va || a.name.localeCompare(b.name);
  }), [rows, sortBy]);
  const shown = all ? sorted : sorted.slice(0, 15);
  const th = (key: string, text: string, title?: string) => (
    <th key={key} role="button" title={title ?? `I-rank ayon sa ${text}`} onClick={() => setSortBy(key)}
      className={`text-center small ${sortBy === key ? "text-primary" : ""}`} style={{ minWidth: 64, verticalAlign: "bottom" }}>
      {text}{sortBy === key && <i className="bi bi-caret-down-fill ms-1" aria-label="naka-rank dito" />}
    </th>
  );
  return (
    <>
      <Table responsive size="sm" className="mb-1 small align-middle heatmap" style={{ fontVariantNumeric: "tabular-nums" }}>
        <thead>
          <tr>
            <th style={{ minWidth: 150 }}>Barangay</th>
            {th("count", "Kabuuan")}
            {th("per_1000", "Bawat 1,000", "Bawat 1,000 residente (populasyon sa Barangay table)")}
            {cats.map((c) => th(c.code, c.name))}
            <th className="text-end small">Bukas · overdue</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr key={r.id}>
              <td><span className="text-secondary me-1">{i + 1}.</span>{r.name}
                {r.change != null && Math.max(r.prev, r.count) >= 5 && Math.abs(r.change) >= .25 && (
                  <span className={`ms-1 ${r.change > 0 ? "text-danger" : "text-success"}`} title={`${r.prev} → ${r.count} vs nakaraang buwan`}>
                    <i className={`bi bi-arrow-${r.change > 0 ? "up" : "down"}-short`} aria-hidden />{Math.abs(Math.round(r.change * 100))}%
                  </span>
                )}
              </td>
              <td className="text-center fw-semibold">{r.count}</td>
              <td className="text-center text-secondary">{r.per_1000 ?? "—"}</td>
              {cats.map((c) => {
                const v = r.cells[c.code] ?? 0;
                const bg = shade(v, max[c.code]);
                const dark = RAMP.indexOf(bg) >= 4;
                return (
                  <td key={c.code} className="text-center" style={{ background: bg, color: dark ? "#fff" : v ? "#1d1d1b" : "#b5b3ad", border: "2px solid #fff" }}
                    title={`${r.name} · ${c.name}: ${v}`}>{v || "·"}</td>
                );
              })}
              <td className="text-end">{r.open_now} · <span className={r.overdue_now ? "text-danger" : ""}>{r.overdue_now}</span></td>
            </tr>
          ))}
        </tbody>
      </Table>
      <div className="d-flex flex-wrap align-items-center gap-2 small text-secondary">
        <span>Mas madilim = mas maraming problema sa isyung iyon (ihinahambing sa loob ng bawat column; ang pinakamadilim ay ≥5 o ang pinakamataas sa column).</span>
        <span className="d-inline-flex align-items-center gap-1" aria-hidden>
          kaunti {RAMP.slice(1).map((c) => <span key={c} style={{ width: 14, height: 10, background: c, display: "inline-block" }} />)} marami
        </span>
        {rows.length > 15 && <Button variant="link" size="sm" className="p-0 ms-auto d-print-none" onClick={() => setAll((x) => !x)}>
          {all ? "Top 15 lang" : `Ipakita lahat (${rows.length})`}</Button>}
      </div>
    </>
  );
}
