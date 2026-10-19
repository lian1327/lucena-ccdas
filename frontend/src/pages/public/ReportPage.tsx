import { Card, Container } from "react-bootstrap";

/** Placeholder — the full reporting form (map pin, photo upload, consent) is built in the citizen-portal step. */
export function ReportPage() {
  return (
    <Container className="py-5" style={{ maxWidth: 720 }}>
      <Card body className="text-center text-secondary">
        <i className="bi bi-tools fs-1" aria-hidden />
        <p className="mt-2 mb-0">The reporting form is coming in the next step.</p>
      </Card>
    </Container>
  );
}
