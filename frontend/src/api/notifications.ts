import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./client";
import type { CitizenNotification, NotificationPage, NotificationStats, StaffAlert, StaffAlertList } from "./types";

const ALERTS = ["staff", "alerts"] as const;

/** Polls once a minute (and when the tab regains focus) so new assignments show without a reload. */
export function useAlerts() {
  return useQuery({
    queryKey: ALERTS,
    queryFn: async () => (await api.get<StaffAlertList>("/staff/alerts/")).data,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
  });
}

export function useReadAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post<StaffAlert>(`/staff/alerts/${id}/read/`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ALERTS }),
  });
}

export function useReadAllAlerts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => (await api.post("/staff/alerts/read-all/")).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ALERTS }),
  });
}

export type NotificationFilters = { status?: string; channel?: string; event?: string; q?: string; page?: number };

export function useNotificationLog(f: NotificationFilters) {
  return useQuery({
    queryKey: ["staff", "notifications", f],
    queryFn: async () => (await api.get<NotificationPage>("/staff/notifications/", { params: f })).data,
    placeholderData: keepPreviousData,
  });
}

export function useNotificationStats() {
  return useQuery({
    queryKey: ["staff", "notifications", "stats"],
    queryFn: async () => (await api.get<NotificationStats>("/staff/notifications/stats/")).data,
  });
}

export function useRetryNotification() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: number) => (await api.post<CitizenNotification>(`/staff/notifications/${id}/retry/`)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["staff", "notifications"] }),
  });
}
