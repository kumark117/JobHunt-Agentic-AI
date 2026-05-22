import type { Job, ResumeArtifact, OutreachArtifact, DecisionPayload, Settings } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// Jobs
export const getJobs = (status?: string) =>
  request<Job[]>(`/api/jobs${status ? `?status=${status}` : ""}`);

export const getPendingJobs = () => request<Job[]>("/api/jobs/pending");

export const getJob = (id: string) => request<Job>(`/api/jobs/${id}`);

export const getResumeArtifacts = (jobId: string) =>
  request<ResumeArtifact[]>(`/api/jobs/${jobId}/resume-artifacts`);

export const getOutreach = (jobId: string) =>
  request<OutreachArtifact>(`/api/jobs/${jobId}/outreach`);

export const setTailorOverride = (jobId: string, tailor_override: "tailor" | "original") =>
  request(`/api/jobs/${jobId}/tailor-override`, {
    method: "PATCH",
    body: JSON.stringify({ tailor_override }),
  });

// Pipeline
export const triggerPipeline = (jobId: string) =>
  request(`/api/pipeline/run/${jobId}`, { method: "POST" });

export const submitDecision = (gate: string, jobId: string, payload: DecisionPayload) =>
  request(`/api/pipeline/hitl/${gate}/${jobId}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

export const getPendingGates = () => request<{ pending: string[] }>("/api/pipeline/pending-gates");

export const resetAllJobs = () =>
  request<{ status: string }>("/api/jobs/reset", { method: "DELETE" });

export const getVersion = () =>
  request<{ api_version: string }>("/version");

export const triggerDiscovery = () =>
  request<{ status: string }>("/api/pipeline/run-discovery", { method: "POST" });

export const getDiscoveryStatus = () =>
  request<{ running: boolean }>("/api/pipeline/discovery-status");

// Settings
export const getSettings = () => request<Settings>("/api/settings/");

export const saveSettings = (settings: Partial<Settings>) =>
  request("/api/settings/", { method: "POST", body: JSON.stringify(settings) });

// SSE — returns an EventSource (browser API)
export const createSSEConnection = () =>
  new EventSource(`${BASE}/api/pipeline/sse`);
