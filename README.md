# AnalystAI

### An AI agent that analyzes your data like a human analyst would, on its own.

Upload a messy spreadsheet. Get back clean data, real insights, charts, a written summary, and a downloadable report, with no prompting needed. A second AI agent checks every finding before you see it, so you're not just trusting one model's guess.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-6E56CF)
![React](https://img.shields.io/badge/Frontend-React%20%2B%20Vite-61DAFB?logo=react&logoColor=white)


[Live Demo](#) &nbsp;·&nbsp; [How It Works](#how-it-works) &nbsp;·&nbsp; [Setup](#getting-started) &nbsp;·&nbsp; [Architecture](#architecture)

---

## See It In Action

![Dashboard placeholder](docs/screenshots/dashboard.png)
*The dashboard: dataset overview, insight cards, and an executive summary, all generated automatically.*

![Chat placeholder](docs/screenshots/chat.png)
*Ask follow-up questions in plain English. The same AI pipeline writes and runs the code live to answer.*

> **Note for reviewers:** the images above are placeholders. Add real screenshots to `docs/screenshots/` using the same filenames and they'll show up here automatically.

---

## Why This Project Is Different

Most "chat with your data" tools just ask an AI model the question and print whatever it says back. That's a guess, not an answer.

AnalystAI doesn't trust an AI model's math. Every number in the report comes from Python code the AI writes and actually runs on your data. Then a second, independent AI agent checks that result before it ever reaches you, even when the code ran with no errors at all.

That second check is the real engineering challenge this project solves, not the charts or the PDF export.

## Skills This Project Demonstrates

| Area | What's in this repo |
|---|---|
| **Agentic AI / LLM orchestration** | 7 AI agents working together in a LangGraph pipeline, each with one job |
| **Self-correcting AI systems** | A dedicated Critic agent that can reject or send back any AI-generated result |
| **Reliability engineering** | Automatic failover across 4 AI providers, usage limits, and safe fallback behavior instead of crashes |
| **Secure code execution** | AI-generated code is checked line by line, then run in an isolated sandbox |
| **Full-stack development** | React frontend, Python backend, PDF generation, and a memory system for chat |
| **Data engineering** | Reliable file parsing for CSV, Excel, PDF, and JSON, even when files are messy |

## Key Features

- **Works with any file** — CSV, Excel, PDF tables, or JSON. Broken headers and odd encodings are fixed automatically.
- **Cleans its own data** — writes and runs its own cleanup code, and fixes it if that code fails.
- **Asks smart questions** — each question builds on what's already been found, not a fixed checklist. It stops once there's nothing new to ask.
- **Double-checks itself** — a second AI agent grades every result (accept, weak accept, redo, or skip) before showing it to you.
- **Runs code safely** — every script is scanned for risky code, then run in an isolated sandbox with a time limit.
- **Keeps working when things fail** — if one AI provider is down, it automatically tries the next one, and there's a hard limit on usage so it never runs away.
- **Answers follow-up questions live** — chat with your data after the report is done; it remembers context from earlier in the session.
- **Exports a full PDF report** — findings, charts, confidence levels, and a summary of what worked and what didn't.

## Architecture

![AnalystAI system architecture](docs/architecture.png)

Seven agents, each with one job, run in this order: **Ingestion → Cleaner → Profiler → Analyst ⇄ Critic → Visualizer → Narrator**. A sandboxed code runner, a shared AI provider layer, and a memory system support all of them.

## How It Works

1. **Ingestion** reads the file, fixes broken headers or encodings, and writes a short description of what the data contains.
2. **Cleaner** writes and runs code to fix missing values, duplicates, and data types, retrying if something breaks.
3. **Profiler** calculates basic statistics and flags data quality issues. No AI call needed here, it's pure math.
4. **Analyst** comes up with one good question at a time, writes code to answer it, and runs that code safely.
5. **Critic** checks the Analyst's answer independently, and can send it back for a redo or drop it if it's not useful.
6. **Visualizer** turns each accepted answer into a chart or table, whichever fits the data better.
7. **Narrator** writes the final summary in plain English, and says clearly when a finding isn't fully certain.
8. The **chat** sends any follow-up question through the same steps, using memory from earlier in the session.

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Agent orchestration | LangGraph | Runs the agents in order and handles retries automatically |
| AI providers | Groq, Cerebras, DeepSeek, Google Gemini | If one is slow or down, it switches to the next |
| Code execution | Python `subprocess` sandbox | Runs AI-written code safely, in isolation, with a time limit |
| Code safety check | Python `ast` module | Scans code for risky commands before it ever runs |
| File parsing | Pandas, openpyxl, PyMuPDF | Reads CSV, Excel, and PDF tables, even messy ones |
| Data validation | Pydantic | Makes sure data passed between agents is in the expected shape |
| Charts | Plotly | Interactive on the dashboard, static in the PDF |
| Chat memory | ChromaDB (local) | Remembers earlier questions in the same session |
| PDF export | ReportLab | Builds the final downloadable report |
| Frontend | React + Vite + Tailwind CSS | Dashboard, chat, history, and export screens |

## Project Structure

```
analystai/
├── agents/
│   ├── ingestion.py       # Reads the file and describes the dataset
│   ├── cleaner.py         # Cleans the data, retries itself on failure
│   ├── profiler.py        # Calculates statistics and data quality flags
│   ├── analyst.py         # Comes up with questions and answers them with code
│   ├── critic.py          # Double-checks every answer the Analyst gives
│   ├── visualizer.py      # Decides chart vs. table and renders it
│   └── narrator.py        # Writes the plain-English summary
├── orchestrator/
│   ├── graph.py           # Defines the agent pipeline
│   └── utils.py           # Shared helper for making AI calls safely
├── sandbox/
│   ├── executor.py        # Runs AI-written code in isolation
│   └── validator.py       # Scans code for risky commands before running it
├── utils/
│   ├── file_reader.py     # Reads and repairs CSV/Excel/PDF/JSON files
│   └── llm_utils.py       # Talks to the AI providers, with automatic failover
├── memory/
│   └── chroma_store.py    # Remembers context for the chat feature
├── output/
│   └── pdf_export.py      # Builds the final PDF report
├── frontend/               # React + Vite + Tailwind app
│   └── src/components/     # Dashboard, chat, upload, export, history screens
├── config.py               # Settings: usage limits, retries, provider order
├── models.py                # Defines the expected shape of agent outputs
├── server.py                 # Starts the backend
└── docs/
    ├── architecture.png
    └── screenshots/
```

## Getting Started

### What you'll need

- Python 3.11 or newer
- Node.js 18+ and npm
- At least one API key from: Groq, Cerebras, DeepSeek, or Google Gemini

### Backend

```bash
git clone <your-repo-url>
cd analystai

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env            # add your API keys here
python server.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:5173` and connects to the backend you started above.

## Environment Variables

```env
GROQ_API_KEY=your_groq_key_here
CEREBRAS_API_KEY=your_cerebras_key_here
DEEPSEEK_API_KEY=your_deepseek_key_here
GEMINI_API_KEY=your_gemini_key_here
```

You don't need all four keys. If one is missing, the app just skips it and uses the next one. You need at least one working key.

## Configuration

These settings live in `config.py`:

| Setting | Default | What it does |
|---|---|---|
| `MAX_LLM_CALLS_PER_RUN` | 25 | Caps how many AI calls one analysis can use |
| `MAX_ANALYST_QUESTIONS` | 3 | How many questions the Analyst asks per dataset |
| `MAX_ANALYST_RETRIES` | 2 | How many times a question can be retried before giving up |
| `MAX_LLM_RETRIES` | 5 | Retries per AI provider before switching to the next one |
| `LIGHT_CHAIN` / `HEAVY_CHAIN` | see `config.py` | Which AI providers handle simple vs. more demanding tasks |

## Safety and Sandboxing

Every piece of AI-generated code goes through two checks before it runs:

- **A static scan:** the code is checked for risky commands, like file access or system calls, before it's allowed to run at all.
- **A sandboxed run:** approved code runs in its own isolated process, with a 30-second time limit, so it can never affect the main app.

## Known Limitations

- The system is only as good as the AI providers behind it. Retrying doesn't fix a question that's genuinely too hard for the model.
- The Critic is also an AI agent, so it can occasionally get a judgment call wrong.
- The 30-second time limit may be too short for very large datasets.
- PDF tables need to have real, readable text. Scanned or image-based PDFs won't work.

## Roadmap

- [ ] Have the Critic check statistical validity, not just whether the logic makes sense.
- [ ] Let the Analyst and Critic go back and forth more than once on a tricky question.
- [ ] Cache results so re-uploading the same file doesn't waste AI usage.
- [ ] Benchmark AnalystAI's accuracy and speed against a human analyst.

## About the Author

Built by **Sonakshi Puri**, ECE undergraduate. This project was built to see how far a self-checking, multi-agent system could go for automated data analysis, and to get real, hands-on experience with the kind of AI agent design that's becoming central to production AI systems.

- GitHub: [your-github-handle](#)
- LinkedIn: [your-linkedin](#)
- Email: your-email@example.com

## License

MIT, see `LICENSE` for details.
