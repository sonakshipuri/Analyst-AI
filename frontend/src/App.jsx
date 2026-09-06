import React, { useEffect, useState } from "react";
import TopNav from "./components/TopNav.jsx";
import UploadScreen from "./components/UploadScreen.jsx";
import ReadyToAnalyze from "./components/ReadyToAnalyze.jsx";
import Dashboard from "./components/Dashboard.jsx";
import History from "./components/History.jsx";
import { api } from "./lib/api.js";

const HISTORY_KEY = "datalyze_history";
const THEME_KEY = "datalyze_theme";

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistoryEntry(entry) {
  const h = loadHistory();
  const next = [entry, ...h.filter((x) => x.session_id !== entry.session_id)].slice(0, 20);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(next));
  return next;
}

function loadInitialTheme() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // localStorage unavailable (private browsing, etc.) — fall through
  }
  if (typeof window !== "undefined" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) {
    return "dark";
  }
  return "light";
}

export default function App() {
  const [activeTab, setActiveTab] = useState("new");
  const [stage, setStage] = useState("upload"); // upload | ready | loading | dashboard
  const [pendingFile, setPendingFile] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [chatHistory, setChatHistory] = useState([]);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState(loadHistory());
  const [theme, setTheme] = useState(loadInitialTheme);

  useEffect(() => {
    if (stage === "dashboard") setActiveTab("current");
  }, [stage]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // ignore write failures — theme just won't persist this session
    }
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  function handleFileSelected(f) {
    setPendingFile(f);
    setError(null);
    setStage("ready");
  }

  function handleClearPending() {
    setPendingFile(null);
    setStage("upload");
  }

  async function handleStartAnalysis() {
    setStage("loading");
    setError(null);
    try {
      const res = await api.analyze(pendingFile, sessionId);
      setSessionId(res.session_id);
      setFile(res.file);
      setResult(res.result);
      setChatHistory([]);
      setStage("dashboard");
      setHistory(
        saveHistoryEntry({
          session_id: res.session_id,
          filename: res.file.name,
          timestamp: Date.now(),
        })
      );
    } catch (e) {
      setError(e.message || "Analysis failed.");
      setStage("ready");
    }
  }

  async function handleOpenHistory(sid) {
    try {
      const res = await api.getSession(sid);
      if (!res.result) {
        setError("That session has expired.");
        return;
      }
      setSessionId(res.session_id);
      setFile(res.file);
      setResult(res.result);
      setChatHistory(res.chat_history || []);
      setStage("dashboard");
      setActiveTab("current");
    } catch (e) {
      setError(e.message);
    }
  }

  function handleNewAnalysis() {
    setPendingFile(null);
    setStage("upload");
    setActiveTab("new");
  }

  function handleTabChange(tab) {
    if (tab === "new") return handleNewAnalysis();
    if (tab === "current" && result) return setActiveTab("current");
    if (tab === "history") return setActiveTab("history");
  }

  return (
    <div className="min-h-screen bg-ivory">
      <TopNav
        activeTab={activeTab}
        onTabChange={handleTabChange}
        hasResult={!!result}
        sessionId={sessionId}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      {error && (
        <div className="mx-auto mt-6 max-w-4xl px-4">
          <div className="glass rounded-2xl border-rust/30 px-4 py-3 text-sm text-rust">
            {error}
          </div>
        </div>
      )}

      {activeTab === "history" ? (
        <History history={history} onOpen={handleOpenHistory} />
      ) : stage === "dashboard" && result ? (
        <Dashboard
          sessionId={sessionId}
          file={file}
          result={result}
          onNewAnalysis={handleNewAnalysis}
          chatHistory={chatHistory}
          setChatHistory={setChatHistory}
        />
      ) : stage === "ready" || stage === "loading" ? (
        <ReadyToAnalyze
          file={pendingFile}
          onStart={handleStartAnalysis}
          onClear={handleClearPending}
          loading={stage === "loading"}
        />
      ) : (
        <UploadScreen onFileSelected={handleFileSelected} />
      )}
    </div>
  );
}