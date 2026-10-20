import { Alert, Card, Table } from "react-bootstrap";
import { Link, useParams } from "react-router-dom";

import { useOfficePeople } from "@/api/analytics";
import { apiErrorMessage } from "@/api/client";
import { useAuth } from "@/auth/AuthContext";
import { FullPageSpinner } from "@/components/FullPageSpinner";
import { PeriodBar, usePeriod } from "@/features/analytics/PeriodBar";
import { pct } from "@/features/analytics/ui";

const COLS = [
  ["accepted", "Tinanggap"], ["responded", "Unang aksyon"], ["inspected", "Inspeksyon"], ["submitted", "Report"],
  ["crew", "Crew"], ["validated", "Nag-validate"], ["returned", "Nagbalik"], ["overrides", "Override"],
] as const;

/** Who in this office did what, with the quality of their proof. Alphabetical; not a ranking. */
export default function OfficePeoplePage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const [period, setPeriod] = usePeriod("90d");
  const q = useOfficePeople(id, period);
  if (q.isLoading) return <FullPageSpinner />;
  if (q.isError) return <Alert variant="danger">{apiErrorMessage(q.error)}</Alert>;
  const d = q.data!;
  const exec = user?.role === "city_admin" || user?.role === "mayor";
  return (
    <div className="analytics-report">
      {exec && <Link to={`/staff/accountability?period=${period}`} className="small text-decoration-none d-print-none">‹ Lahat ng opisina</Link>}
      <div className="d-flex flex-wrap align-items-center gap-2 mt-2 mb-3">
        <div className="me-auto">
          <h1 className="h4 fw-bold mb-0">{d.department.name}: sino ang kumilos</h1>
          <div className="small text-secondary">{d.period.label} · ayon sa pangalan, hindi ranking. Pindutin ang pangalan para makita ang bawat aksyon at litrato.</div>
        </div>
        <PeriodBar period={period} onChange={setPeriod} />
      </div>
      <Card className="border-0 shadow-sm">
        <Card.Body className="p-0">
          <Table responsive hover className="mb-0 small align-middle" style={{ fontVariantNumeric: "tabular-nums" }}>
            <thead className="table-light">
              <tr>
                <th>Tauhan</th>
                {COLS.map(([k, l]) => <th key={k} className="text-end">{l}</th>)}
                <th className="text-end">Litrato</th><th className="text-end">May lokasyon</th><th className="text-end">Red flag</th>
                <th className="text-end" title="Mga report niya na ibinalik ng supervisor">Ibinalik sa kanya</th>
                <th className="text-end" title="Sinabi ng nag-report na hindi pa naayos">Hindi pa naayos</th>
                <th className="text-end">Bukas na hawak</th>
              </tr>
            </thead>
            <tbody>
              {d.people.map((p) => (
                <tr key={p.id} className={p.total_actions === 0 ? "text-secondary" : ""}>
                  <td>
                    <Link to={`/staff/people/${p.id}?period=${period}`} className="fw-semibold text-decoration-none">{p.name}</Link>
                    <div className="text-secondary">{p.role_display}{p.division ? ` · ${p.division}` : ""}</div>
                  </td>
                  {COLS.map(([k]) => <td key={k} className="text-end">{p.actions[k] || <span className="text-secondary">·</span>}</td>)}
                  <td className="text-end">{p.photos}</td>
                  <td className="text-end">{pct(p.located_rate)}</td>
                  <td className={`text-end ${p.red_flag_photos ? "text-danger fw-semibold" : ""}`}>{p.red_flag_photos}</td>
                  <td className="text-end">{p.reports_returned}</td>
                  <td className={`text-end ${p.citizen_not_fixed ? "text-danger" : ""}`}>{p.citizen_not_fixed}</td>
                  <td className="text-end">{p.open_assigned}</td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card.Body>
      </Card>
      <p className="small text-secondary mt-2">
        Para sa coaching at beripikasyon. Ang bilang ng aksyon ay nakadepende sa trabahong naitalaga; hindi ito sukatan ng sipag.
      </p>
    </div>
  );
}
