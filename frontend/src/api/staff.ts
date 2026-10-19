import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { SubmitConcernInput } from "./public";
import type {
  Channel,
  ConcernStatus,
  Department,
  Severity,
  StaffConcernDetail,
  StaffConcernPage,
  StaffSummary,
  StaffUser,
} from "./types";

export type InboxTab = "triage" | "mine" | "overdue" | "open" | "closed" | "all";
export type InboxParams = { tab: InboxTab; q?: string; page?: number };

export const staffKeys = {
  all: ["staff"] as const,
  summary: ["staff", "summary"] as const,
  list: (p: InboxParams) => ["staff", "concerns", p] as const,
  detail: (id: number) => ["staff", "concern", id] as const,
  departments: ["staff", "departments"] as const,
  users: (dept: number) => ["staff", "users", dept] as const,
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

export function useDepartments() {
  return useQuery({
    queryKey: staffKeys.departments,
    queryFn: async () => (await api.get<Department[]>("/staff/departments/")).data,
    staleTime: 60 * 60 * 1000,
  });
}

export function useDepartmentUsers(departmentId: number | undefined) {
  return useQuery({
    queryKey: staffKeys.users(departmentId ?? 0),
    queryFn: async () =>
      (await api.get<StaffUser[]>("/staff/users/", { params: { department: departmentId } })).data,
    enabled: !!departmentId,
    staleTime: 10 * 60 * 1000,
  });
}

/** Every workflow action returns the updated detail; we drop it into the cache and refresh lists/counts. */
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

export const useVerify = (id: number) =>
  useCaseAction<{ category: string; subcategory: string | null; severity: Severity; remarks?: string }>(id, "verify");

export const useAssign = (id: number) =>
  useCaseAction<{ department: number; assigned_to: number | null; due_at: string | null; remarks?: string }>(
    id,
    "assign",
  );

export type StatusInput = { status: ConcernStatus; remarks: string; is_public: boolean; photos?: File[] };
export const useSetStatus = (id: number) =>
  useCaseAction<StatusInput>(id, "status", (v) => {
    const fd = new FormData();
    fd.append("status", v.status);
    fd.append("remarks", v.remarks);
    fd.append("is_public", String(v.is_public));
    v.photos?.forEach((p) => fd.append("photos", p));
    return fd;
  });

export const useEscalate = (id: number) => useCaseAction<{ reason: string }>(id, "escalate");
export const useAddNote = (id: number) => useCaseAction<{ body: string }>(id, "notes");
export const useLinkDuplicate = (id: number) => useCaseAction<{ master_reference: string }>(id, "link-duplicate");
export const useUnlinkDuplicate = (id: number) => useCaseAction<void>(id, "unlink-duplicate", () => ({}));

export type EncodeInput = SubmitConcernInput & { channel: Channel; source_reference?: string };

export function useEncodeConcern() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: EncodeInput) => {
      const fd = new FormData();
      for (const [k, v] of Object.entries(input)) {
        if (k === "images" || v === undefined || v === null || v === "") continue;
        fd.append(k, String(v));
      }
      input.images?.forEach((f) => fd.append("images", f));
      return (await api.post<StaffConcernDetail>("/staff/concerns/", fd)).data;
    },
    onSuccess: (data) => {
      qc.setQueryData(staffKeys.detail(data.id), data);
      qc.invalidateQueries({ queryKey: staffKeys.all });
    },
  });
}
