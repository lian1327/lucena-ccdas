import { Badge } from "react-bootstrap";

const VARIANT: Record<string, string> = { critical: "danger", high: "warning", medium: "info", low: "secondary" };

export function PriorityBadge({ tier, score }: { tier: string; score: number }) {
  return (
    <Badge bg={VARIANT[tier] ?? "secondary"} text={tier === "high" || tier === "medium" ? "dark" : undefined}>
      {tier.toUpperCase()} · {Math.round(score)}
    </Badge>
  );
}
