import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { SubmitConcernInput } from "./public";
import type {
  Channel,
  Department,
  Division,
  EndorsementStatus,
  PriorityLevel,
  Severity,
  StaffConcernDetail,
  StaffConcernPage,
  StaffSummary,
  StaffUser,
} from "./types";

export type InboxTab =
  | "triage" | "to_route" | "for_acceptance" | "mine" | "validation" | "endorsed" | "overdue" | "open" | "closed" | "all";
export type InboxParams = { tab: InboxTab; q?: string; page?: number };

export const staffKeys = {
  all: ["staff"] as const,
  summary: ["staff", "summary"] as const,
  list: (p: InboxParams) => ["staff", "concerns", p] as const,
  detail: (id: number) => ["staff", "concern", id] as const,
  departments: (kind?: string) => ["staff", "departments", kind ?? "all"] as const,
  divisions: (dept: number) => ["staff", "divisions", dept] as const,
  users: (dept: number, div?: number) => ["staff", "users", dept, div ?? 0] as const,
};

export function useStaffSummary() {
  return useQuery({
    queryKey: staffKeys.summary,
    queryFn: async () => (await api.get<StaffSummary>("/staff/summary/")).data,
    refetchInterval: 60_000,
  });
}

export function useStaffConcerns(params: InboxParams) {
  return useQuery({
    queryKey: staffKeys.list(params),
    queryFn: async () =>
      (
        await api.get<StaffConcernPage>("/staff/concerns/", {
          params: { tab: params.tab, q: params.q || undefined, page: params.page ?? 1 },
        })
      ).data,
    placeholderData: keepPreviousData,
  });
}

export function useStaffConcern(id: number) {
  return useQuery({
    queryKey: staffKeys.detail(id),
    queryFn: async () => (await api.get<StaffConcernDetail>(`/staff/concerns/${id}/`)).data,
  });
}

export function useDepartments(kind?: "internal" | "external") {
  return useQuery({
    queryKey: staffKeys.departments(kind),
    queryFn: async () => (await api.get<Department[]>("/staff/departments/", { params: { kind } })).data,
    staleTime: 60 * 60 * 1000,
  });
}

export function usePriorityLevels() {
  return useQuery({
    queryKey: ["staff", "priority-levels"],
    queryFn: async () => (await api.get<PriorityLevel[]>("/staff/priority-levels/")).data,
    staleTime: 60 * 60 * 1000,
  });
}

export function useDivisions(departmentId: number | null | undefined) {
  return useQuery({
    queryKey: staffKeys.divisions(departmentId ?? 0),
    queryFn: async () => (await api.get<Division[]>("/staff/divisions/", { params: { department: departmentId } })).data,
    enabled: !!departmentId,
    staleTime: 60 * 60 * 1000,
  });
}

export function useOfficeUsers(departmentId: number | null | undefined, divisionId?: number | null) {
  return useQuery({
    queryKey: staffKeys.users(departmentId ?? 0, divisionId ?? undefined),
    queryFn: async () =>
      (
        await api.get<StaffUser[]>("/staff/users/", {
          params: { department: departmentId, division: divisionId || undefined },
        })
      ).data,
    enabled: !!departmentId,
    staleTime: 10 * 60 * 1000,
  });
}

/** Every workflow action returns the updated detail; drop it into the cache and refresh lists/counts. */
function useCaseAction<TVars>(id: number, path: string, toBody: (v: TVars) => unknown = (v) => v) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: TVars) =>
      (await api.post<StaffConcernDetail>(`/staff/concerns/${id}/${path}/`, toBody(vars))).data,
    onSuccess: (data) => {
      qc.setQueryData(staffKeys.detail(id), data);
      qc.invalidateQueries({ queryKey: ["staff", "concerns"] });
      qc.invalidateQueries({ queryKey: staffKeys.summary });
    },
  });
}

function toFormData(v: Record<string, unknown>): FormData {
  const fd = new FormData();
  for (const [k, val] of Object.entries(v)) {
    if (val === undefined || val === null) continue;
    if (Array.isArray(val)) val.forEach((f) => fd.append(k, f as Blob));
    else fd.append(k, String(val));
  }
  return fd;
}

export const useVerify = (id: number) =>
  useCaseAction<{ category: string; subcategory: string | null; severity: Severity; remarks?: string }>(id, "verify");
export const useRoute = (id: number) =>
  useCaseAction<{ level: "city" | "barangay"; department?: number | null; division?: number | null; remarks?: string }>(id, "route");
export const useEndorse = (id: number) =>
  useCaseAction<{ agency: number; letter_reference?: string; contact_person?: string; remarks?: string }>(id, "endorse");
export const useAccept = (id: number) =>
  useCaseAction<{
    priority_level: number; priority_reason?: string; screening: Record<string, boolean>; division?: number | null; remarks?: string;
  }>(id, "accept");
export const useReturnToPacd = (id: number) => useCaseAction<{ reason: string }>(id, "return-to-pacd");
export const useSetPriority = (id: number) => useCaseAction<{ priority_level: number; reason: string }>(id, "set-priority");
export const useRespond = (id: number) =>
  useCaseAction<{ remarks: string; photos: File[]; photo_meta?: string }>(id, "respond", (v) => toFormData(v));
export const useAssignDivision = (id: number) => useCaseAction<{ division: number; remarks?: string }>(id, "assign-division");
export const useAssignPerson = (id: number) => useCaseAction<{ person: number; remarks?: string }>(id, "assign-person");
export const useInspect = (id: number) =>
  useCaseAction<{
    findings: string; action_plan?: string; scheduled_for?: string | null; public_message?: string;
    photos?: File[]; photo_meta?: string;
  }>(id, "inspect", (v) => toFormData(v));
export type CompleteInput = {
  remarks: string; photos: File[]; photo_meta: string; before_photos?: File[]; before_meta?: string;
  started_at?: string; finished_at?: string; crew?: string; other_workers?: string; materials?: string; equipment?: string;
};
export const useComplete = (id: number) => useCaseAction<CompleteInput>(id, "complete", (v) => toFormData(v));
export const useValidate = (id: number) =>
  useCaseAction<{ approve: boolean; remarks?: string; photos?: File[]; photo_meta?: string; override_reason?: string }>(
    id, "validate", (v) => toFormData(v));
export const useExtend = (id: number) => useCaseAction<{ new_due_date: string; reason: string }>(id, "extend");
export const useFollowUp = (id: number) =>
  useCaseAction<{
    method: string; notes: string; status?: EndorsementStatus | null; agency_response?: string; public_message?: string;
  }>(id, "follow-up");
export const useFeedback8888 = (id: number) => useCaseAction<{ feedback: string }>(id, "feedback-8888");
export const useReject = (id: number) => useCaseAction<{ remarks: string }>(id, "reject");
export const useClose = (id: number) => useCaseAction<{ remarks?: string }>(id, "close");
export const useReopen = (id: number) => useCaseAction<{ remarks: string }>(id, "reopen");
export const useEscalate = (id: number) => useCaseAction<{ reason: string }>(id, "escalate");
export const useAddNote = (id: number) => useCaseAction<{ body: string }>(id, "notes");
export const useLinkDuplicate = (id: number) => useCaseAction<{ master_reference: string }>(id, "link-duplicate");
export const useUnlinkDuplicate = (id: number) => useCaseAction<void>(id, "unlink-duplicate", () => ({}));

export type EncodeInput = SubmitConcernInput & {
  channel: Channel; source_reference?: string; external_ticket_no?: string; received_at?: string | null;
};

export function useEncodeConcern() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: EncodeInput) => {
      const { images, ...rest } = input;
      const fd = new FormData();
      for (const [k, v] of Object.entries(rest)) {
        if (v === undefined || v === null || v === "") continue;
        fd.append(k, String(v));
      }
      images?.forEach((f) => fd.append("images", f));
      return (await api.post<StaffConcernDetail>("/staff/concerns/", fd)).data;
    },
    onSuccess: (data) => {
      qc.setQueryData(staffKeys.detail(data.id), data);
      qc.invalidateQueries({ queryKey: staffKeys.all });
    },
  });
}
