import { Alert, Button, Table } from "react-bootstrap";
import { Link, useSearchParams } from "react-router-dom";

import { useExecutive } from "@/api/analytics";
import { apiErrorMessage } from "@/api/client";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { LGU_NAME } from "@/config";
import { InsightList, change } from "@/features/analytics/exec";
import { pct } from "@/features/analytics/ui";

const T = {
  en: {
    title: "Monthly Citizen Concerns Report", to: "For the City Mayor", summary: "1. Summary", findings: "2. Key findings",
    brgy: "3. Barangays with the most problems", issues: "4. Problems by issue", offices: "5. Office performance (ARTA)",
    fc: "6. Expected next month", rec: "7. Recommendations", prepared: "Prepared by", noted: "Noted by",
    note: "Counts are problems (reports of the same problem are merged). Forecasts are estimates with an 80% range.",
  },
  fil: {
    title: "Buwanang Ulat ng mga Concern ng Mamamayan", to: "Para sa Punong Lungsod", summary: "1. Buod", findings: "2. Mga natuklasan",
    brgy: "3. Mga barangay na may pinakamaraming problema", issues: "4. Problema ayon sa isyu", offices: "5. Performance ng mga opisina (ARTA)",
    fc: "6. Inaasahan sa susunod na buwan", rec: "7. Mga rekomendasyon", prepared: "Inihanda ni", noted: "Binigyang-pansin ni",
    note: "Ang bilang ay problema (pinagsama ang magkaparehong report). Ang tantiya ay may 80% na saklaw.",
  },
};

/** A4 printable monthly report for the Mayor, from the same data as the Executive tab. */
export default function ExecutiveReportPage() {
  const [params] = useSearchParams();
  const lang = (params.get("lang") === "en" ? "en" : "fil") as "fil" | "en";
  const L = T[lang];
  const q = useExecutive(params.get("month") ?? undefined);
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const t = d.totals;
  const tbl = { size: "sm" as const, bordered: true, className: "small mb-3", style: { fontVariantNumeric: "tabular-nums" } };
  const sentence = lang === "en"
    ? `In ${d.label}, the city received ${t.problems} problems from ${t.reports} citizen reports across ${t.barangays_reporting} barangays (${change(t.change)} vs ${d.prev_label}). ${t.resolved} were resolved; ${t.open_now} remain open, ${t.overdue_now} of them past their ARTA target. On-time resolution was ${pct(d.city.on_time_rate)} against an 85% target.`
    : `Noong ${d.label}, ${t.problems} na problema ang natanggap mula sa ${t.reports} na report ng mamamayan sa ${t.barangays_reporting} barangay (${change(t.change)} kumpara sa ${d.prev_label}). ${t.resolved} ang naayos; ${t.open_now} pa ang bukas at ${t.overdue_now} dito ang lampas na sa ARTA target. Ang on-time ay ${pct(d.city.on_time_rate)} (target 85%).`;
  return (
    <div className="analytics-report bg-white p-3 p-md-4 rounded shadow-sm exec-report" style={{ maxWidth: 920 }}>
      <div className="d-flex gap-2 mb-3 d-print-none">
        <Link to={`/staff/executive?month=${d.month}`} className="small me-auto">‹ Executive</Link>
        <Link to={`?month=${d.month}&lang=${lang === "en" ? "fil" : "en"}`} className="btn btn-sm btn-outline-secondary">{lang === "en" ? "Filipino" : "English"}</Link>
        <Button size="sm" onClick={() => window.print()}><i className="bi bi-printer me-1" aria-hidden />I-print / PDF</Button>
      </div>
      <div className="text-center mb-3">
        <div className="small text-secondary">Republic of the Philippines · {LGU_NAME}</div>
        <h1 className="h5 fw-bold mt-1 mb-0">{L.title}</h1>
        <div>{d.label}{d.partial ? (lang === "en" ? " (to date)" : " (hanggang ngayon)") : ""} · {L.to}</div>
      </div>

      <h2 className="h6 fw-bold">{L.summary}</h2>
      <p className="small">{sentence}</p>

      <h2 className="h6 fw-bold">{L.findings}</h2>
      <div className="mb-3"><InsightList items={d.insights} lang={lang} /></div>

      <h2 className="h6 fw-bold">{L.brgy}</h2>
      <Table {...tbl}>
        <thead className="table-light"><tr><th>#</th><th>Barangay</th><th className="text-end">{lang === "en" ? "Problems" : "Problema"}</th>
          <th className="text-end">/1,000</th><th className="text-end">{lang === "en" ? "Change" : "Pagbabago"}</th><th>{lang === "en" ? "Top issue" : "Pangunahing isyu"}</th>
          <th className="text-end">{lang === "en" ? "Open · overdue" : "Bukas · overdue"}</th></tr></thead>
        <tbody>{d.barangays.slice(0, 10).map((b) => (
          <tr key={b.id}><td>{b.rank}</td><td>{b.name}</td><td className="text-end">{b.count}</td><td className="text-end">{b.per_1000 ?? "—"}</td>
            <td className="text-end">{change(b.change)}</td><td>{b.top_issue}</td><td className="text-end">{b.open_now} · {b.overdue_now}</td></tr>
        ))}</tbody>
      </Table>

      <h2 className="h6 fw-bold">{L.issues}</h2>
      <Table {...tbl}>
        <thead className="table-light"><tr><th>{lang === "en" ? "Issue" : "Isyu"}</th><th className="text-end">{d.label}</th><th className="text-end">{lang === "en" ? "Previous" : "Nakaraan"}</th>
          <th className="text-end">{lang === "en" ? "Change" : "Pagbabago"}</th><th>{lang === "en" ? "Top barangays" : "Nangungunang barangay"}</th></tr></thead>
        <tbody>{d.categories.map((c) => {
          const r = d.rankings.find((x) => x.code === c.code);
          return (<tr key={c.code}><td>{lang === "en" ? c.name_en : c.name}</td><td className="text-end">{c.count}</td><td className="text-end">{c.prev}</td>
            <td className="text-end">{change(c.change)}</td><td>{r?.top.slice(0, 3).map((b) => `${b.barangay} (${b.count})`).join(", ")}</td></tr>);
        })}</tbody>
      </Table>

      <h2 className="h6 fw-bold">{L.offices}</h2>
      <Table {...tbl}>
        <thead className="table-light"><tr><th>{lang === "en" ? "Office" : "Opisina"}</th><th className="text-end">Index</th><th className="text-end">On-time</th>
          <th className="text-end">{lang === "en" ? "Proof" : "Patunay"}</th><th className="text-end">{lang === "en" ? "Open · overdue" : "Bukas · overdue"}</th><th>{lang === "en" ? "Concerns" : "Dahilan"}</th></tr></thead>
        <tbody>{d.offices.map((o) => (
          <tr key={o.code}><td>{o.code}</td><td className="text-end">{o.index ?? "—"}</td><td className="text-end">{pct(o.on_time_rate)}</td>
            <td className="text-end">{pct(o.proof_rate)}</td><td className="text-end">{o.backlog} · {o.overdue}</td><td>{o.flags.slice(0, 2).join("; ")}</td></tr>
        ))}</tbody>
      </Table>

      <h2 className="h6 fw-bold">{L.fc} ({d.forecast.label})</h2>
      <Table {...tbl}>
        <thead className="table-light"><tr><th>{lang === "en" ? "Issue" : "Isyu"}</th><th className="text-end">{lang === "en" ? "Estimate" : "Tantiya"}</th>
          <th className="text-end">{lang === "en" ? "Range (80%)" : "Saklaw (80%)"}</th></tr></thead>
        <tbody>{d.forecast.categories.map((c) => (
          <tr key={c.code}><td>{lang === "en" ? d.categories.find((x) => x.code === c.code)?.name_en ?? c.name : c.name}</td><td className="text-end">{Math.round(c.estimate)}</td><td className="text-end">{c.low}–{c.high}</td></tr>
        ))}</tbody>
      </Table>

      <h2 className="h6 fw-bold">{L.rec}</h2>
      <ol className="small">
        {d.resources.filter((r) => r.status === "short").map((r) => (
          <li key={r.code} className="mb-1"><strong>{r.code}</strong>: {lang === "en" ? r.text_en : r.text}
            {r.focus_barangays.length > 0 && <> {lang === "en" ? "Focus on" : "Tutukan ang"} {r.focus_barangays.map((b) => b.barangay).join(", ")}.</>}</li>
        ))}
        {d.insights.filter((i) => i.kind === "persistent").slice(0, 3).map((i, k) => <li key={`p${k}`} className="mb-1">{lang === "en" ? i.text_en : i.text}</li>)}
      </ol>
      <p className="small text-secondary">{L.note}</p>

      <div className="d-flex justify-content-around text-center small mt-5">
        {[[L.prepared, "City Administrator"], [L.noted, "City Mayor"]].map(([l, n]) => (
          <div key={l} style={{ minWidth: 220 }}><div className="border-top pt-1 fw-semibold">{n}</div><div className="text-secondary">{l}</div></div>
        ))}
      </div>
    </div>
  );
}
