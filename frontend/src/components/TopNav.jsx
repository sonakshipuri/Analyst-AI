import React from "react";

const TABS = [
  { id: "new", label: "New Analysis" },
  { id: "current", label: "Current Analysis" },
  { id: "history", label: "History" },
];

export default function TopNav({ activeTab, onTabChange, hasResult, sessionId, theme, onToggleTheme }) {
  return (
    <header className="sticky top-4 z-40 mx-auto max-w-6xl px-4">
      <div className="glass-strong flex items-center justify-between rounded-full px-4 py-2.5">
        {/* Wordmark — typeset name only, no separate letter mark. */}
        <div className="flex items-baseline gap-2.5 pl-1">
          <span className="font-display text-xl font-semibold tracking-tight text-ink">
            Analyst<span className="text-rust">.</span>AI
          </span>
        </div>

        <nav className="flex items-center gap-1">
          {TABS.map((tab) => {
            const disabled = tab.id !== "new" && !hasResult;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                disabled={disabled}
                onClick={() => onTabChange(tab.id)}
                className={
                  "rounded-full px-4 py-1.5 text-sm font-medium transition-colors " +
                  (active
                    ? "bg-ink text-ivory"
                    : disabled
                    ? "text-ink-soft/35 cursor-not-allowed"
                    : "text-ink-soft hover:text-ink")
                }
              >
                {tab.label}
              </button>
            );
          })}
        </nav>

        <div className="flex items-center gap-3 pr-1">
          {sessionId && (
            <span className="hidden font-mono text-[11px] tracking-tight text-ink-soft/70 sm:inline-block">
              session · {sessionId}
            </span>
          )}
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="theme-toggle"
          >
            {theme === "dark" ? (
              // Sun icon — shown in dark mode, click to go light
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="4" />
                <path
                  d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"
                  strokeLinecap="round"
                />
              </svg>
            ) : (
              // Moon icon — shown in light mode, click to go dark
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </button>
          <div className="flex h-8 w-8 items-center justify-center rounded-full border border-ink/[0.14] text-[11px] font-semibold tracking-wide text-ink">
            AI
          </div>
        </div>
      </div>
    </header>
  );
}