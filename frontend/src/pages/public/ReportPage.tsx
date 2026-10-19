import { lazy, Suspense, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Alert, Button, Card, Col, Container, Form, Row, Spinner } from "react-bootstrap";
import { Link } from "react-router-dom";

import { apiErrorMessage, apiFieldErrors } from "@/api/client";
import { useBarangays, useCategories, useSubmitConcern } from "@/api/public";
import type { AffectedScale, ConcernCreateResponse } from "@/api/types";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { LGU_CENTER } from "@/config";
import type { LatLng } from "@/features/report/LocationPicker";
import { compressImage } from "@/utils/compressImage";

const LocationPicker = lazy(() => import("@/features/report/LocationPicker"));

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
  description: string;
  barangay: string;
  location_description: string;
  danger_now: boolean | null;
  affected_scale: AffectedScale | null;
  is_anonymous: boolean;
  reporter_name: string;
  reporter_contact: string;
  involves_barangay_officials: boolean;
  consent_given: boolean;
};

const EMPTY: FormState = {
  category: "",
  subcategory: "",
  description: "",
  barangay: "",
  location_description: "",
  danger_now: null,
  affected_scale: null,
  is_anonymous: false,
  reporter_name: "",
  reporter_contact: "",
  involves_barangay_officials: false,
  consent_given: false,
};

type Errors = Partial<Record<keyof FormState | "images" | "latitude" | "form", string>>;

function validate(f: FormState): Errors {
  const e: Errors = {};
  if (!f.category) e.category = "Pumili ng uri ng problema.";
  if (f.description.trim().length < 10) e.description = "Pakilarawan nang kaunti pa (kahit isang pangungusap).";
  if (!f.barangay) e.barangay = "Piliin ang barangay.";
  if (f.location_description.trim().length < 4) e.location_description = "Ilagay ang palatandaan o kalye.";
  if (f.danger_now === null) e.danger_now = "Sagutin ito.";
  if (!f.affected_scale) e.affected_scale = "Pumili ng isa.";
  if (!f.is_anonymous) {
    if (!f.reporter_name.trim()) e.reporter_name = "Ilagay ang pangalan, o piliin ang Anonymous.";
    if (!/^(09|\+639|639)\d{9}$/.test(f.reporter_contact.replace(/[\s-]/g, "")))
      e.reporter_contact = "11-digit na mobile number, hal. 09171234567.";
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

export function ReportPage() {
  const categories = useCategories();
  const barangays = useBarangays();
  const submit = useSubmitConcern();

  const [form, setForm] = useState<FormState>(EMPTY);
  const [photos, setPhotos] = useState<File[]>([]);
  const [compressing, setCompressing] = useState(false);
  const [pin, setPin] = useState<LatLng | null>(null);
  const [showMap, setShowMap] = useState(false);
  const [geoMsg, setGeoMsg] = useState<string | null>(null);
  const [errors, setErrors] = useState<Errors>({});
  const [result, setResult] = useState<ConcernCreateResponse | null>(null);
  const topRef = useRef<HTMLDivElement>(null);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: undefined }));
  };

  const selectedCategory = categories.data?.find((c) => c.code === form.category);
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
    const clientErrors = validate(form);
    setErrors(clientErrors);
    if (Object.keys(clientErrors).length) {
      document.querySelector("[data-error='true']")?.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }
    try {
      const res = await submit.mutateAsync({
        category: form.category,
        subcategory: form.subcategory || null,
        description: form.description.trim(),
        barangay: Number(form.barangay),
        location_description: form.location_description.trim(),
        latitude: pin ? pin.lat.toFixed(6) : null,
        longitude: pin ? pin.lng.toFixed(6) : null,
        danger_now: !!form.danger_now,
        affected_scale: form.affected_scale!,
        involves_barangay_officials: form.involves_barangay_officials,
        is_anonymous: form.is_anonymous,
        reporter_name: form.is_anonymous ? "" : form.reporter_name.trim(),
        reporter_contact: form.is_anonymous ? "" : form.reporter_contact.replace(/[\s-]/g, ""),
        consent_given: form.consent_given,
        images: photos,
      });
      setResult(res);
      topRef.current?.scrollIntoView({ behavior: "smooth" });
    } catch (err) {
      const fields = apiFieldErrors(err);
      setErrors({ ...fields, form: apiErrorMessage(err) });
      topRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  };

  const reset = () => {
    setForm(EMPTY);
    setPhotos([]);
    setPin(null);
    setShowMap(false);
    setErrors({});
    setResult(null);
    submit.reset();
  };

  if (result) return <SuccessView result={result} onAgain={reset} />;

  if (categories.isLoading || barangays.isLoading) return <FullPageSpinner />;
  if (categories.isError || barangays.isError)
    return (
      <Container className="py-5">
        <Alert variant="danger">Hindi ma-load ang form. Pakisubukang muli mamaya.</Alert>
      </Container>
    );

  const err = (k: keyof Errors) => ({ "data-error": errors[k] ? "true" : undefined });

  return (
    <Container className="py-4" style={{ maxWidth: 720 }} ref={topRef}>
      <h1 className="h3 fw-bold mb-1">Mag-report ng Problema</h1>
      <p className="text-secondary mb-4">
        Report a community concern · mga 1 minuto lang. Para sa emergency, tumawag agad sa <strong>911</strong>.
      </p>

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
            <Form.Select value={form.barangay} onChange={(e) => set("barangay", e.target.value)} isInvalid={!!errors.barangay}>
              <option value="">— Piliin —</option>
              {barangays.data!.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </Form.Select>
            <FieldError msg={errors.barangay} />
          </Form.Group>

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
        <Section n={4} title="Paano ka namin maa-update?" en="How do we reach you?">
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
                  Mobile number
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
              <Col xs={12} className="small text-secondary mt-1">
                Gagamitin lang ito para ma-update ka tungkol sa report na ito.
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
                <>
                  Nabasa ko at sumasang-ayon ako sa{" "}
                  <Link to="/privacy" target="_blank" rel="noopener">
                    Data Privacy Notice
                  </Link>
                  .
                </>
              }
              checked={form.consent_given}
              onChange={(e) => set("consent_given", e.target.checked)}
              isInvalid={!!errors.consent_given}
            />
            <FieldError msg={errors.consent_given} />
          </div>
        </Section>

        <div className="position-sticky bottom-0 bg-body py-2">
          <Button type="submit" size="lg" className="w-100" disabled={submit.isPending || compressing}>
            {submit.isPending ? (
              <>
                <Spinner size="sm" className="me-2" />
                Ipinapadala…
              </>
            ) : (
              <>
                <i className="bi bi-send me-2" aria-hidden />
                Ipadala ang Report
              </>
            )}
          </Button>
        </div>
      </Form>
    </Container>
  );
}

function SuccessView({ result, onAgain }: { result: ConcernCreateResponse; onAgain: () => void }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(result.reference_no);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — the number is on screen */
    }
  };

  return (
    <Container className="py-5" style={{ maxWidth: 560 }}>
      <Card className="border-0 shadow-sm text-center">
        <Card.Body className="p-4">
          <i className="bi bi-check-circle-fill text-success" style={{ fontSize: 56 }} aria-hidden />
          <h1 className="h4 fw-bold mt-2">Natanggap na ang report mo!</h1>
          <p className="text-secondary mb-3">Ito ang iyong reference number:</p>
          <div className="fs-3 fw-bold font-monospace bg-light rounded py-2 mb-2 user-select-all">{result.reference_no}</div>
          <Button variant="link" size="sm" onClick={copy}>
            <i className={`bi bi-${copied ? "check2" : "clipboard"} me-1`} aria-hidden />
            {copied ? "Nakopya!" : "Kopyahin"}
          </Button>
          <p className="small text-secondary mt-2">
            I-screenshot o isulat ito. Gamitin ito para i-track ang report mo anumang oras.
          </p>
          {result.linked_to_existing && (
            <Alert variant="info" className="small text-start">
              May nauna nang nag-report nito. Pinagsama namin ang mga report para mas mabilis itong maaksyunan.
            </Alert>
          )}
          <div className="d-grid gap-2 mt-3">
            <Link to={`/track/${result.reference_no}`} className="btn btn-primary">
              I-track ang report
            </Link>
            <Button variant="outline-secondary" onClick={onAgain}>
              Mag-report ulit
            </Button>
          </div>
        </Card.Body>
      </Card>
    </Container>
  );
}
