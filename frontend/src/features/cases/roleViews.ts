import type { InboxTab } from "@/api/staff";
import type { Role, StaffSummary } from "@/api/types";

type TabDef = { key: InboxTab; label: string; count?: keyof StaffSummary; danger?: boolean };

const T = {
  triage: { key: "triage", label: "Triage", count: "triage" },
  to_route: { key: "to_route", label: "Ipapasa", count: "to_route" },
  validation: { key: "validation", label: "For validation", count: "validation" },
  endorsed: { key: "endorsed", label: "Endorsed (DPWH atbp.)", count: "endorsed" },
  overdue: { key: "overdue", label: "Overdue", count: "overdue", danger: true },
  open: { key: "open", label: "Lahat ng bukas", count: "open" },
  closed: { key: "closed", label: "Tapos na" },
} satisfies Record<string, TabDef>;

const mine = (label: string): TabDef => ({ key: "mine", label, count: "mine" });

/** Each role sees its own work first. */
export function tabsFor(role: Role | undefined): TabDef[] {
  switch (role) {
    case "pacd":
    case "city_admin":
      return [T.triage, T.to_route, mine("Isasara / 8888 / follow-up"), T.endorsed, T.validation, T.overdue, T.open, T.closed];
    case "dept_head":
      return [mine("Kailangan ng aksyon ko"), T.triage, T.validation, T.endorsed, T.overdue, T.open, T.closed];
    case "division_chief":
      return [mine("Kailangan ng aksyon ko"), T.validation, T.overdue, T.open, T.closed];
    case "dept_staff":
      return [mine("Mga trabaho ko"), T.overdue, T.open, T.closed];
    case "barangay":
      return [T.triage, T.to_route, mine("Barangay-level"), T.validation, T.overdue, T.open, T.closed];
    case "mayor":
      return [T.overdue, T.endorsed, T.open, T.closed];
    default:
      return [T.open, T.closed];
  }
}

export const STAGE_LABEL: Record<string, string> = {
  with_department: "Nasa opisina",
  with_division: "Nasa division",
  assigned: "May tauhan na",
  scheduled: "Nakaiskedyul",
  for_validation: "For validation",
  validated: "Na-validate",
  endorsed: "Endorsed",
};
