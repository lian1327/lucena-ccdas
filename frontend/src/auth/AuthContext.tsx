import { useQueryClient } from "@tanstack/react-query";
import { jwtDecode } from "jwt-decode";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, refreshAccessToken } from "@/api/client";
import type { JwtClaims, Me, Role } from "@/api/types";
import { STAFF_ROLES } from "@/api/types";

import { tokenStore } from "./tokens";

type Status = "loading" | "authenticated" | "anonymous";

type AuthContextValue = {
  status: Status;
  user: Me | null;
  login: (username: string, password: string) => Promise<Me>;
  logout: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
  isStaff: boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchMe(): Promise<Me> {
  return (await api.get<Me>("/auth/me/")).data;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>("loading");
  const [user, setUser] = useState<Me | null>(null);

  const reset = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    setStatus("anonymous");
    queryClient.removeQueries({ predicate: (q) => q.queryKey[0] !== "public" });
  }, [queryClient]);

  // Restore session from the refresh token on first load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const access = await refreshAccessToken();
      if (!access) {
        if (!cancelled) setStatus("anonymous");
        return;
      }
      try {
        const me = await fetchMe();
        if (!cancelled) {
          setUser(me);
          setStatus("authenticated");
        }
      } catch {
        if (!cancelled) reset();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reset]);

  // Refresh token expired mid-session → drop to anonymous.
  useEffect(() => tokenStore.onLogout(reset), [reset]);

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await api.post<{ access: string; refresh: string }>("/auth/token/", { username, password });
    tokenStore.set(data.access, data.refresh);
    jwtDecode<JwtClaims>(data.access); // throws early if the server sent something unexpected
    const me = await fetchMe();
    setUser(me);
    setStatus("authenticated");
    return me;
  }, []);

  const logout = useCallback(async () => {
    const refresh = tokenStore.refresh;
    if (refresh) {
      await api.post("/auth/logout/", { refresh }).catch(() => undefined);
    }
    reset();
  }, [reset]);

  const value = useMemo<AuthContextValue>(() => {
    const hasRole = (...roles: Role[]) => !!user && roles.includes(user.role as Role);
    return { status, user, login, logout, hasRole, isStaff: hasRole(...STAFF_ROLES) };
  }, [status, user, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Where to send a user right after login. */
export function homeFor(user: Me): string {
  return STAFF_ROLES.includes(user.role as Role) ? "/staff" : "/";
}
