# orchestrator/graph.py
import os
import time
from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from agents.ingestion import run_ingestion, generate_schema_profile
from agents.cleaner import run_cleaner
from agents.analyst import run_analyst
from agents.visualizer import run_visualizer
from agents.narrator import run_narrator
from utils.file_reader import read_file
from agents.profiler import profile_dataset

# Pipeline State
class PipelineState(TypedDict):
    file_path: str
    schema: Optional[dict]
    description: Optional[str]
    clean_path: Optional[str]
    cleaning_steps: Optional[list]
    cleaning_success: Optional[bool]
    insights: Optional[list]
    visualized_insights: Optional[list]
    analysis_steps: Optional[list]
    analysis_success: Optional[bool]
    visualization_success: Optional[bool]
    visualization_summary: Optional[dict]
    summary: Optional[str]
    flagged_insights: Optional[list]
    execution_metadata: Optional[dict]
    pipeline_summary: Optional[dict]
    error: Optional[str]
    visualization_skipped: Optional[bool]
    error_details: Optional[list]

# Timing Helper
def record_timing(metadata: dict, agent_name: str, start_time: float, error: dict | None = None):
    """Records agent timing diagnostics and optional structured error metadata for cost auditing and developer debugging."""
    end_time = time.time()
    metadata[agent_name] = {
        "start_time": start_time,
        "end_time": end_time,
        "duration_seconds": round(end_time - start_time, 2)
    }
    if error is not None:
        metadata[agent_name]["error"] = error
    return metadata

# Error Helper
def append_error(state: PipelineState, agent: str, exc: Exception) -> list:
    """Consolidates structured error traces directly into the pipeline state."""
    errors = state.get("error_details") or []
    errors.append({"agent": agent, "error_type": type(exc).__name__, "error_message": str(exc)})
    return errors

# Conditional Routing
def route_after_node(state: PipelineState) -> str:
    if state.get("error") is not None:
        print(f"[Pipeline Halted] {state['error']}")
        return "end"
    return "continue"

# Phase 5 Conditional Router
def route_after_analyst(state: PipelineState) -> str:
    """Routes to Visualizer if eligible columns exist, otherwise bypasses."""
    if state.get("error") is not None:
        print(f"[Pipeline Halted] {state['error']}")
        return "end"
    if state.get("visualization_skipped", False):
        print("[Router] No eligible columns detected. Skipping Visualizer node.")
        return "narrator"
    return "visualizer"

# ============================================================
# Node Functions
# ============================================================

def ingestion_node(state: PipelineState) -> PipelineState:
    print("[Orchestrator] Running Ingestion Agent...")
    start_time = time.time()

    # CHANGE #6: Get metadata once
    metadata = state.get("execution_metadata")
    if metadata is None:
        metadata = {"llm_call_count": 0, "llm_budget_exceeded": False, "truncated": False}
        state["execution_metadata"] = metadata

    try:
        result = run_ingestion(state["file_path"])
        error_details, error_val = state.get("error_details") or [], None
        if result.get("error_detail"):
            err = result["error_detail"]
            error_details.append({"agent": "ingestion", "error_type": err["error_type"], "error_message": err["error_message"]})
            error_val = {"type": err["error_type"], "message": err["error_message"]}
        return {
            **state,
            "schema": result["schema"],
            "description": result["description"],
            "error_details": error_details,
            "execution_metadata": record_timing(metadata, "ingestion", start_time, error=error_val)
        }
    except Exception as e:
        error_details = append_error(state, "ingestion", e)
        return {
            **state,
            "error": f"Ingestion failed: {str(e)}",
            "error_details": error_details,
            "execution_metadata": record_timing(metadata, "ingestion", start_time, error={"type": type(e).__name__, "message": str(e)})
        }

def cleaner_node(state: PipelineState) -> PipelineState:
    print("[Orchestrator] Running Cleaner Agent...")
    start_time = time.time()

    # CHANGE #6: Get metadata once
    metadata = state.get("execution_metadata")
    if metadata is None:
        metadata = {"llm_call_count": 0, "llm_budget_exceeded": False, "truncated": False}
        state["execution_metadata"] = metadata

    try:
        schema = state.get("schema") or {}
        result = run_cleaner(schema, state.get("file_path") or "", state.get("execution_metadata") or {})
        cleaning_steps, cleaning_success, clean_path = result["steps"], result["success"], result["clean_path"]
        if not cleaning_success:
            error_details = state.get("error_details") or []
            error_details.append({
                "agent": "cleaner",
                "error_type": "CleanerFailure",
                "error_message": result.get("error_detail", {}).get("error_message", "Cleaning failed")
            })
            return {
                **state,
                "clean_path": None,
                "cleaning_success": False,
                "error": "Cleaning failed – pipeline halted",
                "error_details": error_details,
                "execution_metadata": record_timing(state.get("execution_metadata") or {}, "cleaner", start_time, error={"type": "CleanerFailure", "message": "Cleaning failed"})
            }
        error_details, error_val = state.get("error_details") or [], None
        if result.get("error_detail"):
            err = result["error_detail"]
            error_details.append({"agent": "cleaner", "error_type": err["error_type"], "error_message": err["error_message"]})
            error_val = {"type": err["error_type"], "message": err["error_message"]}

        if result["success"] and clean_path:
            clean_df = read_file(clean_path)
            print("\n=== CLEAN DF DTYPES ===")
            print(clean_df.dtypes)
            print("=======================\n")

            schema_dict = state.get("schema") or {}
            original_columns = schema_dict.get("columns", [])
            print(f"[DEBUG] Original columns from schema: {original_columns}")
            print(f"[DEBUG] Cleaned columns (before fix): {list(clean_df.columns)}")

            # Drop extra index column if present
            if len(clean_df.columns) == len(original_columns) + 1:
                first_col = clean_df.columns[0]
                if str(first_col).strip().lower().startswith("unnamed") or str(first_col).strip() == "":
                    try:
                        col_values = clean_df.iloc[:, 0]
                        if col_values.dtype in ['int64', 'float64'] and (col_values == range(len(col_values))).all():
                            print("[Graph] Dropping extra index column (first column).")
                            clean_df = clean_df.iloc[:, 1:]
                    except Exception:
                        pass

            # Restore original column names
            if original_columns and len(original_columns) == len(clean_df.columns):
                broken_count = sum(
                    1 for c in clean_df.columns
                    if str(c).strip().lower().startswith("unnamed")
                    or str(c).strip().lower().startswith("column")
                    or str(c).strip().isdigit()
                    or str(c).strip() == ""
                )
                if broken_count > len(clean_df.columns) * 0.5:
                    print("[Graph] Cleaned CSV has broken headers. Restoring original column names.")
                    clean_df.columns = original_columns
                    clean_df.to_csv(clean_path, index=False)
                    print("[Graph] Cleaned CSV overwritten with correct headers.")

            print(f"[DEBUG] Cleaned columns (after fix): {list(clean_df.columns)}")

            print("\n=== GENERATED PROFILE ===")
            print(generate_schema_profile(clean_df))
            print("=========================\n")
            schema = {
                "columns": list(clean_df.columns),
                "dtypes": {col: str(dtype) for col, dtype in clean_df.dtypes.items()},
                "shape": clean_df.shape,
                "nulls": clean_df.isnull().sum().to_dict(),
                "sample": clean_df.head(3).to_dict(orient="records"),
                "schema_profile": generate_schema_profile(clean_df)
            }
            print("[Graph] Schema refreshed after cleaning")

        return {
            **state,
            "clean_path": clean_path,
            "cleaning_steps": cleaning_steps,
            "cleaning_success": cleaning_success,
            "schema": schema,
            "error_details": error_details,
            "execution_metadata": record_timing(metadata, "cleaner", start_time, error=error_val)
        }
    except Exception as e:
        error_details = append_error(state, "cleaner", e)
        if metadata.get("llm_budget_exceeded"):
            metadata["truncated"] = True
            return {
                **state,
                "cleaning_success": False,
                "error_details": error_details,
                "execution_metadata": record_timing(metadata, "cleaner", start_time, error={"type": type(e).__name__, "message": str(e)})
            }
        return {
            **state,
            "error": f"Cleaning failed: {str(e)}",
            "error_details": error_details,
            "execution_metadata": record_timing(metadata, "cleaner", start_time, error={"type": type(e).__name__, "message": str(e)})
        }

def analyst_node(state: PipelineState) -> PipelineState:
    print("[Orchestrator] Running Analyst Agent...")
    start_time = time.time()

    # Get metadata once
    metadata = state.get("execution_metadata")
    if metadata is None:
        metadata = {"llm_call_count": 0, "llm_budget_exceeded": False, "truncated": False}
        state["execution_metadata"] = metadata

    # Skip analysis if cleaning failed
    if not state.get("cleaning_success", False):
        print("[Analyst] Cleaning failed. Skipping analysis.")
        return {
            **state,
            "insights": [],
            "analysis_steps": [{"step": "Analysis skipped because data cleaning failed"}],
            "analysis_success": False,
            "visualization_skipped": True,
            "execution_metadata": record_timing(metadata, "analyst", start_time)
        }

    # Wrap in try/except
    try:
        schema = state.get("schema") or {}

        # Load cleaned DataFrame for profiling
        clean_df = None
        clean_path = state.get("clean_path")

        if clean_path:
            try:
                clean_df = read_file(clean_path)
                print("[Analyst] Cleaned data loaded for profiling.")
            except Exception as e:
                print(f"[Analyst] Could not load cleaned data: {e}")

        # Generate dataset profile
        profile = None
        if clean_df is not None:
            try:
                profile = profile_dataset(clean_df)
                print("[Analyst] Dataset profile generated successfully.")
            except Exception as e:
                print(f"[Analyst] Profiling failed (continuing without profile): {e}")

        # Generate schema_profile if missing
        if "schema_profile" not in schema and clean_df is not None:
            try:
                schema["schema_profile"] = generate_schema_profile(clean_df)
                state["schema"] = schema
                print("[Analyst] Schema profile generated from cleaned CSV.")
            except Exception as e:
                print(f"[Analyst] Could not generate schema profile: {e}")


        # Run the Analyst with profile
        description = state.get("description") or ""
        result = run_analyst(
            schema,
            clean_path or "",
            description,
            metadata,
            profile=profile  # <-- CHANGE #10: Pass profile here
        )
        insights = result.get("insights") or []

        # 3. Compute visualization_skipped
        profile_data = schema.get("schema_profile", {})
        has_numeric = profile_data.get("has_numeric", False)
        has_categorical = profile_data.get("has_categorical", False)

        # Fallback heuristic: treat columns with price/quantity as numeric
        if not has_numeric:
            numeric_keywords = ['price', 'amount', 'salary', 'quantity', 'revenue', 'cost', 'total']
            for col in schema.get("columns", []):
                if any(kw in col.lower() for kw in numeric_keywords):
                    has_numeric = True
                    break

        visualization_skipped = not (has_numeric or has_categorical)

        return {
            **state,
            "insights": insights,
            "analysis_steps": result["steps"],
            "analysis_success": bool(insights) and any(i.get("answer") != "Could not compute" for i in insights),
            "visualization_skipped": visualization_skipped,
            "execution_metadata": record_timing(metadata, "analyst", start_time)
        }

    except Exception as e:
        error_details = append_error(state, "analyst", e)
        if metadata.get("llm_budget_exceeded"):
            metadata["truncated"] = True
            return {
                **state,
                "analysis_success": False,
                "error_details": error_details,
                "execution_metadata": record_timing(metadata, "analyst", start_time, error={"type": type(e).__name__, "message": str(e)})
            }
        return {
            **state,
            "error": f"Analysis failed: {str(e)}",
            "error_details": error_details,
            "execution_metadata": record_timing(metadata, "analyst", start_time, error={"type": type(e).__name__, "message": str(e)})
        }
    

def visualizer_node(state: PipelineState) -> PipelineState:
    print("[Orchestrator] Running Visualizer Agent...")
    start_time = time.time()

    # CHANGE #6: Get metadata once
    metadata = state.get("execution_metadata")
    if metadata is None:
        metadata = {"llm_call_count": 0, "llm_budget_exceeded": False, "truncated": False}
        state["execution_metadata"] = metadata

    # CHANGE #4: Check if clean_path exists
    clean_path = state.get("clean_path")
    cleaning_success = state.get("cleaning_success", False)
    if not clean_path or not os.path.exists(clean_path):
        print("[Visualizer] No clean data available. Skipping visualization.")
        return {
            **state,
            "visualized_insights": [],
            "visualization_success": False,
            "visualization_skipped": True,
            "execution_metadata": record_timing(metadata, "visualizer", start_time)
        }

    try:
        insights = state.get("insights") or []
        enriched_insights = run_visualizer(insights, clean_path) or []
        visualization_summary = {"analyst_chart": 0, "fallback_chart": 0, "none": 0}
        for insight in enriched_insights:
            source = insight.get("visualization_source", "none")
            visualization_summary[source] = visualization_summary.get(source, 0) + 1
        visualization_success = (bool(enriched_insights) and any(ins.get("figure") is not None for ins in enriched_insights))
        return {
            **state,
            "visualized_insights": enriched_insights,
            "visualization_success": visualization_success,
            "execution_metadata": record_timing(metadata, "visualizer", start_time),
            "visualization_summary": visualization_summary
        }
    except Exception as e:
        error_details = append_error(state, "visualizer", e)
        return {
            **state,
            "error": f"Visualization failed: {str(e)}",
            "error_details": error_details,
            "execution_metadata": record_timing(metadata, "visualizer", start_time, error={"type": type(e).__name__, "message": str(e)})
        }

def narrator_node(state: PipelineState) -> PipelineState:
    print("[Orchestrator] Running Narrator Agent...")
    start_time = time.time()

    # CHANGE #6: Get metadata once
    metadata = state.get("execution_metadata")
    if metadata is None:
        metadata = {"llm_call_count": 0, "llm_budget_exceeded": False, "truncated": False}
        state["execution_metadata"] = metadata

    try:
        description = state.get("description") or ""
        insights = state.get("insights") or []
        result = run_narrator(description, insights, metadata)
        error_details, error_val = state.get("error_details") or [], None
        if result.get("error_detail"):
            err = result["error_detail"]
            error_details.append({"agent": "narrator", "error_type": err["error_type"], "error_message": err["error_message"]})
            error_val = {"type": err["error_type"], "message": err["error_message"]}
        return {
            **state,
            "summary": result["summary"],
            "flagged_insights": result["flagged_insights"],
            "error_details": error_details,
            "execution_metadata": record_timing(metadata, "narrator", start_time, error=error_val)
        }
    except Exception as e:
        if metadata.get("llm_budget_exceeded"):
            metadata["truncated"] = True
            return {
                **state,
                "summary": "Analysis was truncated because the LLM budget limit was reached. Returning available insights.",
                "error_details": append_error(state, "narrator", e),
                "execution_metadata": record_timing(metadata, "narrator", start_time, error={"type": type(e).__name__, "message": str(e)})
            }
        return {
            **state,
            "error": f"Narration failed: {str(e)}",
            "error_details": append_error(state, "narrator", e),
            "execution_metadata": record_timing(metadata, "narrator", start_time, error={"type": type(e).__name__, "message": str(e)})
        }

# Graph Builder
def build_pipeline():
    graph = StateGraph(PipelineState)
    graph.add_node("ingestion", ingestion_node)
    graph.add_node("cleaner", cleaner_node)
    graph.add_node("analyst", analyst_node)
    graph.add_node("visualizer", visualizer_node)
    graph.add_node("narrator", narrator_node)
    graph.set_entry_point("ingestion")
    graph.add_conditional_edges("ingestion", route_after_node, {"continue": "cleaner", "end": END})
    graph.add_conditional_edges("cleaner", route_after_node, {"continue": "analyst", "end": END})
    graph.add_conditional_edges("analyst", route_after_analyst, {"visualizer": "visualizer", "narrator": "narrator", "end": END})
    graph.add_conditional_edges("visualizer", route_after_node, {"continue": "narrator", "end": END})
    graph.add_edge("narrator", END)
    return graph.compile()

PIPELINE = build_pipeline()

# Summary Builder Helper
def build_pipeline_summary(result: dict) -> dict:
    successful_agents, failed_agents = [], []
    (successful_agents if result.get("schema") else failed_agents).append("ingestion")
    (successful_agents if result.get("cleaning_success") else failed_agents).append("cleaner")
    (successful_agents if result.get("analysis_success") else failed_agents).append("analyst")
    if not result.get("visualization_skipped"):
        (successful_agents if result.get("visualization_success") else failed_agents).append("visualizer")
    (successful_agents if result.get("summary") else failed_agents).append("narrator")

    metadata = result.get("execution_metadata", {})
    total_pipeline_time = round(sum(info.get("duration_seconds", 0) for key, info in metadata.items() if isinstance(info, dict) and key not in ["llm_call_count", "llm_budget_exceeded", "truncated"]), 2)
    return {
        "total_pipeline_time": total_pipeline_time,
        "successful_agents": successful_agents,
        "failed_agents": failed_agents,
        "llm_call_count": metadata.get("llm_call_count", 0),
        "llm_budget_exceeded": metadata.get("llm_budget_exceeded", False),
        "truncated": metadata.get("truncated", False),
        "visualization_skipped": result.get("visualization_skipped", False),
        "error_details": result.get("error_details", [])
    }

# Public Entry Point
def run_pipeline(file_path: str):
    initial_state: PipelineState = {
        "file_path": file_path,
        "schema": None,
        "description": None,
        "clean_path": None,
        "cleaning_steps": None,
        "cleaning_success": None,
        "insights": None,
        "analysis_steps": None,
        "analysis_success": None,
        "summary": None,
        "flagged_insights": None,
        "execution_metadata": {"llm_call_count": 0, "llm_budget_exceeded": False, "truncated": False},
        "pipeline_summary": None,
        "error": None,
        "visualized_insights": None,
        "visualization_success": None,
        "visualization_summary": None,
        "visualization_skipped": False,
        "error_details": []
    }
    result = PIPELINE.invoke(initial_state)
    if result.get("error"):
        print(f"[Pipeline Terminated] {result['error']}")
    result["pipeline_summary"] = build_pipeline_summary(result)
    result["execution_metadata"] = result.get("execution_metadata", {})
    return result