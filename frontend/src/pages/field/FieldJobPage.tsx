import { useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Alert, Badge, Button, Collapse, Form, Spinner } from "react-bootstrap";
import { Link, useNavigate, useParams } from "react-router-dom";

import { apiErrorMessage } from "@/api/client";
import { BLOCK_REASONS, useFieldJob, type BlockReason, type FieldJob } from "@/api/field";
import { useAuth } from "@/auth/AuthContext";
import { currentPosition, type EvidencePhoto } from "@/features/evidence/capture";
import { directionsUrl, haversineM } from "@/features/field/geo";
import { LiveCamera } from "@/features/field/LiveCamera";
import { formEntries, submitOrQueue, type FieldAction } from "@/features/field/outbox";
import { useOutbox } from "@/features/field/useOutbox";
import { dueLabel, fmtDateTime } from "@/utils/format";

const ACTION_LABEL: Record<FieldAction, string> = {
  arrive: "Dumating sa lugar",
  inspect: "Before na litrato",
  complete: "Tapos na ang trabaho",
  blocker: "Hindi pa matapos",
};

export default function FieldJobPage() {
  const id = Number(useParams().id);
  const { data: job, isLoading, isError, error } = useFieldJob(id);
  if (isLoading) return <div className="text-center py-5"><Spinner /></div>;
  if (!job) {
    return (
      <Alert variant={isError ? "danger" : "secondary"}>
        {isError ? apiErrorMessage(error) : "Wala na ang trabahong ito sa listahan mo."} <Link to="/field">Bumalik</Link>
      </Alert>
    );
  }
  return <JobView job={job} />;
}

function JobView({ job }: { job: FieldJob }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { items } = useOutbox();
  const waiting = new Set(items.filter((i) => i.concernId === job.id && !i.error).map((i) => i.action));
  const due = dueLabel(job.due_at);

  const run = async (action: FieldAction, payload: { json?: Record<string, unknown>; form?: ReturnType<typeof formEntries> }) => {
    const res = await submitOrQueue({ userId: user!.id, concernId: job.id, ref: job.reference_no, action, label: ACTION_LABEL[action], ...payload });
    if (!res.queued) qc.invalidateQueries({ queryKey: ["staff"] });
    return res;
  };

  return (
    <>
      <Link to="/field" className="small d-inline-block mb-2"><i className="bi bi-chevron-left" aria-hidden /> Mga trabaho</Link>
      <section className="field-panel">
        <div className="d-flex justify-content-between gap-2 small">
          <span className="fw-semibold" style={{ color: job.priority_color || undefined }}>{job.priority_code} {job.priority_name}</span>
          <span className="text-secondary">{job.reference_no}</span>
        </div>
        <h1 className="h5 fw-bold my-1">{job.title}</h1>
        {due && <div className={`small ${due.overdue ? "text-danger fw-semibold" : "text-secondary"}`}>Deadline: {due.text}</div>}
        {job.danger_now && <Alert variant="danger" className="py-2 px-3 my-2 small mb-0">Sabi ng nag-report: may panganib ngayon.</Alert>}
        <p className="my-2">{job.description}</p>
        {job.photos.length > 0 && (
          <div className="d-flex gap-2 mb-2">
            {job.photos.map((p) => (
              <a key={p.url} href={p.url} target="_blank" rel="noreferrer" className="field-thumb">
                <img src={p.url} alt="Litrato ng nag-report" />
              </a>
            ))}
          </div>
        )}
        <div className="small"><i className="bi bi-geo-alt me-1" aria-hidden />
          {[job.location_description, job.purok, job.barangay].filter(Boolean).join(", ")}
        </div>
        {job.action_plan && <div className="small text-secondary mt-1">Plano: {job.action_plan}</div>}
        {job.latitude && job.longitude && (
          <a className="btn btn-outline-primary w-100 mt-3" href={directionsUrl(job.latitude, job.longitude)} target="_blank" rel="noreferrer">
            <i className="bi bi-sign-turn-right me-2" aria-hidden />Daan papunta (Google Maps)
          </a>
        )}
      </section>

      <ol className="field-steps">
        <Step n={1} title="Dumating sa lugar" done={!!job.arrived_at} queued={waiting.has("arrive")}
          doneText={job.arrived_at ? `Dumating ${fmtDateTime(job.arrived_at)}` : undefined}>
          <ArriveStep job={job} run={run} />
        </Step>
        <Step n={2} title="Kunan ang 'before'" done={job.before_count > 0} queued={waiting.has("inspect")}
          doneText={job.before_count ? `${job.before_count} litrato na` : undefined}>
          <BeforeStep run={run} />
        </Step>
        <Step n={3} title="Tapos na ang trabaho" done={false} queued={waiting.has("complete")}>
          <DoneStep job={job} hasBefore={job.before_count > 0 || waiting.has("inspect")} run={run}
            onDone={(queued) => navigate("/field", {
              state: { flash: queued
                ? `Naka-save ang report para sa ${job.reference_no}. Ipapadala ito pagbalik ng signal.`
                : `Naipadala ang report para sa ${job.reference_no}. Hinihintay ang beripikasyon ng supervisor.` },
            })} />
        </Step>
      </ol>

      <BlockerPanel job={job} queued={waiting.has("blocker")} run={run} />
    </>
  );
}

type Run = (action: FieldAction, payload: { json?: Record<string, unknown>; form?: ReturnType<typeof formEntries> }) => Promise<{ queued: boolean }>;

function Step({ n, title, done, queued, doneText, children }: {
  n: number; title: string; done: boolean; queued: boolean; doneText?: string; children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const state = queued ? "queued" : done ? "done" : "todo";
  return (
    <li className={`field-step ${state}`}>
      <button type="button" className="field-step-head" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className="field-step-n" aria-hidden>{done && !queued ? <i className="bi bi-check-lg" /> : n}</span>
        <span className="flex-grow-1 text-start">
          <span className="d-block fw-semibold">{title}</span>
          {queued ? <span className="small text-warning-emphasis">Naka-save; ipapadala pagbalik ng signal</span>
            : doneText && <span className="small text-success">{doneText}</span>}
        </span>
        <i className={`bi bi-chevron-${open ? "up" : "down"}`} aria-hidden />
      </button>
      <Collapse in={open}><div><div className="pt-3">{children}</div></div></Collapse>
    </li>
  );
}

function useAction() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const go = async (fn: () => Promise<{ queued: boolean }>, ok: string) => {
    setBusy(true);
    setErr(null);
    setNote(null);
    try {
      const r = await fn();
      // When saved offline, the step header already says "Naka-save; ipapadala…" and updates itself once sent.
      setNote(r.queued ? null : ok);
      return r;
    } catch (e) {
      setErr(e instanceof Error && !("isAxiosError" in e) ? e.message : apiErrorMessage(e));
      return null;
    } finally {
      setBusy(false);
    }
  };
  const msg = (
    <>
      {err && <Alert variant="danger" className="py-2 small mt-2 mb-0">{err}</Alert>}
      {note && <Alert variant="success" className="py-2 small mt-2 mb-0">{note}</Alert>}
    </>
  );
  return { busy, go, msg };
}

function ArriveStep({ job, run }: { job: FieldJob; run: Run }) {
  const { busy, go, msg } = useAction();
  const [dist, setDist] = useState<number | null>(null);
  return (
    <>
      <p className="small text-secondary">Pindutin pagdating sa mismong lugar. Kukunin ang lokasyon ng cellphone; ito ang unang aksyon ng opisina sa kaso.</p>
      <Button size="lg" className="w-100" disabled={busy} onClick={() => go(async () => {
        const p = await currentPosition(15000);
        if (p && job.latitude && job.longitude) {
          setDist(haversineM(p.coords.latitude, p.coords.longitude, Number(job.latitude), Number(job.longitude)));
        }
        return run("arrive", { json: {
          latitude: p?.coords.latitude ?? null, longitude: p?.coords.longitude ?? null,
          accuracy: p ? Math.round(p.coords.accuracy) : null, at: new Date().toISOString(),
        } });
      }, "Naitala ang pagdating mo.")}>
        {busy ? <Spinner size="sm" /> : <><i className="bi bi-geo-fill me-2" aria-hidden />Dumating na ako</>}
      </Button>
      {dist != null && dist > 150 && (
        <div className="small text-warning-emphasis mt-2">Mga {Math.round(dist)} m ka pa mula sa pin ng report. Lumapit sa mismong lugar kung kaya.</div>
      )}
      {msg}
    </>
  );
}

function BeforeStep({ run }: { run: Run }) {
  const { busy, go, msg } = useAction();
  const [photos, setPhotos] = useState<EvidencePhoto[]>([]);
  const [findings, setFindings] = useState("");
  return (
    <>
      <p className="small text-secondary">Kunan ang problema bago galawin, sa mismong lugar.</p>
      <LiveCamera label="Before" value={photos} onChange={setPhotos} />
      <Form.Control as="textarea" rows={2} className="mb-2" placeholder="Ano ang nakita? (opsyonal, hal. 1m x 1m na lubak)"
        value={findings} onChange={(e) => setFindings(e.target.value)} maxLength={2000} />
      <Button size="lg" className="w-100" disabled={busy || !photos.length} onClick={async () => {
        const r = await go(() => run("inspect", { form: formEntries({
          findings: findings.trim() || "Kinunan ang lugar bago simulan ang trabaho.",
          photos: photos.map((p) => p.file), photo_meta: JSON.stringify(photos.map((p) => p.meta)),
        }) }), "Naipadala ang before na litrato.");
        if (r) setPhotos([]);
      }}>
        {busy ? <Spinner size="sm" /> : "Ipadala ang before"}
      </Button>
      {msg}
    </>
  );
}

function DoneStep({ job, hasBefore, run, onDone }: { job: FieldJob; hasBefore: boolean; run: Run; onDone: (queued: boolean) => void }) {
  const { busy, go, msg } = useAction();
  const [after, setAfter] = useState<EvidencePhoto[]>([]);
  const [before, setBefore] = useState<EvidencePhoto[]>([]);
  const [remarks, setRemarks] = useState("");
  const [materials, setMaterials] = useState("");
  const [crew, setCrew] = useState("");
  const ready = after.length > 0 && remarks.trim().length > 0 && (hasBefore || before.length > 0);
  return (
    <>
      {!hasBefore && (
        <>
          <div className="small fw-semibold mb-1">Wala pang before na litrato. Kunan muna:</div>
          <LiveCamera label="Before" value={before} onChange={setBefore} />
        </>
      )}
      <div className="small fw-semibold mb-1">After na litrato (sa parehong anggulo kung kaya)</div>
      <LiveCamera label="After" value={after} onChange={setAfter} />
      <Form.Group className="mb-2">
        <Form.Label className="small fw-semibold mb-1">Ano ang ginawa? <span className="text-danger">*</span></Form.Label>
        <Form.Control as="textarea" rows={2} value={remarks} onChange={(e) => setRemarks(e.target.value)} maxLength={1000}
          placeholder="hal. Tinapalan ng cold mix ang lubak" />
      </Form.Group>
      <Form.Control className="mb-2" placeholder="Materyales na ginamit (opsyonal)" value={materials}
        onChange={(e) => setMaterials(e.target.value)} maxLength={120} />
      <Form.Control className="mb-3" placeholder="Mga kasama (opsyonal)" value={crew}
        onChange={(e) => setCrew(e.target.value)} maxLength={300} />
      <Button size="lg" variant="success" className="w-100" disabled={busy || !ready} onClick={async () => {
        const r = await go(() => run("complete", { form: formEntries({
          remarks: remarks.trim(),
          photos: after.map((p) => p.file), photo_meta: JSON.stringify(after.map((p) => p.meta)),
          before_photos: before.length ? before.map((p) => p.file) : undefined,
          before_meta: before.length ? JSON.stringify(before.map((p) => p.meta)) : undefined,
          finished_at: new Date().toISOString(),
          other_workers: crew.trim() || undefined,
          materials: materials.trim() ? JSON.stringify([{ item: materials.trim() }]) : undefined,
        }) }), "Naipadala.");
        if (r) onDone(r.queued);
      }}>
        {busy ? <Spinner size="sm" /> : <><i className="bi bi-check2-circle me-2" aria-hidden />Ipadala: tapos na</>}
      </Button>
      <div className="small text-secondary mt-2">
        Titingnan muna ito ng {job.division ? "division chief" : "department head"} bago makita ng nag-report na naayos na.
      </div>
      {msg}
    </>
  );
}

function BlockerPanel({ job, queued, run }: { job: FieldJob; queued: boolean; run: Run }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<BlockReason | null>(null);
  const [remarks, setRemarks] = useState("");
  const { busy, go, msg } = useAction();
  return (
    <section className="field-panel mt-3">
      <button type="button" className="field-step-head p-0" onClick={() => setOpen(!open)} aria-expanded={open}>
        <i className="bi bi-exclamation-diamond fs-4 text-warning-emphasis me-2" aria-hidden />
        <span className="flex-grow-1 text-start">
          <span className="d-block fw-semibold">Hindi pa matapos?</span>
          {queued ? <span className="small text-warning-emphasis">Naka-save; ipapadala pagbalik ng signal</span>
            : job.blocked_reason ? <span className="small text-secondary">Naiulat: {job.blocked_reason_display}</span>
            : <span className="small text-secondary">Sabihan ang supervisor kung bakit</span>}
        </span>
        <i className={`bi bi-chevron-${open ? "up" : "down"}`} aria-hidden />
      </button>
      <Collapse in={open}>
        <div>
          <div className="d-grid gap-2 pt-3">
            {BLOCK_REASONS.map((r) => (
              <Button key={r.value} variant={reason === r.value ? "dark" : "outline-dark"} className="text-start"
                onClick={() => setReason(r.value)} aria-pressed={reason === r.value}>
                <i className={`bi bi-${r.icon} me-2`} aria-hidden />{r.label}
              </Button>
            ))}
          </div>
          <Form.Control as="textarea" rows={2} className="my-2" value={remarks} maxLength={500}
            placeholder={reason === "other" ? "Isulat ang dahilan (kailangan)" : "Detalye (opsyonal)"} onChange={(e) => setRemarks(e.target.value)} />
          <Button size="lg" variant="warning" className="w-100" disabled={busy || !reason || (reason === "other" && !remarks.trim())}
            onClick={() => go(() => run("blocker", { json: { reason, remarks: remarks.trim() } }),
              "Naipaalam sa supervisor. Sila ang magpapasya: extension, ilipat sa ibang opisina, o i-endorse.")}>
            {busy ? <Spinner size="sm" /> : "Ipaalam sa supervisor"}
          </Button>
          {msg}
        </div>
      </Collapse>
      {job.blocked_reason && !open && <Badge bg="warning" text="dark" className="mt-2">{job.blocked_reason_display}</Badge>}
    </section>
  );
}
