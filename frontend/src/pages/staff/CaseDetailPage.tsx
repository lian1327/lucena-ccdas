import { useState, type ReactNode } from "react";
import { Alert, Badge, Button, Card, Col, Form, ListGroup, Modal, Row, Spinner } from "react-bootstrap";
import { Link, useParams } from "react-router-dom";

import { apiErrorMessage, apiFieldErrors } from "@/api/client";
import { useCategories } from "@/api/public";
import {
  useAddNote,
  useAssign,
  useDepartmentUsers,
  useDepartments,
  useEscalate,
  useLinkDuplicate,
  useSetStatus,
  useStaffConcern,
  useUnlinkDuplicate,
  useVerify,
  type StatusInput,
} from "@/api/staff";
import type { ConcernStatus, Severity, StaffConcernDetail } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { PriorityBadge } from "@/components/PriorityBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { compressImage } from "@/utils/compressImage";
import { dueLabel, fmtDate, fmtDateTime, timeAgo } from "@/utils/format";

const SEVERITIES: { v: Severity; label: string }[] = [
  { v: 1, label: "1 · Minor" },
  { v: 2, label: "2 · Moderate" },
  { v: 3, label: "3 · Serious" },
  { v: 4, label: "4 · Severe" },
  { v: 5, label: "5 · Critical" },
];

const TRANSITION_LABEL: Partial<Record<ConcernStatus, { label: string; variant: string; icon: string }>> = {
  in_progress: { label: "Sinimulan na ang trabaho", variant: "warning", icon: "hammer" },
  resolved: { label: "Naayos na (Resolved)", variant: "success", icon: "check2-circle" },
  closed: { label: "Isara (Close)", variant: "dark", icon: "archive" },
  rejected: { label: "Hindi maaaksyunan (Reject)", variant: "outline-danger", icon: "x-circle" },
  under_review: { label: "Suriin muli", variant: "outline-secondary", icon: "arrow-counterclockwise" },
};

function Panel({ title, icon, children }: { title: string; icon: string; children: ReactNode }) {
  return (
    <Card className="mb-3 border-0 shadow-sm">
      <Card.Header className="bg-white fw-semibold">
        <i className={`bi bi-${icon} me-2`} aria-hidden />
        {title}
      </Card.Header>
      <Card.Body>{children}</Card.Body>
    </Card>
  );
}

function ErrorText({ err }: { err: unknown }) {
  if (!err) return null;
  return <Alert variant="danger" className="small py-2 mt-2 mb-0">{apiErrorMessage(err)}</Alert>;
}

// ---------------- Verify ----------------
function VerifyPanel({ c }: { c: StaffConcernDetail }) {
  const categories = useCategories();
  const verify = useVerify(c.id);
  const [category, setCategory] = useState(c.category_code ?? "");
  const [sub, setSub] = useState(c.subcategory_code ?? "");
  const [severity, setSeverity] = useState<Severity>(c.severity as Severity);
  const subs = categories.data?.find((x) => x.code === category)?.subcategories ?? [];

  return (
    <Panel title="1. Suriin (Verify)" icon="clipboard-check">
      <p className="small text-secondary">
        Kumpirmahin ang uri at tunay na kalubhaan. Ang verified lang ang binibilang sa analytics.
        {c.danger_now && <strong className="text-danger d-block mt-1">Sinabi ng nag-report: may panganib ngayon.</strong>}
      </p>
      <Form.Group className="mb-2">
        <Form.Label className="small fw-semibold">Kategorya</Form.Label>
        <Form.Select
          value={category}
          onChange={(e) => {
            setCategory(e.target.value);
            setSub("");
          }}
        >
          <option value="">— Piliin —</option>
          {categories.data?.map((x) => (
            <option key={x.code} value={x.code}>
              {x.name}
            </option>
          ))}
        </Form.Select>
      </Form.Group>
      {subs.length > 0 && (
        <Form.Group className="mb-2">
          <Form.Label className="small fw-semibold">Sub-type</Form.Label>
          <Form.Select value={sub} onChange={(e) => setSub(e.target.value)}>
            <option value="">— Wala / hindi tiyak —</option>
            {subs.map((s) => (
              <option key={s.code} value={s.code}>
                {s.name} ({s.name_fil})
              </option>
            ))}
          </Form.Select>
        </Form.Group>
      )}
      <Form.Group className="mb-3">
        <Form.Label className="small fw-semibold">Kalubhaan (staff assessment)</Form.Label>
        <Form.Select value={severity} onChange={(e) => setSeverity(Number(e.target.value) as Severity)}>
          {SEVERITIES.map((s) => (
            <option key={s.v} value={s.v}>
              {s.label}
            </option>
          ))}
        </Form.Select>
      </Form.Group>
      <Button
        className="w-100"
        disabled={!category || verify.isPending}
        onClick={() => verify.mutate({ category, subcategory: sub || null, severity })}
      >
        {verify.isPending ? <Spinner size="sm" /> : "I-verify"}
      </Button>
      <ErrorText err={verify.error} />
    </Panel>
  );
}

// ---------------- Assign ----------------
function AssignPanel({ c }: { c: StaffConcernDetail }) {
  const { user } = useAuth();
  const departments = useDepartments();
  const assign = useAssign(c.id);
  const ownDeptId = departments.data?.find((d) => d.name === user?.department)?.id;
  const [dept, setDept] = useState<number | undefined>(c.case?.department_id ?? undefined);
  const effectiveDept = c.permissions.can_assign_any ? dept : (dept ?? ownDeptId);
  const users = useDepartmentUsers(effectiveDept);
  const [person, setPerson] = useState<number | "">(c.case?.assigned_to_id ?? "");
  const [due, setDue] = useState(c.case?.due_at ? c.case.due_at.slice(0, 10) : "");
  const [remarks, setRemarks] = useState("");

  return (
    <Panel title={c.case ? "Assignment" : "2. Ipasa sa opisina (Assign)"} icon="send">
      <Form.Group className="mb-2">
        <Form.Label className="small fw-semibold">Opisina</Form.Label>
        <Form.Select
          value={effectiveDept ?? ""}
          disabled={!c.permissions.can_assign_any}
          onChange={(e) => {
            setDept(Number(e.target.value) || undefined);
            setPerson("");
          }}
        >
          <option value="">— Piliin —</option>
          {departments.data?.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </Form.Select>
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small fw-semibold">Tauhan (opsyonal)</Form.Label>
        <Form.Select value={person} onChange={(e) => setPerson(e.target.value ? Number(e.target.value) : "")}>
          <option value="">— Buong opisina —</option>
          {users.data?.map((u) => (
            <option key={u.id} value={u.id}>
              {u.full_name}
            </option>
          ))}
        </Form.Select>
      </Form.Group>
      <Form.Group className="mb-2">
        <Form.Label className="small fw-semibold">Target na petsa</Form.Label>
        <Form.Control type="date" value={due} onChange={(e) => setDue(e.target.value)} />
        <Form.Text>Kung blangko: ayon sa SLA ng kategorya.</Form.Text>
      </Form.Group>
      <Form.Group className="mb-3">
        <Form.Label className="small fw-semibold">Mensahe sa nag-report (opsyonal)</Form.Label>
        <Form.Control
          size="sm"
          placeholder="hal. Naipasa na sa City Engineering Office."
          value={remarks}
          onChange={(e) => setRemarks(e.target.value)}
        />
      </Form.Group>
      <Button
        className="w-100"
        disabled={!effectiveDept || assign.isPending}
        onClick={() =>
          assign.mutate({
            department: effectiveDept!,
            assigned_to: person || null,
            due_at: due ? new Date(`${due}T17:00:00`).toISOString() : null,
            remarks,
          })
        }
      >
        {assign.isPending ? <Spinner size="sm" /> : c.case ? "I-update ang assignment" : "Ipasa"}
      </Button>
      <ErrorText err={assign.error} />
    </Panel>
  );
}

// ---------------- Status ----------------
function StatusPanel({ c }: { c: StaffConcernDetail }) {
  const setStatus = useSetStatus(c.id);
  const [target, setTarget] = useState<ConcernStatus | null>(null);
  const [remarks, setRemarks] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [photos, setPhotos] = useState<File[]>([]);
  const fieldErrors = apiFieldErrors(setStatus.error);

  const options = (c.allowed_transitions as ConcernStatus[]).filter((s) => {
    if (s === "assigned") return false; // handled by the Assign panel
    if ((s === "resolved" || s === "closed") && !c.permissions.can_resolve) return false;
    return !!TRANSITION_LABEL[s];
  });
  if (!options.length) return null;

  const open = (s: ConcernStatus) => {
    setTarget(s);
    setRemarks("");
    setPhotos([]);
    setIsPublic(true);
    setStatus.reset();
  };
  const submit = async () => {
    if (!target) return;
    const input: StatusInput = { status: target, remarks, is_public: isPublic, photos };
    setStatus.mutate(input, { onSuccess: () => setTarget(null) });
  };

  return (
    <Panel title="Update ng status" icon="arrow-repeat">
      <div className="d-grid gap-2">
        {options.map((s) => {
          const t =
            s === "in_progress" && c.status === "resolved"
              ? { label: "Buksan muli (Reopen)", variant: "outline-warning", icon: "arrow-counterclockwise" }
              : TRANSITION_LABEL[s]!;
          return (
            <Button key={s} variant={t.variant} onClick={() => open(s)}>
              <i className={`bi bi-${t.icon} me-1`} aria-hidden />
              {t.label}
            </Button>
          );
        })}
      </div>

      <Modal show={!!target} onHide={() => setTarget(null)} centered fullscreen="sm-down">
        <Modal.Header closeButton>
          <Modal.Title className="h5">
            {target === "in_progress" && c.status === "resolved" ? "Buksan muli (Reopen)" : target && TRANSITION_LABEL[target]?.label}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {target === "resolved" && (
            <Alert variant="success" className="small">
              Ang litrato at mensahe ay makikita ng <strong>lahat ng nag-report</strong> nito. Ito ang patunay na
              naayos na.
            </Alert>
          )}
          <Form.Group className="mb-3">
            <Form.Label className="small fw-semibold">
              {target === "resolved"
                ? "Ano ang ginawa?"
                : target === "rejected"
                  ? "Bakit hindi maaaksyunan?"
                  : "Mensahe / remarks"}
            </Form.Label>
            <Form.Control
              as="textarea"
              rows={3}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              isInvalid={!!fieldErrors.remarks}
              placeholder={target === "resolved" ? "hal. Nalinis na ang kanal at inalis ang bara. Salamat sa pag-report!" : ""}
            />
            <Form.Control.Feedback type="invalid">{fieldErrors.remarks}</Form.Control.Feedback>
          </Form.Group>
          {target === "resolved" && (
            <Form.Group className="mb-3">
              <Form.Label className="small fw-semibold">Litrato ng natapos na trabaho (kailangan, hanggang 3)</Form.Label>
              <Form.Control
                type="file"
                accept="image/*"
                multiple
                isInvalid={!!fieldErrors.photos}
                onChange={async (e) => {
                  const files = Array.from((e.target as HTMLInputElement).files ?? []).slice(0, 3);
                  setPhotos(await Promise.all(files.map((f) => compressImage(f))));
                }}
              />
              <Form.Control.Feedback type="invalid">{fieldErrors.photos}</Form.Control.Feedback>
              {photos.length > 0 && <Form.Text>{photos.length} litrato ang napili.</Form.Text>}
            </Form.Group>
          )}
          {target !== "resolved" && target !== "rejected" && (
            <Form.Check
              id="is_public"
              label="Ipakita ang mensahe sa nag-report"
              checked={isPublic}
              onChange={(e) => setIsPublic(e.target.checked)}
            />
          )}
          {setStatus.error && !fieldErrors.remarks && !fieldErrors.photos ? <ErrorText err={setStatus.error} /> : null}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-secondary" onClick={() => setTarget(null)}>
            Kanselahin
          </Button>
          <Button onClick={submit} disabled={setStatus.isPending}>
            {setStatus.isPending ? <Spinner size="sm" /> : "I-save"}
          </Button>
        </Modal.Footer>
      </Modal>
    </Panel>
  );
}

// ---------------- Escalate + notes ----------------
function EscalatePanel({ c }: { c: StaffConcernDetail }) {
  const escalate = useEscalate(c.id);
  const [reason, setReason] = useState("");
  const open = ["submitted", "under_review", "assigned", "in_progress"].includes(c.status);
  if (!c.case || !open || c.case.escalation_level >= 3) return null;
  return (
    <Panel title="Escalate" icon="arrow-up-circle">
      <p className="small text-secondary mb-2">
        Kasalukuyan: <strong>{c.case.escalation_level_display}</strong>. Awtomatikong nag-e-escalate kapag lumampas sa
        target na petsa.
      </p>
      <Form.Control
        size="sm"
        className="mb-2"
        placeholder="Dahilan (hal. kailangan ng budget approval)"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <Button
        size="sm"
        variant="outline-dark"
        className="w-100"
        disabled={!reason.trim() || escalate.isPending}
        onClick={() => escalate.mutate({ reason }, { onSuccess: () => setReason("") })}
      >
        Escalate sa susunod na antas
      </Button>
      <ErrorText err={escalate.error} />
    </Panel>
  );
}

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
            <div className="text-secondary">
              {n.author} · {fmtDateTime(n.created_at)}
            </div>
            {n.body}
          </ListGroup.Item>
        ))}
      </ListGroup>
      {c.permissions.can_act && (
        <Form
          onSubmit={(e) => {
            e.preventDefault();
            if (body.trim()) add.mutate({ body }, { onSuccess: () => setBody("") });
          }}
          className="d-flex gap-2"
        >
          <Form.Control size="sm" placeholder="Magdagdag ng note…" value={body} onChange={(e) => setBody(e.target.value)} />
          <Button size="sm" type="submit" disabled={add.isPending}>
            Add
          </Button>
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
          <p className="small mb-2">
            Duplicate ito ng <strong>{c.duplicate_of}</strong>. Susundan nito ang status ng orihinal.
          </p>
          {c.permissions.can_act && (
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
          {c.permissions.can_act && (
            <Form
              className="d-flex gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (ref.trim()) link.mutate({ master_reference: ref.trim() });
              }}
            >
              <Form.Control size="sm" placeholder="I-link bilang duplicate ng CCD-…" value={ref} onChange={(e) => setRef(e.target.value)} />
              <Button size="sm" type="submit" variant="outline-primary" disabled={link.isPending}>
                Link
              </Button>
            </Form>
          )}
        </>
      )}
      <ErrorText err={link.error ?? unlink.error} />
    </Panel>
  );
}

// ---------------- Page ----------------
export function CaseDetailPage() {
  const id = Number(useParams().id);
  const q = useStaffConcern(id);
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const c = q.data!;
  const reportPhotos = c.attachments.filter((a) => a.kind === "report");
  const fixPhotos = c.attachments.filter((a) => a.kind === "resolution");
  const due = dueLabel(c.case?.due_at);
  const canWork = c.permissions.can_act && c.status !== "closed";

  return (
    <>
      <Link to="/staff/cases" className="small text-decoration-none">
        ‹ Mga Kaso
      </Link>
      <div className="d-flex flex-wrap align-items-center gap-2 mt-2 mb-1">
        <PriorityBadge tier={c.priority_tier} score={c.priority_score} />
        <StatusBadge status={c.status} label={c.status_display} />
        {c.is_verified ? (
          <Badge bg="success-subtle" text="success-emphasis" className="border border-success-subtle">
            Verified
          </Badge>
        ) : (
          <Badge bg="light" text="dark" className="border">Hindi pa verified</Badge>
        )}
        {c.danger_now && <Badge bg="danger">May panganib</Badge>}
        {c.involves_barangay_officials && <Badge bg="dark">Tungkol sa opisyal ng barangay</Badge>}
        <span className="ms-auto small text-secondary">{c.reference_no}</span>
      </div>
      <h1 className="h4 fw-bold">{c.title}</h1>

      <Row className="g-3">
        <Col lg={7}>
          <Card className="mb-3 border-0 shadow-sm">
            <Card.Body>
              <p style={{ whiteSpace: "pre-wrap" }}>{c.description}</p>
              <dl className="row small mb-0">
                <dt className="col-4 text-secondary">Kategorya</dt>
                <dd className="col-8">
                  {c.category ?? "—"}
                  {c.subcategory && ` › ${c.subcategory}`}
                </dd>
                <dt className="col-4 text-secondary">Lokasyon</dt>
                <dd className="col-8">
                  {c.location_description}, {c.barangay}
                  {c.latitude && c.longitude && (
                    <a
                      className="ms-2"
                      target="_blank"
                      rel="noopener"
                      href={`https://www.google.com/maps?q=${c.latitude},${c.longitude}`}
                    >
                      <i className="bi bi-map" aria-hidden /> Mapa
                    </a>
                  )}
                </dd>
                <dt className="col-4 text-secondary">Kalubhaan</dt>
                <dd className="col-8">
                  {c.severity_display} {!c.is_verified && <span className="text-secondary">(hint ng nag-report)</span>}
                </dd>
                <dt className="col-4 text-secondary">Apektado</dt>
                <dd className="col-8">~{c.affected_count} katao</dd>
                <dt className="col-4 text-secondary">Natanggap</dt>
                <dd className="col-8">
                  {fmtDateTime(c.created_at)} via {c.channel_display}
                  {c.encoded_by && ` (encoded ni ${c.encoded_by})`}
                  {c.source_reference && <div className="text-secondary">Source: {c.source_reference}</div>}
                </dd>
                {c.case && (
                  <>
                    <dt className="col-4 text-secondary">Opisina</dt>
                    <dd className="col-8">
                      {c.case.department}
                      {c.case.assigned_to && ` · ${c.case.assigned_to}`}
                    </dd>
                    <dt className="col-4 text-secondary">Target</dt>
                    <dd className={`col-8 ${due?.overdue ? "text-danger fw-semibold" : ""}`}>
                      {fmtDate(c.case.due_at)} {due && `(${due.text})`}
                    </dd>
                  </>
                )}
              </dl>
            </Card.Body>
          </Card>

          {(reportPhotos.length > 0 || fixPhotos.length > 0) && (
            <Card className="mb-3 border-0 shadow-sm">
              <Card.Body>
                {[
                  ["Litrato mula sa nag-report", reportPhotos],
                  ["Patunay ng pagkaayos", fixPhotos],
                ].map(([label, list]) =>
                  (list as typeof reportPhotos).length ? (
                    <div key={label as string} className="mb-2">
                      <div className="small fw-semibold mb-1">{label as string}</div>
                      <div className="d-flex flex-wrap gap-2">
                        {(list as typeof reportPhotos).map((a) => (
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

          <Panel title="Nag-report" icon="person">
            {c.is_anonymous ? (
              <span className="text-secondary small">Anonymous</span>
            ) : (
              <div className="small">
                <div className="fw-semibold">{c.reporter_name || "—"}</div>
                {c.reporter_contact && (
                  <a href={`tel:${c.reporter_contact}`}>
                    <i className="bi bi-telephone me-1" aria-hidden />
                    {c.reporter_contact}
                  </a>
                )}
                <div className="text-secondary mt-1">
                  Gamitin lang ang contact para sa report na ito (RA 10173).
                </div>
              </div>
            )}
          </Panel>

          <Panel title="Timeline" icon="clock-history">
            <ol className="list-unstyled mb-0">
              {c.history.map((h) => (
                <li key={h.id} className="mb-2 small">
                  <StatusBadge status={h.status} label={h.status_display} />{" "}
                  <span className="text-secondary">
                    {fmtDateTime(h.created_at)} · {h.changed_by}
                  </span>
                  {!h.is_public && (
                    <Badge bg="light" text="dark" className="ms-1 border">
                      internal
                    </Badge>
                  )}
                  {h.remarks && <div className="ms-1 mt-1">{h.remarks}</div>}
                </li>
              ))}
            </ol>
          </Panel>
        </Col>

        <Col lg={5}>
          {!c.permissions.can_act && (
            <Alert variant="secondary" className="small">
              Read-only ang access mo sa kasong ito.
            </Alert>
          )}
          {canWork && !c.duplicate_of && (
            <>
              {!c.is_verified && c.status !== "rejected" && <VerifyPanel c={c} />}
              {c.permissions.can_assign && ["submitted", "under_review", "assigned", "in_progress"].includes(c.status) && (
                <AssignPanel key={c.case?.department_id ?? 0} c={c} />
              )}
              <StatusPanel c={c} />
              <EscalatePanel c={c} />
            </>
          )}
          <DuplicatesPanel c={c} />
          <NotesPanel c={c} />
          {c.priority && (
            <Panel title="Priority breakdown" icon="speedometer">
              {[
                ["Kalubhaan", c.priority.severity_component, 0.35],
                ["Apektado", c.priority.affected_component, 0.25],
                ["Ibang nag-report", c.priority.duplicate_component, 0.2],
                ["Tagal na bukas", c.priority.delay_component, 0.2],
              ].map(([label, v, w]) => (
                <div key={label as string} className="mb-1 small">
                  <div className="d-flex justify-content-between">
                    <span>{label as string}</span>
                    <span className="text-secondary">
                      +{Math.round((v as number) * (w as number) * 100)}
                    </span>
                  </div>
                  <div className="progress" style={{ height: 6 }}>
                    <div className="progress-bar" style={{ width: `${(v as number) * 100}%` }} />
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
