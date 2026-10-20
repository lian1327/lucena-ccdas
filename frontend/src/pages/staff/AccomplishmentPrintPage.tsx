import { Alert, Button, Col, Row } from "react-bootstrap";
import { Link, useParams } from "react-router-dom";

import { apiErrorMessage } from "@/api/client";
import { useStaffConcern } from "@/api/staff";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { LGU_NAME } from "@/config";
import { AccountabilityTrail, ReportBlock } from "@/features/evidence/ProofOfWork";
import { EvidencePhotoCard } from "@/features/evidence/ui";
import { fmtDateTime } from "@/utils/format";

/** Printable accomplishment report (A4): case, before/after, crew, materials, sign-off. */
export default function AccomplishmentPrintPage() {
  const id = Number(useParams().id);
  const q = useStaffConcern(id);
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const c = q.data!;
  const k = c.case;
  const before = c.attachments.filter((a) => a.kind === "before");
  const after = c.attachments.filter((a) => a.kind === "resolution");
  const approved = k?.reports.find((r) => r.status === "approved") ?? k?.reports[0];
  return (
    <div className="analytics-report bg-white p-3 p-md-4 rounded shadow-sm" style={{ maxWidth: 900 }}>
      <div className="d-flex d-print-none gap-2 mb-3">
        <Link to={`/staff/cases/${c.id}`} className="small me-auto">‹ Bumalik sa kaso</Link>
        <Button size="sm" onClick={() => window.print()}><i className="bi bi-printer me-1" aria-hidden />I-print / PDF</Button>
      </div>
      <div className="text-center mb-3">
        <div className="small text-secondary">{LGU_NAME}</div>
        <div className="fw-semibold">{k?.department ?? "—"}</div>
        <h1 className="h5 fw-bold mt-2 mb-0">ACCOMPLISHMENT REPORT</h1>
        <div className="small text-secondary">{c.reference_no} · inihanda {fmtDateTime(new Date().toISOString())}</div>
      </div>
      <dl className="row small">
        <dt className="col-3">Problema</dt><dd className="col-9">{c.title}</dd>
        <dt className="col-3">Lugar</dt><dd className="col-9">Brgy. {c.barangay}{c.location_description ? ` · ${c.location_description}` : ""}</dd>
        <dt className="col-3">Natanggap</dt><dd className="col-9">{fmtDateTime(k?.routed_at)} · Target: {fmtDateTime(k?.due_at)}</dd>
        <dt className="col-3">Na-validate</dt><dd className="col-9">{k?.validated_at ? `${fmtDateTime(k.validated_at)} · ${k.validated_by}` : "Hindi pa"}</dd>
      </dl>
      {approved && <ReportBlock r={approved} />}
      <Row className="g-2 my-3">
        <Col xs={6}><div className="small fw-semibold mb-1">BEFORE</div>{before.map((a) => <div key={a.id} className="mb-2"><EvidencePhotoCard a={a} /></div>)}</Col>
        <Col xs={6}><div className="small fw-semibold mb-1">AFTER</div>{after.map((a) => <div key={a.id} className="mb-2"><EvidencePhotoCard a={a} /></div>)}</Col>
      </Row>
      <div className="small fw-semibold mb-1">Talaan ng aksyon</div>
      <AccountabilityTrail steps={c.trail} />
      <Row className="mt-5 small text-center">
        {[["Inihanda ni", approved?.submitted_by], ["Sinuri ni", approved?.reviewed_by], ["Pinagtibay ni", "Department Head"]].map(([l, n]) => (
          <Col key={l}><div className="border-top pt-1 mx-3 fw-semibold">{n ?? " "}</div><div className="text-secondary">{l}</div></Col>
        ))}
      </Row>
    </div>
  );
}
