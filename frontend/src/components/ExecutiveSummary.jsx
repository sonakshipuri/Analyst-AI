import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function splitHeadline(summary) {
  if (!summary) return { headline: "Analysis complete.", rest: "" };
  const match = summary.match(/^(.*?[.!?])(\s+(.*))?$/s);
  if (!match) return { headline: summary, rest: "" };
  return { headline: match[1], rest: (match[3] || "").trim() };
}

export default function ExecutiveSummary({ summary }) {
  const { headline, rest } = splitHeadline(summary);

  return (
    <div className="glass-dark animate-rise rounded-4xl p-8 sm:p-10 text-contrastFg">
      <p className="eyebrow !text-rust">Executive Summary</p>
      <h3 className="mt-3 text-3xl sm:text-4xl font-extrabold leading-tight tracking-tight">
        {headline}
      </h3>
      {rest && (
        <div className="rich-text rich-text-dark mt-4 max-w-2xl text-[15px] leading-relaxed text-contrastFg/60">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{rest}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}