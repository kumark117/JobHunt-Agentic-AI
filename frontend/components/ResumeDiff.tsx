"use client";

import { useState } from "react";
import clsx from "clsx";
import type { ResumeArtifact, DecisionPayload } from "@/lib/types";
import { submitDecision } from "@/lib/api";

interface Props {
  jobId: string;
  artifact: ResumeArtifact;
  attempt: number;
  maxRetries: number;
  onDecision?: () => void;
}

export function ResumeDiff({ jobId, artifact, attempt, maxRetries, onDecision }: Props) {
  const [rejectionNote, setRejectionNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const diff = artifact.diff_json;

  async function handleDecision(decision: "approved" | "rejected" | "skip" | "override") {
    setSubmitting(true);
    const payload: DecisionPayload = { decision };
    if (decision === "rejected" && rejectionNote) {
      payload.feedback = rejectionNote;
    }
    await submitDecision("gate2", jobId, payload);
    setSubmitting(false);
    onDecision?.();
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-slate-900">
          Resume Diff — Attempt {attempt}/{maxRetries}
        </h3>
        <span className="text-xs text-slate-400">{diff?.change_count ?? 0} bullets changed</span>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {diff?.changes?.map((change, i) => (
          <div key={i} className="rounded border border-slate-200 overflow-hidden text-sm">
            <div className="px-3 py-1 bg-slate-50 text-xs text-slate-500 font-medium border-b border-slate-200">
              {change.section}
            </div>
            <div className="grid grid-cols-2 divide-x divide-slate-200">
              <div className="p-3 bg-red-50">
                <p className="text-red-700 leading-relaxed">
                  <span className="text-red-400 mr-1">−</span>
                  {change.original}
                </p>
              </div>
              <div className="p-3 bg-green-50">
                <p className="text-green-700 leading-relaxed">
                  <span className="text-green-400 mr-1">+</span>
                  {change.tailored}
                </p>
                {change.reason && (
                  <p className="mt-1 text-xs text-slate-400 italic">{change.reason}</p>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-slate-200 pt-4 space-y-3">
        <textarea
          value={rejectionNote}
          onChange={(e) => setRejectionNote(e.target.value)}
          placeholder="Rejection note (e.g. 'Too generic — emphasise MCP experience more')..."
          className="w-full text-sm border border-slate-200 rounded p-2 h-16 resize-none focus:outline-none focus:ring-2 focus:ring-brand-500"
        />
        <div className="flex gap-2 justify-end">
          <button
            disabled={submitting}
            onClick={() => handleDecision("skip")}
            className="px-3 py-1.5 text-xs border border-slate-200 rounded hover:bg-slate-50 text-slate-600"
          >
            Skip job
          </button>
          <button
            disabled={submitting || !rejectionNote.trim()}
            onClick={() => handleDecision("rejected")}
            className={clsx(
              "px-3 py-1.5 text-xs border rounded",
              rejectionNote.trim()
                ? "border-orange-300 text-orange-700 hover:bg-orange-50"
                : "border-slate-200 text-slate-300 cursor-not-allowed"
            )}
          >
            Retry with note
          </button>
          <button
            disabled={submitting}
            onClick={() => handleDecision("approved")}
            className="px-4 py-1.5 text-xs bg-brand-500 text-white rounded hover:bg-brand-600 disabled:opacity-50"
          >
            Approve resume →
          </button>
        </div>
      </div>
    </div>
  );
}
