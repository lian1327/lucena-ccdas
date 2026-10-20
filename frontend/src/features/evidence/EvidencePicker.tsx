import { useEffect, useRef, useState } from "react";
import { Button, Form, Spinner } from "react-bootstrap";

import { locationSource, preparePhotos, type EvidencePhoto } from "./capture";

const SRC = {
  exif: { icon: "geo-alt-fill", text: "May GPS mula sa camera", cls: "text-success" },
  device: { icon: "phone", text: "Lokasyon ng cellphone ngayon", cls: "text-success" },
  none: { icon: "geo", text: "Walang lokasyon", cls: "text-warning-emphasis" },
} as const;

/**
 * Camera-first photo input for proof of work. Opens the rear camera on phones, keeps the camera's GPS/time
 * and shows the crew right away whether the photo has a location.
 */
export function EvidencePicker({
  label, value, onChange, required, max = 3, hint,
}: {
  label: string; value: EvidencePhoto[]; onChange: (p: EvidencePhoto[]) => void; required?: boolean; max?: number; hint?: string;
}) {
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => () => value.forEach((p) => URL.revokeObjectURL(p.preview)), []); // eslint-disable-line react-hooks/exhaustive-deps
  const noLoc = value.some((p) => locationSource(p.meta) === "none");
  return (
    <Form.Group className="mb-3">
      <Form.Label className="small fw-semibold mb-1">
        {label} {required && <span className="text-danger">*</span>}
      </Form.Label>
      {hint && <div className="small text-secondary mb-1">{hint}</div>}
      <div className="d-flex flex-wrap gap-2">
        {value.map((p, i) => {
          const s = SRC[locationSource(p.meta)];
          return (
            <div key={p.preview} className="border rounded p-1 small" style={{ width: 128 }}>
              <img src={p.preview} alt="" className="w-100 rounded" style={{ height: 84, objectFit: "cover" }} />
              <div className={`${s.cls} mt-1 lh-sm`}><i className={`bi bi-${s.icon} me-1`} aria-hidden />{s.text}</div>
              <Button variant="link" size="sm" className="p-0 text-danger" onClick={() => onChange(value.filter((_, j) => j !== i))}>Alisin</Button>
            </div>
          );
        })}
        {value.length < max && (
          <button type="button" className="border rounded bg-light d-flex flex-column align-items-center justify-content-center text-secondary"
            style={{ width: 128, height: 132 }} disabled={busy} onClick={() => input.current?.click()}>
            {busy ? <Spinner size="sm" /> : <><i className="bi bi-camera fs-3" aria-hidden /><span className="small">Kumuha / pumili</span></>}
          </button>
        )}
      </div>
      <input ref={input} type="file" accept="image/*" capture="environment" multiple hidden
        onChange={async (e) => {
          const files = Array.from(e.target.files ?? []).slice(0, max - value.length);
          e.target.value = "";
          if (!files.length) return;
          setBusy(true);
          try { onChange([...value, ...(await preparePhotos(files))]); } finally { setBusy(false); }
        }} />
      {noLoc && (
        <Form.Text className="text-warning-emphasis d-block">
          <i className="bi bi-exclamation-triangle me-1" aria-hidden />
          Walang lokasyon ang ilang litrato. I-on ang Location ng camera/cellphone at kunan sa mismong lugar para hindi ma-flag.
        </Form.Text>
      )}
    </Form.Group>
  );
}
