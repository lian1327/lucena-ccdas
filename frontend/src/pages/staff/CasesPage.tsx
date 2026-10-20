import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Form, InputGroup, Nav } from "react-bootstrap";
import { Link, useSearchParams } from "react-router-dom";

import { apiErrorMessage } from "@/api/client";
import { useStaffConcerns, useStaffSummary, type InboxTab } from "@/api/staff";
import type { Role, StaffConcern } from "@/api/types";
import { useAuth } from "@/auth/AuthContext";
import { STAGE_LABEL, tabsFor } from "@/features/cases/roleViews";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { PriorityBadge } from "@/components/PriorityBadge";
import { UrgencyBadge } from "@/components/UrgencyBadge";
import { StatusBadge } from "@/components/StatusBadge";
import { dueLabel, timeAgo } from "@/utils/format";

function CaseRow({ c }: { c: StaffConcern }) {
  const due = dueLabel(c.due_at);
  return (
    <Card as={Link} to={`/staff/cases/${c.id}`} className="text-decoration-none text-body mb-2 case-row">
      <Card.Body className="py-2 px-3">
        <div className="d-flex flex-wrap align-items-center gap-2 mb-1">
          <UrgencyBadge code={c.priority_code} name={c.priority_name} color={c.priority_color} />
          <PriorityBadge tier={c.priority_tier} score={c.priority_score} />
          {c.stage === "for_acceptance" && <Badge bg="primary">For acceptance</Badge>}
          {c.return_reason && c.stage === "returned" && <Badge bg="danger" title={c.return_reason}>Ibinalik ng opisina</Badge>}
          {!c.responded_at && c.response_due_at && new Date(c.response_due_at) < new Date() && (
            <Badge bg="danger">Walang unang aksyon</Badge>
          )}
          {c.danger_now && (
            <Badge bg="danger" title="Sinabi ng nag-report na may panganib">
              <i className="bi bi-exclamation-triangle-fill me-1" aria-hidden />
              Panganib
            </Badge>
          )}
          {!c.is_verified && <Badge bg="light" text="dark" className="border">Hindi pa verified</Badge>}
          {c.is_overdue && <Badge bg="danger">Overdue</Badge>}
          {c.escalation_level > 0 && <Badge bg="dark">Escalated L{c.escalation_level}</Badge>}
          {c.channel === "8888" && !c.external_feedback_sent_at && <Badge bg="warning" text="dark">8888 feedback due</Badge>}
          {c.level === "external" && <Badge bg="dark">Endorsed: {c.department}</Badge>}
          {c.level === "barangay" && <Badge bg="info" text="dark">Barangay-level</Badge>}
          {c.stage === "for_validation" && <Badge bg="success">For validation</Badge>}
          {c.duplicate_count > 0 && (
            <Badge bg="secondary" title="Iba pang nag-report ng parehong problema">
              +{c.duplicate_count} report
            </Badge>
          )}
          <span className="ms-auto small text-secondary">{c.reference_no}</span>
        </div>
        <div className="fw-semibold">{c.title}</div>
        <div className="small text-secondary d-flex flex-wrap gap-x-3 column-gap-3">
          <span>
            <i className="bi bi-geo-alt me-1" aria-hidden />
            {c.barangay}
          </span>
          {c.category && <span>{c.subcategory ?? c.category}</span>}
          <span>{timeAgo(c.created_at)} na</span>
          {c.department && c.level !== "external" && (
            <span>
              <i className="bi bi-building me-1" aria-hidden />
              {c.division ?? c.department}
              {c.assigned_to && ` · ${c.assigned_to}`}
            </span>
          )}
          {c.stage && c.stage !== "for_validation" && c.stage !== "endorsed" && c.status !== "closed" && (
            <span className="text-body-secondary fst-italic">{STAGE_LABEL[c.stage] ?? c.stage}</span>
          )}
          {due && <span className={due.overdue ? "text-danger fw-semibold" : ""}>{due.text}</span>}
        </div>
        <div className="mt-1">
          <StatusBadge status={c.status} label={c.status_display} />
        </div>
      </Card.Body>
    </Card>
  );
}

export function CasesPage() {
  const { user } = useAuth();
  const tabs = tabsFor(user?.role as Role | undefined);
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as InboxTab) || tabs[0].key;
  const page = Number(params.get("page") || 1);
  const q = params.get("q") ?? "";
  const [search, setSearch] = useState(q);
  useEffect(() => setSearch(q), [q]);

  const summary = useStaffSummary();
  const list = useStaffConcerns({ tab, q, page });

  const go = (next: Record<string, string | number | undefined>) => {
    const p = new URLSearchParams(params);
    Object.entries(next).forEach(([k, v]) => (v === undefined || v === "" ? p.delete(k) : p.set(k, String(v))));
    setParams(p);
  };

  return (
    <>
      <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
        <h1 className="h4 fw-bold mb-0 me-auto">Mga Kaso</h1>
        <Link to="/staff/encode" className="btn btn-primary btn-sm">
          <i className="bi bi-plus-lg me-1" aria-hidden />
          I-encode ang report
        </Link>
      </div>

      <Nav variant="tabs" className="mb-3 flex-nowrap overflow-auto text-nowrap">
        {tabs.map((t) => {
          const n = t.count ? summary.data?.[t.count] : undefined;
          return (
            <Nav.Item key={t.key}>
              <Nav.Link active={tab === t.key} onClick={() => go({ tab: t.key, page: undefined })}>
                {t.label}
                {n !== undefined && n > 0 && (
                  <Badge bg={t.danger ? "danger" : "secondary"} pill className="ms-1">
                    {n}
                  </Badge>
                )}
              </Nav.Link>
            </Nav.Item>
          );
        })}
      </Nav>

      <Form
        className="mb-3"
        onSubmit={(e) => {
          e.preventDefault();
          go({ q: search.trim(), page: undefined });
        }}
      >
        <InputGroup>
          <Form.Control
            placeholder="Hanapin: reference no., 8888 ticket, pamagat, palatandaan…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Button type="submit" variant="outline-secondary" aria-label="Hanapin">
            <i className="bi bi-search" />
          </Button>
        </InputGroup>
      </Form>

      {tab === "to_route" && (
        <p className="small text-secondary">Na-verify pero hindi pa naipapasa, o ibinalik ng opisina. Magsisimula ang ARTA target sa pagpasa.</p>
      )}
      {tab === "for_acceptance" && (
        <p className="small text-secondary">Naipasa sa opisina pero hindi pa tinatanggap. Dapat tanggapin o ibalik sa loob ng 1 working day.</p>
      )}
      {tab === "triage" && (
        <p className="small text-secondary">
          Bagong reports na hindi pa nasusuri. Nauuna ang may <strong>panganib</strong>, saka ang may pinakamataas na
          priority.
        </p>
      )}

      {list.isLoading ? (
        <FullPageSpinner />
      ) : list.isError ? (
        <Alert variant="danger">{apiErrorMessage(list.error)}</Alert>
      ) : list.data!.results.length === 0 ? (
        <Card body className="text-center text-secondary">
          <i className="bi bi-inbox fs-2 d-block" aria-hidden />
          Walang kaso dito.
        </Card>
      ) : (
        <div style={{ opacity: list.isPlaceholderData ? 0.6 : 1 }}>
          {list.data!.results.map((c) => (
            <CaseRow key={c.id} c={c} />
          ))}
          <div className="d-flex justify-content-between align-items-center mt-3 small">
            <Button size="sm" variant="outline-secondary" disabled={!list.data!.previous} onClick={() => go({ page: page - 1 })}>
              ‹ Nauna
            </Button>
            <span className="text-secondary">
              Pahina {page} · {list.data!.count} kaso
            </span>
            <Button size="sm" variant="outline-secondary" disabled={!list.data!.next} onClick={() => go({ page: page + 1 })}>
              Susunod ›
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
