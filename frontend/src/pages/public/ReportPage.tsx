import { useState } from "react";
import { Alert, Button, Card, Container } from "react-bootstrap";
import { Link, useSearchParams } from "react-router-dom";

import { useSubmitConcern } from "@/api/public";
import type { ConcernCreateResponse } from "@/api/types";
import { ConcernForm } from "@/features/report/ConcernForm";
import { useSite } from "@/site/useSite";

export function ReportPage() {
  const submit = useSubmitConcern();
  const [result, setResult] = useState<ConcernCreateResponse | null>(null);
  const [formKey, setFormKey] = useState(0);
  const [params] = useSearchParams();

  if (result)
    return (
      <SuccessView
        result={result}
        onAgain={() => {
          setResult(null);
          submit.reset();
          setFormKey((k) => k + 1);
        }}
      />
    );

  return (
    <Container className="py-4" style={{ maxWidth: 720 }}>
      <ConcernForm
        key={formKey}
        mode="public"
        initialCategory={params.get("category") ?? undefined}
        submitting={submit.isPending}
        submitLabel="Ipadala ang Report"
        onSubmit={async (payload) => {
          setResult(await submit.mutateAsync(payload));
          window.scrollTo({ top: 0, behavior: "smooth" });
        }}
        intro={
          <>
            <h1 className="h3 fw-bold mb-1">Mag-report ng Problema</h1>
            <p className="text-secondary mb-4">
              Report a community concern · mga 1 minuto lang. Para sa emergency, tumawag agad sa <strong>911</strong>.
            </p>
          </>
        }
      />
    </Container>
  );
}

function SuccessView({ result, onAgain }: { result: ConcernCreateResponse; onAgain: () => void }) {
  const [copied, setCopied] = useState(false);
  const site = useSite();
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.reference_no);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — the number is on screen */
    }
  };

  return (
    <Container className="py-5" style={{ maxWidth: 560 }}>
      <Card className="border-0 shadow-sm text-center">
        <Card.Body className="p-4">
          <i className="bi bi-check-circle-fill text-success" style={{ fontSize: 56 }} aria-hidden />
          <h1 className="h4 fw-bold mt-2">Natanggap na ang report mo!</h1>
          <p className="text-secondary mb-3">Ito ang iyong reference number:</p>
          <div className="fs-3 fw-bold font-monospace bg-light rounded py-2 mb-2 user-select-all">{result.reference_no}</div>
          <Button variant="link" size="sm" onClick={copy}>
            <i className={`bi bi-${copied ? "check2" : "clipboard"} me-1`} aria-hidden />
            {copied ? "Nakopya!" : "Kopyahin"}
          </Button>
          <p className="small text-secondary mt-2">
            I-screenshot o isulat ito. Gamitin ito para i-track ang report mo anumang oras.
          </p>
          {site.isPrototype && (
            <Alert variant="warning" className="small text-start">
              <strong>Prototype ito.</strong> Hindi naipadala ang report mo sa City Hall. Kung totoong problema ito,
              tumawag sa <a href="tel:8888">8888</a> o lumapit sa PACD ng City Hall.
            </Alert>
          )}
          {result.linked_to_existing && (
            <Alert variant="info" className="small text-start">
              May nauna nang nag-report nito. Pinagsama namin ang mga report para mas mabilis itong maaksyunan.
            </Alert>
          )}
          <div className="d-grid gap-2 mt-3">
            <Link to={`/track/${result.reference_no}`} className="btn btn-primary">
              I-track ang report
            </Link>
            <Button variant="outline-secondary" onClick={onAgain}>
              Mag-report ulit
            </Button>
          </div>
        </Card.Body>
      </Card>
    </Container>
  );
}
