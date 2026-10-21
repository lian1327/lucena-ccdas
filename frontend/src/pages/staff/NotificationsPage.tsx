import { useState } from "react";
import { Badge, Button, Card, Col, Form, Pagination, Row, Table } from "react-bootstrap";
import { Link } from "react-router-dom";

import { useNotificationLog, useNotificationStats, useRetryNotification, type NotificationFilters } from "@/api/notifications";
import { useAuth } from "@/auth/AuthContext";
import { KpiTile } from "@/features/analytics/ui";
import { NOTIF_TONE } from "@/features/notifications/CaseNotifications";
import { fmtDateTime } from "@/utils/format";

const EVENTS: [string, string][] = [
  ["received", "Natanggap"], ["assigned", "Naipasa"], ["in_progress", "Inaaksyunan"], ["extended", "Na-extend"],
  ["resolved", "Naayos"], ["reminder", "Paalala: kumpirmahin"], ["reopened", "Binuksan muli"], ["closed", "Isinara"],
  ["rejected", "Hindi maaaksyunan"],
];

export default function NotificationsPage() {
  const { hasRole } = useAuth();
  const [f, setF] = useState<NotificationFilters>({ page: 1 });
  const log = useNotificationLog(f);
  const stats = useNotificationStats();
  const retry = useRetryNotification();
  const s = stats.data;
  const pages = Math.max(1, Math.ceil((log.data?.count ?? 0) / 25));
  const set = (k: keyof NotificationFilters, v: string) => setF({ ...f, [k]: v || undefined, page: 1 });

  return (
    <div>
      <h1 className="h4 fw-bold mb-1">SMS at email sa mga nag-report</h1>
      <p className="text-secondary small mb-3">
        Bawat mahalagang update ay awtomatikong ipinapaalam. Naka-mask ang mga numero (RA 10173).
        {s && <> Provider: <b>{s.provider}</b>{s.provider === "console" && " (development: walang totoong SMS na lumalabas)"}.</>}
      </p>

      {s && (
        <Row className="g-3 mb-4">
          <Col xs={6} lg><KpiTile label="SMS ngayong buwan" value={s.month_sms.toLocaleString()} sub={`${s.month_credits.toLocaleString()} credits`} /></Col>
          <Col xs={6} lg><KpiTile label="Umabot sa network" value={s.delivered_rate == null ? "—" : `${s.delivered_rate}%`}
            sub="sa may final status" tip="Delivered ÷ (delivered + failed), ayon sa provider." /></Col>
          <Col xs={6} lg><KpiTile label="Nabigo" value={s.failed} tone={s.failed ? "danger" : undefined} sub={`${s.queued} naghihintay`} /></Col>
          <Col xs={6} lg><KpiTile label="Maaabot ng update" value={s.reach_rate == null ? "—" : `${s.reach_rate}%`}
            sub="ng mga report ngayong buwan" tip="Report na may mobile o email at hindi anonymous." /></Col>
          <Col xs={6} lg><KpiTile label="Natitirang credits" value={s.credit_balance == null ? "—" : s.credit_balance.toLocaleString()}
            sub={`${s.opted_out} nag-opt out`} /></Col>
        </Row>
      )}

      <Card className="border-0 shadow-sm">
        <Card.Body>
          <Row className="g-2 mb-3">
            <Col md={3}><Form.Control size="sm" placeholder="Reference no." aria-label="Reference number"
              onChange={(e) => set("q", e.target.value)} /></Col>
            <Col xs={6} md={2}>
              <Form.Select size="sm" aria-label="Channel" onChange={(e) => set("channel", e.target.value)}>
                <option value="">Lahat ng channel</option><option value="sms">SMS</option><option value="email">Email</option>
              </Form.Select>
            </Col>
            <Col xs={6} md={3}>
              <Form.Select size="sm" aria-label="Event" onChange={(e) => set("event", e.target.value)}>
                <option value="">Lahat ng update</option>
                {EVENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </Form.Select>
            </Col>
            <Col xs={6} md={2}>
              <Form.Select size="sm" aria-label="Status" onChange={(e) => set("status", e.target.value)}>
                <option value="">Lahat ng status</option>
                {["queued", "sent", "delivered", "failed"].map((v) => <option key={v}>{v}</option>)}
              </Form.Select>
            </Col>
          </Row>

          <Table responsive size="sm" className="small align-middle">
            <thead>
              <tr><th>Petsa</th><th>Report</th><th>Update</th><th>Para kay</th><th>Mensahe</th><th>Status</th><th /></tr>
            </thead>
            <tbody>
              {log.data?.results.map((n) => (
                <tr key={n.id}>
                  <td className="text-nowrap">{fmtDateTime(n.sent_at ?? n.created_at)}</td>
                  <td className="text-nowrap"><Link to={`/staff/cases/${n.concern_id}`}>{n.reference_no}</Link></td>
                  <td className="text-nowrap"><i className={`bi ${n.channel === "sms" ? "bi-phone" : "bi-envelope"} me-1`} aria-hidden />{n.event_display}</td>
                  <td className="text-nowrap">{n.recipient || <span className="text-secondary">(binura)</span>}</td>
                  <td style={{ minWidth: 260 }}>{n.channel === "sms" ? n.body : n.subject}
                    {n.segments > 1 && <Badge bg="light" text="dark" className="ms-1 border">{n.segments} parts</Badge>}
                    {n.error && <div className="text-danger">{n.error}</div>}</td>
                  <td><Badge bg={NOTIF_TONE[n.status] ?? "secondary"}>{n.status_display}</Badge>
                    {n.status === "queued" && <div className="text-secondary">{fmtDateTime(n.scheduled_for)}</div>}</td>
                  <td>{n.can_retry && hasRole("city_admin", "pacd") && (
                    <Button size="sm" variant="outline-primary" disabled={retry.isPending} onClick={() => retry.mutate(n.id)}>Ulitin</Button>
                  )}</td>
                </tr>
              ))}
              {log.data && !log.data.results.length && (
                <tr><td colSpan={7} className="text-center text-secondary py-4">Wala pang naipapadalang abiso.</td></tr>
              )}
            </tbody>
          </Table>
          {pages > 1 && (
            <Pagination size="sm" className="mb-0">
              <Pagination.Prev disabled={(f.page ?? 1) <= 1} onClick={() => setF({ ...f, page: (f.page ?? 1) - 1 })} />
              <Pagination.Item active>{f.page ?? 1} / {pages}</Pagination.Item>
              <Pagination.Next disabled={(f.page ?? 1) >= pages} onClick={() => setF({ ...f, page: (f.page ?? 1) + 1 })} />
            </Pagination>
          )}
        </Card.Body>
      </Card>
    </div>
  );
}
