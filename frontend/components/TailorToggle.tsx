"use client";

import clsx from "clsx";

interface Props {
  jobId: string;
  currentOverride?: "tailor" | "original" | null;
  globalMode: "always_tailor" | "never_tailor" | "ask_each_time";
  onChange: (choice: "tailor" | "original") => void;
  disabled?: boolean;
}

export function TailorToggle({ jobId, currentOverride, globalMode, onChange, disabled }: Props) {
  const effective = currentOverride ?? (globalMode === "never_tailor" ? "original" : "tailor");

  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-slate-500">Resume:</span>
      <div className="flex rounded border border-slate-200 overflow-hidden text-xs">
        <button
          disabled={disabled}
          onClick={() => onChange("tailor")}
          className={clsx(
            "px-3 py-1 transition-colors",
            effective === "tailor"
              ? "bg-brand-500 text-white"
              : "bg-white text-slate-600 hover:bg-slate-50"
          )}
        >
          Tailor
        </button>
        <button
          disabled={disabled}
          onClick={() => onChange("original")}
          className={clsx(
            "px-3 py-1 transition-colors border-l border-slate-200",
            effective === "original"
              ? "bg-slate-700 text-white"
              : "bg-white text-slate-600 hover:bg-slate-50"
          )}
        >
          Use original
        </button>
      </div>
    </div>
  );
}
