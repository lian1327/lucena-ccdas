import { lazy, Suspense, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Alert, Button, Card, Col, Container, Form, Row, Spinner } from "react-bootstrap";
import { Link } from "react-router-dom";

import { apiErrorMessage, apiFieldErrors } from "@/api/client";
import { useBarangays, useCategories, useSuggestion, type Suggestion, type SubmitConcernInput } from "@/api/public";
import type { AffectedScale } from "@/api/types";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { LGU_CENTER } from "@/config";
import type { LatLng } from "./LocationPicker";
import { locatePin, usePuroks } from "@/api/public";
import type { Locate } from "@/api/types";
import { compressImage } from "@/utils/compressImage";

const LocationPicker = lazy(() => import("./LocationPicker"));

const MAX_PHOTOS = 3;

const SCALES: { value: AffectedScale; fil: string; en: string }[] = [
  { value: "self", fil: "Ako lang", en: "Just me" },
  { value: "household", fil: "Pamilya o bahay", en: "My household" },
  { value: "street", fil: "Buong kalye o purok", en: "Whole street" },
  { value: "barangay", fil: "Buong barangay", en: "Whole barangay" },
];

type FormState = {
  category: string;
  subcategory: string;
  unsure: boolean;
  description: string;
  barangay: string;
  purok: string;
  location_description: string;
  danger_now: boolean | null;
  affected_scale: AffectedScale | null;
  is_anonymous: boolean;
  reporter_name: string;
  reporter_contact: string;
  reporter_email: string;
  notify_sms: boolean;
  involves_barangay_officials: boolean;
  consent_given: boolean;
};

const EMPTY: FormState = {
  category: "",
  subcategory: "",
  unsure: false,
  description: "",
  barangay: "",
  purok: "",
  location_description: "",
  danger_now: null,
  affected_scale: null,
  is_anonymous: false,
  reporter_name: "",
  reporter_contact: "",
  reporter_email: "",
  notify_sms: true,
  involves_barangay_officials: false,
  consent_given: false,
};

type Mode = "public" | "staff";

type Errors = Partial<Record<keyof FormState | "images" | "latitude" | "form", string>>;

function validate(f: FormState, mode: Mode): Errors {
  const e: Errors = {};
  if (!f.category && !f.unsure) e.category = "Pumili ng uri ng problema, o piliin ang 'Hindi sigurado'.";
  if (f.description.trim().length < 10) e.description = "Pakilarawan nang kaunti pa (kahit isang pangungusap).";
  if (!f.barangay) e.barangay = "Piliin ang barangay.";
  if (f.location_description.trim().length < 4) e.location_description = "Ilagay ang palatandaan o kalye.";
  if (f.danger_now === null) e.danger_now = "Sagutin ito.";
  if (!f.affected_scale) e.affected_scale = "Pumili ng isa.";
  if (!f.is_anonymous) {
    if (!f.reporter_name.trim()) e.reporter_name = "Ilagay ang pangalan, o piliin ang Anonymous.";
    const phone = f.reporter_contact.replace(/[\s-]/g, "");
    const phoneRequired = mode === "public"; // walk-ins may have no phone; staff can leave it blank
    if ((phoneRequired || phone) && !/^(09|\+639|639)\d{9}$/.test(phone))
      e.reporter_contact = "11-digit na mobile number, hal. 09171234567.";
    if (f.reporter_email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.reporter_email.trim()))
      e.reporter_email = "Mukhang mali ang email address.";
  }
  if (!f.consent_given) e.consent_given = "Kailangan ang pahintulot para maipadala ang report.";
  return e;
}

/** Numbered section with Filipino heading and a small English subtitle. */
function Section({ n, title, en, children }: { n: number; title: string; en: string; children: ReactNode }) {
  return (
    <Card className="mb-3 border-0 shadow-sm">
      <Card.Body className="p-3 p-md-4">
        <div className="d-flex align-items-baseline gap-2 mb-3">
          <span className="badge rounded-pill text-bg-primary">{n}</span>
          <h2 className="h5 fw-bold mb-0">{title}</h2>
          <span className="small text-secondary">{en}</span>
        </div>
        {children}
      </Card.Body>
    </Card>
  );
}

function FieldError({ msg }: { msg?: string }) {
  return msg ? <div className="small text-danger mt-1">{msg}</div> : null;
}

type Props = {
  mode: Mode;
  submitting: boolean;
  submitLabel: string;
  /** Throw (e.g. the axios error) to show field errors on the form. */
  onSubmit: (payload: SubmitConcernInput) => Promise<void>;
  intro?: ReactNode;
  /** Pre-selects a category, e.g. from a landing-page link (/report?category=drainage). */
  initialCategory?: string;
};

export function ConcernForm({ mode, submitting, submitLabel, onSubmit: submitPayload, intro, initialCategory }: Props) {
  const categories = useCategories();
  const barangays = useBarangays();

  const [form, setForm] = useState<FormState>(() => ({ ...EMPTY, category: initialCategory ?? "" }));
  const [photos, setPhotos] = useState<File[]>([]);
  const [compressing, setCompressing] = useState(false);
  const [pin, setPin] = useState<LatLng | null>(null);
  const [showMap, setShowMap] = useState(false);
  const [geoMsg, setGeoMsg] = useState<string | null>(null);
  const [located, setLocated] = useState<Locate | null>(null);
  const puroks = usePuroks(form.barangay ? Number(form.barangay) : null);

  // Pin → barangay + purok, filled in for the citizen (they can still change the barangay).
  useEffect(() => {
    if (!pin) { setLocated(null); return; }
    let live = true;
    locatePin(pin.lat, pin.lng).then((r) => {
      if (!live) return;
      setLocated(r);
      if (r.barangay_id) {
        setForm((f) => ({ ...f, barangay: String(r.barangay_id), purok: r.purok_id ? String(r.purok_id) : "" }));
        setErrors((e) => ({ ...e, barangay: undefined }));
      }
    }).catch(() => live && setLocated(null));
    return () => { live = false; };
  }, [pin]);
  const [errors, setErrors] = useState<Errors>({});
  const topRef = useRef<HTMLDivElement>(null);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const selectedCategory = categories.data?.find((c) => c.code === form.category);
  const suggestion = useSuggestion(form.description);
  const selectedBarangay = barangays.data?.find((b) => String(b.id) === form.barangay);
  const mapCenter = useMemo<[number, number]>(
    () =>
      selectedBarangay?.center_lat && selectedBarangay?.center_lng
        ? [Number(selectedBarangay.center_lat), Number(selectedBarangay.center_lng)]
        : LGU_CENTER,
    [selectedBarangay],
  );

  const previews = useMemo(() => photos.map((p) => URL.createObjectURL(p)), [photos]);
  useEffect(() => () => previews.forEach((u) => URL.revokeObjectURL(u)), [previews]);

  const onPickPhotos = async (files: FileList | null) => {
    if (!files?.length) return;
    const room = MAX_PHOTOS - photos.length;
    const picked = Array.from(files).slice(0, room);
    setCompressing(true);
    const compressed = await Promise.all(picked.map((f) => compressImage(f)));
    setCompressing(false);
    setPhotos((p) => [...p, ...compressed]);
    setErrors((e) => ({ ...e, images: undefined }));
  };

  const useMyLocation = () => {
    if (!("geolocation" in navigator)) {
      setGeoMsg("Hindi suportado ng browser mo ang location.");
      return;
    }
    setGeoMsg("Hinahanap ang lokasyon mo…");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setPin({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setShowMap(true);
        setGeoMsg(null);
        setErrors((e) => ({ ...e, latitude: undefined }));
      },
      () => setGeoMsg("Hindi makuha ang lokasyon. I-on ang Location o i-pin na lang sa mapa."),
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  };

  const onSubmit = async (ev: FormEvent) => {
    ev.preventDefault();
    const clientErrors = validate(form, mode);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) {
      document.querySelector("[data-error='true']")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    try {
      await submitPayload({
        category: form.category || null,
        subcategory: form.subcategory || null,
        description: form.description.trim(),
        barangay: Number(form.barangay),
        purok: form.purok ? Number(form.purok) : null,
        location_description: form.location_description.trim(),
        latitude: pin ? pin.lat.toFixed(6) : null,
        longitude: pin ? pin.lng.toFixed(6) : null,
        danger_now: !!form.danger_now,
        affected_scale: form.affected_scale!,
        involves_barangay_officials: form.involves_barangay_officials,
        is_anonymous: form.is_anonymous,
        reporter_name: form.is_anonymous ? "" : form.reporter_name.trim(),
        reporter_contact: form.is_anonymous ? "" : form.reporter_contact.replace(/[\s-]/g, ""),
        reporter_email: form.is_anonymous ? "" : form.reporter_email.trim(),
        notify_sms: !form.is_anonymous && form.notify_sms,
        notify_email: !form.is_anonymous,
        consent_given: form.consent_given,
        images: photos,
      });
    } catch (err) {
      const fields = apiFieldErrors(err);
      setErrors({ ...fields, form: apiErrorMessage(err) });
      topRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };


  if (categories.isLoading || barangays.isLoading) return <FullPageSpinner />;
  if (categories.isError || barangays.isError)
    return (
      <Container className="py-5">
        <Alert variant="danger">Hindi ma-load ang form. Pakisubukang muli mamaya.</Alert>
      </Container>
    );

  const err = (k: keyof Errors) => ({ "data-error": errors[k] ? "true" : undefined });

  return (
    <div ref={topRef}>
      {intro}

      {errors.form && <Alert variant="danger">{errors.form}</Alert>}

      <Form onSubmit={onSubmit} noValidate>
        {/* 1. WHAT */}
        <Section n={1} title="Ano ang problema?" en="What's the problem?">
          <Row className="g-2" {...err("category")}>
            {categories.data!.map((c) => {
              const active = form.category === c.code;
              return (
                <Col xs={6} md={3} key={c.code}>
                  <button
                    type="button"
                    onClick={() => {
                      set("category", c.code);
                      set("subcategory", "");
                      set("unsure", false);
                    }}
                    className={`btn w-100 h-100 text-start p-2 border ${active ? "btn-primary" : "btn-light"}`}
                    aria-pressed={active}
                  >
                    <i className={`bi bi-${c.icon} fs-4 d-block`} aria-hidden />
                    <span className="fw-semibold d-block lh-sm">{c.name_fil || c.name}</span>
                    <span className={`small ${active ? "text-white-50" : "text-secondary"}`}>{c.name}</span>
                  </button>
                </Col>
              );
            })}
            <Col xs={12}>
              <Button size="sm" variant={form.unsure ? "secondary" : "outline-secondary"} className="w-100"
                aria-pressed={form.unsure}
                onClick={() => { set("unsure", !form.unsure); if (!form.unsure) { set("category", ""); set("subcategory", ""); } }}>
                <i className="bi bi-question-circle me-1" aria-hidden />Hindi sigurado: ilarawan na lang, kami na ang bahala
              </Button>
            </Col>
          </Row>
          <FieldError msg={errors.category} />

          {selectedCategory && selectedCategory.subcategories.length > 0 && (
            <div className="mt-3">
              <Form.Label className="fw-semibold small mb-2">Anong klase? (opsyonal)</Form.Label>
              <div className="d-flex flex-wrap gap-2">
                {selectedCategory.subcategories.map((s) => (
                  <Button
                    key={s.code}
                    size="sm"
                    variant={form.subcategory === s.code ? "primary" : "outline-secondary"}
                    className="rounded-pill"
                    onClick={() => set("subcategory", form.subcategory === s.code ? "" : s.code)}
                    aria-pressed={form.subcategory === s.code}
                  >
                    {s.name_fil || s.name}
                  </Button>
                ))}
              </div>
            </div>
          )}

          <Form.Group className="mt-3" controlId="description" {...err("description")}>
            <Form.Label className="fw-semibold small">Ikuwento nang maikli</Form.Label>
            <Form.Control
              as="textarea"
              rows={3}
              maxLength={2000}
              placeholder="hal. Tatlong araw nang hindi nakokolekta ang basura, nangangamoy na at nilalangaw."
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              isInvalid={!!errors.description}
            />
            <FieldError msg={errors.description} />
            <AiHint suggestion={suggestion.data ?? null} chosen={form.category} chosenSub={form.subcategory}
              onUse={(cat, sub) => { set("category", cat); set("subcategory", sub ?? ""); set("unsure", false); }} />
          </Form.Group>

          <div className="mt-3" {...err("images")}>
            <Form.Label className="fw-semibold small d-block">
              Litrato (opsyonal, hanggang {MAX_PHOTOS}) — malaking tulong para mabilis maaksyunan
            </Form.Label>
            <div className="d-flex flex-wrap gap-2">
              {previews.map((src, i) => (
                <div key={src} className="position-relative">
                  <img src={src} alt={`Litrato ${i + 1}`} className="rounded border object-fit-cover" width={88} height={88} />
                  <button
                    type="button"
                    className="btn btn-sm btn-dark position-absolute top-0 end-0 py-0 px-1"
                    aria-label="Alisin"
                    onClick={() => setPhotos((p) => p.filter((_, j) => j !== i))}
                  >
                    <i className="bi bi-x" />
                  </button>
                </div>
              ))}
              {photos.length < MAX_PHOTOS && (
                <label
                  className="d-flex flex-column align-items-center justify-content-center border rounded text-secondary bg-light"
                  style={{ width: 88, height: 88, cursor: "pointer", borderStyle: "dashed" }}
                >
                  {compressing ? <Spinner size="sm" /> : <i className="bi bi-camera fs-4" aria-hidden />}
                  <span className="small">Dagdag</span>
                  <input
                    type="file"
                    accept="image/*"
                    multiple
                    hidden
                    onChange={(e) => {
                      onPickPhotos(e.target.files);
                      e.target.value = "";
                    }}
                  />
                </label>
              )}
            </div>
            <FieldError msg={errors.images} />
          </div>
        </Section>

        {/* 2. WHERE */}
        <Section n={2} title="Saan?" en="Where?">
          <Form.Group className="mb-3" controlId="barangay" {...err("barangay")}>
            <Form.Label className="fw-semibold small">Barangay</Form.Label>
            <Form.Select value={form.barangay} onChange={(e) => { set("barangay", e.target.value); set("purok", ""); }} isInvalid={!!errors.barangay}>
              <option value="">— Piliin —</option>
              {barangays.data!.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Form.Select>
            <FieldError msg={errors.barangay} />
          </Form.Group>

          {form.barangay && (puroks.data?.length ?? 0) > 0 && (
            <Form.Group className="mb-3" controlId="purok">
              <Form.Label className="fw-semibold small">Purok <span className="text-secondary fw-normal">(opsyonal)</span></Form.Label>
              <Form.Select value={form.purok} onChange={(e) => set("purok", e.target.value)} disabled={!!located?.purok_id}>
                <option value="">— Hindi alam / laktawan —</option>
                {puroks.data!.filter((p) => !p.is_zone).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
              </Form.Select>
              {located?.purok_id && <Form.Text>Kinuha mula sa pin sa mapa.</Form.Text>}
            </Form.Group>
          )}

          <Form.Group className="mb-3" controlId="landmark" {...err("location_description")}>
            <Form.Label className="fw-semibold small">Palatandaan o kalye</Form.Label>
            <Form.Control
              placeholder="hal. tapat ng chapel sa Purok 3, malapit sa 7-Eleven"
              maxLength={255}
              value={form.location_description}
              onChange={(e) => set("location_description", e.target.value)}
              isInvalid={!!errors.location_description}
            />
            <FieldError msg={errors.location_description} />
          </Form.Group>

          <div className="d-flex flex-wrap gap-2 align-items-center" {...err("latitude")}>
            <Button variant="outline-primary" size="sm" onClick={useMyLocation}>
              <i className="bi bi-crosshair me-1" aria-hidden />
              Gamitin ang lokasyon ko
            </Button>
            <Button variant="outline-secondary" size="sm" onClick={() => setShowMap((s) => !s)}>
              <i className="bi bi-map me-1" aria-hidden />
              {showMap ? "Itago ang mapa" : "I-pin sa mapa"}
            </Button>
            {pin && (
              <span className="small text-success">
                <i className="bi bi-check-circle-fill me-1" aria-hidden />
                Naka-pin
                <button type="button" className="btn btn-link btn-sm p-0 ms-2" onClick={() => setPin(null)}>
                  alisin
                </button>
              </span>
            )}
          </div>
          {geoMsg && <div className="small text-secondary mt-2">{geoMsg}</div>}
          {pin && located && (
            <div className={`small mt-2 ${located.barangay_id ? "text-success" : "text-warning-emphasis"}`}>
              <i className={`bi bi-${located.barangay_id ? "geo-alt-fill" : "exclamation-triangle"} me-1`} aria-hidden />
              {located.barangay_id
                ? <>Nasa <strong>{located.barangay}</strong>{located.purok && <>, <strong>{located.purok}</strong></>} ang pin.</>
                : "Wala sa loob ng mga barangay ng lungsod ang pin. Pakisuri ang lokasyon."}
            </div>
          )}
          <FieldError msg={errors.latitude} />
          {showMap && (
            <div className="mt-2">
              <Suspense fallback={<FullPageSpinner label="Nilo-load ang mapa…" />}>
                <LocationPicker center={mapCenter} value={pin} onChange={setPin} />
              </Suspense>
              <div className="small text-secondary mt-1">I-tap ang mapa para mag-pin. Puwedeng i-drag ang pin.</div>
            </div>
          )}
        </Section>

        {/* 3. HOW SERIOUS */}
        <Section n={3} title="Gaano kalala?" en="How serious?">
          <div className="mb-3" {...err("danger_now")}>
            <Form.Label className="fw-semibold small d-block">May nanganganib ba ngayon?</Form.Label>
            <div className="d-flex gap-2">
              {[
                { v: true, label: "Oo, may panganib", icon: "exclamation-triangle" },
                { v: false, label: "Wala", icon: "dash-circle" },
              ].map((o) => (
                <Button
                  key={String(o.v)}
                  variant={form.danger_now === o.v ? (o.v ? "danger" : "secondary") : "outline-secondary"}
                  className="flex-fill"
                  onClick={() => set("danger_now", o.v)}
                  aria-pressed={form.danger_now === o.v}
                >
                  <i className={`bi bi-${o.icon} me-1`} aria-hidden />
                  {o.label}
                </Button>
              ))}
            </div>
            {form.danger_now && (
              <Alert variant="danger" className="small mt-2 mb-0 py-2">
                Kung may nasaktan o kailangan ng agarang tulong, <strong>tumawag sa 911</strong>. Ang report na ito ay
                uunahin pero hindi ito pang-emergency na hotline.
              </Alert>
            )}
            <FieldError msg={errors.danger_now} />
          </div>

          <div {...err("affected_scale")}>
            <Form.Label className="fw-semibold small d-block">Sino ang apektado?</Form.Label>
            <Row className="g-2">
              {SCALES.map((s) => (
                <Col xs={6} key={s.value}>
                  <Button
                    variant={form.affected_scale === s.value ? "primary" : "outline-secondary"}
                    className="w-100 h-100 text-start"
                    onClick={() => set("affected_scale", s.value)}
                    aria-pressed={form.affected_scale === s.value}
                  >
                    <span className="d-block fw-semibold lh-sm">{s.fil}</span>
                    <span className="small opacity-75">{s.en}</span>
                  </Button>
                </Col>
              ))}
            </Row>
            <FieldError msg={errors.affected_scale} />
          </div>
        </Section>

        {/* 4. CONTACT */}
        <Section
          n={4}
          title={mode === "public" ? "Paano ka namin maa-update?" : "Impormasyon ng nag-report"}
          en={mode === "public" ? "How do we reach you?" : "Reporter details"}
        >
          <Form.Check
            type="switch"
            id="anonymous"
            className="mb-3"
            label={
              <>
                <span className="fw-semibold">Mag-report nang anonymous</span>
                <span className="d-block small text-secondary">
                  Hindi namin malalaman kung sino ka, pero hindi ka rin namin ma-a-update. I-save ang reference number.
                </span>
              </>
            }
            checked={form.is_anonymous}
            onChange={(e) => set("is_anonymous", e.target.checked)}
          />

          {!form.is_anonymous && (
            <Row className="g-3 mb-3">
              <Col md={6} {...err("reporter_name")}>
                <Form.Label className="fw-semibold small" htmlFor="reporter_name">
                  Pangalan
                </Form.Label>
                <Form.Control
                  id="reporter_name"
                  autoComplete="name"
                  value={form.reporter_name}
                  onChange={(e) => set("reporter_name", e.target.value)}
                  isInvalid={!!errors.reporter_name}
                />
                <FieldError msg={errors.reporter_name} />
              </Col>
              <Col md={6} {...err("reporter_contact")}>
                <Form.Label className="fw-semibold small" htmlFor="reporter_contact">
                  Mobile number{mode === "staff" && <span className="text-secondary fw-normal"> (kung mayroon)</span>}
                </Form.Label>
                <Form.Control
                  id="reporter_contact"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  placeholder="09XX XXX XXXX"
                  value={form.reporter_contact}
                  onChange={(e) => set("reporter_contact", e.target.value)}
                  isInvalid={!!errors.reporter_contact}
                />
                <FieldError msg={errors.reporter_contact} />
              </Col>
              <Col md={6} {...err("reporter_email")}>
                <Form.Label className="fw-semibold small" htmlFor="reporter_email">
                  Email <span className="text-secondary fw-normal">(opsyonal)</span>
                </Form.Label>
                <Form.Control
                  id="reporter_email"
                  type="email"
                  autoComplete="email"
                  value={form.reporter_email}
                  onChange={(e) => set("reporter_email", e.target.value)}
                  isInvalid={!!errors.reporter_email}
                />
                <FieldError msg={errors.reporter_email} />
              </Col>
              <Col md={6} className="d-flex align-items-end">
                <Form.Check
                  id="notify_sms"
                  disabled={!form.reporter_contact.trim()}
                  label={<span className="small">Padalhan ako ng SMS kapag may update (libre)</span>}
                  checked={form.notify_sms && !!form.reporter_contact.trim()}
                  onChange={(e) => set("notify_sms", e.target.checked)}
                />
              </Col>
              <Col xs={12} className="small text-secondary mt-1">
                Gagamitin lang ito para ma-update ka tungkol sa report na ito: kapag natanggap, naipasa sa opisina,
                inaaksyunan, at naayos. Walang SMS mula 9 PM hanggang 7 AM. Puwede mo itong itigil anumang oras.
              </Col>
            </Row>
          )}

          <Form.Check
            id="involves_officials"
            className="mb-3"
            label={
              <>
                <span className="fw-semibold">Tungkol ito sa opisyal o tauhan ng barangay</span>
                <span className="d-block small text-secondary">
                  Diretso ito sa City Hall at hindi makikita ng barangay.
                </span>
              </>
            }
            checked={form.involves_barangay_officials}
            onChange={(e) => set("involves_barangay_officials", e.target.checked)}
          />

          <div {...err("consent_given")}>
            <Form.Check
              id="consent"
              label={
                mode === "staff" ? (
                  <>
                    Nakuha ang pahintulot ng nag-report (pasalita o nakasulat) ayon sa{" "}
                    <Link to="/privacy" target="_blank" rel="noopener">
                      Data Privacy Notice
                    </Link>
                    .
                  </>
                ) : (
                <>
                  Nabasa ko at sumasang-ayon ako sa{" "}
                  <Link to="/privacy" target="_blank" rel="noopener">
                    Data Privacy Notice
                  </Link>
                  .
                </>
                )
              }
              checked={form.consent_given}
              onChange={(e) => set("consent_given", e.target.checked)}
              isInvalid={!!errors.consent_given}
            />
            <FieldError msg={errors.consent_given} />
          </div>
        </Section>

        <div className="position-sticky bottom-0 bg-body py-2">
          <Button type="submit" size="lg" className="w-100" disabled={submitting || compressing}>
            {submitting ? (
              <>
                <Spinner size="sm" className="me-2" />
                Ipinapadala…
              </>
            ) : (
              <>
                <i className="bi bi-send me-2" aria-hidden />
                {submitLabel}
              </>
            )}
          </Button>
        </div>
      </Form>
    </div>
  );
}



/** "Mukhang tungkol ito sa…": the AI's reading of the description, one tap to accept. Shown only when it adds something. */
function AiHint({ suggestion: s, chosen, chosenSub, onUse }: {
  suggestion: Suggestion | null; chosen: string; chosenSub: string; onUse: (cat: string, sub: string | null) => void;
}) {
  if (!s || s.confidence < 0.5) return null;
  const same = s.category === chosen && (!s.subcategory || s.subcategory === chosenSub);
  if (same) {
    return <div className="small text-success mt-1"><i className="bi bi-stars me-1" aria-hidden />Tugma sa napili mo.</div>;
  }
  return (
    <div className="small mt-2 p-2 rounded border bg-light-subtle">
      <i className="bi bi-stars me-1 text-primary" aria-hidden />
      Mukhang tungkol ito sa <strong>{s.category_name}</strong>{s.subcategory_name && <> › {s.subcategory_name}</>}
      <span className="text-secondary"> ({Math.round(s.confidence * 100)}%)</span>
      <Button size="sm" variant="link" className="py-0" onClick={() => onUse(s.category, s.subcategory)}>Gamitin ito</Button>
      {chosen && <div className="text-secondary">Puwede mo ring panatilihin ang napili mo; susuriin ito ng LGU.</div>}
    </div>
  );
}
