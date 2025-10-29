"use client";

// Simple helpers to get/set auth token and base URL in localStorage.
// Keys are namespaced to avoid collisions with other apps.

const TOKEN_KEY = "patscore.app_api_key";
const BASE_URL_KEY = "patscore.api_base_url";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function getBaseUrl(): string {
  // Prefer saved value, else env, else sensible default
  const env = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (typeof window !== "undefined") {
    const saved = window.localStorage.getItem(BASE_URL_KEY);
    if (saved) {
      // Migrate legacy default port 8003 → 8010
      if (/:8003(\b|\/?)/.test(saved)) {
        const fixed = saved.replace(":8003", ":8010");
        try {
          window.localStorage.setItem(BASE_URL_KEY, fixed);
          // eslint-disable-next-line no-console
          console.info("Updated saved API base URL from 8003 to:", fixed);
        } catch {}
        return fixed;
      }
      return saved;
    }
  }
  return env || "http://127.0.0.1:8010";
}

export function setBaseUrl(url: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(BASE_URL_KEY, url);
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
}

export const storageKeys = { TOKEN_KEY, BASE_URL_KEY } as const;
