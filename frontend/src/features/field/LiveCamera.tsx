import { useEffect, useRef, useState } from "react";
import { Button, Spinner } from "react-bootstrap";

import { locationSource, preparePhotos, type EvidencePhoto } from "@/features/evidence/capture";

/**
 * Camera-only photo input for the field view. On phones `capture` opens the rear camera directly (no gallery),
 * and each photo is marked `live` with the phone's location at that moment. The server still checks distance,
 * age and reuse; "live" is only a positive signal when the location is at the site.
 */
export function LiveCamera({
  label, value, onChange, max = 3,
}: { label: string; value: EvidencePhoto[]; onChange: (p: EvidencePhoto[]) => void; max?: number }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => () => value.forEach((p) => URL.revokeObjectURL(p.preview)), []); // eslint-disable-line react-hooks/exhaustive-deps
  const noLoc = value.some((p) => locationSource(p.meta) === "none");

  return (
    <div className="mb-3">
      <div className="d-flex flex-wrap gap-2">
        {value.map((p, i) => (
          <div key={p.preview} className="field-thumb">
            <img src={p.preview} alt={`${label} ${i + 1}`} />
            <button type="button" className="field-thumb-x" aria-label="Alisin ang litrato"
              onClick={() => onChange(value.filter((_, j) => j !== i))}>
              <i className="bi bi-x-lg" aria-hidden />
            </button>
          </div>
        ))}
        {value.length < max && (
          <Button variant="outline-dark" className="field-shot" disabled={busy} onClick={() => input.current?.click()}>
            {busy ? <Spinner size="sm" /> : <><i className="bi bi-camera-fill fs-2 d-block" aria-hidden />{label}</>}
          </Button>
        )}
      </div>
      <input ref={input} type="file" accept="image/*" capture="environment" hidden
        onChange={async (e) => {
          const files = Array.from(e.target.files ?? []).slice(0, 1);
          e.target.value = "";
          if (!files.length) return;
          setBusy(true);
          try {
            const [p] = await preparePhotos(files);
            onChange([...value, { ...p, meta: { ...p.meta, live: true } }]);
          } finally {
            setBusy(false);
          }
        }} />
      {noLoc && (
        <div className="small text-warning-emphasis mt-1">
          <i className="bi bi-exclamation-triangle me-1" aria-hidden />
          Walang lokasyon ang litrato. Buksan ang Location ng cellphone at kunan ulit sa mismong lugar.
        </div>
      )}
    </div>
  );
}
