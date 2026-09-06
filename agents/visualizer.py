# agents/visualizer.py
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

FAILURE_MARKERS = [
    "Could not compute",
    "No data available",
    "Analysis generation failed",
    "Skipped by critic"
]

# ============================================================
# FIX 9: Decide whether to show chart or table
# ============================================================
def _should_use_table(grouping_columns: list, result_data: list) -> bool:
    """
    Determine if we should render a table instead of a chart.
    Uses actual grouping columns and number of result rows.
    """
    if not grouping_columns or not result_data:
        return False  # no metadata, proceed with chart

    group_count = len(result_data)
    num_dims = len(grouping_columns)

    if num_dims >= 4:
        return True
    if num_dims == 3 and group_count > 20:
        return True
    return False


def parse_chart_json(chart_json_str: str):
    """Convert a Plotly JSON string into a Plotly figure."""
    try:
        if not chart_json_str or not chart_json_str.strip():
            return None
        fig_dict = json.loads(chart_json_str)
        if not fig_dict or not isinstance(fig_dict, dict):
            return None
        return go.Figure(fig_dict)
    except Exception:
        return None

def build_chart_title(question: str) -> str:
    """Construct a clean, professional title directly derived from the question text."""
    if not question:
        return "Analysis"
    title = question.strip()
    if len(title) > 80:
        title = title[:77] + "..."
    return title

def load_cleaned_dataset(clean_path: str) -> pd.DataFrame:
    """Load a cleaned dataset regardless of file format."""
    ext = clean_path.rsplit(".", 1)[-1].lower()
    if ext == "csv":
        return pd.read_csv(clean_path)
    elif ext in ("xlsx", "xls"):
        return pd.read_excel(clean_path)
    elif ext == "json":
        return pd.read_json(clean_path)
    else:
        raise ValueError(f"Unsupported visualization dataset format: {ext}")

def generate_fallback_chart(insight: dict, clean_path: str):
    """Generate a reasonable fallback visualization if the Analyst Agent did not produce one."""
    try:
        df = load_cleaned_dataset(clean_path)
        title = build_chart_title(insight.get('question', 'Analysis'))
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if numeric_cols:
            means = [df[col].mean() for col in numeric_cols]
            return px.bar(
                x=numeric_cols,
                y=means,
                title=title,
                labels={"x": "Column", "y": "Mean Value"}
            )
        categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
        if categorical_cols:
            col = categorical_cols[0]
            counts = df[col].astype(str).value_counts().head(10)
            return px.bar(
                x=counts.index,
                y=counts.values,
                title=title,
                labels={"x": col, "y": "Count"}
            )
    except Exception as e:
        print(f"[Visualizer Fallback Error] {e}")
    return None

def run_visualizer(insights: list[dict], clean_path: str) -> list[dict]:
    if not clean_path or not os.path.exists(clean_path):
        print("[Visualizer] No valid clean file – skipping enrichment.")
        return [{**insight, "figure": None, "visualization_source": "skipped"} for insight in insights]
    """Enrich insights with Plotly figure objects, falling back to tables for crowded data."""
    enriched = []
    for insight in insights:
        answer = insight.get("answer", "")
        # If the answer contains a failure marker, skip any fallback chart.
        if any(marker in answer for marker in FAILURE_MARKERS):
            enriched.append({
                **insight,
                "figure": None,
                "visualization_source": "failed"
            })
            continue

        # ---- FIX 9: Use metadata to decide chart vs table ----
        grouping_columns = insight.get("grouping_columns", [])
        result_data = insight.get("result_data", [])
        if _should_use_table(grouping_columns, result_data):
            enriched.append({
                **insight,
                "figure": None,
                "table_data": result_data,
                "visualization_source": "table"
            })
            continue

        # ---- Normal chart flow ----
        fig, source, chart_json = None, "none", insight.get("chart_json", "")
        if chart_json:
            fig = parse_chart_json(chart_json)
            if fig is not None:
                source = "analyst_chart"
        if fig is None:
            fig = generate_fallback_chart(insight, clean_path)
            if fig is not None:
                source = "fallback_chart"
        if fig is not None:
            question = insight.get("question", "Analysis")
            title_obj = getattr(fig.layout, "title", None)
            title_text = getattr(title_obj, "text", None)
            if not title_text:
                fig.update_layout(title=build_chart_title(question))

        enriched.append({
            **insight,
            "figure": fig,
            "visualization_source": source
        })
    return enriched