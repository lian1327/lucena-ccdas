import { Badge } from "react-bootstrap";

import { FlagChip } from "@/features/evidence/ui";

type Flag = { code: string; level: string; label: string };

/** Compact screening badges for the case list. Signals for the PACD, never a verdict. */
export function ReviewFlagBadges({ flags }: { flags: Flag[] | undefined }) {
  if (!flags?.length) return null;
  return (
    <>
      {flags.map((f) => (
        <Badge key={f.code} bg={f.level === "good" ? "success" : f.level === "red" ? "danger" : "warning"}
          text={f.level === "amber" ? "dark" : undefined} title={f.label}>
          <i className={`bi bi-${f.level === "good" ? "camera-fill" : "flag-fill"} me-1`} aria-hidden />
          {f.level === "good" ? "Live photo" : "Suriin"}
        </Badge>
      ))}
    </>
  );
}

/** Full explanation on the case page. */
export function ReviewFlagNote({ flags }: { flags: Flag[] | undefined }) {
  if (!flags?.length) return null;
  const warn = flags.some((f) => f.level !== "good");
  return (
    <div className={`small p-2 mb-2 rounded border ${warn ? "border-warning bg-warning-subtle" : "bg-success-subtle border-success-subtle"}`}>
      <div className="mb-1">
        <i className="bi bi-shield-check me-1" aria-hidden />
        <strong>Mga palatandaan sa pagsusuri</strong>
        {warn && <span className="text-secondary"> · hindi ito hatol; tingnan ang report at ang lugar bago magpasya</span>}
      </div>
      {flags.map((f) => <FlagChip key={f.code} f={f} />)}
    </div>
  );
}
