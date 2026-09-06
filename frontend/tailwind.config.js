/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Every token below is backed by a CSS variable defined in index.css
        // (:root for light, .dark for dark). Because every component
        // already uses these token names -- bg-ivory, text-ink,
        // border-ink/[0.10], etc. -- the whole app repaints for dark mode
        // without touching component files. The rgb(var(...) / <alpha-value>)
        // form is required for Tailwind's opacity modifiers (/[0.10] etc.)
        // to keep working with variable-backed colors.
        ivory: "rgb(var(--c-page) / <alpha-value>)",
        "pale-pink": "rgb(var(--c-subtle) / <alpha-value>)",
        paper: "rgb(var(--c-paper) / <alpha-value>)",

        "dusty-pink": "rgb(var(--c-neutral) / <alpha-value>)",
        "dusty-pink-deep": "rgb(var(--c-neutral-deep) / <alpha-value>)",

        olive: "rgb(var(--c-neutral2) / <alpha-value>)",
        "olive-deep": "rgb(var(--c-neutral2-deep) / <alpha-value>)",

        ink: "rgb(var(--c-ink) / <alpha-value>)",
        "ink-soft": "rgb(var(--c-ink-soft) / <alpha-value>)",

        // The ONE accent color in the whole system. Use sparingly —
        // headline numbers, the executive-summary figure, nothing else.
        // Slightly lighter in dark mode (see index.css) for contrast.
        rust: "rgb(var(--c-rust) / <alpha-value>)",

        // Fixed, NOT theme-dependent: text color used only inside the
        // permanently-dark executive-summary panel, which stays dark in
        // both themes. Must not flip with ink/ivory or it goes invisible
        // in dark mode.
        contrastFg: "#F5F2EC",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        body: ["Inter", "system-ui", "sans-serif"],
      },
      boxShadow: {
        // No drop shadows — hairline borders do the separation instead.
        glass: "none",
        "glass-lg": "none",
        "inner-glass": "none",
      },
      borderRadius: {
        "4xl": "1rem",
        "5xl": "1.25rem",
      },
      transitionProperty: {
        theme: "background-color, border-color, color",
      },
    },
  },
  plugins: [],
};