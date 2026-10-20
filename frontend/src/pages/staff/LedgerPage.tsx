import { Alert, Badge, Card, Col, ListGroup, Row } from "react-bootstrap";
import { Link, useParams } from "react-router-dom";

import { useLedger } from "@/api/analytics";
import { apiErrorMessage } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { PeriodBar, usePeriod } from "@/features/analytics/PeriodBar";
import { KpiTile, pct } from "@/features/analytics/ui";
import { FlagChip } from "@/features/evidence/ui";
import { fmtDateTime } from "@/utils/format";

const KIND_ICON: Record<string, string> = {
  accepted: "inbox", responded: "lightning", inspected: "search", report: "clipboard2-check", validated: "patch-check", returned: "arrow-return-left",
};

/** One person's actions in time order, with the photos submitted as evidence for each. */
export default function LedgerPage() {
  const { user } = useAuth();
  const param = useParams().id;
  const id = param === "me" ? Number(user?.id ?? 0) : Number(param);
  const [period, setPeriod] = usePeriod("90d");
  const q = useLedger(id, period);
  if (q.isLoading || !id) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const s = d.summary;
  const self = d.person.id === Number(user?.id);
  return (
    <div className="analytics-report">
      {!self && d.person.department_id && (
        <Link to={`/staff/accountability/${d.person.department_id}?period=${period}`} className="small text-decoration-none d-print-none">‹ {d.person.department}</Link>
      )}
      <div className="d-flex flex-wrap align-items-center gap-2 mt-2 mb-3">
        <div className="me-auto">
          <h1 className="h4 fw-bold mb-0">{self ? "Aking mga aksyon" : d.person.name}</h1>
          <div className="small text-secondary">{d.person.role_display}{d.person.division ? ` · ${d.person.division}` : ""} · {d.period.label}</div>
        </div>
        <PeriodBar period={period} onChange={setPeriod} />
      </div>
      {s && (
        <Row className="g-3 mb-3">
          <Col xs={6} lg={3}><KpiTile label="Mga aksyon" value={s.total_actions} sub={`${s.actions.submitted} report · ${s.actions.validated} validation`} /></Col>
          <Col xs={6} lg={3}><KpiTile label="Litrato na may lokasyon" value={pct(s.located_rate)} sub={`${s.photos} litrato`} /></Col>
          <Col xs={6} lg={3}><KpiTile label="Red-flag na litrato" value={s.red_flag_photos} tone={s.red_flag_photos ? "danger" : undefined} sub={`${s.reports_returned} report ang ibinalik`} /></Col>
          <Col xs={6} lg={3}><KpiTile label="Sabi ng nag-report: hindi pa naayos" value={s.citizen_not_fixed} sub={`${s.recurrences} bumalik ang problema`} /></Col>
        </Row>
      )}
      <Card className="border-0 shadow-sm">
        <Card.Body className="p-0">
          {d.items.length === 0 ? <div className="p-3 small text-secondary">Walang aksyon sa panahong ito.</div> : (
            <ListGroup variant="flush" className="small">
              {d.items.map((it, i) => (
                <ListGroup.Item key={i} className="py-3">
                  <div className="d-flex gap-3">
                    <i className={`bi bi-${KIND_ICON[it.kind] ?? "dot"} fs-5 ${it.ok === false ? "text-danger" : it.ok ? "text-success" : "text-primary"}`} aria-hidden />
                    <div className="flex-grow-1" style={{ minWidth: 0 }}>
                      <div className="d-flex flex-wrap gap-2 align-items-baseline">
                        <span className="fw-semibold">{it.label}</span>
                        <Link to={`/staff/cases/${it.concern_id}`}>{it.reference_no}</Link>
                        <span className="text-secondary">{fmtDateTime(it.at)}</span>
                        {it.ok === false && <Badge bg="danger">lampas / ibinalik</Badge>}
                      </div>
                      <div className="text-truncate">{it.title} · Brgy. {it.barangay}</div>
                      {it.detail && <div className="text-secondary">{it.detail}</div>}
                      {it.flags.length > 0 && <div className="mt-1">{it.flags.map((f) => <FlagChip key={f.code} f={f} />)}</div>}
                      {it.photos.length > 0 && (
                        <div className="d-flex flex-wrap gap-2 mt-2">
                          {it.photos.map((p) => (
                            <a key={p.url} href={p.url} target="_blank" rel="noreferrer" className="text-decoration-none text-reset" style={{ width: 96 }}>
                              <img src={p.url} alt={p.kind} className="rounded border w-100" style={{ height: 72, objectFit: "cover" }} />
                              <div className="text-secondary lh-sm" style={{ fontSize: ".7rem" }}>
                                {p.kind === "before" ? "BEFORE" : p.kind === "resolution" ? "AFTER" : "PROGRESS"}
                                {" · "}{p.gps_source === "none" ? "walang GPS" : p.distance_m != null ? `${Math.round(p.distance_m)} m` : "may GPS"}
                                {p.flags.some((f) => f.level === "red") && <i className="bi bi-x-octagon-fill text-danger ms-1" aria-label="red flag" />}
                              </div>
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </ListGroup.Item>
              ))}
            </ListGroup>
          )}
        </Card.Body>
      </Card>
    </div>
  );
}
