import { Card, Col, Row, Table } from "react-bootstrap";

import type { Executive } from "@/api/types";

import { YoyChart } from "./charts";
import { pct } from "./ui";

type Acc = Executive["accomplishment"];
type Block = Acc["month"];

function pts(a?: number | null, b?: number | null) {
  if (a == null || b == null) return null;
  return Math.round((a - b) * 100);
}

function Delta({ a, b, unit = "pts", invert = false }: { a?: number | null; b?: number | null; unit?: string; invert?: boolean }) {
  const d = pts(a, b);
  if (d == null) return <span className="text-secondary">—</span>;
  const good = invert ? d < 0 : d > 0;
  return (
    <span className={d === 0 ? "text-secondary" : good ? "text-success" : "text-danger"}>
      <i className={`bi bi-arrow-${d > 0 ? "up" : d < 0 ? "down" : "right"}-short`} aria-hidden />{d > 0 ? "+" : ""}{d} {unit}
    </span>
  );
}

function Compare({ title, cur, prev }: { title: string; cur: Block; prev: Block }) {
  return (
    <Card className="border-0 shadow-sm h-100">
      <Card.Body>
        <div className="small text-secondary">{title}</div>
        <div className="d-flex align-items-baseline gap-2 flex-wrap">
          <span className="fs-2 fw-bold lh-1">{cur.accomplished}<span className="fs-5 text-secondary">/{cur.received}</span></span>
          <span className="fs-5">naayos ({pct(cur.accomplished_rate)})</span>
        </div>
        <div className="small text-secondary mb-2">{cur.label}{cur.open ? ` · ${cur.open} bukas pa` : ""}</div>
        <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
          <thead><tr><th /><th className="text-end">Ngayon</th><th className="text-end">Nakaraang taon</th><th className="text-end">Pagbabago</th></tr></thead>
          <tbody>
            <tr><td>Natanggap</td><td className="text-end">{cur.received}</td><td className="text-end">{prev.has_data ? prev.received : "—"}</td>
              <td className="text-end">{prev.has_data && prev.received ? `${cur.received >= prev.received ? "+" : ""}${Math.round((cur.received / prev.received - 1) * 100)}%` : "—"}</td></tr>
            <tr><td title="Patas na paghahambing: parehong panukat para sa lahat ng buwan">Naayos ≤30 araw</td><td className="text-end fw-semibold">{pct(cur.within_30d_rate)}</td>
              <td className="text-end">{prev.has_data ? pct(prev.within_30d_rate) : "—"}</td><td className="text-end">{prev.has_data ? <Delta a={cur.within_30d_rate} b={prev.within_30d_rate} /> : "—"}</td></tr>
            <tr><td>On-time (ARTA)</td><td className="text-end">{pct(cur.on_time_rate)}</td><td className="text-end">{prev.has_data ? pct(prev.on_time_rate) : "—"}</td>
              <td className="text-end">{prev.has_data ? <Delta a={cur.on_time_rate} b={prev.on_time_rate} /> : "—"}</td></tr>
            <tr><td>Median na araw</td><td className="text-end">{cur.median_days ?? "—"}</td><td className="text-end">{prev.has_data ? prev.median_days ?? "—" : "—"}</td>
              <td className="text-end">{prev.has_data && cur.median_days != null && prev.median_days != null
                ? <span className={cur.median_days < prev.median_days ? "text-success" : cur.median_days > prev.median_days ? "text-danger" : "text-secondary"}>
                  {cur.median_days - prev.median_days > 0 ? "+" : ""}{(cur.median_days - prev.median_days).toFixed(1)} araw</span> : "—"}</td></tr>
          </tbody>
        </Table>
        {!prev.has_data && <div className="small text-secondary mt-1">Walang datos para sa parehong panahon noong nakaraang taon.</div>}
      </Card.Body>
    </Card>
  );
}

/** "This month we accomplished 78/100" + fair year-on-year comparison. */
export function AccomplishmentSection({ a, lang }: { a: Acc; lang: "fil" | "en" }) {
  return (
    <Card className="border-0 shadow-sm mb-3">
      <Card.Body>
        <div className="fw-semibold">{lang === "en" ? "Accomplishment and year-on-year comparison" : "Accomplishment at paghahambing taon-taon"}</div>
        <div className="small text-secondary mb-3">
          Sa mga problemang <strong>natanggap</strong> sa panahong iyon, ilan ang naayos na. Ang "naayos ≤{a.mature_days} araw" ang patas na
          panukat sa paghahambing (pareho ang palugit sa bawat buwan); ang "naayos na" ay mas mataas sa mas lumang buwan dahil mas matagal na silang naaksyunan.
        </div>
        <Row className="g-3 mb-3">
          <Col lg={6}><Compare title="Ngayong buwan vs parehong buwan noong nakaraang taon" cur={a.month} prev={a.month_last_year} /></Col>
          <Col lg={6}><Compare title="Year-to-date vs parehong panahon noong nakaraang taon" cur={a.ytd} prev={a.ytd_last_year} /></Col>
        </Row>
        <Row className="g-3">
          <Col lg={7}>
            <div className="small fw-semibold mb-1">Naayos sa loob ng {a.mature_days} araw, bawat buwan</div>
            <div style={{ height: 240 }}><YoyChart points={a.trend} /></div>
            <details className="small mt-1"><summary className="text-secondary">Ipakita bilang table</summary>
              <Table size="sm" className="mb-0"><thead><tr><th>Buwan</th><th className="text-end">Ngayon</th><th className="text-end">Nakaraang taon</th></tr></thead>
                <tbody>{a.trend.map((t) => <tr key={t.month}><td>{t.month}</td><td className="text-end">{pct(t.this_year.within_30d_rate)}</td>
                  <td className="text-end">{pct(t.last_year?.within_30d_rate)}</td></tr>)}</tbody></Table>
            </details>
          </Col>
          <Col lg={5}>
            <div className="small fw-semibold mb-1">Bawat isyu, year-to-date</div>
            <Table size="sm" className="small mb-2" style={{ fontVariantNumeric: "tabular-nums" }}>
              <thead className="table-light"><tr><th>Isyu</th><th className="text-end">Naayos</th><th className="text-end">≤30 araw</th><th className="text-end">vs LY</th></tr></thead>
              <tbody>{a.by_issue.filter((i) => i.this_year.received).map((i) => (
                <tr key={i.code}><td>{lang === "en" ? i.name_en : i.name}</td>
                  <td className="text-end">{i.this_year.accomplished}/{i.this_year.received}</td>
                  <td className="text-end">{pct(i.this_year.within_30d_rate)}</td>
                  <td className="text-end"><Delta a={i.this_year.within_30d_rate} b={i.last_year.received ? i.last_year.within_30d_rate : null} /></td></tr>
              ))}</tbody>
            </Table>
            <div className="small fw-semibold mb-1">Bawat taon</div>
            <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
              <thead className="table-light"><tr><th>Taon</th><th className="text-end">Naayos</th><th className="text-end">≤30 araw</th><th className="text-end">On-time</th><th className="text-end">Median</th></tr></thead>
              <tbody>{a.years.map((y) => (
                <tr key={y.year}><td>{y.year}{y.partial && <span className="text-secondary" title="Hindi buong taon"> *</span>}</td>
                  <td className="text-end">{y.accomplished}/{y.received}</td><td className="text-end">{pct(y.within_30d_rate)}</td>
                  <td className="text-end">{pct(y.on_time_rate)}</td><td className="text-end">{y.median_days ?? "—"}</td></tr>
              ))}</tbody>
            </Table>
            <div className="small text-secondary">* hindi buong taon</div>
          </Col>
        </Row>
      </Card.Body>
    </Card>
  );
}
