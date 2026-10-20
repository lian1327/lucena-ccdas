import { useState } from "react";
import { Alert, Button, Card, Form } from "react-bootstrap";

import { apiErrorMessage } from "@/api/client";
import { useConfirmFix } from "@/api/public";
import type { TrackResult } from "@/api/types";

/** Shown on the tracking page after "Resolved": the citizen, not the office, has the last word. */
export function ConfirmFix({ c }: { c: TrackResult }) {
  const confirm = useConfirmFix(c.reference_no);
  const [choice, setChoice] = useState<boolean | null>(null);
  const [feedback, setFeedback] = useState("");
  const [last4, setLast4] = useState("");

  if (c.citizen_confirmation === "fixed")
    return <Alert variant="success" className="small"><i className="bi bi-hand-thumbs-up me-1" aria-hidden />Salamat! Kinumpirma mong naayos na ito.</Alert>;
  if (c.citizen_confirmation === "not_fixed")
    return <Alert variant="warning" className="small"><i className="bi bi-arrow-counterclockwise me-1" aria-hidden />Natanggap ang sagot mo. Binuksan muli ang kaso at babalikan ng opisina.</Alert>;
  if (!c.can_confirm) return null;

  return (
    <Card className="mb-4 border-primary">
      <Card.Body>
        <h3 className="h6 fw-bold mb-1">Naayos ba talaga?</h3>
        <p className="small text-secondary mb-2">Ikaw ang nakakaalam. Kung hindi pa, bubuksan muli ang kaso at itatala ito laban sa opisina.</p>
        <div className="d-flex gap-2 mb-2">
          <Button variant={choice === true ? "success" : "outline-success"} onClick={() => setChoice(true)}>
            <i className="bi bi-check-lg me-1" aria-hidden />Oo, naayos na
          </Button>
          <Button variant={choice === false ? "danger" : "outline-danger"} onClick={() => setChoice(false)}>
            <i className="bi bi-x-lg me-1" aria-hidden />Hindi pa
          </Button>
        </div>
        {choice !== null && (
          <Form onSubmit={(e) => { e.preventDefault(); confirm.mutate({ fixed: choice, feedback, mobile_last4: last4 || undefined }); }}>
            <Form.Control as="textarea" rows={2} className="mb-2" value={feedback} onChange={(e) => setFeedback(e.target.value)}
              placeholder={choice ? "Komento (opsyonal)" : "Ano pa ang problema? (hal. may butas pa sa gitna)"} />
            {c.confirm_needs_mobile && (
              <Form.Group className="mb-2" style={{ maxWidth: 260 }}>
                <Form.Label className="small">Huling 4 na numero ng mobile na ginamit mo sa report</Form.Label>
                <Form.Control inputMode="numeric" maxLength={4} value={last4} onChange={(e) => setLast4(e.target.value.replace(/\D/g, ""))} />
              </Form.Group>
            )}
            <Button type="submit" disabled={confirm.isPending || (c.confirm_needs_mobile && last4.length !== 4) || (!choice && !feedback.trim())}>
              Ipadala ang sagot
            </Button>
            {confirm.isError && <div className="text-danger small mt-2">{apiErrorMessage(confirm.error)}</div>}
          </Form>
        )}
      </Card.Body>
    </Card>
  );
}
