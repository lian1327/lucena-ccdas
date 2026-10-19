/**
 * Access token: memory only (not readable after a page reload, smaller XSS window).
 * Refresh token: localStorage, so the session survives reloads.
 * For production, move the refresh token to an httpOnly cookie.
 */
const REFRESH_KEY = "ccadss.refresh";

let accessToken: string | null = null;
const logoutListeners = new Set<() => void>();

function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

export const tokenStore = {
  get access(): string | null {
    return accessToken;
  },
  get refresh(): string | null {
    return safeGet(REFRESH_KEY);
  },
  set(access: string, refresh?: string) {
    accessToken = access;
    if (refresh) {
      try {
        localStorage.setItem(REFRESH_KEY, refresh);
      } catch {
        /* storage unavailable: session lasts until reload */
      }
    }
  },
  clear() {
    accessToken = null;
    try {
      localStorage.removeItem(REFRESH_KEY);
    } catch {
      /* ignore */
    }
  },
  onLogout(fn: () => void) {
    logoutListeners.add(fn);
    return () => {
      logoutListeners.delete(fn);
    };
  },
  notifyLoggedOut() {
    logoutListeners.forEach((fn) => fn());
  },
};
