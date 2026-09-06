import React from "react";

function computeQuality(profile) {
  const profiles = Object.values(profile?.column_profiles || {});
  if (!profiles.length) return null;
  const avgMissing = profiles.reduce((sum, p) => sum + (p.missing_pct || 0), 0) / profiles.length;
  return Math.max(0, Math.round(100 - avgMissing));
}

function ColBlock({ label, count, sample, accent }) {
  return (
    <div className={`rounded-2xl p-4 ${accent}`}>
      <p className="text-xs font-medium text-ink-soft">{label}</p>
      <p className="mt-1 text-2xl font-bold text-ink">{count}</p>
      <p className="mt-1 truncate text-[11px] text-ink-soft/80">
        {sample && sample.length ? sample.slice(0, 3).join(", ") : "—"}
      </p>
    </div>
  );
}

export default function DatasetOverview({ file, profile }) {
  const quality = computeQuality(profile);
  const rows = profile?.shape?.rows;
  const cols = profile?.shape?.columns;

  return (
    <div className="card animate-rise">
      <p className="eyebrow">Dataset</p>
      <h3 className="mt-1 text-2xl font-bold text-ink truncate">{file?.name || "Uploaded dataset"}</h3>

      <div className="mt-6 grid grid-cols-3 gap-6 border-b border-ink/[0.06] pb-6">
        <div>
          <p className="text-xs font-medium text-ink-soft">Records</p>
          <p className="mt-1 text-3xl font-extrabold text-ink">{rows?.toLocaleString() ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs font-medium text-ink-soft">Columns</p>
          <p className="mt-1 text-3xl font-extrabold text-ink">{cols ?? "—"}</p>
        </div>
        <div>
          <p className="text-xs font-medium text-ink-soft">Data Quality</p>
          <p className="mt-1 text-3xl font-extrabold text-rust">
            {quality != null ? `${quality}%` : "—"}
          </p>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <ColBlock
          label="Numeric"
          count={profile?.numeric_columns?.length ?? 0}
          sample={profile?.numeric_columns}
          accent="bg-olive/10"
        />
        <ColBlock
          label="Categorical"
          count={profile?.categorical_columns?.length ?? 0}
          sample={profile?.categorical_columns}
          accent="bg-dusty-pink/15"
        />
        <ColBlock
          label="Datetime"
          count={profile?.datetime_columns?.length ?? 0}
          sample={profile?.datetime_columns}
          accent="bg-pale-pink/50"
        />
      </div>
    </div>
  );
}
