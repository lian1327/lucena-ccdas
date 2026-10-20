import { Card, Col, Row } from "react-bootstrap";
import { Link } from "react-router-dom";

import { useStaffSummary } from "@/api/staff";
import type { Role, StaffSummary } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";

type Tile = { key: keyof StaffSummary; label: string; sub: string; tab: string; icon: string; tone: string };

const ALL: Record<string, Tile> = {
  triage: { key: "triage", label: "Kailangang suriin", sub: "Triage", tab: "triage", icon: "clipboard-check", tone: "primary" },
  danger: { key: "danger_unverified", label: "May panganib, hindi pa nasusuri", sub: "Unverified danger", tab: "triage", icon: "exclamation-triangle", tone: "danger" },
  accept: { key: "for_acceptance", label: "Tatanggapin ng opisina", sub: "Office acceptance (1 WD)", tab: "for_acceptance", icon: "inbox", tone: "primary" },
  returned: { key: "returned", label: "Ibinalik ng opisina", sub: "Returned to PACD", tab: "to_route", icon: "arrow-return-left", tone: "danger" },
  response: { key: "response_overdue", label: "Walang unang aksyon (lampas)", sub: "Response overdue", tab: "overdue", icon: "stopwatch", tone: "danger" },
  p1: { key: "p1_open", label: "Bukas na P1 Emergency", sub: "Make-safe priority", tab: "open", icon: "lightning-charge", tone: "danger" },
  to_route: { key: "to_route", label: "Ipapasa sa opisina", sub: "To route", tab: "to_route", icon: "signpost-split", tone: "primary" },
  mine: { key: "mine", label: "Kailangan ng aksyon ko", sub: "My queue", tab: "mine", icon: "person-workspace", tone: "primary" },
  validation: { key: "validation", label: "Hinihintay ang validation", sub: "For validation", tab: "validation", icon: "patch-check", tone: "success" },
  f8888: { key: "feedback_8888_due", label: "8888 feedback na due", sub: "72-hour rule", tab: "mine", icon: "telephone-inbound", tone: "warning" },
  follow: { key: "follow_up_due", label: "Endorsement na kailangang i-follow up", sub: "DPWH / utilities", tab: "endorsed", icon: "box-arrow-up-right", tone: "warning" },
  overdue: { key: "overdue", label: "Lampas na sa ARTA target", sub: "Overdue", tab: "overdue", icon: "alarm", tone: "danger" },
  open: { key: "open", label: "Lahat ng bukas", sub: "Open", tab: "open", icon: "inboxes", tone: "secondary" },
  resolved: { key: "resolved_this_month", label: "Naayos ngayong buwan", sub: "Resolved this month", tab: "closed", icon: "check2-circle", tone: "success" },
};

const BY_ROLE: Partial<Record<Role, string[]>> = {
  pacd: ["triage", "danger", "to_route", "returned", "f8888", "follow", "mine", "resolved"],
  city_admin: ["p1", "danger", "accept", "response", "overdue", "returned", "follow", "resolved"],
  office_desk: ["accept", "mine", "p1", "response", "overdue", "resolved"],
  dept_head: ["mine", "accept", "p1", "response", "validation", "overdue", "resolved"],
  division_chief: ["mine", "p1", "response", "validation", "overdue", "resolved"],
  dept_staff: ["mine", "p1", "response", "overdue", "resolved"],
  barangay: ["triage", "to_route", "mine", "validation", "overdue", "resolved"],
  mayor: ["p1", "overdue", "response", "accept", "follow", "resolved"],
};

export function DashboardPage() {
  const { user } = useAuth();
  const s = useStaffSummary().data;
  const tiles = (BY_ROLE[user?.role as Role] ?? ["open", "resolved"]).map((k) => ALL[k]);

  return (
    <>
      <h1 className="h4 fw-bold">Magandang araw, {user?.first_name || user?.full_name}</h1>
      <p className="text-secondary">
        {user?.role_display}
        {user?.department && ` · ${user.department}`}
        {user?.division && ` · ${user.division}`}
        {user?.barangay && ` · Brgy. ${user.barangay}`}
      </p>
      <Row className="g-3">
        {tiles.map((t) => (
          <Col xs={6} lg={3} key={t.label}>
            <Card as={Link} to={`/staff/cases?tab=${t.tab}`} className="h-100 border-0 shadow-sm text-decoration-none text-body">
              <Card.Body>
                <div className={`text-${t.tone} mb-1`}><i className={`bi bi-${t.icon} fs-4`} aria-hidden /></div>
                <div className="fs-2 fw-bold lh-1">{s?.[t.key] ?? "–"}</div>
                <div className="small fw-semibold mt-1">{t.label}</div>
                <div className="small text-secondary">{t.sub}</div>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>
    </>
  );
}
