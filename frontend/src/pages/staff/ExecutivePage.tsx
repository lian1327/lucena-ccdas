import { useState } from "react";
import { Alert, Badge, Button, ButtonGroup, Card, Col, Form, Row, Table, ToggleButton } from "react-bootstrap";
import { Link, useSearchParams } from "react-router-dom";

import { downloadBarangayCsv, useExecutive } from "@/api/analytics";
import { apiErrorMessage } from "@/api/client";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { ForecastChart } from "@/features/analytics/charts";
import { InsightList, change } from "@/features/analytics/exec";
import { BarangayHeatmap } from "@/features/analytics/Heatmap";
import { GradeChip, KpiTile, pct } from "@/features/analytics/ui";

/** Executive Decision Support: the Mayor's monthly picture. */
export default function ExecutivePage() {
  const [params, setParams] = useSearchParams();
  const month = params.get("month") ?? undefined;
  const [lang, setLang] = useState<"fil" | "en">("fil");
  const [fcCat, setFcCat] = useState<string>("drainage");
  const q = useExecutive(month);
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const t = d.totals;
  const cats = d.categories.map((c) => ({ code: c.code, name: c.name }));
  const fc = d.forecast.categories.find((c) => c.code === fcCat) ?? d.forecast.categories[0];
  const attention = d.offices.filter((o) => o.grade === "attention");
  const nowMonth = new Date().toISOString().slice(0, 7);

  return (
    <div className="analytics-report">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
        <div className="me-auto">
          <h1 className="h4 fw-bold mb-0">Executive: kalagayan ng lungsod</h1>
          <div className="small text-secondary">
            {d.label}{d.partial && " (hanggang ngayon)"} · bilang ng <strong>problema</strong> (pinagsama ang magkaparehong report) · vs {d.prev_label}
          </div>
        </div>
        <Form.Control type="month" size="sm" style={{ width: 160 }} value={d.month} max={nowMonth}
          onChange={(e) => e.target.value && setParams({ month: e.target.value })} aria-label="Buwan" />
        <ButtonGroup size="sm">
          {(["fil", "en"] as const).map((l) => (
            <ToggleButton key={l} id={`lang-${l}`} type="radio" variant="outline-secondary" value={l} checked={lang === l}
              onChange={() => setLang(l)}>{l === "fil" ? "Filipino" : "English"}</ToggleButton>
          ))}
        </ButtonGroup>
        <Button size="sm" variant="outline-primary" onClick={() => downloadBarangayCsv(d.month)}><i className="bi bi-filetype-csv me-1" aria-hidden />CSV</Button>
        <Link to={`/staff/executive/report?month=${d.month}&lang=${lang}`} className="btn btn-sm btn-primary">
          <i className="bi bi-file-earmark-text me-1" aria-hidden />Monthly report
        </Link>
      </div>
      {d.partial && <Alert variant="info" className="small py-2">Hindi pa tapos ang buwan: ang paghahambing ay sa parehong bilang ng araw ng nakaraang buwan.</Alert>}

      <Row className="g-3 mb-3">
        <Col xs={6} lg={2}><KpiTile label="Mga problema" value={t.problems} sub={`${change(t.change)} vs nakaraang buwan`} /></Col>
        <Col xs={6} lg={2}><KpiTile label="Mga nag-report" value={t.reports} sub="kasama ang magkaparehong report"
          tip="Bawat taong nag-report, kahit pareho ang problema. Ipinapakita kung gaano karami ang apektado." /></Col>
        <Col xs={6} lg={2}><KpiTile label="Naayos" value={t.resolved} sub="ngayong buwan" /></Col>
        <Col xs={6} lg={2}><KpiTile label="Bukas · overdue" value={`${t.open_now} · ${t.overdue_now}`} sub="ngayon" tone={t.overdue_now ? "danger" : undefined} /></Col>
        <Col xs={6} lg={2}><KpiTile label="On-time (ARTA)" value={pct(d.city.on_time_rate)} sub={`index ${d.city.index ?? "—"}`} /></Col>
        <Col xs={6} lg={2}><KpiTile label="May patunay" value={pct(d.city.proof_rate)} sub="before/after + lokasyon" /></Col>
      </Row>

      <Row className="g-3 mb-3">
        <Col lg={7}>
          <Card className="border-0 shadow-sm h-100">
            <Card.Body>
              <div className="fw-semibold mb-2"><i className="bi bi-lightbulb me-1" aria-hidden />Mga natuklasan</div>
              <InsightList items={d.insights} lang={lang} />
              <div className="small text-secondary mt-2">Awtomatikong nabuo mula sa datos; may minimum na bilang para hindi mag-alarma sa maliliit na numero.</div>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={5}>
          <Card className="border-0 shadow-sm h-100">
            <Card.Body className="p-0">
              <div className="fw-semibold p-3 pb-2">Bawat isyu</div>
              <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
                <thead className="table-light"><tr><th>Isyu</th><th className="text-end">Ngayon</th><th className="text-end">Nakaraan</th><th className="text-end">Pagbabago</th></tr></thead>
                <tbody>
                  {[...d.categories].sort((a, b) => b.count - a.count).map((c) => (
                    <tr key={c.code}>
                      <td>{c.name}</td><td className="text-end fw-semibold">{c.count}</td><td className="text-end">{c.prev}</td>
                      <td className={`text-end ${c.change != null && c.change >= .2 && c.count >= 10 ? "text-danger" : ""}`}>{change(c.change)}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Card className="border-0 shadow-sm mb-3">
        <Card.Body>
          <div className="fw-semibold mb-2">Barangay × isyu <span className="small text-secondary fw-normal">· pindutin ang column para i-rank ayon sa isyung iyon</span></div>
          <BarangayHeatmap rows={d.barangays} cats={cats} />
        </Card.Body>
      </Card>

      <Row className="g-3 mb-3">
        {d.rankings.filter((r) => r.total).map((r) => (
          <Col key={r.code} sm={6} xl={3}>
            <Card className="border-0 shadow-sm h-100">
              <Card.Body className="small">
                <div className="fw-semibold">{r.name} <span className="text-secondary fw-normal">· {r.total}</span></div>
                {r.top.map((b, i) => (
                  <div key={b.barangay} className="mt-1">
                    <div className="d-flex justify-content-between"><span>{i + 1}. {b.barangay}</span><span className="fw-semibold">{b.count}</span></div>
                    <div style={{ height: 4, background: "#e1e0d9", borderRadius: 2 }}>
                      <div style={{ width: `${(b.share ?? 0) * 100}%`, height: 4, background: "#2a78d6", borderRadius: 2 }} />
                    </div>
                  </div>
                ))}
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      <Row className="g-3 mb-3">
        <Col lg={7}>
          <Card className="border-0 shadow-sm h-100">
            <Card.Body>
              <div className="d-flex flex-wrap align-items-center gap-2 mb-2">
                <div className="fw-semibold me-auto">Tantiya para sa {d.forecast.label}</div>
                <Form.Select size="sm" style={{ width: 220 }} value={fc.code} onChange={(e) => setFcCat(e.target.value)} aria-label="Isyu">
                  {d.forecast.categories.map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
                </Form.Select>
              </div>
              <div style={{ height: 240 }}>
                <ForecastChart labels={d.forecast.month_labels} series={fc.series} next={{ label: d.forecast.label, estimate: fc.estimate, low: fc.low, high: fc.high }} />
              </div>
              <div className="small text-secondary mt-2">
                {fc.name}: ~{Math.round(fc.estimate)} (saklaw {fc.low}–{fc.high}) · paraan: {fc.method_label}
                {fc.backtest_mape != null && <> · error sa huling 4 na buwan: {pct(fc.backtest_mape)} (hula na "pareho sa nakaraang buwan": {pct(fc.naive_mape)})</>}
              </div>
            </Card.Body>
          </Card>
        </Col>
        <Col lg={5}>
          <Card className="border-0 shadow-sm h-100">
            <Card.Body className="p-0">
              <div className="fw-semibold p-3 pb-2">Lahat ng isyu, {d.forecast.label}</div>
              <Table size="sm" className="small mb-0" style={{ fontVariantNumeric: "tabular-nums" }}>
                <thead className="table-light"><tr><th>Isyu</th><th className="text-end">Tantiya</th><th className="text-end">Saklaw</th><th className="text-end">Error</th></tr></thead>
                <tbody>
                  {d.forecast.categories.map((c) => (
                    <tr key={c.code} role="button" onClick={() => setFcCat(c.code)} className={c.code === fc.code ? "table-active" : ""}>
                      <td>{c.name}</td><td className="text-end fw-semibold">{Math.round(c.estimate)}</td>
                      <td className="text-end">{c.low}–{c.high}</td><td className="text-end text-secondary">{pct(c.backtest_mape)}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <div className="small text-secondary p-3">{d.forecast.method} Mas tumpak ito kapag may 2 taon nang datos (para makita ang tag-ulan).</div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Card className="border-0 shadow-sm mb-3">
        <Card.Body className="p-0">
          <div className="fw-semibold p-3 pb-1">Rekomendasyon sa tauhan at kapasidad</div>
          <div className="small text-secondary px-3 pb-2">Kapasidad = average na naayos bawat buwan (huling 3 buwan). Kailangan = tantiyang papasok + ⅓ ng bukas (para maubos sa 3 buwan). Pang-planning lamang.</div>
          <Table responsive size="sm" className="small mb-0 align-middle" style={{ fontVariantNumeric: "tabular-nums" }}>
            <thead className="table-light">
              <tr><th>Opisina</th><th className="text-end">Kapasidad/buwan</th><th className="text-end">Tantiyang papasok</th><th className="text-end">Bukas · overdue</th>
                <th className="text-end">Kulang</th><th className="text-end">Field staff</th><th>Tutukan</th><th style={{ minWidth: 260 }}>Rekomendasyon</th></tr>
            </thead>
            <tbody>
              {d.resources.map((r) => (
                <tr key={r.code}>
                  <td><Link to={`/staff/analytics/${r.department_id}`} className="fw-semibold text-decoration-none">{r.code}</Link></td>
                  <td className="text-end">{r.capacity}</td>
                  <td className="text-end">{Math.round(r.forecast.estimate)} <span className="text-secondary">({r.forecast.low}–{r.forecast.high})</span></td>
                  <td className="text-end">{r.backlog} · <span className={r.overdue ? "text-danger" : ""}>{r.overdue}</span></td>
                  <td className={`text-end ${r.status === "short" ? "text-danger fw-semibold" : "text-success"}`}>
                    {r.status === "short" ? `−${Math.round(r.gap)}` : <><i className="bi bi-check-lg" aria-hidden /> sapat</>}
                  </td>
                  <td className="text-end">{r.field_staff}{r.extra_staff > 0 && <Badge bg="danger" className="ms-1">+{r.extra_staff}</Badge>}</td>
                  <td>{r.focus_barangays.map((b) => b.barangay).join(", ")}</td>
                  <td>{lang === "en" ? r.text_en : r.text}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card.Body>
      </Card>

      {attention.length > 0 && (
        <Card className="border-0 shadow-sm mb-3">
          <Card.Body className="small">
            <div className="fw-semibold mb-2">Mga opisinang kailangan ng aksyon ({d.label})</div>
            {attention.map((o) => (
              <div key={o.code} className="d-flex flex-wrap gap-2 align-items-center border-bottom py-1">
                <Link to={`/staff/analytics/${o.department_id}`} className="fw-semibold">{o.code}</Link>
                <GradeChip grade={o.grade} /><span className="text-secondary">{o.flags.slice(0, 3).join(" · ")}</span>
              </div>
            ))}
          </Card.Body>
        </Card>
      )}
    </div>
  );
}
