import React, { useRef, useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../lib/api.js";

const SUGGESTIONS = [
  "What was the total revenue last period?",
  "Which segment has the lowest performance?",
  "How many repeat entries are there?",
  "What is the overall trend?",
];

export default function AskYourData({ sessionId, chatHistory, setChatHistory }) {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [chatHistory, loading]);

  async function send(question) {
    const q = (question ?? input).trim();
    if (!q || loading) return;
    setInput("");
    setChatHistory((h) => [...h, { role: "user", content: q }]);
    setLoading(true);
    try {
      const res = await api.chat(sessionId, q);
      setChatHistory((h) => [...h.slice(0, -1), ...res.chat_history.slice(-2)]);
    } catch (e) {
      setChatHistory((h) => [...h, { role: "assistant", content: `Something went wrong: ${e.message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card animate-rise">
      <h3 className="text-2xl font-bold text-ink">Ask Your Data</h3>
      <p className="text-sm text-ink-soft">Natural language queries powered by AI</p>

      <div
        ref={scrollRef}
        className="mt-6 max-h-96 space-y-3 overflow-y-auto rounded-3xl bg-pale-pink/40 p-4"
      >
        {chatHistory.length === 0 && (
          <div className="flex items-start gap-2 rounded-2xl bg-paper border border-ink/[0.08] p-3 text-sm text-ink-soft">
            <span className="mt-0.5">✨</span>
            <span>Hi! I can answer any question about your data. What would you like to know?</span>
          </div>
        )}
        {chatHistory.map((m, i) => (
          <div
            key={i}
            className={
              "flex " + (m.role === "user" ? "justify-end" : "justify-start")
            }
          >
            <div
              className={
                "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed " +
                (m.role === "user"
                  ? "bg-ink text-ivory"
                  : "rich-text bg-paper text-ink border border-ink/[0.08]")
              }
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-paper px-4 py-2.5 text-sm text-ink-soft border border-ink/[0.08]">
              <span className="inline-flex gap-1">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-rust [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-rust [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-rust" />
              </span>
            </div>
          </div>
        )}
      </div>

      {chatHistory.length === 0 && (
        <div className="mt-4">
          <p className="mb-2 text-xs font-medium text-ink-soft/70">Suggested questions</p>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-2xl bg-pale-pink/40 px-3 py-2 text-left text-xs text-ink-soft hover:bg-pale-pink/70 transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="mt-4 flex items-center gap-2 rounded-full bg-pale-pink/40 border border-ink/[0.10] p-1.5 pl-4"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about your data..."
          className="flex-1 bg-transparent text-sm text-ink placeholder:text-ink-soft/50 outline-none"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-ivory transition-colors hover:bg-rust disabled:opacity-40"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <path d="M12 19V5M12 5l-6 6M12 5l6 6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
    </div>
  );
}
