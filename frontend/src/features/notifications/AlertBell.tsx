import { Badge, Button, Dropdown } from "react-bootstrap";
import { useNavigate } from "react-router-dom";

import { useAlerts, useReadAlert, useReadAllAlerts } from "@/api/notifications";
import { timeAgo } from "@/utils/format";

const ICON: Record<string, string> = {
  new_case: "inbox", assigned: "person-check", returned: "arrow-return-left", danger: "exclamation-octagon",
  for_validation: "clipboard-check", sent_back: "arrow-counterclockwise", escalated: "arrow-up-circle",
  disputed: "hand-thumbs-down",
};

/** Staff header bell: what now needs *my* action. Opening an alert marks it read and goes to the case. */
export function AlertBell() {
  const alerts = useAlerts();
  const read = useReadAlert();
  const readAll = useReadAllAlerts();
  const navigate = useNavigate();
  const data = alerts.data;
  const unread = data?.unread ?? 0;

  return (
    <Dropdown align="end" className="me-2">
      <Dropdown.Toggle variant="outline-light" size="sm" className="position-relative" aria-label={`Mga alerto, ${unread} hindi pa nababasa`}>
        <i className="bi bi-bell" aria-hidden />
        {unread > 0 && (
          <Badge pill bg={data?.urgent_unread ? "danger" : "warning"} text={data?.urgent_unread ? undefined : "dark"}
            className="position-absolute top-0 start-100 translate-middle">
            {unread > 99 ? "99+" : unread}
          </Badge>
        )}
      </Dropdown.Toggle>
      <Dropdown.Menu data-bs-theme="light" style={{ width: 360, maxWidth: "92vw" }} className="p-0">
        <div className="d-flex justify-content-between align-items-center px-3 py-2 border-bottom">
          <span className="fw-bold">Mga alerto</span>
          {unread > 0 && (
            <Button size="sm" variant="link" className="p-0" onClick={() => readAll.mutate()}>Markahang nabasa lahat</Button>
          )}
        </div>
        <div style={{ maxHeight: 420, overflowY: "auto" }}>
          {!data?.results.length && <div className="px-3 py-4 small text-secondary text-center">Wala kang bagong alerto.</div>}
          {data?.results.map((a) => (
            <Dropdown.Item
              key={a.id}
              as="button"
              className={`d-flex gap-2 px-3 py-2 border-bottom text-wrap ${a.read_at ? "" : "bg-primary-subtle"}`}
              onClick={() => {
                if (!a.read_at) read.mutate(a.id);
                if (a.concern_id) navigate(`/staff/cases/${a.concern_id}`);
              }}
            >
              <i className={`bi bi-${ICON[a.kind] ?? "bell"} ${a.is_urgent ? "text-danger" : "text-primary"} mt-1`} aria-hidden />
              <span className="small">
                <span className={`d-block ${a.read_at ? "" : "fw-bold"}`}>{a.title}</span>
                {a.body && <span className="d-block text-secondary">{a.body}</span>}
                <span className="d-block text-secondary">{timeAgo(a.created_at)}</span>
              </span>
            </Dropdown.Item>
          ))}
        </div>
      </Dropdown.Menu>
    </Dropdown>
  );
}
