import { useState } from "react";
import { Alert, Button, ButtonGroup, Card, Col, OverlayTrigger, Popover, Row, Table, ToggleButton } from "react-bootstrap";
import { Link, useSearchParams } from "react-router-dom";

import { downloadScorecardCsv, useScorecard, type Period } from "@/api/analytics";
import { apiErrorMessage } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { GradeChip, KpiTile, PERIODS, RateCell, misses, pct } from "@/features/analytics/ui";
import { LGU_NAME } from "@/config";

const METHOD = (
  <Popover>
    <Popover.Header>Paano kinukwenta</Popover.Header>
    <Popover.Body className="small">
      Bawat opisina ay sinusukat laban sa <strong>sarili nitong</strong> mga target: ARTA na target na petsa,
      target ng antas ng prayoridad (P1 = 4 oras), at pagtanggap sa loob ng 1 working day. Hindi pinaghahambing ang
      bilis ng magkakaibang uri ng trabaho.
      <hr className="my-2" />
      <strong>Performance index</strong> = 40% on-time · 20% unang aksyon · 15% pagtanggap · 15% kalusugan ng backlog
      (1 − overdue/bukas) · 10% kalidad (hindi na-reopen at hindi bumalik ang problema sa loob ng 30 araw). Kailangan ng ≥5 naresolba sa panahon para magkaroon ng index.
    </Popover.Body>
  </Popover>
);

export function AnalyticsPage() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const period = (params.get("period") as Period) || "90d";
  const q = useScorecard(period);
  const [downloading, setDownloading] = useState(false);
  const allOffices = user?.role === "city_admin" || user?.role === "mayor";

  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const c = d.city;
  const attention = d.offices.filter((o) => o.grade === "attention");

  return (
    <div className="analytics-report">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
        <div className="me-auto">
          <h1 className="h4 fw-bold mb-0">Performance ng mga Opisina</h1>
          <div className="small text-secondary">
            {LGU_NAME} · {d.period.label} · laban sa ARTA at service standards
            <OverlayTrigger trigger={["hover", "focus"]} overlay={METHOD}>
              <Button variant="link" size="sm" className="p-0 ms-2 align-baseline">Paano kinukwenta?</Button>
            </OverlayTrigger>
          </div>
        </div>
        <ButtonGroup size="sm" className="d-print-none">
          {PERIODS.map((p) => (
            <ToggleButton key={p.key} id={`p-${p.key}`} type="radio" variant="outline-secondary" value={p.key}
              checked={period === p.key} onChange={() => setParams({ period: p.key })}>{p.label}</ToggleButton>
          ))}
        </ButtonGroup>
        <Button size="sm" variant="outline-primary" className="d-print-none" disabled={downloading}
          onClick={async () => { setDownloading(true); try { await downloadScorecardCsv(period); } finally { setDownloading(false); } }}>
          <i className="bi bi-filetype-csv me-1" aria-hidden />CSV
        </Button>
        <Button size="sm" variant="primary" className="d-print-none" onClick={() => window.print()}>
          <i className="bi bi-printer me-1" aria-hidden />I-print / PDF
        </Button>
      </div>

      <Row className="g-3 mb-3">
        <Col xs={6} lg={2}><KpiTile label="Natanggap" value={c.received} sub={`${c.resolved} naresolba`} /></Col>
        <Col xs={6} lg={2}><KpiTile label="On-time (ARTA)" value={pct(c.on_time_rate)} sub="naresolba sa target" tone={misses(c.on_time_rate, d.targets.on_time) ? "danger" : undefined}
          tip="Bahagdan ng naresolba na na-validate bago o sa target na petsa (kasama ang isang lehitimong extension)." /></Col>
        <Col xs={6} lg={2}><KpiTile label="Unang aksyon" value={pct(c.response_rate)} sub="sa loob ng target" tip="Unang field action (inspeksyon o make-safe) sa loob ng target ng antas." /></Col>
        <Col xs={6} lg={2}><KpiTile label="P1 make-safe ≤4h" value={pct(c.p1_make_safe_rate)} sub={`${c.p1_cases} P1 cases`} tone={misses(c.p1_make_safe_rate, 0.9) ? "danger" : undefined} /></Col>
        <Col xs={6} lg={2}><KpiTile label="Bukas ngayon" value={c.backlog} sub={`${c.overdue} overdue · ${c.aging_30} >30 araw`} tone={c.overdue ? "danger" : undefined} /></Col>
        <Col xs={6} lg={2}><KpiTile label="Median na araw" value={c.median_days ?? "—"} sub="pagpasa → validation" tip="Konteksto lamang; hindi ginagamit sa index dahil iba-iba ang uri ng trabaho." /></Col>
      </Row>

      {allOffices && attention.length > 0 && (
        <Alert variant="danger" className="small">
          <i className="bi bi-exclamation-triangle-fill me-1" aria-hidden />
          <strong>Kailangan ng aksyon:</strong>{" "}
          {attention.map((o, i) => (
            <span key={o.code}>{i > 0 && " · "}<Link to={`/staff/analytics/${o.department_id}?period=${period}`}>{o.name}</Link> ({o.flags[0]})</span>
          ))}
        </Alert>
      )}

      <Card className="border-0 shadow-sm mb-3">
        <Card.Body className="p-0">
          <Table responsive hover className="mb-0 align-middle small">
            <thead className="table-light">
              <tr>
                <th>#</th><th>Opisina</th><th className="text-end">Index</th><th>Grado</th>
                <th className="text-end">Natanggap</th><th className="text-end">Naresolba</th>
                <th>On-time</th><th>Unang aksyon</th><th>Pagtanggap ≤1 WD</th>
                <th className="text-end">Bukas</th><th className="text-end">Overdue</th><th className="text-end">Median araw</th>
                <th>Dahilan</th>
              </tr>
            </thead>
            <tbody style={{ fontVariantNumeric: "tabular-nums" }}>
              {d.offices.map((o) => (
                <tr key={o.code}>
                  <td className="text-secondary">{o.rank ?? "—"}</td>
                  <td>
                    <Link to={`/staff/analytics/${o.department_id}?period=${period}`} className="fw-semibold text-decoration-none">{o.code}</Link>
                    <div className="text-secondary text-truncate" style={{ maxWidth: 220 }}>{o.name}</div>
                  </td>
                  <td className="text-end fw-bold fs-6">{o.index ?? "—"}</td>
                  <td><GradeChip grade={o.grade} /></td>
                  <td className="text-end">{o.received}</td>
                  <td className="text-end">{o.resolved}</td>
                  <td><RateCell value={o.on_time_rate} target={d.targets.on_time} /></td>
                  <td><RateCell value={o.response_rate} target={d.targets.response} /></td>
                  <td><RateCell value={o.acceptance_rate} target={d.targets.acceptance} /></td>
                  <td className="text-end">{o.backlog}</td>
                  <td className={`text-end ${o.overdue ? "text-danger fw-semibold" : ""}`}>{o.overdue}</td>
                  <td className="text-end">{o.median_days ?? "—"}</td>
                  <td style={{ minWidth: 220 }}>
                    {o.flags.length === 0 ? <span className="text-secondary">Pasado sa lahat ng target</span>
                      : <ul className="mb-0 ps-3">{o.flags.map((f) => <li key={f}>{f}</li>)}</ul>}
                  </td>
                </tr>
              ))}
              <tr className="table-light fw-semibold">
                <td /><td>City-wide</td><td className="text-end">{c.index ?? "—"}</td><td><GradeChip grade={c.grade} /></td>
                <td className="text-end">{c.received}</td><td className="text-end">{c.resolved}</td>
                <td><RateCell value={c.on_time_rate} target={d.targets.on_time} /></td>
                <td><RateCell value={c.response_rate} target={d.targets.response} /></td>
                <td><RateCell value={c.acceptance_rate} target={d.targets.acceptance} /></td>
                <td className="text-end">{c.backlog}</td><td className="text-end">{c.overdue}</td>
                <td className="text-end">{c.median_days ?? "—"}</td><td />
              </tr>
            </tbody>
          </Table>
        </Card.Body>
      </Card>
      <p className="small text-secondary">
        Ang itim na guhit sa bawat bar ay ang target. Ang "median araw" ay konteksto lamang: natural na mas matagal
        ang road repair (20 WD sa ARTA) kaysa sa koleksyon ng basura (3 WD).
      </p>
    </div>
  );
}
