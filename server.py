# backend/server.py
#
# Drop this file into your project ROOT (next to app.py / config.py).
# It imports your existing agents/orchestrator/sandbox/memory/output/utils
# packages exactly as app.py already does -- nothing in your pipeline changes.
#
# Run with:
#   pip install fastapi "uvicorn[standard]" python-multipart
#   uvicorn server:app --reload --port 8000
#
# The React frontend (frontend/) talks to this on http://localhost:8000

import os
import re
import ast
import uuid
import json
import traceback
import tempfile
from typing import Optional

import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from orchestrator.graph import run_pipeline
from memory.chroma_store import store_insights, retrieve_context, clear_session, clean_old_sessions
from utils.llm_utils import get_llm, invoke_llm_with_backoff
from utils.file_reader import read_file
from output.pdf_export import build_pdf
from agents.profiler import profile_dataset

app = FastAPI(title="Datalyze AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = get_llm("app")

# ------------------------------------------------------------------
# In-memory session store (mirrors st.session_state from the old app)
# For production, swap this for redis / a db.
# ------------------------------------------------------------------
SESSIONS: dict[str, dict] = {}


def _new_session() -> dict:
    return {
        "session_id": uuid.uuid4().hex[:8],
        "pipeline_result": None,
        "chat_history": [],
        "pdf_path": None,
        "cleaned_df": None,
        "uploaded_file": None,
    }


def _get_session(session_id: Optional[str]) -> dict:
    if session_id and session_id in SESSIONS:
        return SESSIONS[session_id]
    s = _new_session()
    SESSIONS[s["session_id"]] = s
    return s


try:
    clean_old_sessions(days=7)
except Exception:
    pass


# ------------------------------------------------------------------
# Helpers (ported directly from app.py)
# ------------------------------------------------------------------

def format_answer(answer: str) -> str:
    if not answer or not isinstance(answer, str):
        return "No answer available."
    try:
        data = json.loads(answer)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            keys = list(data[0].keys())
            if len(keys) >= 2:
                label_key = keys[0]
                value_key = next((k for k in keys if k != label_key and isinstance(data[0].get(k), (int, float))), None)
                if value_key:
                    lines = []
                    for item in data:
                        label = item.get(label_key, "?")
                        val = item.get(value_key, 0)
                        try:
                            val = float(val)
                            val_str = f"{val:,.2f}" if abs(val) > 1000 else f"{val:.2f}"
                        except (TypeError, ValueError):
                            val_str = str(val)
                        lines.append(f"- **{label}**: {val_str}")
                    return "\n".join(lines)
    except (json.JSONDecodeError, TypeError, KeyError):
        pass

    if ";" in answer and ":" in answer:
        items = [i.strip() for i in answer.split(";") if i.strip()]
        bullet_items = []
        for item in items:
            if ":" in item:
                key, val = item.split(":", 1)
                key, val = key.strip(), val.strip()
                try:
                    num = float(val)
                    val_str = f"{num:,.2f}" if abs(num) > 1000 else f"{num:.2f}"
                except (TypeError, ValueError):
                    val_str = val
                bullet_items.append(f"- **{key}**: {val_str}")
            else:
                bullet_items.append(f"- {item}")
        if bullet_items:
            return "\n".join(bullet_items)

    cleaned = re.sub(r"\s+", " ", answer).strip()
    try:
        num = float(cleaned)
        return f"{num:,.2f}" if abs(num) > 1000 else f"{num:.2f}"
    except (TypeError, ValueError):
        pass
    return cleaned


def answer_from_data(question: str, df: pd.DataFrame) -> Optional[str]:
    q = question.lower().strip()

    def normalize_column(col: str) -> str:
        s = re.sub(r"([a-z])([A-Z])", r"\1 \2", col)
        s = re.sub(r"_", " ", s)
        return " ".join(s.lower().split())

    col_tokens = {col: normalize_column(col).split() for col in df.columns}

    def all_tokens_present(tokens: list[str]) -> bool:
        for tok in tokens:
            pattern = r"\b" + re.escape(tok) + r"\b"
            if not re.search(pattern, q):
                return False
        return True

    matched_cols = [col for col, tokens in col_tokens.items() if all_tokens_present(tokens)]
    numeric_cols = [c for c in matched_cols if c in df.select_dtypes(include="number").columns]

    complex_markers = [
        r"\bby\b", r"\bper\b", r"\bfor each\b", r"\bcompare\b", r"\bversus\b",
        r"\bvs\b", r"\bgrouped\b", r"\bacross\b", r"\bdistribution\b", r"\btrend\b",
    ]
    is_complex = any(re.search(pattern, q) for pattern in complex_markers)

    if len(matched_cols) == 1 and len(numeric_cols) == 1 and not is_complex:
        col = numeric_cols[0]
        label = normalize_column(col)
        series = df[col].dropna()
        if series.empty:
            return None

        count = len(series)
        lo, hi = series.min(), series.max()
        spread_note = f", ranging from {lo:,.2f} to {hi:,.2f}" if hi != lo else ""

        # This fast-path stays deterministic (no LLM call) for speed and
        # zero hallucination risk on a simple stat -- the sentence framing
        # is what changes, not the source of the number.
        if "average" in q or "mean" in q:
            std = series.std()
            consistency = ""
            if pd.notna(std) and series.mean() != 0:
                cv = abs(std / series.mean())
                if cv < 0.15:
                    consistency = " Values are fairly consistent across the dataset."
                elif cv > 0.6:
                    consistency = " Values vary widely across the dataset."
            return (
                f"The average {label} is {series.mean():,.2f} across {count:,} records"
                f"{spread_note}.{consistency}"
            )
        if "total" in q or "sum" in q:
            return f"The total {label} across all {count:,} records is {series.sum():,.2f}."
        if "max" in q or "highest" in q:
            # df.loc[[idx]].iloc[0], not df.loc[idx] -- the latter can
            # return a DataFrame instead of a Series if the dataset has
            # duplicate index labels (possible after certain cleaning/
            # groupby steps), which _describe_row_context isn't built to
            # handle. This form always yields a single Series.
            row = df.loc[[series.idxmax()]].iloc[0]
            id_note = _describe_row_context(df, row, col)
            return f"The highest {label} is {hi:,.2f}{id_note}, out of {count:,} records{spread_note}."
        if "min" in q or "lowest" in q:
            row = df.loc[[series.idxmin()]].iloc[0]
            id_note = _describe_row_context(df, row, col)
            return f"The lowest {label} is {lo:,.2f}{id_note}, out of {count:,} records{spread_note}."
    return None


def _describe_row_context(df: pd.DataFrame, row: pd.Series, exclude_col: str) -> str:
    """
    For a max/min answer, name the category the extreme value belongs to,
    if a low-cardinality categorical column is available -- e.g. turns
    "The highest revenue is 36022.60" into "...is 36022.60 (South America)"
    instead of leaving the reader to wonder which row it came from.
    """
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    for c in categorical_cols:
        if c == exclude_col:
            continue
        if df[c].nunique() <= 50 and pd.notna(row.get(c)):
            return f" ({row[c]})"
    return ""


def _humanize_list_answer(answer: str) -> str:
    """
    The code-execution chat tier sometimes computes the right thing --
    e.g. "these are the customer IDs to target" -- but the generated code
    prints the raw Python list literal as its ANSWER instead of a
    sentence (`ANSWER: [62130, 44310, 59612, ...]` for hundreds of rows).
    Detect that shape and turn it into something a person can actually
    read, deterministically, without depending on the LLM getting
    formatting right on every call.
    """
    text = answer.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return answer
    # Only handle simple literal lists of numbers/strings -- if it doesn't
    # parse cleanly, leave the original text alone rather than guess.
    try:
        items = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return answer
    if not isinstance(items, list) or len(items) == 0:
        return answer
    if not all(isinstance(x, (int, float, str)) for x in items):
        return answer

    count = len(items)
    preview_n = 15
    preview = ", ".join(str(x) for x in items[:preview_n])
    if count <= preview_n:
        return f"This identifies {count} matching records. IDs: {preview}."
    remaining = count - preview_n
    return (
        f"This identifies {count} matching records -- too many to list individually. "
        f"First {preview_n}: {preview}, and {remaining} more."
    )


def answer_with_code(question: str, df: pd.DataFrame) -> Optional[str]:
    from agents.analyst import generate_analysis_code
    from sandbox.executor import run_code
    from sandbox.validator import validate_code_ast

    schema = {
        "columns": list(df.columns),
        "dtypes": {c: str(dtype) for c, dtype in df.dtypes.items()},
        "nulls": df.isna().sum().to_dict(),
        "sample": df.head(3).to_dict(orient="records"),
        "shape": df.shape,
    }

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp_path = tmp.name
    df.to_csv(tmp_path, index=False)

    def _try_code(code: str) -> Optional[str]:
        is_valid, reason = validate_code_ast(code)
        if not is_valid:
            return None
        result = run_code(code)
        if not result["success"]:
            return None
        match = re.search(r"ANSWER:\s*(.*?)(?:\nCHART_JSON:|\Z)", result["output"], re.DOTALL)
        if not match:
            return None
        return _humanize_list_answer(match.group(1).strip())

    try:
        code = generate_analysis_code(question, schema, tmp_path, {})
        answer = _try_code(code)
        if answer is not None:
            return answer
        code2 = generate_analysis_code(question, schema, tmp_path, {})
        return _try_code(code2)
    except Exception as e:
        print(f"[Chat Analyst] Exception: {e}")
        return None
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


# ------------------------------------------------------------------
# Chart theming -- restyle Plotly figures to match the brand palette
# before sending JSON to the frontend.
# ------------------------------------------------------------------

BRAND_COLORWAY = ["#92736C", "#BFA07C", "#C9A79C", "#6E5646", "#D9C4B0"]


def theme_figure(fig) -> Optional[dict]:
    if fig is None:
        return None
    try:
        fig.update_layout(
            colorway=BRAND_COLORWAY,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color="#3A382F", size=11),
            margin=dict(l=50, r=20, t=56, b=70, pad=4),
            title=dict(
                font=dict(size=12.5, color="#3A382F"),
                x=0.02,
                xanchor="left",
                y=0.98,
                yanchor="top",
                pad=dict(b=10),
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=10),
            ),
            autosize=True,
        )
        fig.update_xaxes(
            gridcolor="rgba(58,56,47,0.08)",
            zerolinecolor="rgba(58,56,47,0.15)",
            automargin=True,
            title=dict(font=dict(size=10.5), standoff=10),
            tickfont=dict(size=9.5),
        )
        fig.update_yaxes(
            gridcolor="rgba(58,56,47,0.08)",
            zerolinecolor="rgba(58,56,47,0.15)",
            automargin=True,
            title=dict(font=dict(size=10.5), standoff=8),
            tickfont=dict(size=9.5),
        )
        return json.loads(fig.to_json())
    except Exception as e:
        print(f"[theme_figure] {e}")
        try:
            return json.loads(fig.to_json())
        except Exception:
            return None


def extract_headline_stat(answer: str) -> Optional[str]:
    """
    Pull the ONE number that should headline an insight card, out of a
    freeform LLM answer string.

    This used to live only in the frontend (InsightCard.jsx) as a
    first-match regex, which grabbed whatever number appeared first in the
    text -- usually the first row of a per-region/per-category breakdown,
    not the actual conclusion. That's a real bug, not a style choice: a
    "which region has the largest share" card was displaying a different
    region's number than the one named in its own answer text.

    This version is centralized here so there's exactly one implementation
    (frontend and PDF export both read this field instead of re-deriving
    it), and it's slightly smarter than "first number" or "last number":

    1. If the answer contains a concluding clause -- "is X, contributing
       Y%", "region is X with $Y", "highest at $Y" -- prefer the number
       tied to that clause, since that's where these agents state the
       actual finding after listing a breakdown.
    2. Otherwise fall back to the LAST money figure, then last percent,
       then last plain number. For single-sentence answers (no breakdown)
       this is identical to "first number", so it doesn't regress those.

    Caveat, stated plainly: this is still regex over freeform text, so it
    is a heuristic, not a guarantee. It can still misfire on unusual
    phrasing. The durable fix is agents/analyst.py emitting its own
    structured headline value -- out of scope here since agents/ isn't
    being touched, but worth revisiting if this keeps misfiring.
    """
    if not answer or not isinstance(answer, str):
        return None

    NUMBER = r"\$?-?[\d,]+(?:\.\d+)?%?[KMB]?"

    # Look for a concluding clause near the end of the text and grab the
    # number closest to it, scanning clauses right-to-left so the LAST
    # conclusion wins if there are several.
    conclusion_cue = re.compile(
        r"(?:is|was|at|with|contributing|totaling|reaches?)\s+.*?(" + NUMBER + r")",
        re.IGNORECASE,
    )
    matches = list(conclusion_cue.finditer(answer))
    if matches:
        return matches[-1].group(1)

    def last(pattern: str) -> Optional[str]:
        found = re.findall(pattern, answer)
        return found[-1] if found else None

    return (
        last(r"\$[\d,]+(?:\.\d+)?[KMB]?")
        or last(r"-?\d+(?:\.\d+)?%")
        or last(r"-?[\d,]+(?:\.\d+)?")
    )


def serialize_insight(insight: dict) -> dict:
    fig = insight.get("figure")
    out = {k: v for k, v in insight.items() if k != "figure"}
    out["chart"] = theme_figure(fig)
    answer_text = insight.get("answer", "")
    out["formatted_answer"] = format_answer(answer_text)
    out["headline_stat"] = extract_headline_stat(answer_text)
    return out


def serialize_result(result: dict) -> dict:
    out = {k: v for k, v in result.items() if k not in ("df",)}
    out["visualized_insights"] = [serialize_insight(i) for i in (result.get("visualized_insights") or [])]
    out.pop("execution_metadata_raw", None)
    return out


# ------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------

@app.get("/api/health")
def health():
    keys = {
        "groq": bool(os.getenv("GROQ_API_KEY")),
        "cerebras": bool(os.getenv("CEREBRAS_API_KEY")),
        "gemini": bool(os.getenv("GEMINI_API_KEY")),
    }
    return {"ok": True, "providers": keys}


@app.post("/api/session/new")
def new_session():
    s = _new_session()
    SESSIONS[s["session_id"]] = s
    return {"session_id": s["session_id"]}


@app.post("/api/session/{session_id}/reset")
def reset_session(session_id: str):
    clear_session(session_id)
    SESSIONS.pop(session_id, None)
    s = _new_session()
    SESSIONS[s["session_id"]] = s
    return {"session_id": s["session_id"]}


@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    session = _get_session(session_id)

    os.makedirs("uploads", exist_ok=True)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "", file.filename or "uploaded_file") or "uploaded_file"
    save_path = os.path.join("uploads", f"{uuid.uuid4()}_{safe_name}")

    contents = await file.read()
    with open(save_path, "wb") as f:
        f.write(contents)

    session["uploaded_file"] = {"name": file.filename, "size": len(contents), "path": save_path}

    try:
        result = run_pipeline(save_path)
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Unable to complete data ingestion right now. Please try again.")

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    session["pipeline_result"] = result
    session["chat_history"] = []
    session["pdf_path"] = None

    try:
        store_insights(session["session_id"], result.get("insights", []), result.get("description", ""))
    except Exception as e:
        print(f"[Chroma] store_insights failed: {e}")

    clean_path = result.get("clean_path")
    session["cleaned_df"] = None
    profile = None
    if clean_path and os.path.exists(clean_path):
        try:
            session["cleaned_df"] = read_file(clean_path)
            profile = profile_dataset(session["cleaned_df"])
        except Exception as e:
            print(f"[Analyze] could not load cleaned data for chat/profile: {e}")

    session["profile"] = profile
    serialized = serialize_result(result)
    serialized["profile"] = profile

    return {
        "session_id": session["session_id"],
        "file": session["uploaded_file"],
        "result": serialized,
    }


@app.get("/api/session/{session_id}")
def get_session(session_id: str):
    session = _get_session(session_id)
    if not session.get("pipeline_result"):
        return {"session_id": session["session_id"], "result": None, "chat_history": []}
    serialized = serialize_result(session["pipeline_result"])
    serialized["profile"] = session.get("profile")
    return {
        "session_id": session["session_id"],
        "file": session.get("uploaded_file"),
        "result": serialized,
        "chat_history": session["chat_history"],
    }


@app.post("/api/chat")
async def chat(session_id: str = Form(...), question: str = Form(...)):
    session = _get_session(session_id)
    result = session.get("pipeline_result")
    if not result:
        raise HTTPException(status_code=400, detail="No analysis loaded for this session yet.")

    session["chat_history"].append({"role": "user", "content": question})

    df = session.get("cleaned_df")
    answer = None

    if df is not None:
        answer = answer_from_data(question, df)

    if not answer and df is not None:
        answer = answer_with_code(question, df)

    if not answer:
        context = retrieve_context(session["session_id"], question) or ""
        prompt = f"""
You are a data analyst.

Dataset Description:
{result.get('description', '')}

Relevant Previous Findings:
{context}

User Question:
{question}

Answer using only the available analysis.
If the answer cannot be determined from the data, say so clearly.
**Do NOT invent examples or hypotheticals.** If you don't have a specific value, say "I don't have that information".
"""
        try:
            response = invoke_llm_with_backoff(llm, prompt)
            answer = response.content if response else "Unable to answer the question."
        except Exception as e:
            traceback.print_exc()
            error_msg = str(e)
            if len(error_msg) > 100:
                error_msg = error_msg[:100] + "..."
            answer = f"Unable to generate an answer: {error_msg}\n\nPlease try rephrasing your question."

    session["chat_history"].append({"role": "assistant", "content": answer})

    return {
        "answer": answer,
        "formatted_answer": format_answer(answer),
        "chat_history": session["chat_history"],
    }


@app.post("/api/export/pdf")
def export_pdf(session_id: str = Form(...)):
    session = _get_session(session_id)
    result = session.get("pipeline_result")
    if not result:
        raise HTTPException(status_code=400, detail="No analysis loaded for this session yet.")
    try:
        pdf_path = build_pdf(result, session["session_id"], session["chat_history"])
        session["pdf_path"] = pdf_path
    except Exception:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="PDF generation failed. Please try again.")
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"datalyze_report_{session['session_id']}.pdf",
    )


@app.get("/api/export/csv/{session_id}")
def export_csv(session_id: str):
    session = _get_session(session_id)
    result = session.get("pipeline_result")
    if not result or not result.get("clean_path") or not os.path.exists(result["clean_path"]):
        raise HTTPException(status_code=400, detail="No cleaned dataset available.")
    return FileResponse(
        result["clean_path"],
        media_type="text/csv",
        filename=f"cleaned_{session['session_id']}.csv",
    )