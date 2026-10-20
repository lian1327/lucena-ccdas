import { Badge } from "react-bootstrap";

/** P1–P4 office-confirmed urgency (separate from the computed 0–100 priority score). */
export function UrgencyBadge({ code, name, color }: { code?: string | null; name?: string | null; color?: string | null }) {
  if (!code) return null;
  const bg = color || "secondary";
  return (
    <Badge bg={bg} text={bg === "warning" || bg === "info" ? "dark" : undefined} title={name ?? undefined}>
      {code === "P1" && <i className="bi bi-lightning-charge-fill me-1" aria-hidden />}
      {code} · {name}
    </Badge>
  );
}
