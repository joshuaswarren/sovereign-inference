// Where the SPA finds its backend, and how it authenticates to the admin API.
//
// Served same-origin by the SIN node (`sin serve`), API_BASE is "" and requests
// are relative. Inside the desktop app the SPA loads from tauri://localhost and
// talks to the app server cross-origin, so the desktop shell injects
// `window.__SOVEREIGN__ = { apiBase, token }` before the bundle runs.

interface SovereignGlobal {
  apiBase?: string;
  token?: string;
}

declare global {
  interface Window {
    __SOVEREIGN__?: SovereignGlobal;
  }
}

const injected: SovereignGlobal = (typeof window !== "undefined" && window.__SOVEREIGN__) || {};

export const API_BASE: string = injected.apiBase ?? "";
export const ADMIN_TOKEN: string = injected.token ?? "";

/** Headers for an `/api/*` request: JSON plus the admin token when present. */
export function apiHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { Accept: "application/json", ...extra };
  if (ADMIN_TOKEN) {
    headers["X-Sovereign-Token"] = ADMIN_TOKEN;
  }
  return headers;
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
