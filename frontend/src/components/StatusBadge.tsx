import { Badge } from "react-bootstrap";

import type { ConcernStatus } from "@/api/types";

const VARIANT: Record<ConcernStatus, string> = {
  submitted: "secondary",
  under_review: "info",
  assigned: "primary",
  in_progress: "warning",
  resolved: "success",
  closed: "dark",
  rejected: "danger",
};

export function StatusBadge({ status, label }: { status: ConcernStatus | undefined; label?: string }) {
  if (!status) return null;
  return (
    <Badge bg={VARIANT[status]} text={status === "in_progress" ? "dark" : undefined} pill>
      {label ?? status.replace("_", " ")}
    </Badge>
  );
}
