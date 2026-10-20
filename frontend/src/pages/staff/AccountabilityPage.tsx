import { Alert, Badge, Button, Card, Col, ListGroup, Row, Table } from "react-bootstrap";
import { Link } from "react-router-dom";

import { useAccountability } from "@/api/analytics";
import { apiErrorMessage } from "@/api/client";
import type { WatchItem } from "@/api/types";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { PeriodBar, usePeriod } from "@/features/analytics/PeriodBar";
import { KpiTile, RateCell, pct } from "@/features/analytics/ui";
import { fmtDateTime } from "@/utils/format";

const WATCH_ICON: Record<WatchItem["kind"], string> = {
  pending_red: "hourglass-split", override: "exclamation-diamond", disputed: "person-exclamation", recurrence: "arrow-repeat",
};

/** Proof of work per office + what supervisors should open next. */
export default function AccountabilityPage() {
  const [period, setPeriod] = usePeriod("90d");
  const q = useAccountability(period);
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const sum = (k: keyof (typeof d.offices)[number]) => d.offices.reduce((a, o) => a + (o[k] as number), 0);
  const resolved = sum("resolved");
  const verified = sum("verified_proof");
  const answered = sum("citizen_answered");

  return (
    <div className="analytics-report">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
        <div className="me-auto">
          <h1 className="h4 fw-bold mb-0">Accountability: patunay ng trabaho</h1>
          <div className="small text-secondary">{d.period.label} · Sino ang kumilos, at ano ang patunay na may ginawa</div>
        </div>
        <PeriodBar period={period} onChange={setPeriod} />
        <Button size="sm" className="d-print-none" onClick={() => window.print()}><i className="bi bi-printer me-1" aria-hidden />I-print</Button>
      </div>

      <Row className="g-3 mb-3">
        <Col xs={6} lg={3}><KpiTile label="May verified na patunay" value={pct(resolved ? verified / resolved : null)}
          sub={`${verified} sa ${resolved} naayos`} tone={resolved && verified / resolved < d.proof_target ? "danger" : undefined}
          tip="May BEFORE at AFTER na litrato, may lokasyon, nasa lugar ng report, at walang red flag." /></Col>
        <Col xs={6} lg={3}><KpiTile label="Inaprubahan kahit may red flag" value={sum("overrides")} sub="may nakasulat na dahilan ng validator" /></Col>
        <Col xs={6} lg={3}><KpiTile label="Sabi ng nag-report: hindi pa naayos" value={sum("citizen_not_fixed")}
          sub={`sa ${answered} sumagot · ${sum("citizen_fixed")} kumpirmadong naayos`} /></Col>
        <Col xs={6} lg={3}><KpiTile label="Bumalik ang problema (≤30 araw)" value={sum("recurrences")} sub="parehong problema, parehong lugar" /></Col>
      </Row>

      <Row className="g-3">
        <Col xl={8}>
          <Card className="border-0 shadow-sm mb-3">
            <Card.Body className="p-0">
              <Table responsive hover className="mb-0 small align-middle" style={{ fontVariantNumeric: "tabular-nums" }}>
                <thead className="table-light">
                  <tr>
                    <th>Opisina</th><th className="text-end">Naayos</th><th className="text-nowrap">Verified na patunay</th>
                    <th className="text-end" title="May before at after na litrato">Before+after</th>
                    <th className="text-end" title="Litratong may red flag">Red flag</th><th className="text-end">Override</th>
                    <th className="text-end" title="Accomplishment report na ibinalik ng supervisor">Ibinalik</th>
                    <th className="text-end" title="Sinabi ng nag-report na hindi pa naayos">Hindi naayos*</th>
                    <th className="text-end" title="Bumalik ang problema sa loob ng 30 araw">Bumalik</th>
                  </tr>
                </thead>
                <tbody>
                  {d.offices.map((o) => (
                    <tr key={o.code}>
                      <td>
                        <Link to={`/staff/accountability/${o.department_id}?period=${period}`} className="fw-semibold text-decoration-none">{o.code}</Link>
                        <div className="text-secondary text-truncate" style={{ maxWidth: 200 }}>{o.name}</div>
                      </td>
                      <td className="text-end">{o.resolved}</td>
                      <td><RateCell value={o.proof_rate} target={d.proof_target} /></td>
                      <td className="text-end">{o.before_after}</td>
                      <td className={`text-end ${o.red_flag_photos ? "text-danger fw-semibold" : ""}`}>{o.red_flag_photos}</td>
                      <td className="text-end">{o.overrides}</td>
                      <td className="text-end">{o.reports_returned}</td>
                      <td className="text-end">{o.citizen_not_fixed}<span className="text-secondary">/{o.citizen_answered}</span></td>
                      <td className="text-end">{o.recurrences}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card.Body>
          </Card>
          <p className="small text-secondary">
            *Sa mga nag-report na sumagot ng "Naayos ba talaga?" sa tracking page. Ang litrato ay may red flag kung kinuha
            malayo sa lugar (&gt;150 m), bago pa natanggap ang kaso, o ginamit na sa ibang kaso. Ebidensya ito, hindi
            hatol: puwedeng aprubahan ng validator basta isulat ang dahilan.
          </p>
        </Col>
        <Col xl={4}>
          <Card className="border-0 shadow-sm">
            <Card.Body className="p-0">
              <div className="small fw-semibold p-3 pb-2">Dapat silipin ({d.watchlist.length})</div>
              {d.watchlist.length === 0 ? <div className="small text-secondary px-3 pb-3">Walang nakabinbin.</div> : (
                <ListGroup variant="flush" className="small overflow-auto" style={{ maxHeight: 720 }}>
                  {d.watchlist.map((w, i) => (
                    <Link key={i} to={`/staff/cases/${w.concern_id}`} className="list-group-item list-group-item-action">
                      <div className="d-flex gap-2">
                        <i className={`bi bi-${WATCH_ICON[w.kind]} ${w.level === "red" ? "text-danger" : "text-warning-emphasis"}`} aria-hidden />
                        <div className="flex-grow-1" style={{ minWidth: 0 }}>
                          <div className="fw-semibold">{w.label}</div>
                          <div className="text-truncate">{w.reference_no} · {w.title}</div>
                          <div className="text-secondary">
                            {w.office && <Badge bg="light" text="dark" className="border me-1">{w.office}</Badge>}
                            {w.who && `${w.who} · `}{fmtDateTime(w.at)}
                          </div>
                          {w.detail && <div className="text-secondary fst-italic text-truncate">"{w.detail}"</div>}
                        </div>
                      </div>
                    </Link>
                  ))}
                </ListGroup>
              )}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
}
