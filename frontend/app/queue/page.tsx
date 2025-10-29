"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface QueueItem {
  patentId: string;
  abstractSha1: string;
  title: string | null;
  abstract: string | null;
  pubDate: string | null;
  source: string | null;
  status: string;
  enqueuedAt: string;
  score: string | null; // High | Medium | Low | null
}

interface Stats {
  queue: {
    pending: number;
    scored: number;
    total: number;
  };
  scores: {
    total: number;
  };
}

export default function QueuePage() {
  const router = useRouter();
  const [queueItems, setQueueItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [selectedItems, setSelectedItems] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [pageSize] = useState(50);

  // Resolve API config with sensible defaults:
  // 1) Use NEXT_PUBLIC_* env vars when available
  // 2) Allow runtime override via localStorage keys
  // 3) Fallback to a known-good local default
  const defaultApiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8010";
  const defaultApiKey = process.env.NEXT_PUBLIC_API_KEY || "";

  // Migrate any stale localStorage base URL pointing at the old 8003 port → 8010
  const apiBaseUrl =
    typeof window !== "undefined"
      ? (() => {
          const stored = localStorage.getItem("patscore.api_base_url");
          if (stored && /:8003(\b|\/?)/.test(stored)) {
            const fixed = stored.replace(":8003", ":8010");
            try {
              localStorage.setItem("patscore.api_base_url", fixed);
              // eslint-disable-next-line no-console
              console.info("Updated saved API base URL from 8003 to:", fixed);
            } catch {}
            return fixed;
          }
          return stored || defaultApiBaseUrl;
        })()
      : defaultApiBaseUrl;
  const apiKey =
    typeof window !== "undefined"
      ? localStorage.getItem("patscore.app_api_key") || defaultApiKey
      : defaultApiKey;

  const fetchQueue = async (page: number = 1) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/queue?page=${page}&page_size=${pageSize}`, {
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
      });
      if (!res.ok) {
        throw new Error(`Failed to fetch queue: ${res.statusText}`);
      }
      const data = await res.json();
      setQueueItems(data.items || []);
      setTotalItems(data.total || 0);
      setCurrentPage(page);
    } catch (err: any) {
      setError(err.message || "Failed to load queue");
      console.error("Queue fetch error:", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/api/stats`, {
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
      });
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (err) {
      console.error("Failed to fetch stats:", err);
    }
  };

  useEffect(() => {
    if (apiKey) {
      fetchQueue();
      fetchStats();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleProcessBatch = async () => {
    if (!confirm("Process all pending items in the queue?")) return;

    setProcessing(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/queue/process-batch`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
      });
      if (!res.ok) {
        throw new Error(`Process failed: ${res.statusText}`);
      }
      const result = await res.json();
      alert(`Processed ${result.processed || 0} items successfully`);
      await fetchQueue();
      await fetchStats();
    } catch (err: any) {
      setError(err.message || "Failed to process batch");
      console.error("Process batch error:", err);
    } finally {
      setProcessing(false);
    }
  };

  const handleSyncToAirtable = async () => {
    if (selectedItems.size === 0) {
      alert("Please select items to sync to Airtable");
      return;
    }

    if (!confirm(`Sync ${selectedItems.size} selected item(s) to Airtable?`)) return;

    setSyncing(true);
    setError(null);
    try {
      const res = await fetch(`${apiBaseUrl}/api/sync-airtable`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          patent_ids: Array.from(selectedItems),
        }),
      });
      if (!res.ok) {
        const errorText = await res.text();
        throw new Error(`Sync failed (${res.status}): ${errorText}`);
      }
      const result = await res.json();
      
      // Build detailed message
      const detailMsg = `✓ Synced: ${result.synced || 0}\n✗ Errors: ${result.errors || 0}\n○ Skipped: ${result.skipped || 0}\n− Removed Low: ${result.removed || 0}`;
      alert(`${result.message}\n\n${detailMsg}`);
      
      console.log("Sync result:", result);
      
      setSelectedItems(new Set()); // Clear selections after sync
      await fetchQueue(currentPage);
      await fetchStats();
    } catch (err: any) {
      const errMsg = err.message || "Failed to sync to Airtable";
      setError(errMsg);
      alert(`Sync error:\n${errMsg}`);
      console.error("Airtable sync error:", err);
    } finally {
      setSyncing(false);
    }
  };

  const handleRefresh = () => {
    fetchQueue();
    fetchStats();
  };

  const toggleSelectItem = (id: string) => {
    const newSelected = new Set(selectedItems);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedItems(newSelected);
  };

  const toggleSelectAll = () => {
    if (selectedItems.size === queueItems.length) {
      setSelectedItems(new Set());
    } else {
      setSelectedItems(new Set(queueItems.map((item) => item.patentId)));
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: "bg-yellow-100 text-yellow-800",
      scored: "bg-green-100 text-green-800",
      synced: "bg-blue-100 text-blue-800",
      failed: "bg-red-100 text-red-800",
    };
    return colors[status] || "bg-gray-100 text-gray-800";
  };

  const getScoreColor = (score: string | null) => {
    if (score === null) return "text-gray-400";
    if (score === "High") return "text-green-600 font-semibold";
    if (score === "Medium") return "text-yellow-600 font-semibold";
    if (score === "Low") return "text-red-600";
    return "text-gray-400";
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading queue...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Patent Queue</h1>
            <p className="mt-2 text-gray-600">
              Manage and process queued patents for scoring and Airtable sync
            </p>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-600">Records Displayed</div>
            <div className="text-4xl font-bold text-blue-600">{queueItems.length}</div>
          </div>
        </div>

        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Total in Queue</div>
              <div className="text-2xl font-bold text-gray-900">{stats.queue.total}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Pending</div>
              <div className="text-2xl font-bold text-yellow-600">{stats.queue.pending}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Scored</div>
              <div className="text-2xl font-bold text-green-600">{stats.queue.scored}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Total Scores</div>
              <div className="text-2xl font-bold text-blue-600">{stats.scores.total}</div>
            </div>
          </div>
        )}

        <div className="mb-6 flex flex-wrap gap-3">
          <button
            onClick={handleRefresh}
            disabled={loading}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            🔄 Refresh
          </button>
          <button
            onClick={handleProcessBatch}
            disabled={processing || (stats?.queue.pending ?? 0) === 0}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {processing ? "⏳ Processing..." : "⚙️ Process Batch"}
          </button>
          <button
            onClick={handleSyncToAirtable}
            disabled={syncing || selectedItems.size === 0}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {syncing ? "⏳ Syncing..." : `📤 Sync to Airtable${selectedItems.size > 0 ? ` (${selectedItems.size})` : ""}`}
          </button>
          <button
            onClick={() => router.push("/ingest")}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            📥 Back to Ingest
          </button>
        </div>

        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start">
              <span className="text-red-600 mr-2">⚠️</span>
              <div className="flex-1">
                <h3 className="text-red-900 font-semibold">Error</h3>
                <p className="text-red-700 text-sm mt-1">{error}</p>
              </div>
              <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600">✕</button>
            </div>
          </div>
        )}

        {queueItems.length === 0 ? (
          <div className="bg-white rounded-lg shadow p-12 text-center">
            <div className="text-6xl mb-4">📋</div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">Queue is Empty</h2>
            <p className="text-gray-600 mb-6">No patents in the queue. Upload and ingest files to add items.</p>
            <button
              onClick={() => router.push("/ingest")}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Go to Ingest Page
            </button>
          </div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left">
                      <input
                        type="checkbox"
                        checked={selectedItems.size === queueItems.length && queueItems.length > 0}
                        onChange={toggleSelectAll}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Patent ID</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Score</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {queueItems.map((item) => (
                    <tr key={item.patentId} className={`hover:bg-gray-50 ${selectedItems.has(item.patentId) ? "bg-blue-50" : ""}`}>
                      <td className="px-4 py-4">
                        <input
                          type="checkbox"
                          checked={selectedItems.has(item.patentId)}
                          onChange={() => toggleSelectItem(item.patentId)}
                          className="rounded border-gray-300"
                        />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">{item.patentId}</div>
                        <div className="text-xs text-gray-500">SHA1: {item.abstractSha1.substring(0, 8)}...</div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm text-gray-900 max-w-md truncate">{item.title || "No title"}</div>
                        {item.abstract && (
                          <div className="text-xs text-gray-500 max-w-md truncate mt-1">{item.abstract.substring(0, 100)}...</div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadge(item.status)}`}>
                          {item.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className={`text-sm ${getScoreColor(item.score)}`}>{item.score ?? "—"}</div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {new Date(item.enqueuedAt).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            {/* Pagination Controls */}
            {totalItems > pageSize && (
              <div className="bg-gray-50 px-4 py-3 flex items-center justify-between border-t border-gray-200">
                <div className="flex-1 flex justify-between sm:hidden">
                  <button
                    onClick={() => fetchQueue(currentPage - 1)}
                    disabled={currentPage === 1}
                    className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => fetchQueue(currentPage + 1)}
                    disabled={currentPage * pageSize >= totalItems}
                    className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
                <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm text-gray-700">
                      Showing <span className="font-medium">{(currentPage - 1) * pageSize + 1}</span> to{" "}
                      <span className="font-medium">{Math.min(currentPage * pageSize, totalItems)}</span> of{" "}
                      <span className="font-medium">{totalItems}</span> results
                    </p>
                  </div>
                  <div>
                    <nav className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px" aria-label="Pagination">
                      <button
                        onClick={() => fetchQueue(currentPage - 1)}
                        disabled={currentPage === 1}
                        className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="sr-only">Previous</span>
                        <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z" clipRule="evenodd" />
                        </svg>
                      </button>
                      
                      {/* Page numbers */}
                      {Array.from({ length: Math.ceil(totalItems / pageSize) }, (_, i) => i + 1)
                        .filter(page => {
                          // Show first page, last page, current page, and pages around current
                          const totalPages = Math.ceil(totalItems / pageSize);
                          return (
                            page === 1 ||
                            page === totalPages ||
                            Math.abs(page - currentPage) <= 1
                          );
                        })
                        .map((page, idx, arr) => {
                          // Add ellipsis if there's a gap
                          const showEllipsisBefore = idx > 0 && page - arr[idx - 1] > 1;
                          return (
                            <React.Fragment key={`page-${page}`}>
                              {showEllipsisBefore && (
                                <span className="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">
                                  ...
                                </span>
                              )}
                              <button
                                onClick={() => fetchQueue(page)}
                                className={`relative inline-flex items-center px-4 py-2 border text-sm font-medium ${
                                  page === currentPage
                                    ? "z-10 bg-blue-50 border-blue-500 text-blue-600"
                                    : "bg-white border-gray-300 text-gray-500 hover:bg-gray-50"
                                }`}
                              >
                                {page}
                              </button>
                            </React.Fragment>
                          );
                        })}
                      
                      <button
                        onClick={() => fetchQueue(currentPage + 1)}
                        disabled={currentPage * pageSize >= totalItems}
                        className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <span className="sr-only">Next</span>
                        <svg className="h-5 w-5" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
                        </svg>
                      </button>
                    </nav>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {selectedItems.size > 0 && (
          <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-blue-900">
              <strong>{selectedItems.size}</strong> item(s) selected
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
