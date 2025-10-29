"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

interface IngestJob {
  jobId: number;
  filename: string;
  status: string;
  matchedCount: number;
  enqueuedCount: number;
  csvUrl: string | null;
  log: string;
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

export default function IngestPage() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentJob, setCurrentJob] = useState<IngestJob | null>(null);
  const [polling, setPolling] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [processingProgress, setProcessingProgress] = useState(0);
  const [processingMessage, setProcessingMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);

  // Resolve API config with env defaults and migrate old 8003 URL → 8010
  const defaultApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8010";
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
      ? localStorage.getItem("patscore.app_api_key") || ""
      : "";

  // Fetch stats on mount and when job completes
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
      fetchStats();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll job status when job is in progress
  useEffect(() => {
    if (!currentJob || currentJob.status === "completed" || currentJob.status === "failed") {
      setPolling(false);
      return;
    }

    setPolling(true);
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${apiBaseUrl}/api/ingest/${currentJob.jobId}`, {
          headers: {
            Authorization: `Bearer ${apiKey}`,
          },
        });
        if (res.ok) {
          const updated = await res.json();
          setCurrentJob(updated);
          if (updated.status === "completed" || updated.status === "failed") {
            setPolling(false);
            clearInterval(interval);
          }
        }
      } catch (err) {
        console.error("Poll error:", err);
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [currentJob, apiBaseUrl, apiKey]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file");
      return;
    }

    setUploading(true);
    setUploadProgress(0);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      // Use XMLHttpRequest to track upload progress
      const xhr = new XMLHttpRequest();

      // Track upload progress
      xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
          const percentComplete = Math.round((e.loaded / e.total) * 100);
          setUploadProgress(percentComplete);
        }
      });

      // Handle completion
      const uploadPromise = new Promise<IngestJob>((resolve, reject) => {
        xhr.addEventListener("load", () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            try {
              const job = JSON.parse(xhr.responseText);
              resolve(job);
            } catch (e) {
              reject(new Error("Failed to parse response"));
            }
          } else {
            try {
              const errData = JSON.parse(xhr.responseText);
              reject(new Error(errData.detail || "Upload failed"));
            } catch (e) {
              reject(new Error("Upload failed"));
            }
          }
        });

        xhr.addEventListener("error", () => {
          reject(new Error("Network error"));
        });

        xhr.open("POST", `${apiBaseUrl}/api/ingest`);
        xhr.setRequestHeader("Authorization", `Bearer ${apiKey}`);
        xhr.send(formData);
      });

      const job = await uploadPromise;
      setCurrentJob(job);
      setFile(null);
      setUploadProgress(100);
      await fetchStats(); // Refresh stats after upload
      
      // Reset file input
      const fileInput = document.getElementById("file-input") as HTMLInputElement;
      if (fileInput) fileInput.value = "";
    } catch (err: any) {
      setError(err.message || "Upload failed");
      setUploadProgress(0);
    } finally {
      setUploading(false);
    }
  };

  const handleProcessBatch = async () => {
    if (!currentJob || currentJob.enqueuedCount === 0) {
      setError("No items in queue to process");
      return;
    }

    setProcessing(true);
    setProcessingProgress(0);
    setProcessingMessage("Starting batch processing...");
    setError(null);

    try {
      const batchSize = 10;
      setProcessingMessage(`Processing batch of ${batchSize} patents...`);
      
      const res = await fetch(
        `${apiBaseUrl}/api/queue/process-batch?batch_size=${batchSize}&mode=keyword&min_relevance=Medium`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
          },
        }
      );

      if (res.ok) {
        const result = await res.json();
        setProcessingProgress(100);
        setProcessingMessage(result.message || "Batch processing completed!");
        await fetchStats(); // Refresh stats
        setTimeout(() => {
          setProcessing(false);
          setProcessingProgress(0);
          setProcessingMessage("");
        }, 2000);
      } else {
        const errData = await res.json().catch(() => ({ detail: "Processing failed" }));
        setError(errData.detail || "Processing failed");
        setProcessing(false);
      }
    } catch (err: any) {
      setError(err.message || "Processing failed");
      setProcessing(false);
    }
  };

  const handleProcessAll = async () => {
    if (!currentJob || currentJob.enqueuedCount === 0) {
      setError("No items in queue to process");
      return;
    }

    setProcessing(true);
    setProcessingProgress(0);
    setProcessingMessage("Starting to process all patents...");
    setError(null);

    try {
      const totalCount = currentJob.enqueuedCount;
      const batchSize = 10;
      const estimatedBatches = Math.ceil(totalCount / batchSize);
      
      setProcessingMessage(`Processing all ${totalCount} patents in batches of ${batchSize}...`);
      
      // Simulate progress updates
      const progressInterval = setInterval(() => {
        setProcessingProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + 10;
        });
      }, 1000);

      const res = await fetch(
        `${apiBaseUrl}/api/queue/process-all?mode=keyword&min_relevance=Medium&batch_size=${batchSize}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
          },
        }
      );

      clearInterval(progressInterval);

      if (res.ok) {
        const result = await res.json();
        setProcessingProgress(100);
        setProcessingMessage(result.message || "All patents processed successfully!");
        await fetchStats(); // Refresh stats
        setTimeout(() => {
          setProcessing(false);
          setProcessingProgress(0);
          setProcessingMessage("");
        }, 3000);
      } else {
        const errData = await res.json().catch(() => ({ detail: "Processing failed" }));
        setError(errData.detail || "Processing failed");
        setProcessing(false);
      }
    } catch (err: any) {
      setError(err.message || "Processing failed");
      setProcessing(false);
    }
  };

  const handleSyncAirtable = async () => {
    setProcessing(true);
    setProcessingProgress(0);
    setProcessingMessage("Syncing to Airtable...");
    setError(null);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProcessingProgress((prev) => {
          if (prev >= 90) return prev;
          return prev + 15;
        });
      }, 500);

      const res = await fetch(`${apiBaseUrl}/api/sync-airtable?min_relevance=Medium`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
      });

      clearInterval(progressInterval);

      if (res.ok) {
        const result = await res.json();
        setProcessingProgress(100);
        setProcessingMessage(result.message || "Airtable sync completed!");
        await fetchStats(); // Refresh stats
        setTimeout(() => {
          setProcessing(false);
          setProcessingProgress(0);
          setProcessingMessage("");
        }, 2000);
      } else {
        const errData = await res.json().catch(() => ({ detail: "Sync failed" }));
        setError(errData.detail || "Sync failed");
        setProcessing(false);
      }
    } catch (err: any) {
      setError(err.message || "Sync failed");
      setProcessing(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            USPTO File Ingest
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mt-2">
            Upload CSV or XML files from USPTO to parse, deduplicate, and queue for scoring
          </p>
        </div>

        {/* Stats Display */}
        {stats && (
          <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              System Stats
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                  {stats.queue.pending}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Pending in Queue
                </div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                  {stats.queue.scored}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Scored in Queue
                </div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-purple-600 dark:text-purple-400">
                  {stats.queue.total}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Total in Queue
                </div>
              </div>
              <div className="text-center">
                <div className="text-3xl font-bold text-indigo-600 dark:text-indigo-400">
                  {stats.scores.total}
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Total Scores
                </div>
              </div>
            </div>
          </div>
        )}

        {/* File Upload Section */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Upload File
          </h2>
          <div className="space-y-4">
            <div>
              <label
                htmlFor="file-input"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                Select USPTO File (.csv, .xml, .gz, .zip)
              </label>
              <input
                id="file-input"
                type="file"
                accept=".csv,.xml,.gz,.zip"
                onChange={handleFileChange}
                disabled={uploading || polling}
                className="block w-full text-sm text-gray-900 dark:text-gray-100
                  file:mr-4 file:py-2 file:px-4
                  file:rounded-md file:border-0
                  file:text-sm file:font-semibold
                  file:bg-blue-50 file:text-blue-700
                  hover:file:bg-blue-100
                  dark:file:bg-blue-900 dark:file:text-blue-200
                  dark:hover:file:bg-blue-800
                  disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>

            {file && (
              <div className="text-sm text-gray-600 dark:text-gray-400">
                Selected: <span className="font-medium">{file.name}</span> ({(file.size / 1024).toFixed(1)} KB)
              </div>
            )}

            {/* Upload Progress Bar */}
            {uploading && (
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
                  <span>Uploading...</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  ></div>
                </div>
              </div>
            )}

            <button
              onClick={handleUpload}
              disabled={!file || uploading || polling}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded-md
                hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed
                font-medium transition-colors"
            >
              {uploading ? `Uploading... ${uploadProgress}%` : "Upload & Parse"}
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-6">
            <p className="text-red-800 dark:text-red-200 text-sm">{error}</p>
          </div>
        )}

        {/* Job Status Section */}
        {currentJob && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Job Status
            </h2>

            {/* Processing Progress Indicator */}
            {currentJob.status === "pending" || currentJob.status === "running" ? (
              <div className="mb-4">
                <div className="flex items-center space-x-3 mb-2">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">
                    Processing file...
                  </span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: "70%" }}></div>
                </div>
              </div>
            ) : null}

            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  File:
                </span>
                <span className="text-sm text-gray-900 dark:text-gray-100">
                  {currentJob.filename}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Status:
                </span>
                <span
                  className={`text-sm font-semibold px-2 py-1 rounded ${
                    currentJob.status === "completed"
                      ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
                      : currentJob.status === "failed"
                      ? "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200"
                      : "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
                  }`}
                >
                  {currentJob.status}
                  {polling && " (polling...)"}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Already Scored:
                </span>
                <span className="text-sm text-gray-900 dark:text-gray-100">
                  {currentJob.matchedCount}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Enqueued for Scoring:
                </span>
                <span className="text-sm text-gray-900 dark:text-gray-100 font-semibold">
                  {currentJob.enqueuedCount}
                </span>
              </div>

              {currentJob.log && (
                <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-900 rounded border border-gray-200 dark:border-gray-700">
                  <p className="text-xs font-mono text-gray-700 dark:text-gray-300">
                    {currentJob.log}
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Processing Progress */}
        {processing && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6 mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Processing
            </h2>
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-green-600"></div>
                <span className="text-sm text-gray-600 dark:text-gray-400">
                  {processingMessage}
                </span>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm text-gray-600 dark:text-gray-400">
                  <span>Progress</span>
                  <span>{processingProgress}%</span>
                </div>
                <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2.5">
                  <div
                    className="bg-green-600 h-2.5 rounded-full transition-all duration-500"
                    style={{ width: `${processingProgress}%` }}
                  ></div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Action Buttons - Always visible if stats show items in queue or if we have a job */}
        {((stats && (stats.queue.total > 0 || stats.scores.total > 0)) || currentJob) && (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
              Actions
            </h2>
            {stats && (
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                {stats.queue.pending > 0 
                  ? `${stats.queue.pending} patent${stats.queue.pending !== 1 ? 's' : ''} pending scoring` 
                  : stats.queue.scored > 0 
                    ? `${stats.queue.scored} patent${stats.queue.scored !== 1 ? 's' : ''} scored and ready to sync`
                    : `${stats.scores.total} patent${stats.scores.total !== 1 ? 's' : ''} in database`}
              </p>
            )}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <button
                onClick={handleProcessBatch}
                disabled={processing || (stats ? stats.queue.pending === 0 : true)}
                className="px-4 py-3 bg-green-600 text-white rounded-md
                  hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed
                  font-medium transition-colors"
              >
                Process Batch (10)
              </button>

              <button
                onClick={handleProcessAll}
                disabled={processing || (stats ? stats.queue.pending === 0 : true)}
                className="px-4 py-3 bg-purple-600 text-white rounded-md
                  hover:bg-purple-700 disabled:bg-gray-400 disabled:cursor-not-allowed
                  font-medium transition-colors"
              >
                Process All
              </button>

              <button
                onClick={handleSyncAirtable}
                disabled={processing || (stats ? stats.scores.total === 0 : false)}
                className="px-4 py-3 bg-indigo-600 text-white rounded-md
                  hover:bg-indigo-700 disabled:bg-gray-400 disabled:cursor-not-allowed
                  font-medium transition-colors"
              >
                Sync to Airtable
              </button>
            </div>

            <div className="mt-4 space-y-2">
              <button
                onClick={() => router.push("/queue")}
                className="w-full px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100
                  rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 font-medium transition-colors"
              >
                View Queue →
              </button>
              <button
                onClick={() => router.push("/scores")}
                className="w-full px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-gray-100
                  rounded-md hover:bg-gray-300 dark:hover:bg-gray-600 font-medium transition-colors"
              >
                View Scores →
              </button>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="mt-6 bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-blue-900 dark:text-blue-200 mb-2">
            How it works:
          </h3>
          <ol className="text-sm text-blue-800 dark:text-blue-300 space-y-1 list-decimal list-inside">
            <li>Upload a USPTO CSV or XML file</li>
            <li>The system parses and checks for duplicates against the master DB</li>
            <li>New patents are added to the scoring queue</li>
            <li>Process the queue with keyword or LLM scoring</li>
            <li>Medium/High relevance patents are stored and can be synced to Airtable</li>
          </ol>
        </div>
      </div>
    </div>
  );
}
