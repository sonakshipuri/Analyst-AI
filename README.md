# AnalystAI

AnalystAI is a multi-agent system that takes a raw data file (CSV, Excel, PDF, or JSON), cleans it, analyzes it, and produces a report with charts and a written summary. A chat interface lets you ask follow-up questions about the data after the report is generated.

The core idea is that every analytical answer is produced by AI-generated code that actually runs against the data, and every result is then reviewed by a separate agent before being included in the final output.

## Screenshots

![Dashboard](docs/screenshots/dashboard.png)

![Chat interface](docs/screenshots/chat.png)

*(Placeholder images. Replace the files in `docs/screenshots/` with real screenshots, same filenames.)*

## Features

- Accepts CSV, Excel, PDF tables, and JSON files
- Automatically detects and repairs broken headers and encoding issues
- Cleans data (missing values, duplicates, incorrect types) using generated code that retries on failure
- Generates analysis questions dynamically based on the dataset and prior findings
- Reviews every result with a separate agent before accepting it
- Generates charts and tables automatically
- Writes a plain-language executive summary
- Supports follow-up questions through a chat interface, with session memory
- Exports the full report as a PDF

## Architecture

![Architecture diagram](docs/architecture.png)

The pipeline is coordinated by LangGraph and consists of seven agents:

1. **Ingestion** – reads the file and produces a schema and description
2. **Cleaner** – cleans the data, retrying if the generated code fails
3. **Profiler** – computes statistics and data quality flags (no LLM call)
4. **Analyst** – generates questions and answers them with generated code
5. **Critic** – reviews each answer and can accept, reject, or request a redo
6. **Visualizer** – builds a chart or table for each accepted answer
7. **Narrator** – writes the final summary

All AI-generated code is checked for unsafe operations before it runs, and then executed in an isolated subprocess with a timeout.

## Tech Stack

| Layer | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM providers | Groq, Cerebras, DeepSeek, Google Gemini |
| Code execution | Python `subprocess` sandbox |
| Code validation | Python `ast` module |
| File parsing | Pandas, openpyxl, PyMuPDF |
| Data validation | Pydantic |
| Charts | Plotly |
| Session memory | ChromaDB |
| PDF export | ReportLab |
| Frontend | React, Vite, Tailwind CSS |

## Project Structure

```
analystai/
├── agents/
│   ├── ingestion.py
│   ├── cleaner.py
│   ├── profiler.py
│   ├── analyst.py
│   ├── critic.py
│   ├── visualizer.py
│   └── narrator.py
├── orchestrator/
│   ├── graph.py
│   └── utils.py
├── sandbox/
│   ├── executor.py
│   └── validator.py
├── utils/
│   ├── file_reader.py
│   └── llm_utils.py
├── memory/
│   └── chroma_store.py
├── output/
│   └── pdf_export.py
├── frontend/
│   └── src/components/
├── config.py
├── models.py
├── server.py
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

cp .env.example .env
# add your API keys to .env

python server.py
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and connects to the backend started above.

## Environment Variables

```env
GROQ_API_KEY=
CEREBRAS_API_KEY=
DEEPSEEK_API_KEY=
GEMINI_API_KEY=
```

At least one key is required. If a provider's key is missing, it is skipped in favor of the next one in the chain.

## Configuration

The following settings can be adjusted in `config.py`:

| Setting | Default | Description |
|---|---|---|
| `MAX_LLM_CALLS_PER_RUN` | 25 | Maximum LLM calls allowed per analysis run |
| `MAX_ANALYST_QUESTIONS` | 3 | Number of questions the Analyst asks per dataset |
| `MAX_ANALYST_RETRIES` | 2 | Retry attempts per question |
| `MAX_LLM_RETRIES` | 5 | Retries per provider before failover |
| `LIGHT_CHAIN` / `HEAVY_CHAIN` | see `config.py` | Provider order for lightweight vs. reasoning-heavy agents |

