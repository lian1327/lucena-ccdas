import { Badge } from "react-bootstrap";

import type { Attachment, EvidenceFlag } from "@/api/types";
import { fmtDateTime } from "@/utils/format";

const LEVEL = {
  red: { bg: "danger", icon: "x-octagon-fill" },
  amber: { bg: "warning", icon: "exclamation-triangle-fill" },
  info: { bg: "secondary", icon: "info-circle" },
} as const;

export function FlagChip({ f }: { f: Pick<EvidenceFlag, "code" | "label"> & { level: string } }) {
  const l = LEVEL[f.level as keyof typeof LEVEL] ?? LEVEL.info;
  return (
    <Badge bg={l.bg} text={f.level === "amber" ? "dark" : undefined} className="fw-normal text-wrap text-start me-1 mb-1">
      <i className={`bi bi-${l.icon} me-1`} aria-hidden />{f.label}
    </Badge>
  );
}

export function GpsLine({ a }: { a: Pick<Attachment, "gps_source" | "distance_m" | "gps_accuracy_m"> }) {
  if (a.gps_source === "none") return <span className="text-warning-emphasis"><i className="bi bi-geo me-1" aria-hidden />Walang lokasyon</span>;
  const src = a.gps_source === "exif" ? "GPS ng camera" : `lokasyon ng cellphone${a.gps_accuracy_m ? ` (±${Math.round(a.gps_accuracy_m)} m)` : ""}`;
  return (
    <span className={a.distance_m != null && a.distance_m > 150 ? "text-danger" : "text-success"}>
      <i className="bi bi-geo-alt-fill me-1" aria-hidden />
      {a.distance_m != null ? `${Math.round(a.distance_m)} m mula sa pin` : "may lokasyon"} · {src}
    </span>
  );
}

/** One evidence photo with where/when/by-whom and any check flags. */
export function EvidencePhotoCard({ a, compact }: { a: Attachment; compact?: boolean }) {
  return (
    <figure className="m-0 border rounded overflow-hidden bg-white h-100">
      <a href={a.url} target="_blank" rel="noreferrer">
        <img src={a.url} alt={a.kind} className="w-100" style={{ height: compact ? 110 : 170, objectFit: "cover" }} />
      </a>
      <figcaption className="p-2 small lh-sm">
        <div><GpsLine a={a} /></div>
        <div className="text-secondary">
          <i className="bi bi-clock me-1" aria-hidden />
          {a.taken_at ? `Kinuha ${fmtDateTime(a.taken_at)}` : `In-upload ${fmtDateTime(a.uploaded_at)}`}
          {a.time_source === "upload" && <span title="Walang oras mula sa camera"> *</span>}
        </div>
        {a.uploaded_by && <div className="text-secondary"><i className="bi bi-person me-1" aria-hidden />{a.uploaded_by}</div>}
        {a.flags.length > 0 && <div className="mt-1">{a.flags.map((f) => <FlagChip key={f.code} f={f} />)}</div>}
      </figcaption>
    </figure>
  );
}
