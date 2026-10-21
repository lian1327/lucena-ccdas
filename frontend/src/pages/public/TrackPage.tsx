import axios from "axios";
import { useState, type FormEvent } from "react";
import { Alert, Button, Card, Container, Form, InputGroup } from "react-bootstrap";
import { useNavigate, useParams } from "react-router-dom";

import { useTrackConcern } from "@/api/public";
import { apiErrorMessage } from "@/api/client";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmFix } from "@/features/report/ConfirmFix";
import { SmsPreference } from "@/features/report/SmsPreference";

const fmt = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("en-PH", { dateStyle: "medium", timeStyle: "short" }) : "—";

export function TrackPage() {
  const { ref } = useParams();
  const navigate = useNavigate();
  const [input, setInput] = useState(ref ?? "");
  const query = useTrackConcern(ref);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    const value = input.trim().toUpperCase();
    if (value) navigate(`/track/${encodeURIComponent(value)}`);
  };

  const notFound = axios.isAxiosError(query.error) && query.error.response?.status === 404;
  const c = query.data;

  return (
    <Container className="py-5" style={{ maxWidth: 720 }}>
      <h1 className="h3 fw-bold">Track a Concern</h1>
      <p className="text-secondary">Enter the reference number you received after submitting.</p>

      <Form onSubmit={onSubmit} className="mb-4">
        <InputGroup size="lg">
          <Form.Control
            placeholder="CCD-2026-XXXXXX"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            aria-label="Reference number"
            className="text-uppercase"
          />
          <Button type="submit">Track</Button>
        </InputGroup>
      </Form>

      {query.isFetching && <FullPageSpinner label="Looking up…" />}
      {notFound && <Alert variant="warning">No concern found with reference <strong>{ref}</strong>.</Alert>}
      {query.isError && !notFound && <Alert variant="danger">{apiErrorMessage(query.error)}</Alert>}

      {c && !query.isFetching && (
        <Card>
          <Card.Body>
            <div className="d-flex justify-content-between align-items-start gap-2 mb-2">
              <div>
                <div className="small text-secondary">{c.reference_no}</div>
                <h2 className="h5 mb-0">{c.title}</h2>
              </div>
              <StatusBadge status={c.status} label={c.status_display} />
            </div>
            <dl className="row small mb-4">
              <dt className="col-5 col-sm-4 text-secondary">Category</dt>
              <dd className="col-7 col-sm-8">
                {c.category ?? "Being classified"}
                {c.subcategory && <span className="text-secondary"> › {c.subcategory}</span>}
              </dd>
              <dt className="col-5 col-sm-4 text-secondary">Barangay</dt>
              <dd className="col-7 col-sm-8">{c.barangay}</dd>
              <dt className="col-5 col-sm-4 text-secondary">Handling office</dt>
              <dd className="col-7 col-sm-8">{c.assigned_office ?? "Not yet assigned"}</dd>
              {c.priority_level && (
                <>
                  <dt className="col-5 col-sm-4 text-secondary">Antas</dt>
                  <dd className="col-7 col-sm-8">{c.priority_level}</dd>
                </>
              )}
              {c.target_date && (
                <>
                  <dt className="col-5 col-sm-4 text-secondary">Target na petsa</dt>
                  <dd className="col-7 col-sm-8">
                    {fmt(c.target_date).split(",").slice(0, 2).join(",")}
                    {c.deadline_extended && <span className="badge text-bg-secondary ms-1">na-extend</span>}
                  </dd>
                </>
              )}
              <dt className="col-5 col-sm-4 text-secondary">Submitted</dt>
              <dd className="col-7 col-sm-8">{fmt(c.created_at)}</dd>
              {c.resolved_at && (
                <>
                  <dt className="col-5 col-sm-4 text-secondary">Resolved</dt>
                  <dd className="col-7 col-sm-8">{fmt(c.resolved_at)}</dd>
                </>
              )}
            </dl>
            {c.endorsed_to && (
              <Alert variant="secondary" className="small">
                Ang problemang ito ay sakop ng <strong>{c.endorsed_to}</strong>. Inendorso ito ng City Hall at patuloy
                na sinusubaybayan; makikita mo rito ang mga update.
              </Alert>
            )}
            {c.linked_to_reference && (
              <Alert variant="info" className="small">
                This was reported by others too and is being handled together with{" "}
                <strong>{c.linked_to_reference}</strong>.
              </Alert>
            )}

            {c.resolution_photos.length > 0 && (
              <div className="mb-4">
                <h3 className="h6">
                  <i className="bi bi-check2-circle text-success me-1" aria-hidden />
                  Patunay na naayos na
                </h3>
                <div className="row g-2">
                  {([["Bago", c.before_photos], ["Pagkatapos", c.resolution_photos]] as const).map(([label, list]) =>
                    list.length ? (
                      <div key={label} className="col-6">
                        <div className="small text-secondary mb-1">{label}</div>
                        <div className="d-grid gap-2">
                          {list.map((url) => (
                            <a key={url} href={url} target="_blank" rel="noopener">
                              <img src={url} alt={`Litrato: ${label.toLowerCase()}`} className="w-100 rounded border object-fit-cover" style={{ height: 160 }} />
                            </a>
                          ))}
                        </div>
                      </div>
                    ) : null,
                  )}
                </div>
              </div>
            )}

            <ConfirmFix c={c} />
            <SmsPreference c={c} />

            <h3 className="h6">Timeline</h3>
            <ol className="list-unstyled border-start ps-3 mb-0">
              {c.timeline.map((t, i) => (
                <li key={i} className="mb-3 position-relative">
                  <span
                    className="position-absolute bg-primary rounded-circle"
                    style={{ width: 10, height: 10, left: -21, top: 6 }}
                  />
                  <div className="d-flex gap-2 align-items-center">
                    <StatusBadge status={t.status} label={t.status_display} />
                    <span className="small text-secondary">{fmt(t.created_at)}</span>
                  </div>
                  {t.remarks && <div className="small mt-1">{t.remarks}</div>}
                </li>
              ))}
            </ol>
          </Card.Body>
        </Card>
      )}
    </Container>
  );
}
