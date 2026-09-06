# AnalystAI

### An AI agent that analyzes your data like a human analyst would, autonomously.

Upload a messy spreadsheet. Get back cleaned data, genuine insights (not just summary stats), charts, a written executive summary, and a downloadable report, with a second AI agent independently fact-checking every finding before you see it. No prompting required.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-6E56CF)
![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?logo=react&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

[Live Demo](#) &nbsp;·&nbsp; [How It Works](#how-it-works) &nbsp;·&nbsp; [Setup](#getting-started) &nbsp;·&nbsp; [Architecture](#architecture)

---

## See It In Action

![Dashboard placeholder](docs/screenshots/dashboard.png)
*Dashboard: dataset overview, auto-generated insight cards, and executive summary, all produced without a human writing a single query.*

![Chat placeholder](docs/screenshots/chat.png)
*Ask follow-up questions in plain English. The same agent pipeline writes and runs the code live.*

> **Note for reviewers:** the three images above are placeholders. Swap in real screenshots at `docs/screenshots/` with the same filenames and they'll appear automatically.

---

## Why This Project Is Different

Most "chat with your data" tools just ask an LLM the question and print whatever it says back. That's a guess dressed up as an answer.

**AnalystAI never trusts an LLM's arithmetic.** Every quantitative claim is answered by LLM-*written* Python code that actually executes against the real dataset, and every one of those results then goes through a second, independent AI agent whose entire job is to catch wrong answers before they reach the user, even when the code ran perfectly and produced no error.

That self-correction loop, not the charts or the PDF export, is the interesting engineering problem this project solves.

## Skills This Project Demonstrates

| Area | What's in this repo |
|---|---|
| **Agentic AI / LLM orchestration** | 7 cooperating agents coordinated as a LangGraph state machine, with conditional routing and failure recovery |
| **Self-correcting AI systems** | An independent Critic agent reviews and can reject/retry every AI-generated result |
| **Systems reliability engineering** | 4-provider LLM failover, hard call budgets, graceful degradation instead of crashes |
| **Secure code execution** | AST-level static analysis + sandboxed subprocess execution for all LLM-generated code |
| **Full-stack delivery** | React/Vite/Tailwind frontend, Python backend, PDF report generation, vector-based session memory |
| **Data engineering** | Robust file parsing across CSV/Excel/PDF/JSON with automatic header and encoding repair |

## Key Features

- **Zero-config ingestion** — CSV, Excel, PDF tables, and JSON; broken headers and bad encodings are auto-repaired before anything else runs.
- **Self-cleaning data** — an LLM-written cleaning script fixes nulls, duplicates, and types, and retries itself on failure.
- **Adaptive analysis** — each question is generated based on what's already been found, not a fixed checklist, and the agent stops itself once there's nothing new to ask.
- **Independent critique** — a Critic agent grades every insight (`accept` / `weak_accept` / `regenerate` / `skip`) before it's shown to the user.
- **Sandboxed execution** — every generated script is AST-validated, then run in an isolated, timeboxed subprocess.
- **Resilient by design** — Groq → Cerebras → DeepSeek → Gemini failover plus a hard per-run LLM budget mean the pipeline degrades gracefully instead of crashing.
- **Live follow-up chat** — ask ad-hoc questions after the report is generated, answered by the same pipeline with session memory via ChromaDB.
- **One-click PDF export** — full report with findings, charts, confidence flags, and pipeline diagnostics via ReportLab.

## Architecture

![AnalystAI system architecture](docs/architecture.png)

Seven single-responsibility agents, coordinated by a LangGraph state machine: **Ingestion → Cleaner → Profiler → Analyst ⇄ Critic → Visualizer → Narrator**, backed by a sandboxed code-execution engine, a multi-provider LLM layer, and ChromaDB session memory.

## How It Works

1. **Ingestion** parses the file (with header repair and encoding fallback) and generates a schema and natural-language description.
2. **Cleaner** writes and runs Pandas code to fix nulls, duplicates, and types, retrying on failure.
3. **Profiler** computes deterministic statistics, correlations, and data-quality flags, no LLM call needed.
4. **Analyst** generates one adaptive question at a time, filters out trivial or overly complex ones, writes analysis code, and runs it in the sandbox.
5. **Critic** independently reviews every executed insight and can force a retry (`regenerate`) or drop it (`skip`) rather than trusting execution success alone.
6. **Visualizer** picks a chart or table per insight and renders it, with a deterministic fallback if none was produced.
7. **Narrator** writes the executive summary, explicitly flagging any low-confidence findings.
8. The **chat interface** routes follow-up questions through the same Analyst → Critic → sandbox loop, using ChromaDB for context.

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Agent orchestration | LangGraph | State-machine pipeline with conditional routing and built-in retry semantics |
| LLM providers | Groq, Cerebras, DeepSeek, Google Gemini | Cascading failover so one provider's outage doesn't stall the pipeline |
| Code execution | Python `subprocess` sandbox | Agent-written Pandas/Plotly code runs isolated, with a timeout |
| Static safety check | Python `ast` module | Blocks disallowed imports/calls before a single line executes |
| Data parsing | Pandas, openpyxl, PyMuPDF | CSV, Excel, and PDF-table extraction with header repair |
| Structured outputs | Pydantic | Agent-to-agent handoffs are schema-validated, not raw JSON |
| Charts | Plotly | Interactive in the dashboard, static in the PDF |
| Session memory | ChromaDB (local) | Per-session vector store for chat follow-up context |
| PDF export | ReportLab | Assembles the final downloadable report |
| Frontend | React + Vite + Tailwind CSS | Dashboard, chat, history, and export UI |

## Project Structure

```
analystai/
├── agents/
│   ├── ingestion.py       # Schema profiling + dataset description
│   ├── cleaner.py         # Self-correcting data cleaning loop
│   ├── profiler.py        # Deterministic statistical profiling
│   ├── analyst.py         # Adaptive question generation + code execution
│   ├── critic.py          # Independent verdict on every insight
│   ├── visualizer.py      # Chart-vs-table decisioning
│   └── narrator.py        # Executive summary generation
├── orchestrator/
│   ├── graph.py           # LangGraph pipeline definition
│   └── utils.py           # Shared, budget-aware LLM call wrapper
├── sandbox/
│   ├── executor.py        # Isolated subprocess code execution
│   └── validator.py       # AST-based static safety checks
├── utils/
│   ├── file_reader.py     # Smart multi-format, multi-encoding file reader
│   └── llm_utils.py       # Multi-provider LLM abstraction + failover
├── memory/
│   └── chroma_store.py    # Session-scoped vector memory
├── output/
│   └── pdf_export.py      # ReportLab PDF report builder
├── frontend/               # React + Vite + Tailwind CSS app
│   └── src/components/     # Dashboard, chat, upload, export, history, etc.
├── config.py               # Provider chains, budgets, retry limits
├── models.py                # Pydantic schemas for agent outputs
├── server.py                 # API entry point
└── docs/
    ├── architecture.png
    └── screenshots/
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- An API key for at least one of: Groq, Cerebras, DeepSeek, Google Gemini

### Backend

```bash
git clone <your-repo-url>
cd analystai

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # then fill in your API keys
python server.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and talks to the backend started above.

## Environment Variables

```env
GROQ_API_KEY=your_groq_key_here
CEREBRAS_API_KEY=your_cerebras_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
GEMINI_API_KEY=your_gemini_key_here
```

You don't need all four; the failover chain skips any provider whose key is missing or invalid. At least one working key is required.

## Configuration

Tunable limits live in `config.py`:

| Setting | Default | Meaning |
|---|---|---|
| `MAX_LLM_CALLS_PER_RUN` | 25 | Hard budget on LLM calls per analysis run |
| `MAX_ANALYST_QUESTIONS` | 3 | Questions the Analyst agent asks per dataset |
| `MAX_ANALYST_RETRIES` | 2 | Retry attempts per question before it's marked low-confidence |
| `MAX_LLM_RETRIES` | 5 | Retries per provider before failing over to the next one |
| `LIGHT_CHAIN` / `HEAVY_CHAIN` | see `config.py` | Provider order for light agents (ingestion, cleaning, narration) vs. heavy reasoning (analysis, critique) |

## Safety and Sandboxing

Every piece of LLM-generated code passes two independent checks before it runs:

- **Static (AST-based):** parsed and walked for disallowed imports (`os`, `subprocess`, `socket`, `sys`) and unsafe calls (`eval`, `exec`, `__import__`) before execution.
- **Dynamic (sandboxed subprocess):** validated code runs as an isolated OS process with a 30-second timeout and forced UTF-8 encoding, never `eval()`/`exec()` in the main server process.

## Known Limitations

- Reliability is bounded by the underlying LLM providers; retrying can't rescue a question that genuinely exceeds the model's reasoning ability.
- The Critic agent is itself an LLM call and can occasionally misjudge a verdict.
- The sandbox's 30-second timeout may be too short for very large datasets.
- PDF-table extraction requires genuinely extractable text; scanned/image-based PDFs aren't supported.

## Roadmap

- [ ] Extend the Critic to check statistical validity (sample size, confounders), not just logical correctness.
- [ ] Allow multi-round Analyst/Critic negotiation instead of a fixed retry count.
- [ ] Cache results by (dataset fingerprint, question) to avoid re-spending LLM budget on repeat uploads.
- [ ] Formal accuracy/latency benchmarking against a human-analyst baseline.

## About the Author

Built by **Sonakshi Puri**, ECE undergraduate. This project explores how far a self-correcting, multi-agent architecture can be pushed for autonomous data analysis, and gets hands-on with the agentic AI patterns (ReAct loops, multi-agent orchestration, LLM-generated code execution) that are increasingly central to production AI systems.

- GitHub: [your-github-handle](#)
- LinkedIn: [your-linkedin](#)
- Email: your-email@example.com

## License

MIT, see `LICENSE` for details.
