/**
 * Office receiving & screening, priority level, and first response (make-safe).
 * Rendered only when the backend permission allows it.
 */
import { useMemo, useState } from "react";
import { Alert, Button, Form, Table } from "react-bootstrap";

import { useAccept, useDivisions, usePriorityLevels, useRespond, useReturnToPacd, useSetPriority } from "@/api/staff";
import type { PriorityLevel, StaffConcernDetail } from "@/api/types";
import { UrgencyBadge } from "@/components/UrgencyBadge";
import { fmtDateTime } from "@/utils/format";

import { ErrorText, Panel, PhotoPicker, SubmitButton } from "./ui";

type P = { c: StaffConcernDetail };

export function targetText(l: PriorityLevel) {
  const resp = l.response_hours ? `${l.response_hours} oras` : `${l.response_working_days} working day${(l.response_working_days ?? 0) > 1 ? "s" : ""}`;
  const res = l.resolution_cap_days ? `≤ ${l.resolution_cap_days} WD (o ARTA max kung mas maikli)` : "ARTA max ng serbisyo";
  return `Unang aksyon: ${resp} · Resolusyon: ${res}`;
}

function PriorityPicker({ value, onChange, suggested }: { value: number | null; onChange: (id: number) => void; suggested?: string | null }) {
  const levels = usePriorityLevels();
  return (
    <div className="d-grid gap-2 mb-2">
      {levels.data?.map((l) => (
        <Form.Check
          key={l.id}
          type="radio"
          id={`lvl-${l.code}`}
          name="priority-level"
          checked={value === l.id}
          onChange={() => onChange(l.id)}
          label={
            <span>
              <UrgencyBadge code={l.code} name={l.name_fil || l.name} color={l.color} />
              {suggested === l.code && <span className="small text-primary ms-1">(suggested)</span>}
              <span className="d-block small text-secondary">{l.description}</span>
              <span className="d-block small text-secondary">{targetText(l)}</span>
            </span>
          }
        />
      ))}
    </div>
  );
}

// ---------------- Office acceptance ----------------
export function AcceptPanel({ c }: P) {
  const k = c.case;
  const accept = useAccept(c.id);
  const ret = useReturnToPacd(c.id);
  const levels = usePriorityLevels();
  const divisions = useDivisions(k?.department_id);
  const checklist = useMemo(() => k?.screening_checklist ?? [], [k]);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [level, setLevel] = useState<number | null>(k?.priority_level?.id ?? null);
  const [reason, setReason] = useState("");
  const [division, setDivision] = useState<number | null>(k?.division_id ?? null);
  const [returning, setReturning] = useState(false);
  const [returnReason, setReturnReason] = useState("");
  if (!c.permissions.accept || !k) return null;

  const changed = !!level && level !== k.priority_level?.id;
  const answered = checklist.every((q) => q in answers);
  const anyNo = checklist.some((q) => answers[q] === false);
  const levelCode = levels.data?.find((l) => l.id === level)?.code;
  const dueInfo = k.acceptance_due_at ? `Tanggapin o ibalik bago ${fmtDateTime(k.acceptance_due_at)}.` : "";

  return (
    <Panel title={`Pagtanggap ng ${k.department}`} icon="inbox" tone="primary"
      hint={<>Suriin kung sakop talaga ng opisina at kumpirmahin ang antas ng prayoridad. {dueInfo}</>}>
      {checklist.length > 0 && (
        <Table size="sm" className="small mb-3 align-middle">
          <tbody>
            {checklist.map((q) => (
              <tr key={q}>
                <td>{q}</td>
                <td className="text-nowrap text-end">
                  {[true, false].map((v) => (
                    <Button key={String(v)} size="sm" className="ms-1" aria-pressed={answers[q] === v}
                      variant={answers[q] === v ? (v ? "success" : "danger") : "outline-secondary"}
                      onClick={() => setAnswers((a) => ({ ...a, [q]: v }))}>
                      {v ? "Oo" : "Hindi"}
                    </Button>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      {anyNo && (
        <Alert variant="warning" className="small py-2">
          May "Hindi" sa screening. Kung hindi sakop ng opisina, <strong>ibalik sa PACD</strong> o ipa-endorso.
        </Alert>
      )}

      <Form.Label className="small fw-semibold">Antas ng prayoridad</Form.Label>
      <PriorityPicker value={level} onChange={setLevel} suggested={c.suggested_priority?.code} />
      {changed && (
        <Form.Control size="sm" className="mb-2" placeholder="Dahilan ng pagbabago ng antas (kailangan)"
          value={reason} onChange={(e) => setReason(e.target.value)} />
      )}

      {(divisions.data?.length ?? 0) > 0 && (
        <Form.Select className="mb-3" value={division ?? ""} onChange={(e) => setDivision(Number(e.target.value) || null)} aria-label="Division">
          <option value="">— Division (opsyonal) —</option>
          {divisions.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
        </Form.Select>
      )}

      <SubmitButton pending={accept.isPending} disabled={!level || !answered || (changed && !reason.trim())}
        onClick={() => accept.mutate({ priority_level: level!, priority_reason: reason, screening: answers, division })}>
        <i className="bi bi-check2 me-1" aria-hidden /> Tanggapin{levelCode ? ` bilang ${levelCode}` : ""}
      </SubmitButton>
      <ErrorText err={accept.error} />

      {returning ? (
        <div className="mt-3">
          <Form.Control as="textarea" rows={2} className="mb-2" placeholder="Bakit hindi sakop ng opisina? (makikita ng PACD)"
            value={returnReason} onChange={(e) => setReturnReason(e.target.value)} />
          <SubmitButton pending={ret.isPending} variant="outline-danger" disabled={!returnReason.trim()}
            onClick={() => ret.mutate({ reason: returnReason })}>Ibalik sa PACD</SubmitButton>
          <ErrorText err={ret.error} />
        </div>
      ) : (
        <Button variant="link" size="sm" className="w-100 mt-1 text-danger" onClick={() => setReturning(true)}>
          Hindi sakop ng opisina: ibalik sa PACD
        </Button>
      )}
    </Panel>
  );
}

// ---------------- Priority (after acceptance) ----------------
export function PriorityPanel({ c }: P) {
  const k = c.case;
  const set = useSetPriority(c.id);
  const [editing, setEditing] = useState(false);
  const [level, setLevel] = useState<number | null>(k?.priority_level?.id ?? null);
  const [reason, setReason] = useState("");
  if (!k?.priority_level || (k.level === "city" && !k.accepted_at)) return null;
  const l = k.priority_level;
  const overdue = !k.responded_at && k.response_due_at && new Date(k.response_due_at) < new Date();

  return (
    <Panel title="Prayoridad at unang aksyon" icon="lightning-charge" tone={overdue ? "danger" : l.code === "P1" ? "danger" : undefined}>
      <div className="mb-2"><UrgencyBadge code={l.code} name={l.name_fil || l.name} color={l.color} /></div>
      <div className="small text-secondary mb-2">{targetText(l)}</div>
      {k.priority_reason && <div className="small mb-2">Dahilan: {k.priority_reason}</div>}
      <div className={`small ${overdue ? "text-danger fw-semibold" : ""}`}>
        {k.responded_at ? (
          <>
            <i className="bi bi-check2-circle text-success me-1" aria-hidden />
            Unang aksyon: {fmtDateTime(k.responded_at)} · {k.responded_by}
            {k.response_remarks && <div className="text-body">{k.response_remarks}</div>}
          </>
        ) : k.response_due_at ? (
          <>Unang aksyon due: {fmtDateTime(k.response_due_at)}{overdue && " (LAMPAS)"}</>
        ) : null}
      </div>
      {k.breaches.length > 0 && (
        <Alert variant="danger" className="small py-2 mt-2 mb-0">
          {k.breaches.map((b) => <div key={b}>• {b}</div>)}
        </Alert>
      )}
      {c.permissions.set_priority && (editing ? (
        <div className="mt-3">
          <PriorityPicker value={level} onChange={setLevel} />
          <Form.Control size="sm" className="mb-2" placeholder="Dahilan (kailangan)" value={reason} onChange={(e) => setReason(e.target.value)} />
          <SubmitButton pending={set.isPending} disabled={!level || level === l.id || !reason.trim()} variant="outline-primary"
            onClick={() => set.mutate({ priority_level: level!, reason }, { onSuccess: () => { setEditing(false); setReason(""); } })}>
            I-save ang antas
          </SubmitButton>
          <ErrorText err={set.error} />
        </div>
      ) : (
        <Button variant="link" size="sm" className="px-0 mt-1" onClick={() => setEditing(true)}>Baguhin ang antas</Button>
      ))}
    </Panel>
  );
}

// ---------------- First response / make-safe ----------------
export function RespondPanel({ c }: P) {
  const respond = useRespond(c.id);
  const [remarks, setRemarks] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  if (!c.permissions.respond) return null;
  const p1 = c.case?.priority_level?.code === "P1";
  return (
    <Panel title={p1 ? "Make-safe (P1)" : "Unang aksyon"} icon="cone-striped" tone={p1 ? "danger" : "primary"}
      hint={p1 ? "Gawing ligtas muna ang lugar (barricade, warning sign, alis ng sagabal). Ito ang humihinto sa response clock."
        : "Kung hindi pa makakapag-inspeksyon, itala ang unang ginawa. Ang site inspection ay binibilang din bilang unang aksyon."}>
      <Form.Control as="textarea" rows={2} className="mb-2" value={remarks} onChange={(e) => setRemarks(e.target.value)}
        placeholder="hal. Nilagyan ng barricade at warning sign. Papalitan ang takip bukas. (makikita ng nag-report)" />
      <PhotoPicker label="Litrato (opsyonal, internal)" value={photos} onChange={setPhotos} />
      <SubmitButton pending={respond.isPending} disabled={!remarks.trim()} variant={p1 ? "danger" : "primary"}
        onClick={() => respond.mutate({ remarks, photos })}>I-log ang unang aksyon</SubmitButton>
      <ErrorText err={respond.error} />
    </Panel>
  );
}
