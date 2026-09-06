# agents/analyst.py
import json
import re
import time
from typing import Optional
from sandbox.executor import run_code
from sandbox.validator import validate_code_ast
from utils.llm_utils import get_llm
from orchestrator.utils import safe_llm_call
from config import MAX_ANALYST_QUESTIONS, MAX_ANALYST_RETRIES
from agents.critic import validate_insight

# Centralized LLM initialization
llm = get_llm("analyst")

# Identifier patterns for numeric metric filtering
IDENTIFIER_PATTERNS = ['id', 'index', 'row', 'key', 'hash', 'serial']

def _is_identifier_column(col: str) -> bool:
    col_lower = col.lower().strip()
    return any(pattern in col_lower for pattern in IDENTIFIER_PATTERNS)

# Insightfulness filter — trivial question detection
TRIVIAL_PATTERNS = [
    r'how many (rows?|records?|entries?)',
    r'how many (products?|items?|categories?|brands?)',
    r'list all',
    r'count of',
    r'show me',
    r'what are the (categories|brands)',
    r'(highest|largest|most).* number of',
    r'(highest|largest|most).* count of',
]

def _is_trivial_question(question: str) -> bool:
    q_lower = question.lower().strip()
    for pattern in TRIVIAL_PATTERNS:
        if re.search(pattern, q_lower):
            return True
    return False

def _is_insightful_question(question: str) -> bool:
    q_lower = question.lower().strip()
    insightful_keywords = [
        'dominate', 'dominant', 'concentrate', 'concentration',
        'fragment', 'fragmentation', 'diverse', 'diversity',
        'distribution', 'represent', 'representation',
        'compare', 'comparison', 'margin', 'lead', 'trail',
        'outlier', 'anomaly', 'relationship', 'correlate',
        'trend', 'pattern', 'significant', 'majority',
        'minority', 'proportion', 'ratio', 'skew'
    ]
    return any(kw in q_lower for kw in insightful_keywords)

# Build capabilities
def build_column_capabilities(schema: dict) -> dict:
    dtypes = schema.get("dtypes", {})
    IDENTIFIER_PATTERNS_FALLBACK = ['id', 'title', 'name', 'show_id', 'index']
    schema_profile = {
        "numeric_columns": [],
        "datetime_columns": [],
        "categorical_columns": [],
        "identifier_columns": [],
        "total_columns": len(dtypes),
        "has_numeric": False,
        "has_datetime": False,
        "has_categorical": False,
    }
    for column, dtype in dtypes.items():
        col = str(column)
        dt = str(dtype).lower()
        col_lower = col.lower()
        if any(pattern in col_lower for pattern in IDENTIFIER_PATTERNS_FALLBACK):
            schema_profile["identifier_columns"].append(col)
            continue
        if any(x in dt for x in ["int", "float", "double", "decimal", "number"]):
            schema_profile["numeric_columns"].append(col)
            schema_profile["has_numeric"] = True
        elif any(x in dt for x in ["datetime", "date", "timestamp"]):
            schema_profile["datetime_columns"].append(col)
            schema_profile["has_datetime"] = True
        elif any(x in dt for x in ["category", "bool", "object", "string", "str"]):
            schema_profile["categorical_columns"].append(col)
            schema_profile["has_categorical"] = True
    return schema_profile

# Question Complexity Budget
def assess_question_complexity(question: str) -> int:
    score = 0
    ops = ['average', 'mean', 'sum', 'count', 'max', 'min', 'median']
    for op in ops:
        if op in question.lower():
            score += 1
    dims = ['and', 'by', 'per', 'for each', 'compared to']
    for dim in dims:
        if dim in question.lower():
            score += 1
    if 'after accounting' in question.lower():
        score += 2
    if 'controlling for' in question.lower():
        score += 2
    if 'interaction' in question.lower():
        score += 2
    return score

# Build question constraints (unused directly but kept)
def build_question_constraints(schema_profile: dict) -> list[str]:
    allowed = []
    blocked = []
    if schema_profile["has_numeric"]:
        allowed.append("- Aggregations (sum, mean, max) and distributions are allowed.")
    else:
        blocked.append("- DO NOT ask aggregation or statistical math questions (no numeric columns exist).")
    if schema_profile["has_datetime"]:
        allowed.append("- Time-series analysis and temporal trends are allowed.")
    else:
        blocked.append("- DO NOT ask temporal trend or time-based questions (no datetime columns exist).")
    if schema_profile["has_categorical"] and schema_profile["has_numeric"]:
        allowed.append("- Cross-tabulations and group-by comparisons are highly encouraged.")
    return allowed + blocked

# Insight-Oriented Question Generation
def generate_next_question(
    schema: dict,
    description: str,
    capabilities: dict,
    prior_findings: list,
    execution_metadata: dict,
    profile: Optional[dict] = None,
) -> str | None:
    available_dimensions = capabilities.get("categorical_columns", [])
    identifier_cols = capabilities.get("identifier_columns", [])
    available_dimensions = [c for c in available_dimensions if c not in identifier_cols]

    numeric_metrics = [c for c in capabilities.get("numeric_columns", []) if not _is_identifier_column(c)]
    has_meaningful_metrics = len(numeric_metrics) > 0

    if prior_findings:
        findings_formatted = "\n".join(
            f"- Question: {f['question']}\n  Answer Summary: {f['answer']}"
            for f in prior_findings
        )
    else:
        findings_formatted = "None. This is the first analytical step."

    profile_text = ""
    if profile:
        summary = profile.get("summary_text", "")
        if summary:
            profile_text = f"\nData Profile Summary:\n{summary}\n"

    if has_meaningful_metrics:
        question_guidance = """
Focus on questions that uncover relationships, trends, or comparisons involving numeric metrics.
Examples of GOOD questions:
- "What is the average rating by genre and which genre has the highest?"
- "Which country has the highest views and by what margin?"
- "How does runtime vary by type and which type has the most outliers?"
- "What is the total revenue per region and which region contributes the most?"
"""
    else:
        question_guidance = """
CRITICAL: This dataset has NO meaningful numeric metrics to aggregate.
DO NOT ask trivial counting questions like "How many products per category?" or "List all brands".
Instead, focus on analytical comparisons of distributions and dominance:
- "Which category dominates the catalog and by how much over the second place?"
- "Is the brand portfolio highly fragmented or concentrated around a few brands?"
- "Which product attributes are most common and which are rare?"
- "What is the distribution of categories and does any single category over-index?"
- "How diverse is the product catalog and what does that imply for business?"
- "Which categories appear underrepresented given the total portfolio?"
"""

    prompt = f"""You are a senior business analyst inspecting a fresh dataset. Your task is to generate ONE analytical, insight-producing question.

Dataset description:
{description}

{profile_text}

Available Columns for Analysis:
- Numeric Columns (can aggregate): {numeric_metrics}
- Groupable Columns (dimensions): {available_dimensions}
- Temporal Columns (time-based): {capabilities.get('datetime_columns', [])}

IMPORTANT CONSTRAINTS:
- Keep questions focused on BUSINESS INSIGHT, not just counts or lists.
- Avoid trivial enumerations (e.g., "list all categories") unless framed as a comparison or dominance question.
{question_guidance}

Prior Discoveries in this Session:
{findings_formatted}

Requirements:
- Use ONLY columns listed in Available Columns.
- Do NOT use identifier columns (like id, title, name, index).
- If all valuable angles explored, reply with: STOP

Return ONLY the raw question or STOP. No explanations. No markdown fences.
"""
    try:
        response = safe_llm_call(llm, prompt, execution_metadata)
        cleaned = response.content.strip().replace('"', '').replace("'", "")
        if cleaned.upper() == "STOP":
            return None
        return cleaned
    except Exception as e:
        if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
            raise
        return None

# Code Generation with DATA_JSON and GROUPING_COLUMNS
def generate_analysis_code(
    question: str,
    schema: dict,
    clean_path: str,
    execution_metadata: dict,
) -> str:
    datetime_cols = [
        col for col, dtype in schema.get("dtypes", {}).items()
        if any(x in str(dtype).lower() for x in ["datetime", "date", "timestamp"])
    ]
    exact_columns = schema.get("columns", list(schema.keys()))
    
    prompt = f"""Write Python code to answer this question:
Question:
{question}

Dataset:
{clean_path}

Columns:
{schema.get('columns', list(schema.keys()))}
Column Types:
{schema.get('dtypes', schema)}
Datetime Columns:
{datetime_cols}

CRITICAL: The dataset columns are exactly: {exact_columns}.
CRITICAL: Do NOT import os, subprocess, socket, sys, eval, exec. These are blocked for security. Use ONLY pandas, numpy, plotly, json, re.
CRITICAL: Never use deprecated Plotly properties like `titlefont`, `xaxis_titlefont`, `yaxis_titlefont`, `tickangle` as a top-level kwarg, or `showlegend=True` inside `update_layout` shorthand. Use the nested form instead: `title=dict(text="...", font=dict(size=14))`, and for axes use `fig.update_xaxes(title=dict(font=dict(...)))` / `fig.update_yaxes(...)`.

You MUST use these exact column names as they appear. Do not rename, simplify, or guess.
If the question mentions a column like "salary", find the exact column name from the list that contains that word, but use the exact string.
To be safe, you can add a mapping at the start of your code:
# Find the correct column names (example)
salary_col = next((c for c in df.columns if 'salary' in c.lower()), None)
dept_col = next((c for c in df.columns if 'department' in c.lower()), None)
# Then use salary_col and dept_col in your aggregation.
# If a column is not found, handle gracefully.

Requirements:
1. Read dataset using pandas.
2. Immediately convert all datetime columns.
Example:
for col in DATETIME_COLUMNS:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
3. Compute the answer.
4. Handle empty datasets safely.
5. Build a Plotly chart.
6. Print exactly:
ANSWER: <answer>
7. Print exactly:
CHART_JSON: <figure_json>
8. Print exactly:
DATA_JSON: <json_array_of_results>
9. Print exactly:
GROUPING_COLUMNS: <json_array_of_grouping_column_names>

DATA_JSON RULES:
- DATA_JSON must contain the final summarized dataset used to build the visualization, not raw source rows.
- For grouped analysis, output exactly one object per resulting group.
- Do not output the entire source dataset.
- Limit structured results to at most 100 rows.
- Use json.dumps(..., default=str) so values are JSON serializable.

GROUPING_COLUMNS RULES:
- List the actual column names used for grouping (e.g., ["Product", "Location"]).
- If no grouping (e.g., simple average), print: GROUPING_COLUMNS: []

EMPTY DATA RULES:
- Before calling: .idxmax(), .idxmin(), .iloc[0], .max(), .min(), .mean() or plotting, verify the dataframe is not empty.
Example:
if df.empty:
    print("ANSWER: No data available for this question")
    print("CHART_JSON: {{}}")
    print("DATA_JSON: []")
    print("GROUPING_COLUMNS: []")
    # Stop processing after printing these values.
- If a filter produces no rows: print: ANSWER: No data available for this question CHART_JSON: {{}} DATA_JSON: [] GROUPING_COLUMNS: [] instead of throwing an exception.

CRITICAL WARNING: 
- Use fig.to_json() to generate the chart string.
- NEVER use fig.show(), plt.show(), or any command that opens a window. This code runs headlessly and will hang the server completely if you include interactive display commands.
- NEVER assume a dataframe contains rows.
- NEVER call: idxmax() idxmin() iloc[0] without checking first.
- Always return: CHART_JSON: {{}} when no visualization can be created.
- NEVER use errors="ignore" in pandas operations (especially to_numeric or to_datetime). Use errors="coerce".
- To create DATA_JSON, use: result_df.to_dict(orient="records") and json.dumps(..., default=str).

Return ONLY Python code. No markdown. No explanation.
"""
    response = safe_llm_call(llm, prompt, execution_metadata)
    code = response.content
    code = code.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    return code

# Chart JSON validation
def validate_chart_json(chart_json: str) -> bool:
    try:
        parsed = json.loads(chart_json)
        if not isinstance(parsed, dict) or not parsed or not isinstance(parsed.get("data"), list):
            return False
        return True
    except Exception:
        return False

# Parse output with DATA_JSON and GROUPING_COLUMNS
def parse_output(output: str) -> tuple[str, str, Optional[list], list]:
    answer, chart_json, data_json, grouping_cols = "", "", None, []
    answer_match = re.search(r"ANSWER:\s*(.*?)(?:\nCHART_JSON:|\Z)", output, re.DOTALL)
    chart_match = re.search(r"CHART_JSON:\s*(.*?)(?:\nDATA_JSON:|\Z)", output, re.DOTALL)
    data_match = re.search(r"DATA_JSON:\s*(.*?)(?:\nGROUPING_COLUMNS:|\Z)", output, re.DOTALL)
    group_match = re.search(r"GROUPING_COLUMNS:\s*(.*?)$", output, re.DOTALL)

    if answer_match:
        answer = answer_match.group(1).strip()
        answer = answer.replace('\u2011', '-').replace('\u2013', '-').replace('\u2014', '-')
    if chart_match:
        chart_json = chart_match.group(1).strip()
    if data_match:
        try:
            data_json = json.loads(data_match.group(1).strip())
        except json.JSONDecodeError:
            data_json = None
    if group_match:
        try:
            grouping_cols = json.loads(group_match.group(1).strip())
            if not isinstance(grouping_cols, list):
                grouping_cols = []
        except json.JSONDecodeError:
            grouping_cols = []

    return answer, chart_json, data_json, grouping_cols

# Confidence
def calculate_confidence(answer: str, retries_used: int) -> str:
    if not answer or answer == "Could not compute" or "No data available" in answer:
        return "low"
    if retries_used == 0:
        return "high"
    return "medium"

# Retry prompt with attempt history
def build_retry_prompt(
    code: str,
    stdout: str,
    stderr: str,
    schema: dict,
    critic_reason: str | None = None,
    attempt_history: list | None = None,
) -> str:
    history_text = ""
    if attempt_history and len(attempt_history) > 1:
        history_text = "\nPREVIOUS ATTEMPTS:\n"
        for h in attempt_history[:-1]:
            status = "✅" if h.get("success", False) else "❌"
            error_preview = h.get("error", "No error")[:200]
            history_text += f"Attempt {h['attempt']}: {status} {error_preview}\n"

    prompt = f"""The following Python code failed or was rejected.
{history_text}
Reason / Errors:
{stderr}
STDOUT (if any):
{stdout}
Original Code:
{code}

Dataset Schema Context:
Columns: {schema.get('columns', list(schema.keys()))}
Column Types: {schema.get('dtypes', schema)}

Requirements:
- Fix the issue.
- Remove unsafe imports (os, subprocess, socket, sys) or blocked functions (eval, exec, __import__) if flagged.
- Use ONLY allowed packages: pandas, numpy, plotly, json, re.
- Do NOT use fig.show() or plt.show().
- Handle empty datasets safely.
- Convert datetime columns when necessary.
- NEVER use errors="ignore" in pandas. Always use errors="coerce".
- Verify dataframe rows exist before calling: idxmax() idxmin() iloc[0] max() min() mean() or generating plots.
- Ensure to print ANSWER, CHART_JSON, DATA_JSON, and GROUPING_COLUMNS exactly as required.
- Return ONLY the corrected Python code. No markdown. No explanation.
CRITICAL: Do NOT import os, subprocess, socket, sys, eval, exec. These are blocked for security. Use ONLY pandas, numpy, plotly, json, re.
CRITICAL: Never use deprecated Plotly properties like `titlefont`, `xaxis_titlefont`, `yaxis_titlefont`, `tickangle` as a top-level kwarg, or `showlegend=True` inside `update_layout` shorthand. Use the nested form instead: `title=dict(text="...", font=dict(size=14))`, and for axes use `fig.update_xaxes(title=dict(font=dict(...)))` / `fig.update_yaxes(...)`.
"""
    if critic_reason:
        prompt += f"\nCRITIC FEEDBACK FOR REGENERATION:\n{critic_reason}\nThe previous code successfully executed but produced an incorrect, incomplete, or unsatisfactory analysis.\nAdjust the analytical logic, computation steps, and chart output format to resolve the critic's concerns."
    return prompt

# Main Analyst orchestrator
def run_analyst(
    schema: dict,
    clean_path: str,
    description: str,
    execution_metadata: dict,
    max_retries: int = MAX_ANALYST_RETRIES,
    profile: Optional[dict] = None,
) -> dict:
    insights, all_steps, prior_findings = [], [], []

    # Build capabilities
    capabilities = schema.get("schema_profile")
    if not capabilities:
        print("[Analyst] Warning: schema_profile missing from schema. Falling back to heuristic builder.")
        capabilities = build_column_capabilities(schema)

    original_numeric = capabilities.get("numeric_columns", [])
    cleaned_numeric = [col for col in original_numeric if not _is_identifier_column(col)]
    capabilities["numeric_columns"] = cleaned_numeric
    capabilities["has_numeric"] = len(cleaned_numeric) > 0

    all_steps.append({"step": "Schema capability detection (sanitized)", "capabilities": capabilities})
    print(f"[Analyst] Capabilities derived: {capabilities}")

    asked_questions = set()

    for idx in range(MAX_ANALYST_QUESTIONS):
        if execution_metadata.get("llm_budget_exceeded"):
            all_steps.append({"step": f"Budget exhausted. Terminating sequential question loop at step {idx+1}."})
            break

        all_steps.append({"step": f"Generating sequential question {idx+1}..."})
        try:
            question = generate_next_question(
                schema, description, capabilities, prior_findings,
                execution_metadata,
                profile=profile
            )
        except Exception as e:
            if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
                print("[Analyst] Budget exhausted during adaptive question generation.")
                break
            raise

        if question is None:
            all_steps.append({"step": "Analyst terminated early (agent decided all areas explored)"})
            print("[Analyst] Received early STOP condition. Concluding analysis.")
            break

        q_normalized = question.lower().strip()
        if q_normalized in asked_questions:
            all_steps.append({"step": f"Question {idx+1} is a duplicate. Skipping."})
            print(f"[Analyst] Skipping duplicate question: {question}")
            continue
        asked_questions.add(q_normalized)

        if _is_trivial_question(question) and not _is_insightful_question(question):
            all_steps.append({"step": f"Question {idx+1} rejected as trivial. Skipping."})
            print(f"[Analyst] Skipping trivial question: {question}")
            retry_question = None
            try:
                retry_question = generate_next_question(
                    schema, description, capabilities, prior_findings,
                    execution_metadata,
                    profile=profile
                )
            except Exception:
                pass
            if retry_question:
                retry_q_norm = retry_question.lower().strip()
                if retry_q_norm not in asked_questions and _is_insightful_question(retry_question):
                    question = retry_question
                    asked_questions.add(retry_q_norm)
                    print(f"[Analyst] Replaced trivial question with: {question}")
                else:
                    continue
            else:
                continue

        complexity = assess_question_complexity(question)
        if complexity > 6:
            all_steps.append({"step": f"Question {idx+1} too complex (score: {complexity}). Trying to regenerate..."})
            print(f"[Analyst] Question too complex (score: {complexity}), attempting to regenerate.")
            retry_question = None
            try:
                retry_question = generate_next_question(
                    schema, description, capabilities, prior_findings,
                    execution_metadata,
                    profile=profile
                )
            except Exception:
                pass
            if retry_question:
                retry_q_norm = retry_question.lower().strip()
                if retry_q_norm not in asked_questions and _is_insightful_question(retry_question):
                    new_complexity = assess_question_complexity(retry_question)
                    if new_complexity <= 6:
                        question = retry_question
                        asked_questions.add(retry_q_norm)
                        print(f"[Analyst] Replaced overly complex question with: {question} (score: {new_complexity})")
                    else:
                        all_steps.append({"step": f"Regenerated question still too complex (score: {new_complexity}). Skipping."})
                        continue
                else:
                    continue
            else:
                continue

        all_steps.append({"step": f"Analysing question {idx+1}: {question}"})
        print(f"[Analyst] Processing adaptive question {idx+1}: {question}")

        try:
            code = generate_analysis_code(question, schema, clean_path, execution_metadata)
        except Exception as e:
            if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
                print("[Analyst] Budget exhausted during analysis code generation. Returning partial insights.")
                break
            insights.append({
                "question": question,
                "answer": "Analysis generation failed",
                "chart_json": "",
                "confidence": "low",
                "critic_reason": None,
                "grouping_columns": [],
                "result_data": None,
            })
            all_steps.append({"step": f"Question {idx+1} code generation failed", "error": str(e)})
            continue

        attempt_history = []
        answer, chart_json, retries_used, success, confidence_override, critic_skipped, fully_accepted = (
            "", "", 0, False, None, False, False
        )
        data_json = None
        grouping_columns = []
        last_critic_reason = None

        for attempt in range(max_retries):
            is_valid, reason = validate_code_ast(code)
            if not is_valid:
                retries_used += 1
                all_steps.append({"step": "AST validation failed", "reason": reason})
                attempt_history.append({"attempt": attempt+1, "success": False, "error": f"AST Blocked: {reason}"})
                try:
                    code = safe_llm_call(
                        llm,
                        build_retry_prompt(
                            code, "", f"AST Blocked: {reason}", schema,
                            attempt_history=attempt_history
                        ),
                        execution_metadata,
                    ).content
                    continue
                except Exception as e:
                    if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
                        print("[Analyst] Budget exhausted during AST retry generation.")
                        break
                    else:
                        raise

            start = time.time()
            result = run_code(code)
            print(f"[Analyst] Execution attempt {attempt + 1} took {round(time.time() - start, 2)}s")

            attempt_history.append({
                "attempt": attempt + 1,
                "success": result["success"],
                "error": result.get("error", ""),
                "output": result.get("output", "")[:500],
            })

            if result["success"]:
                print("[Analyst] Execution Success")
                answer, chart_json, data_json, grouping_columns = parse_output(result["output"])
                if chart_json and not validate_chart_json(chart_json):
                    chart_json = ""

                try:
                    critic_res = validate_insight(question, answer, code, chart_json, execution_metadata)
                    verdict, reason = critic_res.get("verdict", "accept"), critic_res.get("reason", "")
                except Exception as e:
                    if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
                        print("[Analyst] Budget exhausted during critic evaluation.")
                        break
                    verdict, reason = "accept", f"Critic evaluation bypassed due to runtime exception: {str(e)}"

                last_critic_reason = reason

                all_steps.append({
                    "step": f"Critic evaluation (attempt {attempt + 1}) for Q{idx+1}: {verdict.upper()} (Reason: {reason})"
                })

                if verdict == "accept":
                    success, fully_accepted = True, True
                    all_steps.append({"step": f"Analysis succeeded on attempt {attempt + 1}"})
                    break
                elif verdict == "weak_accept":
                    success, confidence_override = True, "medium"
                    all_steps.append({"step": f"Analysis weakly accepted on attempt {attempt + 1} (Reason: {reason})"})
                    break
                elif verdict == "skip":
                    success, critic_skipped, confidence_override, answer, chart_json = (
                        False, True, "low", f"Could not compute (Skipped by critic: {reason})", ""
                    )
                    all_steps.append({"step": f"Analysis skipped by critic on attempt {attempt + 1} (Reason: {reason})"})
                    break
                elif verdict == "regenerate":
                    print(f"[Analyst] Critic requested regeneration: {reason}")
                    if attempt == max_retries - 1:
                        all_steps.append({
                            "step": f"Regeneration requested by critic but retries exhausted. (Reason: {reason})"
                        })
                        confidence_override, answer, chart_json = "low", (
                            f"Could not compute (Failed critic review: {reason})"
                        ), ""
                        break
                    retries_used += 1
                    try:
                        code = safe_llm_call(
                            llm,
                            build_retry_prompt(
                                code,
                                result.get("output", ""),
                                result.get("error", "") or "No runtime error, but analysis failed critic review.",
                                schema,
                                critic_reason=reason,
                                attempt_history=attempt_history,
                            ),
                            execution_metadata,
                        ).content
                        continue
                    except Exception as e:
                        if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
                            print("[Analyst] Budget exhausted during critic retry generation.")
                            break
                        all_steps.append({"step": "Retry generation failed", "error": str(e)})
                        break
            else:
                retries_used += 1
                print(f"[Analyst] Execution Failed: {result.get('error', '')}")
                all_steps.append({
                    "step": f"Analysis failed (attempt {attempt + 1})",
                    "stdout": result.get("output", ""),
                    "stderr": result.get("error", ""),
                })
                try:
                    code = safe_llm_call(
                        llm,
                        build_retry_prompt(
                            code,
                            result.get("output", ""),
                            result.get("error", ""),
                            schema,
                            attempt_history=attempt_history,
                        ),
                        execution_metadata,
                    ).content
                except Exception as e:
                    if "LLM budget exceeded" in str(e) or execution_metadata.get("llm_budget_exceeded"):
                        print("[Analyst] Budget exhausted during error correction retry.")
                        break
                    all_steps.append({"step": "Retry generation failed", "error": str(e)})
                    break

        if execution_metadata.get("llm_budget_exceeded"):
            print("[Analyst] Budget exhausted post-execution. Exiting loop.")
            break

        if not success and not critic_skipped:
            all_steps.append({"step": f"Analysis failed after {max_retries} attempts", "question": question})

        confidence = confidence_override if confidence_override else calculate_confidence(answer, retries_used)

        insight = {
            "question": question,
            "answer": answer if answer else "Could not compute",
            "chart_json": chart_json,
            "confidence": confidence,
            "critic_reason": last_critic_reason if success else None,
            "grouping_columns": grouping_columns,
            "result_data": data_json,
        }
        insights.append(insight)

        if success and answer and fully_accepted:
            prior_findings.append({"question": question, "answer": answer[:300]})

    return {"insights": insights, "steps": all_steps}