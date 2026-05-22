"use client";

import clsx from "clsx";
import Link from "next/link";
import type { Job, DecisionPayload } from "@/lib/types";
import { PipelineStatus } from "./PipelineStatus";
import { TailorToggle } from "./TailorToggle";
import { submitDecision, setTailorOverride } from "@/lib/api";

interface Props {
  job: Job;
  globalTailorMode: "always_tailor" | "never_tailor" | "ask_each_time";
  onDecision?: () => void;
}

function ScoreBadge({ score }: { score: number }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center w-10 h-10 rounded-full text-sm font-bold",
        score >= 80 && "bg-green-100 text-green-800",
        score >= 65 && score < 80 && "bg-yellow-100 text-yellow-800",
        score < 65 && "bg-red-100 text-red-800"
      )}
    >
      {score}
    </span>
  );
}

export function JobCard({ job, globalTailorMode, onDecision }: Props) {
  const isPendingTriage = job.status === "pending_triage" || job.status === "pending_triage_tailor";
  const isPendingApply = job.status === "pending_apply";

  async function handleFastApply() {
    await submitDecision("gate3", job.id, { decision: "approved" });
    onDecision?.();
  }

  async function handleDecision(decision: "approved" | "skip", tailorChoice?: "tailor" | "original") {
    const payload: DecisionPayload = { decision };
    if (tailorChoice) payload.tailor_choice = tailorChoice;
    await submitDecision("gate1", job.id, payload);
    onDecision?.();
  }

  async function handleTailorOverride(choice: "tailor" | "original") {
    await setTailorOverride(job.id, choice);
    onDecision?.();
  }

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 hover:shadow-sm transition-shadow">
      <div className="flex items-start gap-4">
        {job.fit_score != null && <ScoreBadge score={job.fit_score} />}

        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div>
              <Link href={`/jobs/${job.id}`} className="font-medium text-slate-900 hover:text-brand-600 hover:underline">
                {job.title}
              </Link>
              <p className="text-sm text-slate-500">
                {job.company}
                <span className="mx-1">·</span>
                <span className="capitalize">{job.source}</span>
              </p>
            </div>
            <a
              href={job.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-brand-600 hover:underline shrink-0"
            >
              View JD ↗
            </a>
          </div>

          <div className="mt-2">
            <PipelineStatus status={job.status} />
          </div>

          {job.fit_summary?.summary && (
            <p className="mt-2 text-sm text-slate-600 line-clamp-2">{job.fit_summary.summary}</p>
          )}

          {isPendingApply && (
            <div className="mt-4 flex items-center justify-between gap-3">
              <Link href={`/jobs/${job.id}`} className="text-xs text-brand-600 hover:underline">
                Review outreach drafts →
              </Link>
              <button
                onClick={handleFastApply}
                className="px-4 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700"
              >
                Fast Apply ⚡
              </button>
            </div>
          )}

          {isPendingTriage && (
            <div className="mt-4 flex items-center gap-3 flex-wrap">
              <TailorToggle
                jobId={job.id}
                currentOverride={job.tailor_override}
                globalMode={globalTailorMode}
                onChange={handleTailorOverride}
              />
              <div className="flex gap-2 ml-auto">
                <button
                  onClick={() => handleDecision("skip")}
                  className="px-3 py-1 text-xs border border-slate-200 rounded hover:bg-slate-50 text-slate-600"
                >
                  Skip
                </button>
                <button
                  onClick={() => handleDecision("approved", job.tailor_override ?? undefined)}
                  className="px-4 py-1 text-xs bg-brand-500 text-white rounded hover:bg-brand-600"
                >
                  Approve →
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
