"use client";

import { useCallback, useEffect, useState } from "react";
import { getJobs, getSettings, triggerDiscovery, getDiscoveryStatus, resetAllJobs } from "@/lib/api";
import { JobCard } from "@/components/JobCard";
import { SSEListener } from "@/components/SSEListener";
import type { Job, SSEEvent, Settings } from "@/lib/types";

const STATUS_FILTERS = [
  { label: "All", value: "" },
  { label: "Pending action", value: "pending" },
  { label: "Applied", value: "applied" },
  { label: "Archived", value: "archived" },
];

export default function DashboardPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [notifications, setNotifications] = useState<string[]>([]);
  const [discovering, setDiscovering] = useState(false);
  const [resetting, setResetting] = useState(false);

  const loadJobs = useCallback(async () => {
    const status = filter === "pending" ? undefined : filter || undefined;
    const data = await getJobs(status);
    const filtered =
      filter === "pending"
        ? data.filter((j) =>
            ["pending_triage", "pending_resume_review", "pending_apply", "pending_triage_tailor"].includes(j.status)
          )
        : data;
    setJobs(filtered);
  }, [filter]);

  useEffect(() => {
    Promise.all([loadJobs(), getSettings().then(setSettings)]).finally(() =>
      setLoading(false)
    );
  }, [loadJobs]);

  const handleReset = useCallback(async () => {
    if (!confirm("Delete all jobs and pipeline data?")) return;
    setResetting(true);
    try {
      await resetAllJobs();
      await loadJobs();
    } finally {
      setResetting(false);
    }
  }, [loadJobs]);

  const handleRunDiscovery = useCallback(async () => {
    setDiscovering(true);
    try {
      await triggerDiscovery();
      const poll = setInterval(async () => {
        const { running } = await getDiscoveryStatus();
        if (!running) {
          clearInterval(poll);
          setDiscovering(false);
          loadJobs();
          setNotifications((n) => ["Discovery complete", ...n.slice(0, 4)]);
        }
      }, 3000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      setDiscovering(false);
      setNotifications((n) => [`Discovery error: ${msg}`, ...n.slice(0, 4)]);
    }
  }, [loadJobs]);

  const handleSSEEvent = useCallback(
    (event: SSEEvent) => {
      const labels: Record<string, string> = {
        gate1_ready: "Gate 1 ready",
        gate2_ready: "Gate 2 ready",
        gate3_ready: "Gate 3 ready",
        job_applied: "Marked as Applied",
        job_archived: "Job archived",
        pipeline_error: "Pipeline error",
        tailor_skipped: "Tailor skipped",
      };
      const label = labels[event.event];
      if (label) {
        setNotifications((n) => [`${label} — ${event.job_id.slice(0, 8)}`, ...n.slice(0, 4)]);
        loadJobs();
      }
    },
    [loadJobs]
  );

  return (
    <>
      <SSEListener onEvent={handleSSEEvent} />

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Job Pipeline</h1>
            <p className="text-sm text-slate-500 mt-1">{jobs.length} jobs</p>
          </div>
          <div className="flex items-center gap-2">
            {notifications.slice(0, 1).map((n, i) => (
              <span
                key={i}
                className="inline-flex items-center px-3 py-1 rounded-full bg-brand-50 text-brand-700 text-xs border border-brand-200"
              >
                {n}
              </span>
            ))}
            <button
              onClick={handleReset}
              disabled={resetting || discovering}
              className="px-4 py-1.5 text-sm rounded-full border border-slate-200 text-slate-500 hover:border-red-300 hover:text-red-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              {resetting ? "Resetting…" : "Reset All"}
            </button>
            <button
              onClick={handleRunDiscovery}
              disabled={discovering}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 text-sm rounded-full bg-brand-500 text-white hover:bg-brand-600 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
            >
              {discovering ? (
                <>
                  <span className="inline-block w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Discovering…
                </>
              ) : (
                "Run Discovery"
              )}
            </button>
          </div>
        </div>

        <div className="flex gap-2">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setFilter(f.value)}
              className={`px-4 py-1.5 text-sm rounded-full border transition-colors ${
                filter === f.value
                  ? "bg-brand-500 text-white border-brand-500"
                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-300"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="text-slate-400 text-sm">Loading...</div>
        ) : jobs.length === 0 ? (
          <div className="text-center py-20 text-slate-400">
            <p className="text-lg">No jobs here yet.</p>
            <p className="text-sm mt-2">Hit <strong className="text-slate-600">Run Discovery</strong> above to populate the pipeline.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {jobs.map((job) => (
              <JobCard
                key={job.id}
                job={job}
                globalTailorMode={settings?.tailor_mode ?? "always_tailor"}
                onDecision={loadJobs}
              />
            ))}
          </div>
        )}
      </div>
    </>
  );
}
