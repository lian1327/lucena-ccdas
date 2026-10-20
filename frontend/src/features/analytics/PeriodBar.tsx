import { ButtonGroup, ToggleButton } from "react-bootstrap";
import { useSearchParams } from "react-router-dom";

import type { Period } from "@/api/analytics";

import { PERIODS } from "./ui";

export function usePeriod(fallback: Period = "90d") {
  const [params, setParams] = useSearchParams();
  const period = (params.get("period") as Period) || fallback;
  return [period, (p: Period) => setParams({ period: p })] as const;
}

export function PeriodBar({ period, onChange }: { period: Period; onChange: (p: Period) => void }) {
  return (
    <ButtonGroup size="sm" className="d-print-none">
      {PERIODS.map((p) => (
        <ToggleButton key={p.key} id={`p-${p.key}`} type="radio" variant="outline-secondary" value={p.key}
          checked={period === p.key} onChange={() => onChange(p.key as Period)}>{p.label}</ToggleButton>
      ))}
    </ButtonGroup>
  );
}
