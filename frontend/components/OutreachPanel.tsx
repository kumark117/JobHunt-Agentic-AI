"use client";

import { useState } from "react";
import type { OutreachArtifact, DecisionPayload } from "@/lib/types";
import { submitDecision } from "@/lib/api";

interface Props {
  jobId: string;
  artifact: OutreachArtifact;
  onDecision?: () => void;
}

function parseJson(raw: string): { body?: string; subject?: string } {
  try {
    return JSON.parse(raw);
  } catch {
    return { body: raw };
  }
}

export function OutreachPanel({ jobId, artifact, onDecision }: Props) {
  const [submitting, setSubmitting] = useState(false);
  const note = parseJson(artifact.linkedin_note);
  const letter = parseJson(artifact.cover_letter);

  async function handleDecision(decision: "approved" | "skip") {
    setSubmitting(true);
    const payload: DecisionPayload = { decision };
    await submitDecision("gate3", jobId, payload);
    setSubmitting(false);
    onDecision?.();
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-medium text-slate-900 mb-3">LinkedIn Note</h3>
        <div className="bg-slate-50 rounded border border-slate-200 p-4">
          {note.subject && (
            <p className="text-xs text-slate-500 mb-2">Subject: {note.subject}</p>
          )}
          <p className="text-sm text-slate-700 whitespace-pre-wrap">{note.body ?? artifact.linkedin_note}</p>
          {note.char_count && (
            <p className="mt-2 text-xs text-slate-400">{note.char_count} / 300 chars</p>
          )}
        </div>
      </div>

      <div>
        <h3 className="font-medium text-slate-900 mb-3">Cover Letter</h3>
        <div className="bg-slate-50 rounded border border-slate-200 p-4">
          {letter.subject && (
            <p className="text-xs text-slate-500 mb-2">Subject: {letter.subject}</p>
          )}
          <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
            {letter.body ?? artifact.cover_letter}
          </p>
        </div>
      </div>

      <div className="flex gap-2 justify-end border-t border-slate-200 pt-4">
        <button
          disabled={submitting}
          onClick={() => handleDecision("skip")}
          className="px-3 py-1.5 text-xs border border-slate-200 rounded hover:bg-slate-50 text-slate-600"
        >
          Skip / Archive
        </button>
        <button
          disabled={submitting}
          onClick={() => handleDecision("approved")}
          className="px-4 py-1.5 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
        >
          Apply
        </button>
      </div>
    </div>
  );
}
