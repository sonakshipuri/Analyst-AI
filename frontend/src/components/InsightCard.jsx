import React from "react";
import Plot from "react-plotly.js";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

function lastMatch(text, regex) {
  const all = text.match(regex);
  return all && all.length ? all[all.length - 1] : null;
}

function extractStat(text = "") {
  // Narrative answers list per-item breakdowns first and state the actual
  // conclusion at the end ("...the region with the largest share is X ($Y)").
  // Taking the LAST figure of a kind, not the first, matches the conclusion
  // instead of an arbitrary row from the breakdown.
  const money = lastMatch(text, /\$[\d,]+(\.\d+)?[KMB]?/g);
  if (money) return money;
  const pct = lastMatch(text, /-?\d+(\.\d+)?%/g);
  if (pct) return pct;
  const num = lastMatch(text, /-?[\d,]+(\.\d+)?/g);
  if (num) return num;
  return null;
}

const TREND_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M3 17l6-6 4 4 8-8" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M14 7h7v7" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const WARN_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 9v4m0 4h.01M10.3 3.9L2.6 17a2 2 0 001.7 3h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);
const AWARD_ICON = (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="12" cy="8" r="5" />
    <path d="M8.5 13.5L7 22l5-3 5 3-1.5-8.5" strokeLinecap="round" strokeLinejoin="round" />
  </svg>
);

function pickIcon(text = "") {
  const t = text.toLowerCase();
  if (/(risk|concern|declin|drop|caution)/.test(t)) return WARN_ICON;
  if (/(top|region|channel|leader|best)/.test(t)) return AWARD_ICON;
  return TREND_ICON;
}

/**
 * Tracks the live .dark class on <html>. The chart's colors are baked
 * into JSON by the backend at analysis time (theme_figure() in
 * server.py), but the user can toggle light/dark AFTER a chart already
 * exists on screen -- theme is a frontend-only, post-render concern, so
 * this has to be reactive on the client, not something the server can
 * get right once and forget.
 */
function useIsDarkMode() {
  const [isDark, setIsDark] = React.useState(
    () => typeof document !== "undefined" && document.documentElement.classList.contains("dark")
  );
  React.useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      setIsDark(root.classList.contains("dark"));
    });
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);
  return isDark;
}

/**
 * The server hardcodes chart text to a dark brown (#3A382F) that reads
 * fine on a white card and goes nearly invisible on a dark one. Since
 * paper/plot background are already transparent, only text and gridline
 * colors need overriding here -- axis titles, tick labels, chart title,
 * and legend all inherit from layout.font.color unless an axis/legend
 * sets its own, so those are patched explicitly too.
 */
function themeChartLayout(layout, isDark) {
  if (!isDark) return layout;
  // Matches --c-ink-soft's dark-mode value in index.css (204 199 193) —
  // same derived palette as everything else, not a separate guess.
  const textColor = "#CCC7C1";
  const gridColor = "rgba(204, 199, 193, 0.14)";
  const patched = { ...layout, font: { ...(layout.font || {}), color: textColor } };
  if (layout.title) {
    patched.title = { ...layout.title, font: { ...(layout.title.font || {}), color: textColor } };
  }
  if (layout.legend) {
    patched.legend = { ...layout.legend, font: { ...(layout.legend.font || {}), color: textColor } };
  }
  for (const axisKey of Object.keys(layout)) {
    if (!/^(xaxis|yaxis)\d*$/.test(axisKey) || !layout[axisKey]) continue;
    const axis = layout[axisKey];
    patched[axisKey] = {
      ...axis,
      color: textColor,
      gridcolor: gridColor,
      zerolinecolor: gridColor,
      tickfont: { ...(axis.tickfont || {}), color: textColor },
      title: axis.title
        ? { ...axis.title, font: { ...(axis.title.font || {}), color: textColor } }
        : axis.title,
    };
  }
  return patched;
}

export default function InsightCard({ insight, index }) {
  const stat =
    insight.headline_stat ?? extractStat(insight.formatted_answer || insight.answer || "");
  const isDark = useIsDarkMode();

  return (
    <div
      className="card flex flex-col animate-rise"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-ink/[0.05] text-ink-soft">
            {pickIcon(insight.question)}
          </div>
          <p className="text-sm font-semibold text-ink">{insight.question}</p>
        </div>
      </div>

      {stat && <p className="mt-4 text-3xl font-extrabold text-rust">{stat}</p>}

      <div className="rich-text mt-2 text-[13px] leading-relaxed text-ink-soft">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{insight.formatted_answer || insight.answer || ""}</ReactMarkdown>
      </div>

      {insight.chart && (
        <div className="mt-5 -mx-2 overflow-hidden rounded-2xl">
          <Plot
            data={insight.chart.data}
            layout={themeChartLayout({ ...insight.chart.layout, autosize: true, height: 260 }, isDark)}
            config={{ displayModeBar: false, responsive: true }}
            style={{ width: "100%" }}
            useResizeHandler
          />
        </div>
      )}

      {!insight.chart && insight.table_data && insight.table_data.length > 0 && (
        <div className="mt-5 overflow-x-auto rounded-2xl border border-ink/[0.06]">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-ink/[0.03] text-ink-soft">
                {Object.keys(insight.table_data[0]).map((k) => (
                  <th key={k} className="px-3 py-2 font-medium">{k}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {insight.table_data.slice(0, 8).map((row, i) => (
                <tr key={i} className="border-t border-ink/[0.04]">
                  {Object.values(row).map((v, j) => (
                    <td key={j} className="px-3 py-2 text-ink">{String(v)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {insight.critic_reason && (
        <p className="mt-3 text-[11px] italic text-ink-soft/60">Note: {insight.critic_reason}</p>
      )}
    </div>
  );
}