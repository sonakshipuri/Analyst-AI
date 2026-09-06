import React from "react";

export default function History({ history, onOpen }) {
  return (
    <section className="latte-field mx-auto max-w-3xl px-4 pt-16 pb-24">
      <p className="eyebrow">History</p>
      <h1 className="mt-1 text-4xl font-extrabold text-ink">Past Analyses</h1>
      <p className="mt-2 text-ink-soft">Revisit results from this browser session.</p>

      <div className="mt-8 space-y-3">
        {history.length === 0 && (
          <div className="card text-center text-ink-soft">
            Nothing here yet — run an analysis to see it appear.
          </div>
        )}
        {history.map((h) => (
          <button
            key={h.session_id}
            onClick={() => onOpen(h.session_id)}
            className="card flex w-full items-center justify-between text-left hover:bg-pale-pink/50 transition-colors"
          >
            <div className="min-w-0">
              <p className="truncate font-medium text-ink">{h.filename}</p>
              <p className="text-xs text-ink-soft">{new Date(h.timestamp).toLocaleString()}</p>
            </div>
            <span className="pill border border-ink/[0.10] font-mono text-ink-soft text-xs shrink-0">{h.session_id}</span>
          </button>
        ))}
      </div>
    </section>
  );
}