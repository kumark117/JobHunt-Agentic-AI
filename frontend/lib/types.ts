export type JobStatus =
  | "discovered"
  | "scored"
  | "pending_triage"
  | "pending_triage_tailor"
  | "approved_triage"
  | "tailoring"
  | "pending_resume_review"
  | "resume_approved"
  | "retry_tailor"
  | "tailor_skipped"
  | "outreach_drafting"
  | "pending_apply"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "archived";

export interface FitSummary {
  score: number;
  matched: string[];
  gaps: string[];
  red_flags: string[];
  summary: string;
  ats_keywords?: string[];
}

export interface Job {
  id: string;
  source: string;
  url: string;
  title: string;
  company: string;
  jd_text?: string;
  fit_score?: number;
  fit_summary?: FitSummary;
  status: JobStatus;
  tailor_attempt: number;
  tailor_override?: "tailor" | "original" | null;
  discovered_at?: string;
  updated_at?: string;
}

export interface DiffChange {
  section: string;
  original: string;
  tailored: string;
  reason: string;
}

export interface DiffResult {
  added: string[];
  removed: string[];
  reordered: string[];
  summary_changed: boolean;
  change_count: number;
  changes: DiffChange[];
}

export interface ResumeArtifact {
  id: string;
  attempt: number;
  original_json: Record<string, unknown>;
  tailored_json: Record<string, unknown>;
  diff_json: DiffResult;
  pdf_path?: string;
  created_at?: string;
}

export interface OutreachArtifact {
  id: string;
  linkedin_note: string;
  cover_letter: string;
  created_at?: string;
}

export interface SSEEvent {
  event: string;
  job_id: string;
  data: Record<string, unknown>;
  ts: string;
}

export interface DecisionPayload {
  decision: "approved" | "rejected" | "skip" | "override";
  feedback?: string;
  manual_resume?: Record<string, unknown>;
  tailor_choice?: "tailor" | "original";
}

export interface Settings {
  tailor_mode: "always_tailor" | "never_tailor" | "ask_each_time";
  fit_score_threshold: number;
  max_tailor_retries: number;
  discovery_sources: Record<string, boolean>;
  target_roles: string[];
  target_locations: string[];
}
