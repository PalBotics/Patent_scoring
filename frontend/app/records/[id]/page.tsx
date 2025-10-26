"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, RecordDetail } from "@/lib/api";

export default function RecordDetailPage() {
  const params = useParams();
  const id = params?.id as string;

  const [record, setRecord] = useState<RecordDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!id) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError("");
      const res = await api.get<RecordDetail>(`/api/v1/records/${id}`);
      if (!cancelled) {
        if (res.ok) {
          setRecord(res.data);
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
  }, [id]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Link href="/records" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
          ← Back to Records
        </Link>
        <div>Loading record...</div>
      </div>
    );
  }

  if (error || !record) {
    return (
      <div className="space-y-4">
        <Link href="/records" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
          ← Back to Records
        </Link>
        <div className="text-red-600 dark:text-red-400">{error || "Record not found"}</div>
      </div>
    );
  }

  const patentId = (record as any).patentId ?? (record as any).patent_id ?? "";
  const updated = (record as any).updated_at ?? (record as any).updatedAt ?? "";

  return (
    <div className="space-y-4">
      <Link href="/records" className="text-sm text-blue-600 dark:text-blue-400 hover:underline">
        ← Back to Records
      </Link>

      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">{record.title}</h1>
          <div className="mt-2 text-sm text-zinc-500 dark:text-zinc-400">
            Patent ID: {patentId}
          </div>
        </div>

        <div className="grid gap-4">
          <div>
            <div className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Abstract</div>
            <p className="mt-1 text-zinc-900 dark:text-zinc-100 whitespace-pre-wrap">{record.abstract}</p>
          </div>

          {record.relevance && (
            <div>
              <div className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Relevance</div>
              <div className="mt-1">{record.relevance}</div>
            </div>
          )}

          {record.subsystem && record.subsystem.length > 0 && (
            <div>
              <div className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Subsystem</div>
              <div className="mt-1 flex flex-wrap gap-2">
                {record.subsystem.map((s, i) => (
                  <span key={i} className="rounded bg-zinc-200 dark:bg-zinc-700 px-2 py-1 text-sm">
                    {s}
                  </span>
                ))}
              </div>
            </div>
          )}

          {updated && (
            <div>
              <div className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Updated</div>
              <div className="mt-1 text-sm">{updated}</div>
            </div>
          )}

          {record.sha1 && (
            <div>
              <div className="text-sm font-medium text-zinc-700 dark:text-zinc-300">SHA1</div>
              <div className="mt-1 font-mono text-xs text-zinc-600 dark:text-zinc-400">{record.sha1}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
