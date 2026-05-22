import clsx from "clsx";
import type { JobStatus } from "@/lib/types";

const STAGES: { label: string; statuses: JobStatus[] }[] = [
  { label: "Discovered", statuses: ["discovered", "scored"] },
  { label: "Triage", statuses: ["pending_triage", "pending_triage_tailor", "approved_triage"] },
  { label: "Tailor", statuses: ["tailoring", "pending_resume_review", "resume_approved", "retry_tailor", "tailor_skipped"] },
  { label: "Outreach", statuses: ["outreach_drafting", "pending_apply"] },
  { label: "Applied", statuses: ["applied", "interviewing", "offer"] },
];

const TERMINAL: JobStatus[] = ["archived", "rejected", "offer"];

function getStageIndex(status: JobStatus): number {
  return STAGES.findIndex((s) => s.statuses.includes(status));
}

interface Props {
  status: JobStatus;
}

export function PipelineStatus({ status }: Props) {
  const currentIndex = getStageIndex(status);
  const isTerminal = TERMINAL.includes(status);

  if (isTerminal) {
    return (
      <span
        className={clsx(
          "inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
          status === "offer" && "bg-green-100 text-green-800",
          status === "rejected" && "bg-red-100 text-red-800",
          status === "archived" && "bg-slate-100 text-slate-600"
        )}
      >
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  }

  return (
    <div className="flex items-center gap-1">
      {STAGES.map((stage, i) => (
        <div key={stage.label} className="flex items-center gap-1">
          <div
            className={clsx(
              "h-2 w-2 rounded-full",
              i < currentIndex && "bg-brand-500",
              i === currentIndex && "bg-brand-500 ring-2 ring-brand-200",
              i > currentIndex && "bg-slate-200"
            )}
          />
          {i < STAGES.length - 1 && (
            <div className={clsx("h-px w-4", i < currentIndex ? "bg-brand-500" : "bg-slate-200")} />
          )}
        </div>
      ))}
      <span className="ml-2 text-xs text-slate-500">{status.replace(/_/g, " ")}</span>
    </div>
  );
}
