import { useState } from "react";
import { Button, Form, InputGroup } from "react-bootstrap";

import { apiErrorMessage } from "@/api/client";
import { useSmsPreference } from "@/api/public";
import type { TrackResult } from "@/api/types";

/** "SMS updates: on · Itigil" on the tracking page. The number is never shown; the last 4 digits prove it's yours. */
export function SmsPreference({ c }: { c: TrackResult }) {
  const pref = useSmsPreference(c.reference_no);
  const [open, setOpen] = useState(false);
  const [last4, setLast4] = useState("");
  if (c.sms_updates === "none") return null;
  const on = c.sms_updates === "on";

  return (
    <div className="border rounded p-3 mb-4 small">
      <div className="d-flex flex-wrap align-items-center gap-2">
        <i className={`bi ${on ? "bi-chat-dots text-primary" : "bi-chat-slash text-secondary"} fs-5`} aria-hidden />
        <span className="flex-grow-1">
          {on
            ? "Makakatanggap ka ng SMS sa bawat mahalagang update (wala mula 9 PM hanggang 7 AM)."
            : "Naka-off ang SMS updates. Makikita mo pa rin ang progreso dito."}
        </span>
        {!open && (
          <Button size="sm" variant="outline-secondary" onClick={() => setOpen(true)}>
            {on ? "Itigil ang SMS" : "Buksan muli ang SMS"}
          </Button>
        )}
      </div>
      {open && (
        <Form
          className="mt-2"
          onSubmit={(e) => {
            e.preventDefault();
            pref.mutate({ sms: !on, mobile_last4: last4 }, { onSuccess: () => { setOpen(false); setLast4(""); } });
          }}
        >
          <Form.Label htmlFor="sms-last4" className="mb-1">Huling 4 na numero ng mobile na ginamit mo sa report</Form.Label>
          <InputGroup style={{ maxWidth: 300 }}>
            <Form.Control id="sms-last4" inputMode="numeric" maxLength={4} value={last4}
              onChange={(e) => setLast4(e.target.value.replace(/\D/g, ""))} />
            <Button type="submit" disabled={last4.length !== 4 || pref.isPending}>
              {on ? "Itigil" : "Buksan"}
            </Button>
            <Button variant="link" onClick={() => setOpen(false)}>Kanselahin</Button>
          </InputGroup>
          {pref.isError && <div className="text-danger mt-1">{apiErrorMessage(pref.error)}</div>}
        </Form>
      )}
    </div>
  );
}
