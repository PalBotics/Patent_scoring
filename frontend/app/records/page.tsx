"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, ListRecordsResponse, RecordSummary } from "@/lib/api";

const PAGE_SIZE = 25;

export default function RecordsPage() {
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");

  const page = useMemo(() => Math.floor(offset / PAGE_SIZE) + 1, [offset]);
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      const query = `/api/v1/records?limit=${PAGE_SIZE}&offset=${offset}`;
      const res = await api.get<ListRecordsResponse>(query);
      if (!cancelled) {
        if (res.ok) {
          setRecords(res.data.records);
          setTotal(res.data.total);
        } else {
          setError(res.error);
        }
        setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [offset]);

  function nextPage() {
    if (offset + PAGE_SIZE < total) setOffset(offset + PAGE_SIZE);
  }
  function prevPage() {
    setOffset(Math.max(0, offset - PAGE_SIZE));
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Records</h1>
      <div className="flex items-center gap-2 text-sm">
        <button onClick={prevPage} disabled={offset === 0} className="rounded border px-3 py-1 disabled:opacity-50">Prev</button>
        <button onClick={nextPage} disabled={offset + PAGE_SIZE >= total} className="rounded border px-3 py-1 disabled:opacity-50">Next</button>
        <span>
          Page {page} of {totalPages} • Total {total}
        </span>
      </div>

      {loading && <div>Loading…</div>}
      {error && <div className="text-red-600">{error}</div>}

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2 pr-4">Patent ID</th>
              <th className="py-2 pr-4">Title</th>
              <th className="py-2 pr-4">Relevance</th>
              <th className="py-2 pr-4">Updated</th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => {
              const patentId = (r as any).patentId ?? (r as any).patent_id ?? "";
              const updated = (r as any).updated_at ?? (r as any).updatedAt ?? "";
              return (
              <tr key={r.id} className="border-b align-top">
                <td className="py-2 pr-4 whitespace-nowrap">{patentId}</td>
                <td className="py-2 pr-4">
                  <Link href={`/records/${r.id}`} className="font-medium text-blue-600 dark:text-blue-400 hover:underline">
                    {r.title}
                  </Link>
                  <div className="text-zinc-500 dark:text-zinc-400 line-clamp-2 max-w-xl">{r.abstract}</div>
                </td>
                <td className="py-2 pr-4">{r.relevance ?? "-"}</td>
                <td className="py-2 pr-4 whitespace-nowrap">{updated}</td>
              </tr>
            );})}
            {!loading && records.length === 0 && (
              <tr>
                <td className="py-4 text-zinc-500" colSpan={4}>No records found.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
