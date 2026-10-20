import type { Insight } from "@/api/types";

export const INSIGHT_ICON: Record<string, string> = {
  red: "exclamation-octagon-fill text-danger", amber: "exclamation-triangle-fill text-warning", info: "info-circle-fill text-primary",
};

export function InsightList({ items, lang }: { items: Insight[]; lang: "fil" | "en" }) {
  if (!items.length) return <p className="small text-secondary mb-0">Walang kapansin-pansing pagbabago ngayong buwan.</p>;
  return (
    <ul className="list-unstyled mb-0">
      {items.map((i, k) => (
        <li key={k} className="d-flex gap-2 mb-2 small">
          <i className={`bi bi-${INSIGHT_ICON[i.level]} mt-1`} aria-label={i.level === "red" ? "mataas" : i.level === "amber" ? "bantayan" : "impormasyon"} />
          <span>{lang === "en" ? i.text_en : i.text}</span>
        </li>
      ))}
    </ul>
  );
}

export const change = (v: number | null | undefined) =>
  v == null ? "—" : `${v > 0 ? "▲ +" : v < 0 ? "▼ " : ""}${Math.round(v * 100)}%`;
