import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";

import { tokenStore } from "@/auth/tokens";
import { API_BASE } from "@/config";

export const api = axios.create({ baseURL: API_BASE, timeout: 30_000 });

api.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

/** Exchanges the refresh token for a new access token. Concurrent callers share one request. */
export function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.refresh;
  if (!refresh) return Promise.resolve(null);
  if (!refreshing) {
    refreshing = axios
      .post<{ access: string; refresh?: string }>(`${API_BASE}/auth/token/refresh/`, { refresh })
      .then(({ data }) => {
        tokenStore.set(data.access, data.refresh ?? refresh);
        return data.access;
      })
      .catch(() => {
        tokenStore.clear();
        return null;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

type RetryableConfig = InternalAxiosRequestConfig & { _retried?: boolean };

api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const config = error.config as RetryableConfig | undefined;
    if (error.response?.status === 401 && config && !config._retried && tokenStore.refresh) {
      config._retried = true;
      const access = await refreshAccessToken();
      if (access) {
        config.headers.Authorization = `Bearer ${access}`;
        return api(config);
      }
      tokenStore.notifyLoggedOut();
    }
    return Promise.reject(error);
  },
);

/** Turns DRF error payloads ({detail}, {field: [msg]}, [msg]) into one readable string. */
export function apiErrorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (!axios.isAxiosError(err)) return fallback;
  if (!err.response) return "Cannot reach the server. Check your connection.";
  if (err.response.status === 429) return "Too many requests. Please wait a moment and try again.";
  const data = err.response.data as unknown;
  if (typeof data === "string") return data || fallback;
  if (Array.isArray(data)) return data.join(" ");
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    if (typeof obj.detail === "string") return obj.detail;
    const first = Object.values(obj)[0];
    if (Array.isArray(first)) return String(first[0]);
    if (typeof first === "string") return first;
  }
  return fallback;
}

/** Field-level DRF errors, for showing under each form input. */
export function apiFieldErrors(err: unknown): Record<string, string> {
  if (!axios.isAxiosError(err) || !err.response?.data || typeof err.response.data !== "object") return {};
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(err.response.data as Record<string, unknown>)) {
    if (Array.isArray(v) && v.length) out[k] = String(v[0]);
    else if (typeof v === "string") out[k] = v;
  }
  return out;
}
