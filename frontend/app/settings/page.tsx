"use client";

import { useEffect, useMemo, useState } from "react";
import { api, HealthResponse, SettingsResponse } from "@/lib/api";
import { getBaseUrl, setBaseUrl, getToken, setToken, storageKeys } from "@/lib/auth";

export default function SettingsPage() {
  const [baseUrl, setBaseUrlState] = useState<string>(getBaseUrl());
  const [token, setTokenState] = useState<string>(getToken() || "");
  const [saving, setSaving] = useState(false);
  const [health, setHealth] = useState<string>("");
  const [settings, setSettings] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    // Attempt an initial health check on mount with current values
    void runChecks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function runChecks() {
    setError("");
    const h = await api.get<HealthResponse>("/api/v1/health");
    setHealth(h.ok ? JSON.stringify(h.data) : `Error: ${h.error}`);
    const s = await api.get<SettingsResponse>("/api/settings");
    setSettings(s.ok ? JSON.stringify(s.data) : `Error: ${s.error}`);
  }

  async function saveAll(e: React.FormEvent) {
    e.preventDefault();
    try {
      setSaving(true);
      setBaseUrl(baseUrl);
      setToken(token);
      await runChecks();
    } catch (err: any) {
      setError(err?.message || "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  const hint = useMemo(
    () => `Values saved in localStorage keys: ${storageKeys.BASE_URL_KEY} and ${storageKeys.TOKEN_KEY}`,
    []
  );

  return (
    <div className="mx-auto max-w-2xl p-6">
      <h1 className="text-2xl font-semibold mb-4">Settings</h1>
      <form onSubmit={saveAll} className="space-y-4">
        <div>
          <label className="block text-sm font-medium">API Base URL</label>
          <input
            className="mt-1 w-full rounded border px-3 py-2 text-black"
            value={baseUrl}
            onChange={(e) => setBaseUrlState(e.target.value)}
            placeholder="http://127.0.0.1:8003"
          />
        </div>
        <div>
          <label className="block text-sm font-medium">APP_API_KEY</label>
          <input
            className="mt-1 w-full rounded border px-3 py-2 text-black"
            value={token}
            onChange={(e) => setTokenState(e.target.value)}
            placeholder="patscore-..."
          />
        </div>
        <div className="text-xs text-zinc-500">{hint}</div>
        <button
          type="submit"
          className="rounded bg-black text-white px-4 py-2 disabled:opacity-50"
          disabled={saving}
        >
          {saving ? "Saving..." : "Save & Test"}
        </button>
      </form>

      <div className="mt-8 grid gap-4">
        <div>
          <h2 className="font-medium">Health</h2>
          <pre className="mt-1 whitespace-pre-wrap rounded bg-zinc-100 p-3 text-sm text-black">{health}</pre>
        </div>
        <div>
          <h2 className="font-medium">Settings (requires token)</h2>
          <pre className="mt-1 whitespace-pre-wrap rounded bg-zinc-100 p-3 text-sm text-black">{settings}</pre>
        </div>
        {error && (
          <div className="text-red-600">{error}</div>
        )}
      </div>
    </div>
  );
}
