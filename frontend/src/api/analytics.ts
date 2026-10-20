import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { api } from "./client";
import type { Accountability, Ledger, OfficeDetail, People, Scorecard } from "./types";

export type Period = "this_month" | "last_month" | "quarter" | "90d" | "12m";

export function useScorecard(period: Period) {
  return useQuery({
    queryKey: ["analytics", "scorecard", period],
    queryFn: async () => (await api.get<Scorecard>("/staff/analytics/offices/", { params: { period } })).data,
    placeholderData: keepPreviousData,
  });
}

export function useOfficeDetail(id: number, period: Period) {
  return useQuery({
    queryKey: ["analytics", "office", id, period],
    queryFn: async () => (await api.get<OfficeDetail>(`/staff/analytics/offices/${id}/`, { params: { period } })).data,
    placeholderData: keepPreviousData,
  });
}

/** CSV needs the auth header, so fetch as a blob and trigger a download. */
export async function downloadScorecardCsv(period: Period) {
  const res = await api.get<Blob>("/staff/analytics/offices.csv", { params: { period }, responseType: "blob" });
  const name = /filename="([^"]+)"/.exec(res.headers["content-disposition"] ?? "")?.[1] ?? "ccadss-office-kpis.csv";
  const url = URL.createObjectURL(res.data);
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// ----- Step 10: accountability -----
export function useAccountability(period: Period) {
  return useQuery({
    queryKey: ["analytics", "accountability", period],
    queryFn: async () => (await api.get<Accountability>("/staff/analytics/accountability/", { params: { period } })).data,
  });
}

export function useOfficePeople(id: number, period: Period) {
  return useQuery({
    queryKey: ["analytics", "people", id, period],
    queryFn: async () => (await api.get<People>(`/staff/analytics/offices/${id}/people/`, { params: { period } })).data,
    enabled: id > 0,
  });
}

export function useLedger(id: number, period: Period) {
  return useQuery({
    queryKey: ["analytics", "ledger", id, period],
    queryFn: async () => (await api.get<Ledger>(`/staff/analytics/people/${id}/`, { params: { period } })).data,
    enabled: id > 0,
  });
}
