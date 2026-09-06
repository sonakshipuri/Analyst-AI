import React from "react";

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(2)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

const ICONS = { csv: "📄", xlsx: "📊", xls: "📊", json: "🗂️", pdf: "📕" };

export default function ReadyToAnalyze({ file, onStart, onClear, loading }) {
  const ext = file.name.split(".").pop().toLowerCase();

  return (
    <section className="latte-field mx-auto max-w-4xl px-4 pt-16 pb-24 animate-rise">
      <div className="card">
        <h2 className="text-4xl font-extrabold text-ink">Ready to Analyze</h2>
        <p className="mt-1 text-ink-soft">Your file is set, start the agents when you're ready.</p>

        <div className="mt-8 flex items-center gap-4 rounded-3xl border border-ink/[0.08] bg-pale-pink/40 p-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl border border-ink/[0.10] bg-paper text-xl">
            {ICONS[ext] || "📄"}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate font-medium text-ink">{file.name}</p>
            <p className="text-sm text-ink-soft">{fmtSize(file.size)}</p>
          </div>
          <button onClick={onClear} className="btn-ghost !px-3 text-sm" disabled={loading}>
            Remove
          </button>
          <button onClick={onStart} disabled={loading} className="btn-accent whitespace-nowrap">
            {loading ? (
              <>
                <span className="h-2 w-2 animate-ping rounded-full bg-ink/70" />
                Analyzing…
              </>
            ) : (
              "Start Analysis"
            )}
          </button>
        </div>

        {loading && <AgentProgress />}
      </div>
    </section>
  );
}

const STEPS = [
  { key: "ingestion", label: "Ingestion", desc: "Profiling schema & describing dataset" },
  { key: "cleaner", label: "Cleaner", desc: "Handling nulls, duplicates & types" },
  { key: "analyst", label: "Analyst", desc: "Generating & validating insights" },
  { key: "visualizer", label: "Visualizer", desc: "Building charts from findings" },
  { key: "narrator", label: "Narrator", desc: "Writing the executive summary" },
];

function AgentProgress() {
  const [active, setActive] = React.useState(0);

  React.useEffect(() => {
    const id = setInterval(() => {
      setActive((a) => Math.min(a + 1, STEPS.length - 1));
    }, 1800);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="mt-8 grid grid-cols-1 gap-2 sm:grid-cols-5">
      {STEPS.map((s, i) => (
        <div
          key={s.key}
          className={
            "rounded-2xl border p-3 text-left transition-all " +
            (i < active
              ? "border-ink/20 bg-ink/[0.03]"
              : i === active
              ? "border-rust/50 bg-rust/[0.06] animate-pulse"
              : "border-ink/[0.08] bg-transparent opacity-50")
          }
        >
          <p className="text-xs font-semibold text-ink">{s.label}</p>
          <p className="mt-0.5 text-[11px] leading-tight text-ink-soft">{s.desc}</p>
        </div>
      ))}
    </div>
  );
}
