export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const mins = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (mins < 1) return "ngayon lang";
  if (mins < 60) return `${mins} min`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs} oras`;
  const days = Math.round(hrs / 24);
  return `${days} araw`;
}

export function fmtDateTime(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleString("en-PH", { dateStyle: "medium", timeStyle: "short" }) : "—";
}

export function fmtDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString("en-PH", { dateStyle: "medium" }) : "—";
}

export function dueLabel(iso: string | null | undefined): { text: string; overdue: boolean } | null {
  if (!iso) return null;
  const days = Math.ceil((new Date(iso).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return { text: `${-days} araw lampas`, overdue: true };
  if (days === 0) return { text: "due ngayon", overdue: false };
  return { text: `${days} araw pa`, overdue: false };
}
