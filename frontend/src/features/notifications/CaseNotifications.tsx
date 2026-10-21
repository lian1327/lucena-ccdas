import { Badge } from "react-bootstrap";

import type { StaffConcernDetail } from "@/api/types";
import { Panel } from "@/features/cases/ui";
import { fmtDateTime } from "@/utils/format";

export const NOTIF_TONE: Record<string, string> = {
  queued: "secondary", sent: "primary", delivered: "success", failed: "danger", skipped: "light",
};

/** What the reporter was told, and whether it reached them. */
export function CaseNotifications({ c }: { c: StaffConcernDetail }) {
  const rows = c.notifications ?? [];
  if (!rows.length) return null;
  return (
    <Panel title="Mga abiso sa nag-report" icon="chat-dots" hint="SMS at email na awtomatikong ipinadala sa bawat update.">
      <ul className="list-unstyled mb-0 small">
        {rows.map((n) => (
          <li key={n.id} className="mb-2 pb-2 border-bottom">
            <div className="d-flex flex-wrap gap-1 align-items-center">
              <i className={`bi ${n.channel === "sms" ? "bi-phone" : "bi-envelope"}`} aria-hidden />
              <span className="fw-semibold">{n.event_display}</span>
              <Badge bg={NOTIF_TONE[n.status] ?? "secondary"} text={n.status === "skipped" ? "dark" : undefined}>{n.status}</Badge>
              <span className="text-secondary ms-auto">{fmtDateTime(n.sent_at ?? n.created_at)}</span>
            </div>
            {n.channel === "sms" && <div className="text-secondary mt-1">{n.body}</div>}
            {n.error && <div className="text-danger mt-1">{n.error}</div>}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
