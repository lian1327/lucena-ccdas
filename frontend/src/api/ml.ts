import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { MLOverview, ModelVersionInfo } from "./types";

export function useMLOverview() {
  return useQuery({ queryKey: ["ml"], queryFn: async () => (await api.get<MLOverview>("/staff/ml/")).data });
}

export function useRetrain() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (v: { real_only?: boolean; notes?: string }) =>
      (await api.post<ModelVersionInfo>("/staff/ml/train/", v, { timeout: 300_000 })).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ml"] }),
  });
}

export function useActivate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post<ModelVersionInfo>(`/staff/ml/versions/${id}/activate/`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ml"] }),
  });
}
