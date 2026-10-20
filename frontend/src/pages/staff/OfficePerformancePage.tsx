import { Alert, Badge, Button, ButtonGroup, Card, Col, Row, Table, ToggleButton } from "react-bootstrap";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { useOfficeDetail, type Period } from "@/api/analytics";
import { apiErrorMessage } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { AgingBars, FlowBars, OnTimeTrend } from "@/features/analytics/charts";
import { GradeChip, KpiTile, PERIODS, RateCell, misses, pct } from "@/features/analytics/ui";
import { fmtDate } from "@/utils/format";

function ChartCard({ title, children, height = 240, table }: { title: string; children: React.ReactNode; height?: number; table?: React.ReactNode }) {
  return (
    <Card className="border-0 shadow-sm h-100">
      <Card.Body>
        <div className="small fw-semibold mb-2">{title}</div>
        <div style={{ height }}>{children}</div>
        {table && (
          <details className="mt-2 small">
            <summary className="text-secondary">Ipakita bilang table</summary>
            {table}
          </details>
        )}
      </Card.Body>
    </Card>
  );
}

export function OfficePerformancePage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const period = (params.get("period") as Period) || "90d";
  const q = useOfficeDetail(id, period);

  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const k = d.kpis;
  const c = d.city;
  const vsCity = (a?: number | null, b?: number | null) =>
    a == null || b == null ? null : Math.round((a - b) * 100);
  const diff = vsCity(k.on_time_rate, c.on_time_rate);

  return (
    <div className="analytics-report">
      {(user?.role === "city_admin" || user?.role === "mayor") && (
        <Link to={`/staff/analytics?period=${period}`} className="small text-decoration-none d-print-none">‹ Lahat ng opisina</Link>
      )}
      <div className="d-flex flex-wrap align-items-center gap-2 mt-2 mb-3">
        <div className="me-auto">
          <h1 className="h4 fw-bold mb-0">{d.department.name}</h1>
          <div className="small text-secondary">{d.period.label} · Index {k.index ?? "—"} <GradeChip grade={k.grade} /></div>
        </div>
        <ButtonGroup size="sm" className="d-print-none">
          {PERIODS.map((p) => (
            <ToggleButton key={p.key} id={`p-${p.key}`} type="radio" variant="outline-secondary" value={p.key}
              checked={period === p.key} onChange={() => setParams({ period: p.key })}>{p.label}</ToggleButton>
          ))}
        </ButtonGroup>
        <Button size="sm" className="d-print-none" onClick={() => window.print()}><i className="bi bi-printer me-1" aria-hidden />I-print / PDF</Button>
      </div>

      {k.flags.length > 0 && (
        <Alert variant={k.grade === "attention" ? "danger" : "warning"} className="small">
          <strong>Mga dapat pagtuunan:</strong>
          <ul className="mb-0 ps-3">{k.flags.map((f) => <li key={f}>{f}</li>)}</ul>
        </Alert>
      )}

      <Row className="g-3 mb-3">
        <Col xs={6} lg={2}><KpiTile label="On-time (ARTA)" value={pct(k.on_time_rate)}
          sub={diff == null ? "" : `${diff >= 0 ? "+" : ""}${diff} pts vs city`} tone={misses(k.on_time_rate, 0.85) ? "danger" : undefined} /></Col>
        <Col xs={6} lg={2}><KpiTile label="Unang aksyon" value={pct(k.response_rate)} sub={`city ${pct(c.response_rate)}`} /></Col>
        <Col xs={6} lg={2}><KpiTile label="P1 make-safe ≤4h" value={pct(k.p1_make_safe_rate)} sub={`${k.p1_cases} P1`} /></Col>
        <Col xs={6} lg={2}><KpiTile label="Pagtanggap ≤1 WD" value={pct(k.acceptance_rate)} sub={`${k.returned} ibinalik sa PACD`} /></Col>
        <Col xs={6} lg={2}><KpiTile label="Bukas / overdue" value={`${k.backlog} / ${k.overdue}`} sub={`${k.aging_30} >30 araw`} tone={k.overdue ? "danger" : undefined} /></Col>
        <Col xs={6} lg={2}><KpiTile label="Median · p90 araw" value={`${k.median_days ?? "—"} · ${k.p90_days ?? "—"}`}
          sub={`extension ${pct(k.extension_rate)} · reopen ${pct(k.reopen_rate)}`} /></Col>
      </Row>

      <Row className="g-3 mb-3">
        <Col lg={7}>
          <ChartCard title="On-time rate bawat buwan (vs city average at 85% target)" height={260}
            table={<Table size="sm" className="mb-0"><thead><tr><th>Buwan</th><th>Opisina</th><th>City</th></tr></thead>
              <tbody>{d.trend.map((t, i) => <tr key={t.month}><td>{t.label}</td><td>{pct(t.on_time_rate)}</td><td>{pct(d.city_trend[i]?.on_time_rate)}</td></tr>)}</tbody></Table>}>
            <OnTimeTrend office={d.trend} city={d.city_trend} label={d.department.code} />
          </ChartCard>
        </Col>
        <Col lg={5}>
          <ChartCard title="Natanggap vs naresolba bawat buwan" height={260}
            table={<Table size="sm" className="mb-0"><thead><tr><th>Buwan</th><th>Natanggap</th><th>Naresolba</th></tr></thead>
              <tbody>{d.trend.map((t) => <tr key={t.month}><td>{t.label}</td><td>{t.received}</td><td>{t.resolved}</td></tr>)}</tbody></Table>}>
            <FlowBars office={d.trend} />
          </ChartCard>
        </Col>
      </Row>

      <Row className="g-3 mb-3">
        <Col lg={7}>
          <Card className="border-0 shadow-sm h-100">
            <Card.Body className="p-0">
              <div className="small fw-semibold p-3 pb-2">Bawat division</div>
              <Table responsive size="sm" className="mb-0 small align-middle" style={{ fontVariantNumeric: "tabular-nums" }}>
                <thead className="table-light"><tr><th>Division</th><th className="text-end">Natanggap</th><th className="text-end">Naresolba</th><th>On-time</th><th>Unang aksyon</th><th className="text-end">Bukas</th><th className="text-end">Overdue</th><th className="text-end">Median</th></tr></thead>
                <tbody>
                  {d.divisions.map((v) => (
                    <tr key={v.id}>
                      <td>{v.name}</td><td className="text-end">{v.received}</td><td className="text-end">{v.resolved}</td>
                      <td><RateCell value={v.on_time_rate} target={0.85} /></td><td><RateCell value={v.response_rate} target={0.85} /></td>
                      <td className="text-end">{v.backlog}</td><td className={`text-end ${v.overdue ? "text-danger fw-semibold" : ""}`}>{v.overdue}</td>
                      <td className="text-end">{v.median_days ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={5}>
          <ChartCard title="Edad ng mga bukas na kaso" height={200}
            table={<Table size="sm" className="mb-0"><tbody>{d.aging.map((a) => <tr key={a.bucket}><td>{a.bucket}</td><td>{a.count}</td></tr>)}</tbody></Table>}>
            <AgingBars data={d.aging} />
          </ChartCard>
        </Col>
      </Row>

      <Row className="g-3">
        <Col lg={7}>
          <Card className="border-0 shadow-sm h-100">
            <Card.Body className="p-0">
              <div className="small fw-semibold p-3 pb-2">Pinakamatagal na overdue (top 10)</div>
              {d.oldest_overdue.length === 0 ? <div className="small text-secondary px-3 pb-3">Walang overdue.</div> : (
                <Table responsive size="sm" hover className="mb-0 small align-middle">
                  <thead className="table-light"><tr><th>Ref</th><th>Problema</th><th>Barangay</th><th>Antas</th><th>Target</th><th className="text-end">Lampas</th><th>Escalation</th></tr></thead>
                  <tbody>
                    {d.oldest_overdue.map((o) => (
                      <tr key={o.id}>
                        <td><Link to={`/staff/cases/${o.id}`}>{o.reference_no}</Link></td>
                        <td className="text-truncate" style={{ maxWidth: 220 }}>{o.title}</td>
                        <td>{o.barangay}</td><td>{o.priority ?? "—"}</td><td>{fmtDate(o.due_at)}</td>
                        <td className="text-end text-danger fw-semibold">{o.days_overdue} araw</td>
                        <td>{o.escalation_level ? <Badge bg="dark">L{o.escalation_level}</Badge> : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card.Body>
          </Card>
        </Col>
        <Col lg={5}>
          <Card className="border-0 shadow-sm mb-3">
            <Card.Body className="small">
              <div className="fw-semibold mb-2">Pinakamadalas na isyu ({d.period.label})</div>
              {d.top_issues.map((t) => (
                <div key={t.name} className="d-flex justify-content-between border-bottom py-1"><span>{t.name}</span><span>{t.count}</span></div>
              ))}
            </Card.Body>
          </Card>
          {d.workload.length > 0 && (
            <Card className="border-0 shadow-sm">
              <Card.Body className="small">
                <div className="fw-semibold">Bukas na kaso bawat tauhan</div>
                <div className="text-secondary mb-2">Workload lamang, para sa pagbabalanse ng trabaho; hindi ranking ng tao.</div>
                {d.workload.map((w) => (
                  <div key={w.name} className="d-flex justify-content-between border-bottom py-1"><span>{w.name}</span><span>{w.open}</span></div>
                ))}
              </Card.Body>
            </Card>
          )}
        </Col>
      </Row>
    </div>
  );
}
