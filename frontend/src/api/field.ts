import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { components } from "./schema";

export type FieldJob = components["schemas"]["FieldJob"];
export type BlockReason = components["schemas"]["BlockerRequest"]["reason"];

export const fieldKeys = {
  jobs: ["staff", "field", "jobs"] as const,
  job: (id: number) => ["staff", "field", "job", id] as const,
};

export function useFieldJobs() {
  return useQuery({
    queryKey: fieldKeys.jobs,
    queryFn: async () => (await api.get<FieldJob[]>("/staff/field/jobs/")).data,
    refetchInterval: 120_000,
    gcTime: 24 * 60 * 60 * 1000, // keep the last list on screen if the signal drops
  });
}

export function useFieldJob(id: number) {
  const qc = useQueryClient();
  return useQuery({
    queryKey: fieldKeys.job(id),
    queryFn: async () => (await api.get<FieldJob>(`/staff/field/jobs/${id}/`)).data,
    initialData: () => qc.getQueryData<FieldJob[]>(fieldKeys.jobs)?.find((j) => j.id === id),
    gcTime: 24 * 60 * 60 * 1000,
  });
}

export const BLOCK_REASONS: { value: BlockReason; label: string; icon: string }[] = [
  { value: "materials", label: "Kulang ang materyales", icon: "box-seam" },
  { value: "equipment", label: "Kailangan ng equipment / tauhan", icon: "truck" },
  { value: "weather", label: "Masamang panahon / baha", icon: "cloud-rain-heavy" },
  { value: "access", label: "Hindi mapasok / pribadong lupa", icon: "sign-stop" },
  { value: "wrong_office", label: "Hindi sakop ng aming opisina", icon: "arrow-left-right" },
  { value: "national", label: "National road / ibang ahensya", icon: "signpost-split" },
  { value: "not_found", label: "Walang nakitang problema", icon: "search" },
  { value: "other", label: "Iba pa", icon: "three-dots" },
];
