import { HOTLINES } from "@/config";
import { useSite } from "@/site/useSite";

/** Shown on every public page in prototype mode. Plain and impossible to miss. */
export function PrototypeBanner() {
  const site = useSite();
  if (!site.isPrototype) return null;
  const e = HOTLINES.find((h) => h.emergency);
  return (
    <div className="prototype-banner" role="note">
      <div className="container d-flex flex-column flex-md-row gap-1 gap-md-3 py-2 small">
        <strong className="text-nowrap"><i className="bi bi-info-circle-fill me-1" aria-hidden />Prototype para sa pananaliksik</strong>
        <span>
          Hindi ipinapadala sa City Hall ang mga report dito. Para sa totoong problema, tumawag sa{" "}
          <a href="tel:8888">8888</a> o lumapit sa PACD ng City Hall
          {e ? <>. Emergency: <a href={`tel:${e.number}`}>{e.number}</a></> : null}.
          {site.sample_data && " Halimbawang datos lamang ang mga numero at larawan."}
        </span>
      </div>
    </div>
  );
}
