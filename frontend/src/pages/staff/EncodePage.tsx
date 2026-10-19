import { useState } from "react";
import { Card, Col, Form, Row } from "react-bootstrap";
import { Link, useNavigate } from "react-router-dom";

import { useEncodeConcern } from "@/api/staff";
import type { Channel } from "@/api/types";
import { ConcernForm } from "@/features/report/ConcernForm";

const CHANNELS: { value: Channel; label: string; hint: string }[] = [
  { value: "walk_in", label: "Walk-in", hint: "hal. Action Center logbook #112" },
  { value: "facebook", label: "Facebook comment / post", hint: "I-paste ang link ng post o comment" },
  { value: "messenger", label: "Messenger", hint: "Pangalan ng sender o petsa ng mensahe" },
  { value: "barangay", label: "Barangay report", hint: "hal. Brgy. blotter / logbook no." },
  { value: "hotline", label: "Hotline / tawag", hint: "Oras ng tawag, numerong tumawag" },
];

/** Staff encode concerns received outside the portal, so every channel lands in one inbox with the same taxonomy. */
export function EncodePage() {
  const encode = useEncodeConcern();
  const navigate = useNavigate();
  const [channel, setChannel] = useState<Channel>("walk_in");
  const [source, setSource] = useState("");
  const hint = CHANNELS.find((c) => c.value === channel)?.hint;

  return (
    <div style={{ maxWidth: 760 }}>
      <Link to="/staff/cases" className="small text-decoration-none">
        ‹ Mga Kaso
      </Link>
      <h1 className="h4 fw-bold mt-2">I-encode ang report</h1>
      <p className="small text-secondary">
        Para sa reports na natanggap sa walk-in, Facebook, Messenger, barangay, o hotline. Parehong form ng citizen
        portal, kaya pare-pareho ang data para sa analytics.
      </p>
      <ConcernForm
        mode="staff"
        submitting={encode.isPending}
        submitLabel="I-save ang report"
        intro={
          <Card className="mb-3 border-0 shadow-sm">
            <Card.Body>
              <Row className="g-2">
                <Col md={5}>
                  <Form.Label className="small fw-semibold" htmlFor="channel">
                    Saan natanggap?
                  </Form.Label>
                  <Form.Select id="channel" value={channel} onChange={(e) => setChannel(e.target.value as Channel)}>
                    {CHANNELS.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </Form.Select>
                </Col>
                <Col md={7}>
                  <Form.Label className="small fw-semibold" htmlFor="source">
                    Source reference (opsyonal)
                  </Form.Label>
                  <Form.Control
                    id="source"
                    placeholder={hint}
                    maxLength={300}
                    value={source}
                    onChange={(e) => setSource(e.target.value)}
                  />
                </Col>
              </Row>
            </Card.Body>
          </Card>
        }
        onSubmit={async (payload) => {
          const created = await encode.mutateAsync({ ...payload, channel, source_reference: source.trim() });
          navigate(`/staff/cases/${created.id}`, { replace: true });
        }}
      />
    </div>
  );
}
