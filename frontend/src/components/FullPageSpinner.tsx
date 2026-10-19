import { Spinner } from "react-bootstrap";

export function FullPageSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="d-flex flex-column align-items-center justify-content-center py-5 gap-2 text-secondary">
      <Spinner animation="border" role="status" />
      <span className="small">{label}</span>
    </div>
  );
}
