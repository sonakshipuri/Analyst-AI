import React, { useState } from "react";
import { api } from "../lib/api.js";

export default function ExportSection({ sessionId }) {
  const [generating, setGenerating] = useState(false);

  async function handlePdf() {
    setGenerating(true);
    try {
      const blob = await api.exportPdf(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `datalyze_report_${sessionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(`Could not generate the report: ${e.message}`);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="animate-rise">
      <h3 className="text-2xl font-bold text-ink">Ready to Export</h3>
      <p className="text-sm text-ink-soft">Download your analysis and cleaned data</p>

      <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <button
          onClick={handlePdf}
          disabled={generating}
          className="group flex flex-col items-start gap-3 rounded-4xl border border-ink/[0.10] bg-paper p-6 text-left transition-all hover:border-ink/25 disabled:opacity-60"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-ink/[0.10] text-ink">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <path d="M14 2v6h6" />
            </svg>
          </div>
          <div>
            <p className="font-display text-lg font-bold text-ink">PDF Report</p>
            <p className="mt-1 text-xs text-ink-soft leading-relaxed">
              Complete analysis with insights, charts, executive summary, and data quality metrics
            </p>
          </div>
          <span className="text-xs font-semibold text-rust">
            {generating ? "Generating…" : "↓ Generate Report"}
          </span>
        </button>

        <a
          href={api.csvUrl(sessionId)}
          className="group flex flex-col items-start gap-3 rounded-4xl border border-ink/[0.10] bg-paper p-6 text-left transition-all hover:border-ink/25"
        >
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-ink/[0.10] text-ink">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <ellipse cx="12" cy="5" rx="8" ry="3" />
              <path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5" />
              <path d="M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" />
            </svg>
          </div>
          <div>
            <p className="font-display text-lg font-bold text-ink">Clean Dataset</p>
            <p className="mt-1 text-xs text-ink-soft leading-relaxed">
              Processed data with missing values handled, duplicates removed, and standardized formats
            </p>
          </div>
          <span className="text-xs font-semibold text-rust">↓ Download CSV</span>
        </a>
      </div>
    </div>
  );
}
