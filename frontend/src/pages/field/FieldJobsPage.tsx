import { useEffect, useMemo, useState } from "react";
import { Alert, Badge, Button, ButtonGroup, Spinner } from "react-bootstrap";
import { Link, useLocation } from "react-router-dom";

import { apiErrorMessage } from "@/api/client";
import { useFieldJobs, type FieldJob } from "@/api/field";
import { haversineM } from "@/features/field/geo";
import { currentPosition } from "@/features/evidence/capture";
import { dueLabel, timeAgo } from "@/utils/format";

type Sort = "urgent" | "near";

export default function FieldJobsPage() {
  const { data, isLoading, isError, error, refetch, isFetching, dataUpdatedAt } = useFieldJobs();
  const [sort, setSort] = useState<Sort>("urgent");
  const [here, setHere] = useState<{ lat: number; lng: number } | null>(null);
  const flash = (useLocation().state as { flash?: string } | null)?.flash;

  useEffect(() => {
    void currentPosition(8000).then((p) => p && setHere({ lat: p.coords.latitude, lng: p.coords.longitude }));
  }, []);

  const jobs = useMemo(() => {
    const withDist = (data ?? []).map((j) => ({
      j,
      d: here && j.latitude && j.longitude ? haversineM(here.lat, here.lng, Number(j.latitude), Number(j.longitude)) : null,
    }));
    if (sort === "near") withDist.sort((a, b) => (a.d ?? Infinity) - (b.d ?? Infinity));
    return withDist;
  }, [data, here, sort]);

  if (isLoading) return <div className="text-center py-5"><Spinner /></div>;
  if (isError && !data) return <Alert variant="danger">{apiErrorMessage(error)}</Alert>;

  return (
    <>
      <div className="d-flex align-items-center justify-content-between mb-3">
        <h1 className="h4 mb-0">Mga trabaho ko</h1>
        <Button variant="outline-secondary" size="sm" onClick={() => void refetch()} disabled={isFetching}
          aria-label="I-refresh ang listahan">
          <i className={`bi bi-arrow-clockwise ${isFetching ? "spin" : ""}`} aria-hidden />
        </Button>
      </div>
      {flash && <Alert variant="success" className="py-2 small">{flash}</Alert>}
      <ButtonGroup className="w-100 mb-3" aria-label="Ayos ng listahan">
        <Button variant={sort === "urgent" ? "dark" : "outline-dark"} onClick={() => setSort("urgent")}>Pinaka-urgent</Button>
        <Button variant={sort === "near" ? "dark" : "outline-dark"} onClick={() => setSort("near")} disabled={!here}>
          Pinakamalapit
        </Button>
      </ButtonGroup>
      {isError && <div className="small text-warning-emphasis mb-2">Huling na-update {timeAgo(new Date(dataUpdatedAt).toISOString())} ang nakaraan.</div>}

      {jobs.length === 0 && (
        <div className="text-center text-secondary py-5">
          <i className="bi bi-check2-circle fs-1 d-block mb-2" aria-hidden />
          Wala kang naka-assign na trabaho ngayon.
        </div>
      )}
      <ul className="list-unstyled d-grid gap-2">
        {jobs.map(({ j, d }) => <JobCard key={j.id} j={j} distance={d} />)}
      </ul>
    </>
  );
}

function JobCard({ j, distance }: { j: FieldJob; distance: number | null }) {
  const due = dueLabel(j.due_at);
  return (
    <li>
      <Link to={`/field/jobs/${j.id}`} className="field-card" style={{ borderLeftColor: j.priority_color || "#898781" }}>
        <div className="d-flex justify-content-between gap-2">
          <span className="small fw-semibold" style={{ color: j.priority_color || undefined }}>
            {j.priority_code ?? "—"} {j.priority_name}
          </span>
          {due && <span className={`small ${due.overdue ? "text-danger fw-semibold" : "text-secondary"}`}>{due.text}</span>}
        </div>
        <div className="fw-bold fs-6 my-1">{j.title}</div>
        <div className="small text-secondary">
          <i className="bi bi-geo-alt me-1" aria-hidden />
          {[j.location_description, j.purok, j.barangay].filter(Boolean).join(", ")}
          {distance != null && <> · {distance < 1000 ? `${Math.round(distance)} m` : `${(distance / 1000).toFixed(1)} km`}</>}
        </div>
        <div className="mt-2 d-flex flex-wrap gap-1">
          {j.danger_now && <Badge bg="danger">May panganib</Badge>}
          {j.assigned_to_me ? <Badge bg="primary">Sa iyo</Badge> : j.assigned_to && <Badge bg="light" text="dark">{j.assigned_to}</Badge>}
          {j.arrived_at && <Badge bg="success"><i className="bi bi-geo-fill me-1" aria-hidden />Dumating</Badge>}
          {j.before_count > 0 && <Badge bg="success">Before ✓</Badge>}
          {j.blocked_reason && <Badge bg="warning" text="dark">{j.blocked_reason_display}</Badge>}
        </div>
      </Link>
    </li>
  );
}
