import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { BarangayPuroks, BarangayStat, Boundaries, Hotspots, MapPoints } from "./types";

export type MapFilters = {
  days: number;
  category?: string;
  status: "all" | "open" | "resolved";
  priority?: string;
};

const params = (f: MapFilters) => ({
  days: f.days, category: f.category || undefined, status: f.status, priority: f.priority || undefined,
});

export function useMapPoints(f: MapFilters) {
  return useQuery({
    queryKey: ["gis", "points", f],
    queryFn: async () => (await api.get<MapPoints>("/staff/map/points/", { params: params(f) })).data,
    placeholderData: keepPreviousData,
  });
}

export function useBarangayStats(f: MapFilters) {
  return useQuery({
    queryKey: ["gis", "barangays", f],
    queryFn: async () => (await api.get<BarangayStat[]>("/staff/map/barangays/", { params: params(f) })).data,
    placeholderData: keepPreviousData,
  });
}

export function useHotspots(f: MapFilters, eps_m = 75, min_samples = 4) {
  return useQuery({
    queryKey: ["gis", "hotspots", f, eps_m, min_samples],
    queryFn: async () =>
      (await api.get<Hotspots>("/staff/map/hotspots/", { params: { ...params(f), eps_m, min_samples } })).data,
    placeholderData: keepPreviousData,
  });
}

// ----- Step 12: boundaries & puroks -----
export function useBoundaries(level: "barangay" | "purok", f: MapFilters, barangay?: number | null, enabled = true) {
  return useQuery({
    queryKey: ["gis", "boundaries", level, f, barangay ?? null],
    queryFn: async () =>
      (await api.get<Boundaries>("/staff/map/boundaries/", { params: { ...params(f), level, barangay: barangay || undefined } })).data,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
    enabled,
  });
}

export function useBarangayPuroks(id: number | null, f: MapFilters) {
  return useQuery({
    queryKey: ["gis", "barangay-puroks", id, f],
    queryFn: async () => (await api.get<BarangayPuroks>(`/staff/map/barangays/${id}/puroks/`, { params: params(f) })).data,
    enabled: !!id,
    placeholderData: keepPreviousData,
  });
}
