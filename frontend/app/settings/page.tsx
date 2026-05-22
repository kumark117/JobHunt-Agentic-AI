"use client";

import { useEffect, useState } from "react";
import { getSettings, saveSettings } from "@/lib/api";
import type { Settings } from "@/lib/types";

const SOURCE_LABELS: Record<string, string> = {
  linkedin: "LinkedIn",
  naukri: "Naukri.com",
  wellfound: "Wellfound (AngelList)",
  instahyre: "Instahyre",
  glassdoor: "Glassdoor",
  indeed: "Indeed India",
  cutshort: "Cutshort",
  company_careers: "Company Careers",
  hn_hiring: "HN Who's Hiring",
  yc_jobs: "YC Job Board",
};

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getSettings().then(setSettings);
  }, []);

  async function handleSave() {
    if (!settings) return;
    setSaving(true);
    await saveSettings(settings);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  if (!settings) return <p className="text-slate-400">Loading settings...</p>;

  return (
    <div className="max-w-2xl space-y-8">
      <h1 className="text-2xl font-bold text-slate-900">Settings</h1>

      <section className="bg-white rounded-lg border border-slate-200 p-6 space-y-4">
        <h2 className="font-semibold text-slate-900">Resume Tailoring</h2>
        <div className="space-y-2">
          {(["always_tailor", "never_tailor", "ask_each_time"] as const).map((mode) => (
            <label key={mode} className="flex items-center gap-3 cursor-pointer">
              <input
                type="radio"
                name="tailor_mode"
                value={mode}
                checked={settings.tailor_mode === mode}
                onChange={() => setSettings({ ...settings, tailor_mode: mode })}
                className="accent-brand-500"
              />
              <div>
                <p className="text-sm font-medium text-slate-800">
                  {mode === "always_tailor" && "Always tailor"}
                  {mode === "never_tailor" && "Never tailor"}
                  {mode === "ask_each_time" && "Ask me each time"}
                </p>
                <p className="text-xs text-slate-500">
                  {mode === "always_tailor" && "Default — zero-click for the common case"}
                  {mode === "never_tailor" && "Always use original resume, skip Gate 2"}
                  {mode === "ask_each_time" && "Prompt on every Gate 1 card"}
                </p>
              </div>
            </label>
          ))}
        </div>
      </section>

      <section className="bg-white rounded-lg border border-slate-200 p-6 space-y-4">
        <h2 className="font-semibold text-slate-900">Pipeline Thresholds</h2>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Fit Score Threshold (Gate 1 minimum)
            </label>
            <input
              type="number"
              min={40}
              max={95}
              value={settings.fit_score_threshold}
              onChange={(e) =>
                setSettings({ ...settings, fit_score_threshold: parseInt(e.target.value) })
              }
              className="w-full border border-slate-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Max Tailor Retries (Gate 2)
            </label>
            <input
              type="number"
              min={1}
              max={5}
              value={settings.max_tailor_retries}
              onChange={(e) =>
                setSettings({ ...settings, max_tailor_retries: parseInt(e.target.value) })
              }
              className="w-full border border-slate-200 rounded px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
          </div>
        </div>
      </section>

      <section className="bg-white rounded-lg border border-slate-200 p-6 space-y-4">
        <h2 className="font-semibold text-slate-900">Discovery Sources</h2>
        <div className="grid grid-cols-2 gap-2">
          {Object.entries(settings.discovery_sources ?? {}).map(([source, enabled]) => (
            <label key={source} className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    discovery_sources: {
                      ...settings.discovery_sources,
                      [source]: e.target.checked,
                    },
                  })
                }
                className="accent-brand-500"
              />
              <span className="text-sm text-slate-700">{SOURCE_LABELS[source] ?? source}</span>
            </label>
          ))}
        </div>
      </section>

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2 bg-brand-500 text-white text-sm rounded hover:bg-brand-600 disabled:opacity-50"
        >
          {saving ? "Saving..." : "Save settings"}
        </button>
        {saved && <span className="text-sm text-green-600">Saved</span>}
      </div>
    </div>
  );
}
