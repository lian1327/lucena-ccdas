import { Alert, Badge, Col, Row, Table } from "react-bootstrap";
import { Link } from "react-router-dom";

import type { AccomplishmentReport, StaffConcernDetail, TrailStep } from "@/api/types";
import { Panel } from "@/features/cases/ui";
import { fmtDateTime } from "@/utils/format";

import { EvidencePhotoCard, FlagChip } from "./ui";

const REPORT_BADGE: Record<string, string> = { submitted: "warning", approved: "success", returned: "secondary" };

export function ReportBlock({ r }: { r: AccomplishmentReport }) {
  return (
    <div className="border rounded p-2 mb-2 small">
      <div className="d-flex flex-wrap align-items-center gap-2 mb-1">
        <Badge bg={REPORT_BADGE[r.status]} text={r.status === "submitted" ? "dark" : undefined}>{r.status_display}</Badge>
        <span className="text-secondary">{fmtDateTime(r.submitted_at)} · {r.submitted_by}</span>
      </div>
      <div className="mb-1">{r.work_done}</div>
      <dl className="row mb-0">
        <dt className="col-4 text-secondary fw-normal">Crew ({r.headcount})</dt>
        <dd className="col-8 mb-1">{[...r.crew, r.other_workers].filter(Boolean).join(", ") || "—"}</dd>
        <dt className="col-4 text-secondary fw-normal">Oras sa site</dt>
        <dd className="col-8 mb-1">
          {r.started_at ? `${fmtDateTime(r.started_at)} – ${fmtDateTime(r.finished_at)}` : fmtDateTime(r.finished_at)}
          {r.man_hours != null && <span className="text-secondary"> · {r.man_hours} man-hours</span>}
        </dd>
        {r.materials.length > 0 && (
          <>
            <dt className="col-4 text-secondary fw-normal">Materyales</dt>
            <dd className="col-8 mb-1">{r.materials.map((m) => `${m.qty ?? ""} ${m.unit ?? ""} ${m.item}`.trim()).join(" · ")}</dd>
          </>
        )}
        {r.equipment && (<><dt className="col-4 text-secondary fw-normal">Kagamitan</dt><dd className="col-8 mb-1">{r.equipment}</dd></>)}
        {r.reviewed_by && (
          <>
            <dt className="col-4 text-secondary fw-normal">{r.status === "returned" ? "Ibinalik ni" : "Na-validate ni"}</dt>
            <dd className="col-8 mb-1">
              {r.reviewed_by} · {fmtDateTime(r.reviewed_at)}
              {r.review_remarks && <div className="text-secondary">{r.review_remarks}</div>}
              {r.override_reason && (
                <div className="text-danger-emphasis"><i className="bi bi-exclamation-diamond me-1" aria-hidden />Inaprubahan kahit may red flag: {r.override_reason}</div>
              )}
            </dd>
          </>
        )}
      </dl>
    </div>
  );
}

function TrailIcon({ s }: { s: TrailStep }) {
  if (!s.who && !s.at) return <i className="bi bi-circle text-secondary" aria-hidden />;
  if (s.ok === false) return <i className="bi bi-x-circle-fill text-danger" aria-label="Lampas sa target / hindi pasado" />;
  if (s.ok === true) return <i className="bi bi-check-circle-fill text-success" aria-label="Pasok sa target" />;
  return <i className="bi bi-record-circle-fill text-primary" aria-hidden />;
}

export function AccountabilityTrail({ steps }: { steps: TrailStep[] }) {
  return (
    <Table size="sm" className="small mb-0 align-top">
      <tbody>
        {steps.map((s) => (
          <tr key={s.key} className={!s.who && !s.at ? "text-secondary" : ""}>
            <td style={{ width: 22 }}><TrailIcon s={s} /></td>
            <td className="fw-semibold" style={{ width: "32%" }}>{s.label}</td>
            <td>
              {s.who ?? "—"}{s.at && <span className="text-secondary"> · {fmtDateTime(s.at)}</span>}
              {s.detail && <div className="text-secondary">{s.detail}</div>}
            </td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

/** Before/after evidence, accomplishment reports and who did what, on the case page. */
export function ProofOfWork({ c }: { c: StaffConcernDetail }) {
  const k = c.case;
  const before = c.attachments.filter((a) => a.kind === "before");
  const progress = c.attachments.filter((a) => a.kind === "progress");
  const after = c.attachments.filter((a) => a.kind === "resolution");
  const ev = k?.evidence;
  if (!k) return null;
  const started = before.length || after.length || k.reports.length;

  return (
    <div id="proof">
      <Panel title="Patunay ng trabaho" icon="shield-check">
        {c.citizen_confirmation === "not_fixed" && (
          <Alert variant="danger" className="small py-2">
            <i className="bi bi-person-exclamation me-1" aria-hidden /><strong>Sabi ng nag-report: hindi pa naayos.</strong>{" "}
            {c.citizen_feedback} <span className="text-secondary">({fmtDateTime(c.citizen_confirmed_at)})</span>
          </Alert>
        )}
        {c.citizen_confirmation === "fixed" && (
          <Alert variant="success" className="small py-2">
            <i className="bi bi-hand-thumbs-up me-1" aria-hidden />Kinumpirma ng nag-report na naayos na. {c.citizen_feedback}
          </Alert>
        )}
        {c.recurrence_of && (
          <Alert variant="warning" className="small py-2">
            <i className="bi bi-arrow-repeat me-1" aria-hidden />Bumalik ang problema: naayos na ito dati sa {c.recurrence_of} (≤30 araw).
          </Alert>
        )}
        {c.recurrences.length > 0 && (
          <Alert variant="warning" className="small py-2">
            <i className="bi bi-arrow-repeat me-1" aria-hidden />Matapos maayos, may bagong report sa parehong lugar:{" "}
            {c.recurrences.map((r) => <Link key={r.id} to={`/staff/cases/${r.id}`} className="me-2">{r.reference_no}</Link>)}
          </Alert>
        )}

        {!started ? (
          <p className="small text-secondary mb-2">Wala pang before/after na litrato o accomplishment report.</p>
        ) : (
          <>
            {ev && (
              <div className="mb-2 small">
                {ev.verified
                  ? <Badge bg="success"><i className="bi bi-shield-check me-1" aria-hidden />Verified: may before at after, nasa lugar</Badge>
                  : <Badge bg="light" text="dark" className="border">Hindi pa verified</Badge>}{" "}
                {ev.red_flags.map((f) => <FlagChip key={f.code} f={f} />)}
                {ev.amber_flags.map((f) => <FlagChip key={f.code} f={f} />)}
              </div>
            )}
            <Row className="g-2 mb-3">
              <Col xs={6}>
                <div className="small fw-semibold mb-1">BEFORE</div>
                {before.length ? <div className="d-grid gap-2">{before.map((a) => <EvidencePhotoCard key={a.id} a={a} />)}</div>
                  : <div className="border rounded p-3 small text-secondary text-center">Walang before na litrato</div>}
              </Col>
              <Col xs={6}>
                <div className="small fw-semibold mb-1">AFTER</div>
                {after.length ? <div className="d-grid gap-2">{after.map((a) => <EvidencePhotoCard key={a.id} a={a} />)}</div>
                  : <div className="border rounded p-3 small text-secondary text-center">Wala pang after na litrato</div>}
              </Col>
            </Row>
            {progress.length > 0 && (
              <>
                <div className="small fw-semibold mb-1">Make-safe / progress</div>
                <Row className="g-2 mb-3">{progress.map((a) => <Col xs={4} key={a.id}><EvidencePhotoCard a={a} compact /></Col>)}</Row>
              </>
            )}
          </>
        )}

        {k.reports.length > 0 && (
          <>
            <div className="d-flex align-items-center mb-1">
              <div className="small fw-semibold me-auto">Accomplishment report{k.reports.length > 1 ? `s (${k.reports.length})` : ""}</div>
              <Link to={`/staff/cases/${c.id}/accomplishment`} className="btn btn-sm btn-outline-secondary py-0">
                <i className="bi bi-printer me-1" aria-hidden />I-print
              </Link>
            </div>
            {k.reports.map((r) => <ReportBlock key={r.id} r={r} />)}
          </>
        )}

        <div className="small fw-semibold mt-3 mb-1">Sino ang gumawa ng ano</div>
        <AccountabilityTrail steps={c.trail} />
      </Panel>
    </div>
  );
}
