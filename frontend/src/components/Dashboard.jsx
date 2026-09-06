import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import DatasetOverview from "./DatasetOverview.jsx";
import ExecutiveSummary from "./ExecutiveSummary.jsx";
import InsightCard from "./InsightCard.jsx";
import AskYourData from "./AskYourData.jsx";
import ExportSection from "./ExportSection.jsx";

function DiagnosticsStrip({ pipelineSummary }) {
  if (!pipelineSummary) return null;
  const time = pipelineSummary.total_pipeline_time;
  const failed = pipelineSummary.failed_agents || [];
  return (
    <div className="flex flex-wrap items-center gap-2 animate-rise">
      {time != null && (
        <span className="pill border border-ink/[0.10] bg-transparent text-ink-soft text-xs">{Number(time).toFixed(1)}s pipeline time</span>
      )}
      <span className={"pill text-xs border " + (failed.length ? "border-rust/30 bg-rust/[0.06] text-rust" : "border-ink/[0.10] bg-transparent text-ink-soft")}>
        {failed.length ? `⚠ ${failed.length} agent issue${failed.length > 1 ? "s" : ""}` : "✓ all agents completed"}
      </span>
    </div>
  );
}

export default function Dashboard({ sessionId, file, result, onNewAnalysis, chatHistory, setChatHistory }) {
  const insights = result?.visualized_insights || [];

  return (
    <section className="latte-field mx-auto max-w-6xl px-4 pb-32 pt-12">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="animate-rise">
          <p className="eyebrow">Analysis complete</p>
          <h1 className="mt-1 text-4xl sm:text-5xl font-extrabold tracking-tight text-ink">
            Your Data, Decoded.
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <DiagnosticsStrip pipelineSummary={result?.pipeline_summary} />
          <button onClick={onNewAnalysis} className="btn-ghost text-sm">
            New Analysis
          </button>
        </div>
      </div>

      <div className="mt-8">
        <DatasetOverview file={file} profile={result?.profile} />
      </div>

      {result?.description && (
        <div className="rich-text mt-6 animate-rise rounded-3xl bg-pale-pink/40 p-5 text-sm leading-relaxed text-ink-soft">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.description}</ReactMarkdown>
        </div>
      )}

      <div className="mt-6">
        <ExecutiveSummary summary={result?.summary} />
      </div>

      <div className="mt-12">
        <h2 className="text-3xl font-extrabold text-ink">Key Insights</h2>
        <p className="text-sm text-ink-soft">
          {insights.length} validated insight{insights.length === 1 ? "" : "s"} from autonomous analysis
        </p>
        <div className="mt-5 grid grid-cols-1 gap-5 sm:grid-cols-2">
          {insights.map((insight, i) => (
            <InsightCard key={i} insight={insight} index={i} />
          ))}
          {insights.length === 0 && (
            <div className="card sm:col-span-2 text-center text-ink-soft">
              No validated insights were generated for this dataset.
            </div>
          )}
        </div>
      </div>

      <div className="mt-12">
        <AskYourData sessionId={sessionId} chatHistory={chatHistory} setChatHistory={setChatHistory} />
      </div>

      <div className="mt-12">
        <ExportSection sessionId={sessionId} />
      </div>
    </section>
  );
}
