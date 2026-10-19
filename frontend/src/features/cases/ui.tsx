import { useState, type ReactNode } from "react";
import { Alert, Button, Card, Form, Spinner } from "react-bootstrap";

import { apiErrorMessage, apiFieldErrors } from "@/api/client";
import type { StaffConcernDetail } from "@/api/types";
import { compressImage } from "@/utils/compressImage";

export function Panel({
  title, icon, tone, children, hint,
}: { title: string; icon: string; tone?: "primary" | "warning" | "success" | "danger"; children: ReactNode; hint?: ReactNode }) {
  return (
    <Card className={`mb-3 border-0 shadow-sm ${tone ? `border-start border-4 border-${tone}` : ""}`}>
      <Card.Header className="bg-white fw-semibold">
        <i className={`bi bi-${icon} me-2`} aria-hidden />
        {title}
      </Card.Header>
      <Card.Body>
        {hint && <div className="small text-secondary mb-2">{hint}</div>}
        {children}
      </Card.Body>
    </Card>
  );
}

export function ErrorText({ err }: { err: unknown }) {
  if (!err) return null;
  const fields = apiFieldErrors(err);
  const msg = Object.keys(fields).length > 1 ? Object.values(fields).join(" ") : apiErrorMessage(err);
  return <Alert variant="danger" className="small py-2 mt-2 mb-0">{msg}</Alert>;
}

export function SubmitButton({
  pending, children, variant = "primary", disabled, onClick, className = "w-100",
}: { pending: boolean; children: ReactNode; variant?: string; disabled?: boolean; onClick?: () => void; className?: string }) {
  return (
    <Button type={onClick ? "button" : "submit"} variant={variant} className={className} disabled={pending || disabled} onClick={onClick}>
      {pending ? <Spinner size="sm" /> : children}
    </Button>
  );
}

export function PhotoPicker({ value, onChange, label }: { value: File[]; onChange: (f: File[]) => void; label: string }) {
  const [busy, setBusy] = useState(false);
  return (
    <Form.Group className="mb-2">
      <Form.Label className="small fw-semibold">{label}</Form.Label>
      <Form.Control
        type="file"
        accept="image/*"
        multiple
        disabled={busy}
        onChange={async (e) => {
          const files = Array.from((e.target as HTMLInputElement).files ?? []).slice(0, 3);
          setBusy(true);
          onChange(await Promise.all(files.map((f) => compressImage(f))));
          setBusy(false);
        }}
      />
      {value.length > 0 && <Form.Text>{value.length} litrato ang napili.</Form.Text>}
    </Form.Group>
  );
}

// ---------------- Stage stepper ----------------
type Step = { key: string; label: string };

const INTERNAL: Step[] = [
  { key: "received", label: "Natanggap" },
  { key: "verified", label: "Na-verify" },
  { key: "routed", label: "Naipasa" },
  { key: "assigned", label: "May tauhan" },
  { key: "inspected", label: "Na-inspeksyon" },
  { key: "done", label: "Tapos ang trabaho" },
  { key: "validated", label: "Na-validate" },
  { key: "closed", label: "Sarado" },
];
const EXTERNAL: Step[] = [
  { key: "received", label: "Natanggap" },
  { key: "verified", label: "Na-verify" },
  { key: "endorsed", label: "Inendorso" },
  { key: "agency", label: "Aksyon ng ahensya" },
  { key: "validated", label: "Na-validate ng LGU" },
  { key: "closed", label: "Sarado" },
];

/** Each step is marked done on its own fact, so skipped steps (e.g. endorsed before verifying) show honestly. */
export function stepsFor(c: StaffConcernDetail): { steps: Step[]; done: boolean[] } {
  const k = c.case;
  if (k?.level === "external") {
    const e = k.endorsements[0];
    const done = [
      true,
      c.is_verified,
      true,
      !!e && ["scheduled", "completed"].includes(e.status),
      !!k.validated_at,
      c.status === "closed",
    ];
    return { steps: EXTERNAL, done };
  }
  const steps = k?.level === "barangay" ? INTERNAL.filter((s) => s.key !== "assigned") : INTERNAL;
  const flags: Record<string, boolean> = {
    received: true,
    verified: c.is_verified,
    routed: !!k,
    assigned: !!k?.assigned_to,
    inspected: !!k?.inspected_at,
    done: !!k?.work_completed_at,
    validated: !!k?.validated_at,
    closed: c.status === "closed",
  };
  return { steps, done: steps.map((s) => flags[s.key]) };
}

export function Stepper({ c }: { c: StaffConcernDetail }) {
  if (c.status === "rejected") return <Alert variant="danger" className="py-2 small">Hindi inaksyunan (rejected).</Alert>;
  const { steps, done } = stepsFor(c);
  const current = done.indexOf(false);
  return (
    <div className="d-flex flex-wrap gap-1 mb-3 small" aria-label="Yugto ng kaso">
      {steps.map((s, i) => (
        <span
          key={s.key}
          className={`px-2 py-1 rounded-pill border ${
            done[i] ? "bg-success-subtle border-success-subtle text-success-emphasis"
              : i === current ? "bg-primary text-white border-primary"
                : "bg-light text-secondary"
          }`}
        >
          {done[i] && <i className="bi bi-check2 me-1" aria-hidden />}
          {s.label}
        </span>
      ))}
    </div>
  );
}
