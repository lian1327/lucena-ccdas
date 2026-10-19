import { Card, Col, Row } from "react-bootstrap";
import { Link } from "react-router-dom";

import { useStaffSummary } from "@/api/staff";
import { useAuth } from "@/auth/AuthContext";

/** Work-queue summary. Charts and KPIs come with the analytics module. */
export function DashboardPage() {
  const { user } = useAuth();
  const s = useStaffSummary().data;

  const tiles = [
    { label: "Kailangang suriin", sub: "Triage", value: s?.triage, to: "triage", icon: "clipboard-check", tone: "primary" },
    { label: "May panganib, hindi pa nasusuri", sub: "Unverified danger", value: s?.danger_unverified, to: "triage", icon: "exclamation-triangle", tone: "danger" },
    { label: "Sa opisina ko", sub: "My office", value: s?.mine, to: "mine", icon: "person-workspace", tone: "secondary" },
    { label: "Lampas na sa target", sub: "Overdue", value: s?.overdue, to: "overdue", icon: "alarm", tone: "danger" },
    { label: "Lahat ng bukas", sub: "Open", value: s?.open, to: "open", icon: "inboxes", tone: "secondary" },
    { label: "Naayos ngayong buwan", sub: "Resolved this month", value: s?.resolved_this_month, to: "closed", icon: "check2-circle", tone: "success" },
  ];

  return (
    <>
      <h1 className="h4 fw-bold">Magandang araw, {user?.first_name || user?.full_name}</h1>
      <p className="text-secondary">
        {user?.role_display}
        {user?.department && ` · ${user.department}`}
        {user?.barangay && ` · ${user.barangay}`}
      </p>
      <Row className="g-3">
        {tiles.map((t) => (
          <Col xs={6} lg={4} key={t.label}>
            <Card as={Link} to={`/staff/cases?tab=${t.to}`} className="h-100 border-0 shadow-sm text-decoration-none text-body">
              <Card.Body>
                <div className={`text-${t.tone} mb-1`}>
                  <i className={`bi bi-${t.icon} fs-4`} aria-hidden />
                </div>
                <div className="fs-2 fw-bold lh-1">{t.value ?? "–"}</div>
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
