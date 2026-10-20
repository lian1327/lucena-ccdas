import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type {
  Barangay,
  Category,
  ConcernCreateRequest,
  ConcernCreateResponse,
  PublicStats,
  TrackResult,
} from "./types";

export const publicKeys = {
  categories: ["public", "categories"] as const,
  barangays: ["public", "barangays"] as const,
  stats: ["public", "stats"] as const,
  track: (ref: string) => ["public", "track", ref.toUpperCase()] as const,
};

const HOUR = 60 * 60 * 1000;

export function useCategories() {
  return useQuery({
    queryKey: publicKeys.categories,
    queryFn: async () => (await api.get<Category[]>("/public/categories/")).data,
    staleTime: HOUR,
  });
}

export function useBarangays() {
  return useQuery({
    queryKey: publicKeys.barangays,
    queryFn: async () => (await api.get<Barangay[]>("/public/barangays/")).data,
    staleTime: HOUR,
  });
}

export function usePublicStats() {
  return useQuery({
    queryKey: publicKeys.stats,
    queryFn: async () => (await api.get<PublicStats>("/public/stats/")).data,
    staleTime: 5 * 60 * 1000,
  });
}

export function useTrackConcern(referenceNo: string | undefined) {
  const ref = referenceNo?.trim() ?? "";
  return useQuery({
    queryKey: publicKeys.track(ref),
    queryFn: async () =>
      (await api.get<TrackResult>(`/public/concerns/track/${encodeURIComponent(ref)}/`)).data,
    enabled: ref.length > 0,
    retry: false, // a 404 means "no such reference", not a transient error
  });
}

export type SubmitConcernInput = Omit<ConcernCreateRequest, "images"> & { images?: File[] };

function toFormData(input: SubmitConcernInput): FormData {
  const fd = new FormData();
  for (const [key, value] of Object.entries(input)) {
    if (key === "images" || value === undefined || value === null || value === "") continue;
    fd.append(key, String(value));
  }
  input.images?.forEach((file) => fd.append("images", file));
  return fd;
}

export function useSubmitConcern() {
  return useMutation({
    mutationFn: async (input: SubmitConcernInput) =>
      (await api.post<ConcernCreateResponse>("/public/concerns/", toFormData(input))).data,
  });
}

/** "Naayos ba talaga?" — reporter confirms or disputes the fix. */
export function useConfirmFix(referenceNo: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { fixed: boolean; feedback?: string; mobile_last4?: string }) =>
      (await api.post<TrackResult>(`/public/concerns/track/${encodeURIComponent(referenceNo)}/confirm/`, v)).data,
    onSuccess: (data) => qc.setQueryData(publicKeys.track(referenceNo), data),
  });
}
