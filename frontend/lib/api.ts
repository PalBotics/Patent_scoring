"use client";

import { getBaseUrl, getToken } from "./auth";

export type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string; status?: number };

async function request<T>(path: string, init: RequestInit = {}): Promise<ApiResult<T>> {
  const base = getBaseUrl().replace(/\/$/, "");
  const url = `${base}${path.startsWith("/") ? path : "/" + path}`;

  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  try {
    const res = await fetch(url, { ...init, headers, cache: "no-store" });
    const contentType = res.headers.get("content-type") || "";
    const isJson = contentType.includes("application/json");
    const body = isJson ? await res.json() : await res.text();
    if (!res.ok) {
      const msg = typeof body === "string" ? body : body?.detail || JSON.stringify(body);
      return { ok: false, error: msg || `HTTP ${res.status}`, status: res.status };
    }
    return { ok: true, data: body as T };
  } catch (e: any) {
    return { ok: false, error: e?.message || "Network error" };
  }
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
};

export type HealthResponse = { status: string };
export type SettingsResponse = { apiKeyConfigured: boolean; airtableConfigured?: boolean };

// Records types (aligned with backend schemas)
export type RecordSummary = {
  id: string;
  patent_id: string;
  title: string;
  abstract: string;
  relevance?: string | null;
  score?: number;
  subsystem?: string[];
  sha1?: string;
  updated_at?: string;
};

export type ListRecordsResponse = {
  total: number;
  offset: number;
  limit: number;
  records: RecordSummary[];
};

export type RecordDetail = RecordSummary; // Same structure for now
