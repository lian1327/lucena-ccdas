import { useState } from "react";
import { Alert, Badge, Button, Card, Col, Form, ListGroup, Row } from "react-bootstrap";
import { Link, useParams } from "react-router-dom";

import { apiErrorMessage } from "@/api/client";
import { useAddNote, useLinkDuplicate, useStaffConcern, useUnlinkDuplicate } from "@/api/staff";
import type { StaffConcernDetail } from "@/api/types";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { PriorityBadge } from "@/components/PriorityBadge";
import { StatusBadge } from "@/components/StatusBadge";
import {
  AssignPanel,
  CompletePanel,
  DeadlinePanel,
  EndorsePanel,
  EndorsementPanel,
  Hotline8888Panel,
  InspectPanel,
  OutcomePanel,
  RoutePanel,
  ValidatePanel,
  VerifyPanel,
} from "@/features/cases/ActionPanels";
import { AcceptPanel, PriorityPanel, RespondPanel } from "@/features/cases/ScreeningPanels";
import { ErrorText, Panel, Stepper } from "@/features/cases/ui";
import { UrgencyBadge } from "@/components/UrgencyBadge";
import { ProofOfWork } from "@/features/evidence/ProofOfWork";
import { dueLabel, fmtDate, fmtDateTime, timeAgo } from "@/utils/format";

function NotesPanel({ c }: { c: StaffConcernDetail }) {
  const add = useAddNote(c.id);
  const [body, setBody] = useState("");
  if (!c.case) return null;
  return (
    <Panel title="Internal notes (hindi nakikita ng publiko)" icon="lock">
      {c.notes.length === 0 && <p className="small text-secondary">Wala pang notes.</p>}
      <ListGroup variant="flush" className="mb-2">
        {c.notes.map((n) => (
          <ListGroup.Item key={n.id} className="px-0 small">
            <div className="text-secondary">{n.author} · {fmtDateTime(n.created_at)}</div>
            {n.body}
          </ListGroup.Item>
        ))}
      </ListGroup>
      {c.permissions.notes && (
        <Form className="d-flex gap-2" onSubmit={(e) => { e.preventDefault(); if (body.trim()) add.mutate({ body }, { onSuccess: () => setBody("") }); }}>
          <Form.Control size="sm" placeholder="Magdagdag ng note…" value={body} onChange={(e) => setBody(e.target.value)} />
          <Button size="sm" type="submit" disabled={add.isPending}>Add</Button>
        </Form>
      )}
    </Panel>
  );
}

function DuplicatesPanel({ c }: { c: StaffConcernDetail }) {
  const link = useLinkDuplicate(c.id);
  const unlink = useUnlinkDuplicate(c.id);
  const [ref, setRef] = useState("");
  return (
    <Panel title="Kaparehong reports" icon="link-45deg">
      {c.duplicate_of ? (
        <>
          <p className="small mb-2">Duplicate ito ng <strong>{c.duplicate_of}</strong>; susundan nito ang status ng orihinal.</p>
          {c.permissions.link && (
            <Button size="sm" variant="outline-secondary" onClick={() => unlink.mutate()} disabled={unlink.isPending}>
              Hindi duplicate (i-unlink)
            </Button>
          )}
        </>
      ) : (
        <>
          {c.duplicates.length === 0 ? (
            <p className="small text-secondary">Walang naka-link na ibang report.</p>
          ) : (
            <ListGroup variant="flush" className="mb-2 small">
              {c.duplicates.map((d) => (
                <ListGroup.Item key={d.id} className="px-0 d-flex justify-content-between">
                  <Link to={`/staff/cases/${d.id}`}>{d.reference_no}</Link>
                  <span className="text-secondary">{timeAgo(d.created_at)} na</span>
                </ListGroup.Item>
              ))}
            </ListGroup>
          )}
          {c.permissions.link && (
            <Form className="d-flex gap-2" onSubmit={(e) => { e.preventDefault(); if (ref.trim()) link.mutate({ master_reference: ref.trim() }); }}>
              <Form.Control size="sm" placeholder="Duplicate ng CCD-…" value={ref} onChange={(e) => setRef(e.target.value)} />
              <Button size="sm" type="submit" variant="outline-primary" disabled={link.isPending}>Link</Button>
            </Form>
          )}
        </>
      )}
      <ErrorText err={link.error ?? unlink.error} />
    </Panel>
  );
}

function WorkRecord({ c }: { c: StaffConcernDetail }) {
  const k = c.case;
  if (!k || (!k.inspected_at && !k.work_completed_at && !k.validated_at)) return null;
  return (
    <Panel title="Talaan ng trabaho" icon="tools">
      <dl className="row small mb-0">
        {k.inspected_at && (
          <>
            <dt className="col-4 text-secondary">Inspeksyon</dt>
            <dd className="col-8">
              {fmtDateTime(k.inspected_at)} · {k.inspected_by}
              <div>{k.inspection_findings}</div>
              {k.action_plan && <div className="text-secondary">Plano: {k.action_plan}</div>}
              {k.scheduled_for && <div className="text-secondary">Iskedyul: {fmtDate(k.scheduled_for)}</div>}
            </dd>
          </>
        )}
        {k.work_completed_at && (
          <>
            <dt className="col-4 text-secondary">Natapos</dt>
            <dd className="col-8">{fmtDateTime(k.work_completed_at)} · {k.work_completed_by}<div>{k.completion_remarks}</div></dd>
          </>
        )}
        {k.validated_at && (
          <>
            <dt className="col-4 text-secondary">Na-validate</dt>
            <dd className="col-8">{fmtDateTime(k.validated_at)} · {k.validated_by}</dd>
          </>
        )}
      </dl>
    </Panel>
  );
}

export function CaseDetailPage() {
  const id = Number(useParams().id);
  const q = useStaffConcern(id);
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const c = q.data!;
  const k = c.case;
  const reportPhotos = c.attachments.filter((a) => a.kind === "report");
  const due = dueLabel(k?.due_at);
  const nothingToDo = !Object.entries(c.permissions).some(([key, v]) => v && !["can_act", "notes", "link", "route_any_office"].includes(key));

  return (
    <>
      <Link to="/staff/cases" className="small text-decoration-none">‹ Mga Kaso</Link>
      <div className="d-flex flex-wrap align-items-center gap-2 mt-2 mb-1">
        <UrgencyBadge code={c.priority_code} name={c.priority_name} color={c.priority_color} />
        <PriorityBadge tier={c.priority_tier} score={c.priority_score} />
        <StatusBadge status={c.status} label={c.status_display} />
        {k?.stage === "for_acceptance" && <Badge bg="primary">Hinihintay ang pagtanggap ng {k.department}</Badge>}
        {k?.stage === "returned" && <Badge bg="danger">Ibinalik sa PACD</Badge>}
        {c.is_verified ? (
          <Badge bg="success-subtle" text="success-emphasis" className="border border-success-subtle">Verified</Badge>
        ) : (
          <Badge bg="light" text="dark" className="border">Hindi pa verified</Badge>
        )}
        {c.danger_now && <Badge bg="danger">May panganib</Badge>}
        {c.channel === "8888" && <Badge bg="warning" text="dark">8888</Badge>}
        {k?.level === "external" && <Badge bg="dark">Endorsed: {k.department}</Badge>}
        {k?.level === "barangay" && <Badge bg="info" text="dark">Barangay-level</Badge>}
        {c.involves_barangay_officials && <Badge bg="dark">Tungkol sa opisyal ng barangay</Badge>}
        <span className="ms-auto small text-secondary">{c.reference_no}</span>
      </div>
      <h1 className="h4 fw-bold">{c.title}</h1>
      <Stepper c={c} />

      <Row className="g-3">
        <Col lg={7} className="order-last order-lg-first">
          <Card className="mb-3 border-0 shadow-sm">
            <Card.Body>
              <p style={{ whiteSpace: "pre-wrap" }}>{c.description}</p>
              <dl className="row small mb-0">
                <dt className="col-4 text-secondary">Kategorya</dt>
                <dd className="col-8">{c.category ?? "—"}{c.subcategory && ` › ${c.subcategory}`}</dd>
                <dt className="col-4 text-secondary">Lokasyon</dt>
                <dd className="col-8">
                  {c.location_description}, {c.barangay}
                  {c.latitude && c.longitude && (
                    <a className="ms-2" target="_blank" rel="noopener" href={`https://www.google.com/maps?q=${c.latitude},${c.longitude}`}>
                      <i className="bi bi-map" aria-hidden /> Mapa
                    </a>
                  )}
                </dd>
                <dt className="col-4 text-secondary">Kalubhaan</dt>
                <dd className="col-8">{c.severity_display} {!c.is_verified && <span className="text-secondary">(hint ng nag-report)</span>}</dd>
                <dt className="col-4 text-secondary">Apektado</dt>
                <dd className="col-8">~{c.affected_count} katao</dd>
                <dt className="col-4 text-secondary">Natanggap</dt>
                <dd className="col-8">
                  {fmtDateTime(c.created_at)} via {c.channel_display}
                  {c.encoded_by && ` (encoded ni ${c.encoded_by})`}
                  {c.source_reference && <div className="text-secondary text-break">Source: {c.source_reference}</div>}
                </dd>
                {k && (
                  <>
                    <dt className="col-4 text-secondary">Hawak ng</dt>
                    <dd className="col-8">
                      {k.level === "barangay" ? `Barangay ${c.barangay}` : k.department}
                      {k.division && <div className="text-secondary">{k.division}</div>}
                      {k.assigned_to && <div>{k.assigned_to}</div>}
                    </dd>
                    {k.accepted_at && (
                      <>
                        <dt className="col-4 text-secondary">Tinanggap</dt>
                        <dd className="col-8">{fmtDateTime(k.accepted_at)} · {k.accepted_by}</dd>
                      </>
                    )}
                    <dt className="col-4 text-secondary">Target</dt>
                    <dd className={`col-8 ${due?.overdue ? "text-danger fw-semibold" : ""}`}>
                      {fmtDate(k.due_at)} {due && c.status !== "closed" && c.status !== "resolved" && `(${due.text})`}
                      {k.extended_at && <Badge bg="secondary" className="ms-1">extended</Badge>}
                    </dd>
                  </>
                )}
              </dl>
            </Card.Body>
          </Card>

          {reportPhotos.length > 0 && (
            <Card className="mb-3 border-0 shadow-sm">
              <Card.Body>
                {([["Litrato mula sa nag-report", reportPhotos]] as const).map(([label, list]) =>
                  list.length ? (
                    <div key={label} className="mb-2">
                      <div className="small fw-semibold mb-1">{label}</div>
                      <div className="d-flex flex-wrap gap-2">
                        {list.map((a) => (
                          <a key={a.id} href={a.url} target="_blank" rel="noopener">
                            <img src={a.url} alt="" width={120} height={120} className="rounded border object-fit-cover" />
                          </a>
                        ))}
                      </div>
                    </div>
                  ) : null,
                )}
              </Card.Body>
            </Card>
          )}

          <WorkRecord c={c} />
          <ProofOfWork c={c} />

          <Panel title="Nag-report" icon="person">
            {c.is_anonymous ? (
              <span className="text-secondary small">Anonymous</span>
            ) : (
              <div className="small">
                <div className="fw-semibold">{c.reporter_name || "—"}</div>
                {c.reporter_contact && (
                  <a href={`tel:${c.reporter_contact}`}><i className="bi bi-telephone me-1" aria-hidden />{c.reporter_contact}</a>
                )}
                <div className="text-secondary mt-1">Gamitin lang ang contact para sa report na ito (RA 10173).</div>
              </div>
            )}
          </Panel>

          <Panel title="Timeline" icon="clock-history">
            <ol className="list-unstyled mb-0">
              {c.history.map((h) => (
                <li key={h.id} className="mb-2 small">
                  <StatusBadge status={h.status} label={h.status_display} />{" "}
                  <span className="text-secondary">{fmtDateTime(h.created_at)} · {h.changed_by}</span>
                  {!h.is_public && <Badge bg="light" text="dark" className="ms-1 border">internal</Badge>}
                  {h.remarks && <div className="ms-1 mt-1">{h.remarks}</div>}
                </li>
              ))}
            </ol>
          </Panel>
        </Col>

        <Col lg={5}>
          {!c.permissions.can_act && <Alert variant="secondary" className="small">Read-only ang access mo (oversight).</Alert>}
          {c.permissions.can_act && nothingToDo && c.status !== "closed" && (
            <Alert variant="light" className="small border">
              Walang hakbang na para sa iyo sa yugtong ito. Makikita mo pa rin ang progreso dito.
            </Alert>
          )}
          {k?.stage === "returned" && k.return_reason && (
            <Alert variant="danger" className="small">
              <strong>Ibinalik ng opisina:</strong> {k.return_reason}
            </Alert>
          )}
          <Hotline8888Panel c={c} />
          <VerifyPanel c={c} />
          <AcceptPanel c={c} />
          <RoutePanel c={c} />
          <RespondPanel c={c} />
          <AssignPanel c={c} />
          <InspectPanel c={c} />
          <CompletePanel c={c} />
          <ValidatePanel c={c} />
          <EndorsementPanel c={c} />
          <EndorsePanel c={c} compact={!!k} />
          <PriorityPanel c={c} />
          <DeadlinePanel c={c} />
          <OutcomePanel c={c} />
          <DuplicatesPanel c={c} />
          <NotesPanel c={c} />
          {c.priority && (
            <Panel title="Priority breakdown" icon="speedometer">
              {([
                ["Kalubhaan", c.priority.severity_component, 0.35],
                ["Apektado", c.priority.affected_component, 0.25],
                ["Ibang nag-report", c.priority.duplicate_component, 0.2],
                ["Tagal na bukas", c.priority.delay_component, 0.2],
              ] as const).map(([label, v, w]) => (
                <div key={label} className="mb-1 small">
                  <div className="d-flex justify-content-between">
                    <span>{label}</span>
                    <span className="text-secondary">+{Math.round(v * w * 100)}</span>
                  </div>
                  <div className="progress" style={{ height: 6 }}>
                    <div className="progress-bar" style={{ width: `${v * 100}%` }} />
                  </div>
                </div>
              ))}
              <div className="small text-secondary mt-2">
                {c.priority.duplicate_count} ibang tao ang nag-report · {Math.round(c.priority.days_open)} araw na bukas
              </div>
            </Panel>
          )}
        </Col>
      </Row>
    </>
  );
}
