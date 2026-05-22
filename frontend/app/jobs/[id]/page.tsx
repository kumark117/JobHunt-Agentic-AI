"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getJob, getResumeArtifacts, getOutreach, getSettings } from "@/lib/api";
import { PipelineStatus } from "@/components/PipelineStatus";
import { ResumeDiff } from "@/components/ResumeDiff";
import { OutreachPanel } from "@/components/OutreachPanel";
import type { Job, ResumeArtifact, OutreachArtifact, Settings } from "@/lib/types";

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [artifacts, setArtifacts] = useState<ResumeArtifact[]>([]);
  const [outreach, setOutreach] = useState<OutreachArtifact | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = async () => {
    const [j, arts, cfg] = await Promise.all([
      getJob(id),
      getResumeArtifacts(id).catch(() => []),
      getSettings().catch(() => null),
    ]);
    setJob(j);
    setArtifacts(arts);
    setSettings(cfg);

    if (
      j.status === "pending_apply" ||
      j.status === "applied" ||
      j.status === "outreach_drafting"
    ) {
      const out = await getOutreach(id).catch(() => null);
      setOutreach(out);
    }
  };

  useEffect(() => {
    reload().finally(() => setLoading(false));
  }, [id]);

  if (loading) return <p className="text-slate-400">Loading...</p>;
  if (!job) return <p className="text-red-500">Job not found.</p>;

  const latestArtifact = artifacts[artifacts.length - 1];
  const showResumeDiff =
    job.status === "pending_resume_review" && latestArtifact;
  const showOutreach =
    (job.status === "pending_apply" || job.status === "applied") && outreach;

  return (
    <div className="space-y-8">
      <div className="flex items-start gap-4">
        <Link href="/" className="text-sm text-slate-400 hover:text-slate-700 mt-1">
          ← Back
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-slate-900">{job.title}</h1>
          <p className="text-slate-500">
            {job.company}
            <span className="mx-2">·</span>
            <a href={job.url} target="_blank" rel="noopener noreferrer" className="text-brand-600 hover:underline">
              View posting ↗
            </a>
          </p>
          <div className="mt-3">
            <PipelineStatus status={job.status} />
          </div>
        </div>
        {job.fit_score != null && (
          <div className="text-center">
            <div className="text-3xl font-bold text-slate-900">{job.fit_score}</div>
            <div className="text-xs text-slate-400">fit score</div>
          </div>
        )}
      </div>

      {job.fit_summary && (
        <section className="bg-white rounded-lg border border-slate-200 p-5 space-y-4">
          <h2 className="font-semibold text-slate-900">Fit Analysis</h2>
          <p className="text-sm text-slate-600">{job.fit_summary.summary}</p>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="font-medium text-green-700 mb-1">Matched</p>
              <ul className="space-y-0.5">
                {job.fit_summary.matched.map((m, i) => (
                  <li key={i} className="text-slate-600 flex gap-1.5">
                    <span className="text-green-500 mt-0.5">✓</span> {m}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="font-medium text-orange-700 mb-1">Gaps</p>
              <ul className="space-y-0.5">
                {job.fit_summary.gaps.map((g, i) => (
                  <li key={i} className="text-slate-600 flex gap-1.5">
                    <span className="text-orange-400 mt-0.5">△</span> {g}
                  </li>
                ))}
              </ul>
            </div>
          </div>
          {job.fit_summary.red_flags.length > 0 && (
            <div className="bg-red-50 rounded p-3 text-sm">
              <p className="font-medium text-red-700 mb-1">Red flags</p>
              {job.fit_summary.red_flags.map((f, i) => (
                <p key={i} className="text-red-600">• {f}</p>
              ))}
            </div>
          )}
        </section>
      )}

      {showResumeDiff && (
        <section className="bg-white rounded-lg border border-slate-200 p-5">
          <ResumeDiff
            jobId={job.id}
            artifact={latestArtifact}
            attempt={latestArtifact.attempt}
            maxRetries={settings?.max_tailor_retries ?? 3}
            onDecision={reload}
          />
        </section>
      )}

      {showOutreach && (
        <section className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-4">Outreach Drafts</h2>
          <OutreachPanel jobId={job.id} artifact={outreach} onDecision={reload} />
        </section>
      )}

      {job.jd_text && (
        <section className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="font-semibold text-slate-900 mb-3">Job Description</h2>
          <pre className="text-sm text-slate-600 whitespace-pre-wrap font-sans leading-relaxed max-h-80 overflow-y-auto">
            {job.jd_text}
          </pre>
        </section>
      )}
    </div>
  );
}
