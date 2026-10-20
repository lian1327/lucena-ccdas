/**
 * "Next step" panels. Each one renders only when the backend says this user may do it now
 * (StaffConcernDetail.permissions), so the UI never offers an action the API would refuse.
 */
import { useState } from "react";
import { Alert, Badge, Button, ButtonGroup, Form, ListGroup, Modal, ToggleButton } from "react-bootstrap";

import { useCategories } from "@/api/public";
import { useAuth } from "@/auth/AuthContext";
import {
  useAssignDivision,
  useAssignPerson,
  useClose,
  useComplete,
  useDepartments,
  useDivisions,
  useEndorse,
  useEscalate,
  useExtend,
  useFeedback8888,
  useFollowUp,
  useInspect,
  useOfficeUsers,
  useReject,
  useReopen,
  useRoute,
  useValidate,
  useVerify,
} from "@/api/staff";
import type { CompleteInput } from "@/api/staff";
import type { EndorsementStatus, Severity, StaffConcernDetail } from "@/api/types";
import { fmtDate, fmtDateTime } from "@/utils/format";

import { EvidencePicker } from "@/features/evidence/EvidencePicker";
import { evidenceFields, type EvidencePhoto } from "@/features/evidence/capture";
import { FlagChip } from "@/features/evidence/ui";

import { ErrorText, Panel, SubmitButton } from "./ui";

type P = { c: StaffConcernDetail };

const SEVERITIES: { v: Severity; label: string }[] = [
  { v: 1, label: "1 · Minor" }, { v: 2, label: "2 · Moderate" }, { v: 3, label: "3 · Serious" },
  { v: 4, label: "4 · Severe" }, { v: 5, label: "5 · Critical" },
];

// ---------------- 1. Verify ----------------
export function VerifyPanel({ c }: P) {
  const categories = useCategories();
  const verify = useVerify(c.id);
  const [category, setCategory] = useState(c.category_code ?? "");
  const [sub, setSub] = useState(c.subcategory_code ?? "");
  const [severity, setSeverity] = useState<Severity>(c.severity as Severity);
  const subs = categories.data?.find((x) => x.code === category)?.subcategories ?? [];
  if (!c.permissions.verify) return null;

  return (
    <Panel title="Suriin ang report (Verify)" icon="clipboard-check" tone="primary"
      hint={<>Kumpirmahin ang uri at tunay na kalubhaan. Ang verified lang ang binibilang sa analytics.
        {c.danger_now && <strong className="text-danger d-block mt-1">Sinabi ng nag-report: may panganib ngayon.</strong>}</>}>
      <Form onSubmit={(e) => { e.preventDefault(); verify.mutate({ category, subcategory: sub || null, severity }); }}>
        <Form.Select className="mb-2" value={category} onChange={(e) => { setCategory(e.target.value); setSub(""); }} aria-label="Kategorya">
          <option value="">— Kategorya —</option>
          {categories.data?.map((x) => <option key={x.code} value={x.code}>{x.name}</option>)}
        </Form.Select>
        {subs.length > 0 && (
          <Form.Select className="mb-2" value={sub} onChange={(e) => setSub(e.target.value)} aria-label="Sub-type">
            <option value="">— Sub-type: wala / hindi tiyak —</option>
            {subs.map((s) => <option key={s.code} value={s.code}>{s.name} ({s.name_fil})</option>)}
          </Form.Select>
        )}
        <Form.Select className="mb-3" value={severity} onChange={(e) => setSeverity(Number(e.target.value) as Severity)} aria-label="Kalubhaan">
          {SEVERITIES.map((s) => <option key={s.v} value={s.v}>Kalubhaan: {s.label}</option>)}
        </Form.Select>
        <SubmitButton pending={verify.isPending} disabled={!category}>I-verify</SubmitButton>
        <ErrorText err={verify.error} />
      </Form>
    </Panel>
  );
}

// ---------------- 2. Route ----------------
export function RoutePanel({ c }: P) {
  const route = useRoute(c.id);
  const anyOffice = c.permissions.route_any_office;
  const departments = useDepartments("internal");
  const [level, setLevel] = useState<"city" | "barangay">(c.case?.level === "barangay" ? "barangay" : "city");
  const [dept, setDept] = useState<number | null>(c.case?.department_id ?? c.suggested_route.department_id ?? null);
  const [div, setDiv] = useState<number | null>(c.case?.division_id ?? c.suggested_route.division_id ?? null);
  const divisions = useDivisions(dept);
  const [remarks, setRemarks] = useState("");
  if (!c.permissions.route || (c.case && c.case.level === "external")) return null;
  const rerouting = !!c.case;

  return (
    <Panel title={rerouting ? "Ilipat (Re-route)" : "Ipasa (Route)"} icon="signpost-split" tone={rerouting ? undefined : "primary"}
      hint={rerouting ? "Magsisimula ng bagong ARTA target ang bagong opisina." : "Magsisimula ang ARTA target sa pagpasa."}>
      <ButtonGroup className="w-100 mb-2">
        {[["city", "City Hall office"], ["barangay", `Barangay ${c.barangay}`]].map(([v, label]) => (
          <ToggleButton key={v} id={`lvl-${v}`} type="radio" variant="outline-primary" size="sm" value={v}
            checked={level === v} onChange={() => setLevel(v as "city" | "barangay")}>
            {label}
          </ToggleButton>
        ))}
      </ButtonGroup>
      {level === "city" && anyOffice && (
        <>
          <Form.Select className="mb-2" value={dept ?? ""} aria-label="Opisina"
            onChange={(e) => { setDept(Number(e.target.value) || null); setDiv(null); }}>
            <option value="">— Opisina —</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.id}>{d.name}{d.id === c.suggested_route.department_id ? " (default)" : ""}</option>
            ))}
          </Form.Select>
          {(divisions.data?.length ?? 0) > 0 && (
            <Form.Select className="mb-2" value={div ?? ""} aria-label="Division" onChange={(e) => setDiv(Number(e.target.value) || null)}>
              <option value="">— Division: hayaang pumili ang Department Head —</option>
              {divisions.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Form.Select>
          )}
        </>
      )}
      {level === "city" && !anyOffice && (
        <div className="small mb-2">I-e-elevate sa City Hall; ang PACD ang magpapasa sa tamang opisina
          {c.suggested_route.department && <> (malamang: <strong>{c.suggested_route.department}</strong>)</>}.</div>
      )}
      {level === "barangay" && <div className="small mb-2">Ang barangay ang mag-aaksyon at magva-validate.</div>}
      <Form.Control size="sm" className="mb-2" placeholder="Mensahe sa nag-report (opsyonal)" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
      <SubmitButton pending={route.isPending} disabled={level === "city" && anyOffice && !dept}
        onClick={() => route.mutate({ level, department: level === "city" ? dept : null, division: level === "city" ? div : null, remarks })}>
        {rerouting ? "Ilipat" : "Ipasa"}
      </SubmitButton>
      <ErrorText err={route.error} />
    </Panel>
  );
}

// ---------------- Endorse (external agency) ----------------
export function EndorsePanel({ c, compact }: P & { compact?: boolean }) {
  const agencies = useDepartments("external");
  const endorse = useEndorse(c.id);
  const [open, setOpen] = useState(!compact);
  const [agency, setAgency] = useState<number | null>(null);
  const [letter, setLetter] = useState("");
  const [contact, setContact] = useState("");
  if (!c.permissions.endorse) return null;
  if (!open)
    return (
      <Button variant="outline-secondary" size="sm" className="w-100 mb-3" onClick={() => setOpen(true)}>
        <i className="bi bi-box-arrow-up-right me-1" aria-hidden /> Hindi sakop ng LGU? I-endorso (hal. DPWH)
      </Button>
    );
  return (
    <Panel title="I-endorso sa ibang ahensya" icon="box-arrow-up-right"
      hint="Para sa national roads (DPWH), linya ng kuryente, tubig, atbp. Patuloy itong susubaybayan ng LGU.">
      <Form.Select className="mb-2" value={agency ?? ""} onChange={(e) => setAgency(Number(e.target.value) || null)} aria-label="Ahensya">
        <option value="">— Ahensya —</option>
        {agencies.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
      </Form.Select>
      <Form.Control size="sm" className="mb-2" placeholder="Endorsement letter / memo no." value={letter} onChange={(e) => setLetter(e.target.value)} />
      <Form.Control size="sm" className="mb-2" placeholder="Contact person sa ahensya" value={contact} onChange={(e) => setContact(e.target.value)} />
      <SubmitButton pending={endorse.isPending} disabled={!agency} variant="outline-primary"
        onClick={() => endorse.mutate({ agency: agency!, letter_reference: letter, contact_person: contact })}>
        I-endorso
      </SubmitButton>
      <ErrorText err={endorse.error} />
    </Panel>
  );
}

// ---------------- 3. Division & person ----------------
export function AssignPanel({ c }: P) {
  const k = c.case;
  const divisions = useDivisions(k?.department_id);
  const [div, setDiv] = useState<number | null>(k?.division_id ?? null);
  const users = useOfficeUsers(k?.department_id, k?.division_id);
  const [person, setPerson] = useState<number | null>(k?.assigned_to_id ?? null);
  const assignDiv = useAssignDivision(c.id);
  const assignPerson = useAssignPerson(c.id);
  if (!k || k.work_completed_at || (!c.permissions.assign_division && !c.permissions.assign_person)) return null;
  const needsDivision = !k.division_id;
  const needsPerson = !k.assigned_to_id;

  return (
    <Panel title="Italaga (Assign)" icon="person-gear" tone={needsDivision || needsPerson ? "primary" : undefined}>
      {c.permissions.assign_division && (divisions.data?.length ?? 0) > 0 && (
        <Form.Group className="mb-3">
          <Form.Label className="small fw-semibold">Division</Form.Label>
          <div className="d-flex gap-2">
            <Form.Select value={div ?? ""} onChange={(e) => setDiv(Number(e.target.value) || null)}>
              <option value="">— Piliin —</option>
              {divisions.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </Form.Select>
            <SubmitButton className="" pending={assignDiv.isPending} disabled={!div || div === k.division_id}
              onClick={() => assignDiv.mutate({ division: div! })}>Ipasa</SubmitButton>
          </div>
          <ErrorText err={assignDiv.error} />
        </Form.Group>
      )}
      {c.permissions.assign_person && (
        <Form.Group>
          <Form.Label className="small fw-semibold">Engineer / crew</Form.Label>
          <div className="d-flex gap-2">
            <Form.Select value={person ?? ""} onChange={(e) => setPerson(Number(e.target.value) || null)}>
              <option value="">— Piliin —</option>
              {users.data?.map((u) => <option key={u.id} value={u.id}>{u.full_name} · {u.role_display}</option>)}
            </Form.Select>
            <SubmitButton className="" pending={assignPerson.isPending} disabled={!person || person === k.assigned_to_id}
              onClick={() => assignPerson.mutate({ person: person! })}>Italaga</SubmitButton>
          </div>
          <ErrorText err={assignPerson.error} />
        </Form.Group>
      )}
    </Panel>
  );
}

// ---------------- 4. Inspect ----------------
export function InspectPanel({ c }: P) {
  const inspect = useInspect(c.id);
  const [findings, setFindings] = useState("");
  const [plan, setPlan] = useState("");
  const [date, setDate] = useState("");
  const [before, setBefore] = useState<EvidencePhoto[]>([]);
  if (!c.permissions.inspect || c.case?.inspected_at) return null;
  return (
    <Panel title="Site inspection" icon="search" tone="primary"
      hint="Itala ang nakita at plano, at kunan ng BEFORE na litrato sa mismong lugar. Sasabihan ang nag-report kung kailan ang trabaho.">
      <Form onSubmit={(e) => {
        e.preventDefault();
        inspect.mutate({ findings, action_plan: plan, scheduled_for: date || null, ...evidenceFields(before, "photos", "photo_meta") });
      }}>
        <Form.Control as="textarea" rows={2} className="mb-2" placeholder="Nakita sa inspeksyon" value={findings} onChange={(e) => setFindings(e.target.value)} />
        <Form.Control as="textarea" rows={2} className="mb-2" placeholder="Plano / materyales / tauhan" value={plan} onChange={(e) => setPlan(e.target.value)} />
        <Form.Label className="small fw-semibold">Nakaiskedyul sa</Form.Label>
        <Form.Control type="date" className="mb-3" value={date} onChange={(e) => setDate(e.target.value)} />
        <EvidencePicker label="BEFORE na litrato" value={before} onChange={setBefore}
          hint="Kailangan bago maisumite ang 'Tapos na'. Puwede ring kunan mamaya." />
        <SubmitButton pending={inspect.isPending} disabled={!findings.trim()}>I-save ang inspeksyon</SubmitButton>
        <ErrorText err={inspect.error} />
      </Form>
    </Panel>
  );
}

// ---------------- 5. Complete work = accomplishment report ----------------
type MaterialRow = { item: string; qty: string; unit: string };

const toLocalInput = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);

export function CompletePanel({ c }: P) {
  const complete = useComplete(c.id);
  const k = c.case;
  const users = useOfficeUsers(k?.department_id, k?.division_id);
  const { user: me } = useAuth();
  const [remarks, setRemarks] = useState("");
  const [after, setAfter] = useState<EvidencePhoto[]>([]);
  const [before, setBefore] = useState<EvidencePhoto[]>([]);
  const [started, setStarted] = useState("");
  const [finished, setFinished] = useState(() => toLocalInput(new Date()));
  const [crew, setCrew] = useState<number[]>([]);
  const [others, setOthers] = useState("");
  const [equipment, setEquipment] = useState("");
  const [materials, setMaterials] = useState<MaterialRow[]>([{ item: "", qty: "", unit: "" }]);
  if (!c.permissions.complete) return null;
  const hasBefore = c.attachments.some((a) => a.kind === "before");
  const ready = remarks.trim() && after.length && (hasBefore || before.length);
  const setMat = (i: number, patch: Partial<MaterialRow>) =>
    setMaterials((m) => m.map((row, j) => (j === i ? { ...row, ...patch } : row)));

  return (
    <Panel title="Accomplishment report" icon="clipboard2-check" tone={k?.inspected_at ? "primary" : undefined}
      hint="Patunay na may ginawa: ano, sino, gamit, at BEFORE/AFTER na litrato sa mismong lugar. Ive-verify pa ng supervisor.">
      <Form onSubmit={(e) => {
        e.preventDefault();
        complete.mutate({
          remarks,
          ...evidenceFields(after, "photos", "photo_meta"),
          ...(before.length ? evidenceFields(before, "before_photos", "before_meta") : {}),
          started_at: started ? new Date(started).toISOString() : undefined,
          finished_at: finished ? new Date(finished).toISOString() : undefined,
          crew: JSON.stringify(crew),
          other_workers: others,
          equipment,
          materials: JSON.stringify(materials.filter((m) => m.item.trim()).map((m) => ({
            item: m.item.trim(), qty: m.qty ? Number(m.qty) : null, unit: m.unit.trim(),
          }))),
        } as CompleteInput);
      }}>
        <Form.Label className="small fw-semibold">Ano ang ginawa? <span className="text-danger">*</span></Form.Label>
        <Form.Control as="textarea" rows={2} className="mb-3" placeholder="Hal. Tinapalan ng cold mix ang 2 butas (1×1 m)." value={remarks}
          onChange={(e) => setRemarks(e.target.value)} />

        {!hasBefore && (
          <EvidencePicker label="BEFORE na litrato" required value={before} onChange={setBefore}
            hint="Walang before na litrato mula sa inspeksyon. Kunan ang kalagayan bago ang trabaho." />
        )}
        <EvidencePicker label="AFTER na litrato" required value={after} onChange={setAfter}
          hint="Parehong anggulo ng before, sa mismong lugar." />

        <div className="row g-2 mb-3">
          <div className="col-6">
            <Form.Label className="small fw-semibold">Sinimulan</Form.Label>
            <Form.Control type="datetime-local" size="sm" value={started} onChange={(e) => setStarted(e.target.value)} />
          </div>
          <div className="col-6">
            <Form.Label className="small fw-semibold">Natapos</Form.Label>
            <Form.Control type="datetime-local" size="sm" value={finished} onChange={(e) => setFinished(e.target.value)} />
          </div>
        </div>

        <Form.Label className="small fw-semibold">Kasama sa crew</Form.Label>
        <div className="border rounded p-2 mb-2 small" style={{ maxHeight: 140, overflowY: "auto" }}>
          {users.data?.some((u) => u.id !== me?.id) ? users.data.filter((u) => u.id !== me?.id).map((u) => (
            <Form.Check key={u.id} id={`crew-${u.id}`} label={`${u.full_name} · ${u.role_display}`}
              checked={crew.includes(u.id)} onChange={(e) => setCrew((x) => e.target.checked ? [...x, u.id] : x.filter((i) => i !== u.id))} />
          )) : <span className="text-secondary">Walang ibang tauhan sa listahan. (Kasama ka na bilang nagsumite.)</span>}
        </div>
        <Form.Control size="sm" className="mb-3" placeholder="Iba pang trabahador (job order), hiwalay ng kuwit" value={others}
          onChange={(e) => setOthers(e.target.value)} />

        <Form.Label className="small fw-semibold">Materyales na ginamit</Form.Label>
        {materials.map((m, i) => (
          <div key={i} className="d-flex gap-1 mb-1">
            <Form.Control size="sm" placeholder="Materyales" value={m.item} onChange={(e) => setMat(i, { item: e.target.value })} />
            <Form.Control size="sm" type="number" min="0" step="any" placeholder="Dami" style={{ width: 80 }} value={m.qty}
              onChange={(e) => setMat(i, { qty: e.target.value })} />
            <Form.Control size="sm" placeholder="Unit" style={{ width: 80 }} value={m.unit} onChange={(e) => setMat(i, { unit: e.target.value })} />
          </div>
        ))}
        <Button variant="link" size="sm" className="p-0 mb-3" onClick={() => setMaterials((x) => [...x, { item: "", qty: "", unit: "" }])}>
          + Magdagdag ng materyales
        </Button>
        <Form.Control size="sm" className="mb-3" placeholder="Kagamitan (hal. dump truck, compactor)" value={equipment}
          onChange={(e) => setEquipment(e.target.value)} />

        <SubmitButton pending={complete.isPending} disabled={!ready} variant="success">Isumite para i-validate</SubmitButton>
        {!ready && <Form.Text className="d-block">Kailangan: ano ang ginawa, {hasBefore ? "" : "BEFORE at "}AFTER na litrato.</Form.Text>}
        <ErrorText err={complete.error} />
      </Form>
    </Panel>
  );
}

// ---------------- 6. Validate ----------------
export function ValidatePanel({ c }: P) {
  const validate = useValidate(c.id);
  const k = c.case!;
  const external = k?.level === "external";
  const [remarks, setRemarks] = useState(k?.completion_remarks ?? "");
  const [photos, setPhotos] = useState<EvidencePhoto[]>([]);
  const [override, setOverride] = useState("");
  const [returning, setReturning] = useState(false);
  const [why, setWhy] = useState("");
  if (!c.permissions.validate) return null;
  const hasProof = c.attachments.some((a) => a.kind === "resolution");
  const ev = k.evidence;
  const reds = ev?.red_flags ?? [];
  const needOverride = reds.length > 0;

  return (
    <Panel title={external ? "I-validate ang aksyon ng ahensya" : "I-validate ang trabaho"} icon="patch-check" tone="success"
      hint={external ? "Kumpirmahin sa lugar na naayos na, at kumuha ng litrato." :
        <>Isinumite ni <strong>{k.work_completed_by}</strong> · {fmtDateTime(k.work_completed_at)}. Tingnan ang <a href="#proof">Patunay ng trabaho</a> bago aprubahan.</>}>
      {!external && ev && (
        <div className="small mb-2">
          {ev.verified
            ? <div className="text-success"><i className="bi bi-shield-check me-1" aria-hidden />Pasado ang photo checks: may before at after, nasa lugar.</div>
            : (
              <>
                {!ev.has_before_after && <div className="text-warning-emphasis"><i className="bi bi-exclamation-triangle me-1" aria-hidden />Kulang: {ev.before ? "" : "walang BEFORE"}{!ev.before && !ev.after ? ", " : ""}{ev.after ? "" : "walang AFTER"}.</div>}
                {reds.map((f) => <FlagChip key={f.code} f={f} />)}
                {ev.amber_flags.map((f) => <FlagChip key={f.code} f={f} />)}
              </>
            )}
        </div>
      )}
      <Form.Label className="small fw-semibold">Mensahe sa nag-report</Form.Label>
      <Form.Control as="textarea" rows={2} className="mb-2" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
      {(external || !hasProof) && <EvidencePicker label="Litrato (kailangan kung wala pa)" value={photos} onChange={setPhotos} />}
      {needOverride && (
        <>
          <Form.Label className="small fw-semibold text-danger">Bakit aaprubahan kahit may red flag? <span className="text-danger">*</span></Form.Label>
          <Form.Control as="textarea" rows={2} className="mb-1" value={override} onChange={(e) => setOverride(e.target.value)}
            placeholder="Hal. Personal kong ininspeksyon kahapon; mahina ang GPS sa ilalim ng tulay." />
          <Form.Text className="d-block mb-2">Itatala ito sa iyong pangalan at makikita ng Department Head at City Administrator.</Form.Text>
        </>
      )}
      <SubmitButton pending={validate.isPending && !returning} variant="success"
        disabled={(!hasProof && !photos.length) || (needOverride && override.trim().length < 15)}
        onClick={() => validate.mutate({ approve: true, remarks, ...evidenceFields(photos, "photos", "photo_meta"), override_reason: override })}>
        <i className="bi bi-check2-circle me-1" aria-hidden /> Aprubahan: Naayos na
      </SubmitButton>
      {!external && (
        returning ? (
          <div className="mt-2">
            <Form.Control size="sm" className="mb-2" placeholder="Ano pa ang kailangang gawin?" value={why} onChange={(e) => setWhy(e.target.value)} />
            <SubmitButton pending={validate.isPending} variant="outline-warning" disabled={!why.trim()}
              onClick={() => validate.mutate({ approve: false, remarks: why }, { onSuccess: () => setReturning(false) })}>
              Ibalik sa crew
            </SubmitButton>
          </div>
        ) : (
          <Button variant="link" size="sm" className="w-100 mt-1 text-warning-emphasis" onClick={() => setReturning(true)}>Hindi pa tapos, ibalik sa crew</Button>
        )
      )}
      <ErrorText err={validate.error} />
    </Panel>
  );
}

// ---------------- External endorsement tracking ----------------
const ENDORSE_STATUS_VARIANT: Record<string, string> = {
  endorsed: "secondary", acknowledged: "info", scheduled: "warning", completed: "success", declined: "danger",
};

export function EndorsementPanel({ c }: P) {
  const followUp = useFollowUp(c.id);
  const e = c.case?.endorsements[0];
  const [method, setMethod] = useState("call");
  const [notes, setNotes] = useState("");
  const [status, setStatus] = useState<EndorsementStatus | "">("");
  const [response, setResponse] = useState("");
  const [publicMsg, setPublicMsg] = useState("");
  if (!e || c.case?.level !== "external") return null;

  return (
    <Panel title={`Endorsement: ${e.agency}`} icon="box-arrow-up-right" tone={e.follow_up_due ? "warning" : undefined}>
      <div className="d-flex flex-wrap gap-2 align-items-center mb-2">
        <Badge bg={ENDORSE_STATUS_VARIANT[e.status]}>{e.status_display}</Badge>
        {e.follow_up_due && <Badge bg="warning" text="dark">Follow-up due</Badge>}
      </div>
      <dl className="row small mb-2">
        <dt className="col-5 text-secondary">Inendorso</dt><dd className="col-7">{fmtDate(e.endorsed_at)} ni {e.endorsed_by}</dd>
        {e.letter_reference && <><dt className="col-5 text-secondary">Letter no.</dt><dd className="col-7">{e.letter_reference}</dd></>}
        {e.contact_person && <><dt className="col-5 text-secondary">Contact</dt><dd className="col-7">{e.contact_person}</dd></>}
        <dt className="col-5 text-secondary">Susunod na follow-up</dt><dd className="col-7">{fmtDate(e.next_follow_up_at)}</dd>
        {e.agency_response && <><dt className="col-5 text-secondary">Sagot ng ahensya</dt><dd className="col-7">{e.agency_response}</dd></>}
      </dl>
      {e.follow_ups.length > 0 && (
        <ListGroup variant="flush" className="small mb-2">
          {e.follow_ups.map((f) => (
            <ListGroup.Item key={f.id} className="px-0">
              <span className="text-secondary">{fmtDateTime(f.at)} · {f.method} · {f.by}</span>
              <div>{f.notes}</div>
            </ListGroup.Item>
          ))}
        </ListGroup>
      )}
      {c.permissions.follow_up && (
        <Form onSubmit={(ev) => {
          ev.preventDefault();
          followUp.mutate({ method, notes, status: status || null, agency_response: response, public_message: publicMsg },
            { onSuccess: () => { setNotes(""); setResponse(""); setPublicMsg(""); setStatus(""); } });
        }}>
          <div className="d-flex gap-2 mb-2">
            <Form.Select size="sm" style={{ maxWidth: 120 }} value={method} onChange={(ev) => setMethod(ev.target.value)} aria-label="Paraan">
              {["call", "letter", "email", "visit", "meeting"].map((m) => <option key={m}>{m}</option>)}
            </Form.Select>
            <Form.Select size="sm" value={status} onChange={(ev) => setStatus(ev.target.value as EndorsementStatus | "")} aria-label="Bagong status">
              <option value="">Status: walang pagbabago</option>
              <option value="acknowledged">Acknowledged ng ahensya</option>
              <option value="scheduled">Nakaiskedyul ang aksyon</option>
              <option value="completed">Tapos na raw (ive-verify ng LGU)</option>
              <option value="declined">Tinanggihan / hindi sakop</option>
            </Form.Select>
          </div>
          <Form.Control size="sm" as="textarea" rows={2} className="mb-2" placeholder="Notes ng follow-up (internal)" value={notes} onChange={(ev) => setNotes(ev.target.value)} />
          <Form.Control size="sm" className="mb-2" placeholder="Sagot ng ahensya (opsyonal)" value={response} onChange={(ev) => setResponse(ev.target.value)} />
          <Form.Control size="sm" className="mb-2" placeholder="Update para sa nag-report (opsyonal)" value={publicMsg} onChange={(ev) => setPublicMsg(ev.target.value)} />
          <SubmitButton pending={followUp.isPending} disabled={!notes.trim()} variant="outline-primary">I-log ang follow-up</SubmitButton>
          <ErrorText err={followUp.error} />
        </Form>
      )}
    </Panel>
  );
}

// ---------------- 8888 ----------------
export function Hotline8888Panel({ c }: P) {
  const send = useFeedback8888(c.id);
  const [text, setText] = useState("");
  if (c.channel !== "8888") return null;
  const due = c.external_feedback_due_at ? new Date(c.external_feedback_due_at) : null;
  const hoursLeft = due ? Math.round((due.getTime() - Date.now()) / 3_600_000) : null;
  return (
    <Panel title={`8888 Ticket ${c.external_ticket_no}`} icon="telephone-inbound"
      tone={!c.external_feedback_sent_at ? (hoursLeft !== null && hoursLeft < 12 ? "danger" : "warning") : "success"}>
      {c.external_feedback_sent_at ? (
        <div className="small">
          <Badge bg="success" className="mb-1">Feedback sent {fmtDateTime(c.external_feedback_sent_at)}</Badge>
          <div>{c.external_feedback}</div>
        </div>
      ) : (
        <>
          <div className={`small mb-2 ${hoursLeft !== null && hoursLeft < 0 ? "text-danger fw-semibold" : ""}`}>
            Concrete and specific na feedback sa 8888 focal person: due {fmtDateTime(c.external_feedback_due_at)}
            {hoursLeft !== null && ` (${hoursLeft < 0 ? `${-hoursLeft} oras lampas` : `${hoursLeft} oras pa`})`}.
          </div>
          {c.permissions.feedback_8888 && (
            <Form onSubmit={(e) => { e.preventDefault(); send.mutate({ feedback: text }); }}>
              <Form.Control as="textarea" rows={3} className="mb-2" value={text} onChange={(e) => setText(e.target.value)}
                placeholder="Ano ang konkretong aksyon, sino, at kailan. hal. Naipasa sa GSO noong Okt 20; papalitan ang bombilya sa Okt 22." />
              <SubmitButton pending={send.isPending} disabled={text.trim().length < 30}>I-record ang feedback</SubmitButton>
              <ErrorText err={send.error} />
            </Form>
          )}
        </>
      )}
    </Panel>
  );
}

// ---------------- Deadline (ARTA) ----------------
export function DeadlinePanel({ c }: P) {
  const extend = useExtend(c.id);
  const [open, setOpen] = useState(false);
  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const k = c.case;
  if (!k?.due_at) return null;
  const overdue = c.is_overdue;
  return (
    <Panel title="Target na petsa (ARTA)" icon="calendar-check" tone={overdue ? "danger" : undefined}>
      <div className={`fs-5 fw-semibold ${overdue ? "text-danger" : ""}`}>{fmtDate(k.due_at)}</div>
      {k.extended_at && (
        <div className="small text-secondary">
          Na-extend mula {fmtDate(k.original_due_at)}: {k.extension_reason}
        </div>
      )}
      {c.permissions.extend && !open && (
        <Button variant="link" size="sm" className="px-0" onClick={() => setOpen(true)}>Mag-file ng extension (isang beses lang)</Button>
      )}
      {open && (
        <Form className="mt-2" onSubmit={(e) => { e.preventDefault(); extend.mutate({ new_due_date: date, reason }, { onSuccess: () => setOpen(false) }); }}>
          <Form.Control type="date" className="mb-2" value={date} onChange={(e) => setDate(e.target.value)}
            max={k.max_extension_due?.slice(0, 10)} min={k.due_at.slice(0, 10)} />
          {k.max_extension_due && <Form.Text className="d-block mb-2">Pinakahuli: {fmtDate(k.max_extension_due)} (hindi lalampas sa orihinal na haba).</Form.Text>}
          <Form.Control size="sm" className="mb-2" placeholder="Dahilan (makikita ng nag-report)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <SubmitButton pending={extend.isPending} disabled={!date || !reason.trim()} variant="outline-primary">I-extend</SubmitButton>
          <ErrorText err={extend.error} />
        </Form>
      )}
    </Panel>
  );
}

// ---------------- Outcomes: close / reopen / reject / escalate ----------------
export function OutcomePanel({ c }: P) {
  const close = useClose(c.id);
  const reopen = useReopen(c.id);
  const reject = useReject(c.id);
  const escalate = useEscalate(c.id);
  const [modal, setModal] = useState<null | "reopen" | "reject" | "escalate">(null);
  const [text, setText] = useState("");
  const p = c.permissions;
  if (!p.close && !p.reopen && !p.reject && !p.escalate) return null;

  const run = () => {
    const done = { onSuccess: () => { setModal(null); setText(""); } };
    if (modal === "reopen") reopen.mutate({ remarks: text }, done);
    if (modal === "reject") reject.mutate({ remarks: text }, done);
    if (modal === "escalate") escalate.mutate({ reason: text }, done);
  };
  const pending = reopen.isPending || reject.isPending || escalate.isPending;
  const err = reopen.error ?? reject.error ?? escalate.error;

  return (
    <Panel title="Iba pang aksyon" icon="three-dots">
      <div className="d-grid gap-2">
        {p.close && (
          <SubmitButton pending={close.isPending} variant="dark" onClick={() => close.mutate({})}>
            <i className="bi bi-archive me-1" aria-hidden /> Isara (naipaalam na sa nag-report)
          </SubmitButton>
        )}
        {p.reopen && <Button variant="outline-warning" onClick={() => setModal("reopen")}>Buksan muli (Reopen)</Button>}
        {p.escalate && (
          <Button variant="outline-dark" onClick={() => setModal("escalate")}>
            Escalate{c.case && c.case.escalation_level > 0 ? ` (kasalukuyan: ${c.case.escalation_level_display})` : ""}
          </Button>
        )}
        {p.reject && <Button variant="outline-danger" onClick={() => setModal("reject")}>Hindi maaaksyunan (Reject)</Button>}
      </div>
      <ErrorText err={close.error} />
      <Modal show={!!modal} onHide={() => setModal(null)} centered>
        <Modal.Header closeButton>
          <Modal.Title className="h5">
            {modal === "reopen" ? "Buksan muli" : modal === "reject" ? "Reject" : "Escalate sa susunod na antas"}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {modal === "reject" && <Alert variant="warning" className="small">Makikita ng nag-report ang dahilan.</Alert>}
          <Form.Control as="textarea" rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder="Dahilan" />
          <ErrorText err={err} />
        </Modal.Body>
        <Modal.Footer>
          <Button variant="outline-secondary" onClick={() => setModal(null)}>Kanselahin</Button>
          <SubmitButton className="" pending={pending} disabled={!text.trim()} onClick={run}>I-save</SubmitButton>
        </Modal.Footer>
      </Modal>
    </Panel>
  );
}
