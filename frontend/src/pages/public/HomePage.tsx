/**
 * TEMPORARY home page — proves the API wiring (stats + categories).
 * Replaced by the full landing page in the next step.
 */
import { Card, Col, Container, Row } from "react-bootstrap";
import { Link } from "react-router-dom";

import { useCategories, usePublicStats } from "@/api/public";
import { FullPageSpinner } from "@/components/FullPageSpinner";

export function HomePage() {
  const stats = usePublicStats();
  const categories = useCategories();
  const t = stats.data?.totals;

  return (
    <Container className="py-5">
      <div className="text-center mb-5">
        <h1 className="fw-bold">Report a community concern</h1>
        <p className="text-secondary">Submit, then track it until it's resolved.</p>
        <div className="d-flex gap-2 justify-content-center">
          <Link to="/report" className="btn btn-primary btn-lg">Report a Concern</Link>
          <Link to="/track" className="btn btn-outline-secondary btn-lg">Track a Concern</Link>
        </div>
      </div>

      {stats.isLoading ? (
        <FullPageSpinner label="Loading stats…" />
      ) : stats.isError ? (
        <p className="text-danger text-center">Could not load stats — is the Django server running?</p>
      ) : (
        <Row className="g-3 mb-5">
          {[
            ["Concerns received", t?.total],
            ["Open", t?.open],
            ["Resolved", t?.resolved],
            ["Resolution rate", `${t?.resolution_rate ?? 0}%`],
          ].map(([label, value]) => (
            <Col xs={6} md={3} key={label as string}>
              <Card body className="text-center h-100">
                <div className="fs-2 fw-bold">{value}</div>
                <div className="small text-secondary">{label}</div>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      <h2 className="h5 mb-3">Categories</h2>
      <Row className="g-3">
        {categories.data?.map((c) => (
          <Col xs={6} md={3} key={c.code}>
            <Card body className="h-100">
              <i className={`bi bi-${c.icon} fs-3 text-primary`} aria-hidden />
              <div className="fw-semibold mt-2">{c.name}</div>
              <div className="small text-secondary">{c.name_fil}</div>
            </Card>
          </Col>
        ))}
      </Row>
    </Container>
  );
}
