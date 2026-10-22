import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { useCategories, usePublicStats, useRecentFixes } from "@/api/public";
import type { RecentFix } from "@/api/types";
import { HOTLINES } from "@/config";
import { useSite } from "@/site/useSite";

const DAY = new Intl.DateTimeFormat("fil-PH", { day: "numeric", month: "short", timeZone: "Asia/Manila" });
const fmt = (iso: string | null) => (iso ? DAY.format(new Date(iso)) : "—");
const tel = (n: string) => `tel:${n.replace(/[^\d+]/g, "")}`;

/* ---------------------------------------------------------------- hero */

function TrackInline() {
  const navigate = useNavigate();
  const [ref, setRef] = useState("");
  const go = (e: FormEvent) => {
    e.preventDefault();
    const v = ref.trim();
    if (v) navigate(`/track/${encodeURIComponent(v)}`);
  };
  return (
    <form onSubmit={go} className="track-inline pt-3 mt-4" role="search" aria-label="Subaybayan ang report">
      <label htmlFor="hero-ref" className="form-label fw-bold mb-1">May reference number ka na?</label>
      <div className="input-group">
        <input id="hero-ref" className="form-control" placeholder="hal. CCD-2026-7KQ2MX" value={ref}
          onChange={(e) => setRef(e.target.value)} autoComplete="off" />
        <button className="btn btn-outline-primary" type="submit">Subaybayan</button>
      </div>
    </form>
  );
}

function Receipt({ fixes }: { fixes: RecentFix[] }) {
  const [i, setI] = useState(0);
  const site = useSite();
  const f = fixes[i % fixes.length];
  const steps: [string, string | null][] = [
    ["Natanggap", f.reported_at],
    ["Naipasa", f.routed_at],
    ["Inspeksyon", f.inspected_at],
    ["Naayos", f.resolved_at],
  ];
  return (
    <section className="gov-receipt" aria-label="Halimbawa ng naayos na report">
      <div className="receipt-head d-flex justify-content-between align-items-center px-3 py-2">
        <span>{site.sample_data ? "Halimbawa ng naayos (sample data)" : "Naayos kamakailan"}</span>
        {fixes.length > 1 && (
          <span className="d-flex align-items-center gap-1">
            <button type="button" className="btn btn-sm btn-link p-0 px-1" aria-label="Nakaraang halimbawa"
              onClick={() => setI((i - 1 + fixes.length) % fixes.length)}><i className="bi bi-chevron-left" aria-hidden /></button>
            <span aria-live="polite">{(i % fixes.length) + 1} / {fixes.length}</span>
            <button type="button" className="btn btn-sm btn-link p-0 px-1" aria-label="Susunod na halimbawa"
              onClick={() => setI((i + 1) % fixes.length)}><i className="bi bi-chevron-right" aria-hidden /></button>
          </span>
        )}
      </div>
      <div className="pair">
        <figure>
          {f.before_url && <img src={f.before_url} alt={`Bago ayusin: ${f.problem}`} loading="lazy" />}
          <figcaption>Bago</figcaption>
        </figure>
        <figure>
          {f.after_url && <img src={f.after_url} alt={`Pagkatapos ayusin: ${f.problem}`} loading="lazy" />}
          <figcaption>Pagkatapos</figcaption>
        </figure>
      </div>
      <div className="px-3 pt-3 pb-2">
        <div className="gov-head fw-bold fs-5 lh-sm">{f.problem}</div>
        <div className="small text-secondary">
          Brgy. {f.barangay}{f.purok ? `, ${f.purok}` : ""}
          {f.office ? <> · {f.office}</> : null}
        </div>
      </div>
      <div className="tear" aria-hidden />
      <div className="px-3 py-3">
        <ol className="trail">
          {steps.map(([label, at]) => (
            <li key={label} className={at ? "" : "missing"}>
              <b>{label}</b>{fmt(at)}
            </li>
          ))}
        </ol>
        <div className="d-flex flex-wrap gap-2 align-items-center mt-3 small">
          <span className="fw-bold">{f.days.toLocaleString("fil-PH", { maximumFractionDigits: 1 })} araw mula report</span>
          <span className={`badge ${f.on_time ? "text-bg-success" : "text-bg-warning"}`}>
            <i className={`bi ${f.on_time ? "bi-check2" : "bi-clock-history"} me-1`} aria-hidden />
            {f.on_time ? "Nasa takdang oras" : "Lumampas sa takdang oras"}
          </span>
          {f.citizen_confirmed && (
            <span className="badge text-bg-light border"><i className="bi bi-person-check me-1" aria-hidden />Kinumpirma ng nag-report</span>
          )}
        </div>
      </div>
    </section>
  );
}

function Hero() {
  const fixes = useRecentFixes();
  const list = fixes.data ?? [];
  return (
    <section className="hero">
      <div className="container py-5">
        <div className="row g-4 g-lg-5 align-items-center">
          <div className="col-lg-6">
            <h1 className="mb-3">May sira sa inyong lugar? <span className="text-nowrap">I-report</span> at subaybayan hanggang maayos.</h1>
            <p className="lede mb-4">
              Butas na kalsada, patay na poste ng ilaw, baradong kanal, basurang hindi nakokolekta: ipadala dito
              kasama ang larawan at lokasyon. May reference number ang bawat report, at may larawang patunay ang
              bawat aksyon ng opisina.
            </p>
            <div className="d-flex flex-wrap align-items-center gap-3">
              <Link to="/report" className="btn btn-primary btn-lg px-4">
                <i className="bi bi-camera me-2" aria-hidden />Mag-report ng problema
              </Link>
              <span className="text-secondary">Walang account na kailangan. Puwedeng hindi magpakilala.</span>
            </div>
            <TrackInline />
          </div>
          <div className="col-lg-6">
            {list.length > 0 ? <Receipt fixes={list} /> : <HowProofWorks />}
          </div>
        </div>
      </div>
    </section>
  );
}

/** Shown in place of the receipt until the city has its first photo-documented fix. */
function HowProofWorks() {
  return (
    <div className="gov-receipt p-4">
      <div className="gov-head fw-bold fs-5 mb-2">Bawat naayos, may patunay</div>
      <p className="mb-0 text-secondary">
        Kapag natapos ang trabaho, nag-a-upload ang opisina ng larawan bago at pagkatapos, may petsa at lokasyon.
        Makikita mo ito sa pahina ng iyong report, at ikaw ang magkukumpirma kung talagang naayos.
      </p>
    </div>
  );
}

/* ---------------------------------------------------------------- sections */

function Transparency() {
  const stats = usePublicStats();
  const site = useSite();
  const t = stats.data?.totals;
  if (!t || !t.resolved_90d) return null;
  const onTime = Math.round(t.on_time_rate_90d ?? 0);
  return (
    <section className="border-bottom bg-white">
      <div className="container py-4">
        <p className="transparency mb-1">
          Sa nakaraang 90 araw, <strong>{t.resolved_90d.toLocaleString("fil-PH")}</strong> na problema ang naayos.
          Kalahati ay natapos sa loob ng <strong>{(t.median_days_90d ?? 0).toLocaleString("fil-PH")} araw</strong>,
          at <strong>{onTime}%</strong> ang nasa takdang oras ng ARTA.
        </p>
        <p className="small text-secondary mb-0">
          {site.sample_data
            ? "Halimbawang datos (synthetic) para ipakita kung paano gagana ang ulat na ito. Hindi ito totoong datos ng lungsod."
            : "Awtomatikong binibilang mula sa mga report sa portal na ito. Ipinapakita namin ang buong numero, kahit hindi pa ito 100%."}
        </p>
      </div>
    </section>
  );
}

function EmergencyNotice() {
  const e = HOTLINES.find((h) => h.emergency);
  if (!e) return null;
  return (
    <section className="container pt-5">
      <div className="emergency shadow-sm p-3 p-md-4 d-flex flex-column flex-md-row gap-3 align-items-md-center">
        <i className="bi bi-exclamation-octagon-fill text-danger fs-2" aria-hidden />
        <div className="flex-grow-1">
          <div className="fw-bold">Emergency ba? Huwag dito mag-report.</div>
          <div className="text-secondary">Sunog, aksidente, krimen o may nasaktan: tumawag agad. Hindi binabantayan nang 24 oras ang portal na ito.</div>
        </div>
        <a href={tel(e.number)} className="text-decoration-none text-center">
          <span className="num d-block">{e.number}</span>
          <span className="small text-secondary">{e.label}</span>
        </a>
      </div>
    </section>
  );
}

const STEPS = [
  ["Mag-report", "Ilarawan ang problema, kumuha ng larawan, at i-pin ang lokasyon. Bibigyan ka ng reference number."],
  ["Sinusuri at ipinapasa", "Tinitingnan ng PACD kung kumpleto ang report, saka ipinapasa sa tamang opisina. Kung may parehong report na, pinagsasama ang mga ito para isang aksyon lang."],
  ["Inaaksyunan", "Ininspeksyon at inaayos ng opisina. Nag-a-upload sila ng larawan bago at pagkatapos, kasama ang petsa at lokasyon ng pagkuha."],
  ["Ikaw ang magkukumpirma", "Makikita mo ang patunay sa pahina ng iyong report. Kung hindi talaga naayos, sabihin mo at bubuksan itong muli."],
];

function HowItWorks() {
  return (
    <section className="container py-5">
      <div className="row g-4">
        <div className="col-lg-4">
          <h2 className="section-title">Paano ito gumagana</h2>
          <p className="text-secondary">Mula report hanggang kumpirmasyon, nakikita mo ang bawat hakbang at kung sinong opisina ang may hawak.</p>
        </div>
        <div className="col-lg-8">
          <ol className="steps row g-4">
            {STEPS.map(([title, body]) => (
              <li key={title} className="col-md-6">
                <h3 className="h5 fw-bold mb-1">{title}</h3>
                <p className="mb-0 text-secondary">{body}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function Categories() {
  const cats = useCategories();
  if (!cats.data?.length) return null;
  return (
    <section className="bg-white border-top border-bottom">
      <div className="container py-5">
        <h2 className="section-title mb-1">Ano ang gusto mong i-report?</h2>
        <p className="text-secondary mb-4">Piliin ang uri para mas mabilis maipasa. Hindi sigurado? Ilarawan na lang sa form.</p>
        <div className="row g-0 column-gap-5">
          {cats.data.map((c) => (
            <div className="col-md" key={c.code} style={{ flex: "1 1 40%" }}>
              <Link to={`/report?category=${encodeURIComponent(c.code)}`} className="cat-link">
                <i className={`bi bi-${c.icon || "chat-left-text"}`} aria-hidden />
                <span>
                  <span className="fw-bold">{c.name_fil || c.name}</span>
                  {c.name_fil && <small>{c.name}</small>}
                </span>
                <i className="bi bi-chevron-right ms-auto fs-6 text-secondary" aria-hidden />
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ServiceStandard() {
  const rows: [string, string, string][] = [
    ["3", "Simple", "hal. pagpapalit ng pundidong ilaw, paghakot ng basura"],
    ["7", "Complex", "kailangan ng inspeksyon o ng ibang opisina"],
    ["20", "Highly technical", "kailangan ng pag-aaral, materyales o kontrata"],
  ];
  return (
    <section className="service-strip">
      <div className="container py-5">
        <div className="row g-4 align-items-end">
          <div className="col-lg-4">
            <h2 className="section-title mb-2">Takdang oras ng serbisyo</h2>
            <p className="mb-0">
              Ayon sa Ease of Doing Business and Efficient Government Service Delivery Act (RA 11032), binibilang sa
              working days mula nang maipasa sa opisina.
            </p>
          </div>
          {rows.map(([d, label, ex]) => (
            <div className="col-4 col-lg-2 col-xl" key={label}>
              <div className="days">{d}</div>
              <div className="fw-bold">araw · {label}</div>
              <div className="small">{ex}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Hotlines() {
  return (
    <section className="container py-5">
      <h2 className="section-title mb-3">Mga hotline</h2>
      <div className="row g-4">
        {HOTLINES.map((h) => (
          <div className="col-sm-6 col-lg-4" key={h.label + h.number}>
            <a href={tel(h.number)} className="hotline-num">{h.number}</a>
            <div className="fw-bold">{h.label}</div>
            {h.note && <div className="small text-secondary">{h.note}</div>}
          </div>
        ))}
      </div>
    </section>
  );
}

export const FAQ: [string, string][] = [
  ["Kailangan ko bang gumawa ng account?", "Hindi. Ilagay lang ang iyong mobile number kung gusto mong makatanggap ng update. Puwede ring mag-report nang hindi nagpapakilala."],
  ["Na-report na ito ng kapitbahay ko. Dapat pa ba akong mag-report?", "Oo. Pinagsasama ng sistema ang magkakaparehong report sa iisang lugar, kaya isang aksyon lang ang gagawin, pero mas tumataas ang priority kapag mas marami ang apektado."],
  ["Gaano katagal bago maayos?", "Depende sa uri: 3, 7 o 20 working days ayon sa ARTA. Makikita mo ang takdang petsa sa pahina ng iyong report."],
  ["Paano kung sinabing tapos na pero hindi naman?", "Sa loob ng 30 araw, pindutin ang \"Hindi pa naayos\" sa pahina ng report. Bubuksan ito ulit at makikita ng mga namamahala."],
  ["Sino ang nakakakita ng aking pangalan at numero?", "Ang mga awtorisadong kawani lang na humahawak ng report. Hindi kailanman ipinapakita sa publiko ang iyong pagkakakilanlan (RA 10173, Data Privacy Act)."],
];

function FaqTeaser() {
  return (
    <section className="bg-white border-top">
      <div className="container py-5">
        <div className="row g-4">
          <div className="col-lg-4">
            <h2 className="section-title">Mga madalas itanong</h2>
            <Link to="/about#faq">Tingnan lahat ng tanong at ang Citizen's Charter</Link>
          </div>
          <div className="col-lg-8 faq">
            {FAQ.slice(0, 4).map(([q, a]) => (
              <details key={q}>
                <summary>{q}</summary>
                <p>{a}</p>
              </details>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export function HomePage() {
  return (
    <>
      <Hero />
      <Transparency />
      <EmergencyNotice />
      <HowItWorks />
      <Categories />
      <ServiceStandard />
      <Hotlines />
      <FaqTeaser />
    </>
  );
}
