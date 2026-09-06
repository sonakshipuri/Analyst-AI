import React, { useCallback, useRef, useState } from "react";

const ACCEPTED = [".csv", ".xlsx", ".xls", ".json", ".pdf"];

export default function UploadScreen({ onFileSelected }) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const handleFiles = useCallback(
    (files) => {
      if (!files || !files.length) return;
      const file = files[0];
      const ext = "." + file.name.split(".").pop().toLowerCase();
      if (!ACCEPTED.includes(ext)) return;
      onFileSelected(file);
    },
    [onFileSelected]
  );

  return (
    <div className="upload-grid w-full min-h-[calc(100vh-140px)]">
      <section className="latte-field mx-auto flex min-h-[calc(100vh-140px)] max-w-5xl flex-col items-center justify-center px-4 text-center">
        <div className="latte-field-accent" aria-hidden="true" />
        <p className="eyebrow mb-4 animate-rise">Autonomous data analysis</p>
        <h1 className="animate-rise whitespace-nowrap text-6xl lg:text-7xl font-extrabold tracking-tight text-ink">
          Analysis, Simplified.
        </h1>
        <p
          className="animate-rise mx-auto mt-5 whitespace-nowrap text-lg text-ink-soft"
          style={{ animationDelay: "80ms" }}
        >
          Upload your data and let AI agents analyze it automatically
        </p>

        <div
          className="animate-rise mt-12 w-full"
          style={{ animationDelay: "160ms" }}
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            handleFiles(e.dataTransfer.files);
          }}
        >
          <button
            onClick={() => inputRef.current?.click()}
            className={
              "group flex w-full flex-col items-center justify-center gap-4 rounded-4xl border-2 border-dashed px-8 py-20 transition-all duration-300 " +
              (dragOver
                ? "glass-strong border-dusty-pink-deep scale-[1.01]"
                : "glass border-ink/[0.14] hover:border-dusty-pink")
            }
          >
            <div className="flex h-16 w-16 items-center justify-center rounded-3xl border border-ink/[0.12] bg-paper text-ink transition-transform group-hover:scale-105">
              <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 16V4M12 4l-4 4M12 4l4 4" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div>
              <p className="font-display text-2xl font-bold text-ink">Drop your file here</p>
              <p className="mt-1 text-ink-soft">
                or click to <span className="text-rust font-medium underline underline-offset-4">browse</span>
              </p>
            </div>
            <p className="text-sm text-ink-soft/70">CSV, Excel, JSON, or PDF</p>
          </button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED.join(",")}
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </div>
      </section>
    </div>
  );
}