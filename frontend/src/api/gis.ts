import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { BarangayStat, Hotspots, MapPoints } from "./types";

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
