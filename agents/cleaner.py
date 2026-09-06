# agents/cleaner.py
import os
import json
import re
from sandbox.executor import run_code
from sandbox.validator import validate_code_ast
from utils.llm_utils import (
    get_llm,
    strip_code_fences
)
from orchestrator.utils import safe_llm_call

llm = get_llm("cleaner")

def get_output_path(file_path: str) -> str:
    base, _ = os.path.splitext(file_path)
    return f"{base}_clean.csv"

def build_cleaning_prompt(schema: dict, file_path: str, clean_path: str) -> str:
    read_code = f"""
from utils.file_reader import read_file
df = read_file(r'{file_path}')
"""
    return f"""
You are a Python data-cleaning expert using Pandas.
Dataset schema:
Columns: {schema.get('columns', [])}
Data types: {schema.get('dtypes', {})}
Null counts: {schema.get('nulls', {})}
Sample rows: {json.dumps(schema.get('sample', []), default=str)}

Write Python code that:
1. Imports pandas
2. Imports:
from utils.file_reader import read_file
3. Reads the dataset using:
{read_code}
4. Fill numeric nulls with the column median.
5. Fill categorical nulls with 'Unknown'.
6. Remove exact duplicate rows.
7. Convert obvious date columns to datetime.
8. Standardize text columns safely.
9. MANDATORY:
df.to_csv(
    r'{clean_path}',
    index=False
)
The output MUST be saved EXACTLY to this path.
Do NOT change the filename.
Do NOT create another filename.
Do NOT use a relative path.
10. Print: CLEANED ROWS:

CRITICAL RULES:
- Before using .str methods, verify the column is a string column.
  Example:
  if pd.api.types.is_string_dtype(df[col]):
      df[col] = (
          df[col]
          .astype(str)
          .str.strip()
          .str.title()
      )
- NEVER use inplace=True.
  BAD: df[col].fillna(value, inplace=True)
  GOOD: df[col] = df[col].fillna(value)
- NEVER use chained assignments.
  BAD: df[df["sales"] > 0]["region"] = "North"
  GOOD: mask = df["sales"] > 0
  df.loc[mask, "region"] = "North"

Return ONLY Python code. No markdown. No explanations.
"""

def build_retry_prompt(original_code: str, stdout: str, stderr: str) -> str:
    return f"""
The following generated Python code failed.
STDOUT: {stdout}
STDERR: {stderr}
Original code:
{original_code}

Fix the code so it executes successfully.

Requirements:
- Fix the issue.
- Remove unsafe imports or unsupported libraries.
- Use only: pandas, numpy, utils.file_reader
- Do NOT use: os, subprocess, socket, sys, eval, exec.
- Save output to the same path.
- NEVER use inplace=True.
- NEVER use chained assignments.
- Verify a column is a string before using .str methods.

Return ONLY Python code. No markdown. No explanations.
"""

def generate_code(prompt: str, execution_metadata: dict | None = None) -> str:
    if execution_metadata is None:
        execution_metadata = {}
    try:
        response = safe_llm_call(llm, prompt, execution_metadata)
        content = response.content if hasattr(response, 'content') else str(response)
        return strip_code_fences(content)
    except Exception as e:
        if "LLM budget exceeded" in str(e):
            raise
        print(f"[Cleaner Gemini Error] {str(e)}")
        raise RuntimeError(f"Gemini generation failed: {str(e)}")

def run_cleaner(schema: dict, file_path: str, execution_metadata: dict | None = None, max_retries: int = 3) -> dict:
    if execution_metadata is None:
        execution_metadata = {}
    steps = []
    clean_path = get_output_path(file_path)
    error_detail = None

    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        steps.append({"step": "PDF detected - bypassing cleaner"})
        return {"clean_path": file_path, "steps": steps, "success": True, "error_detail": None, "pdf_bypass": True}

    try:
        prompt = build_cleaning_prompt(schema, file_path, clean_path)
        code = generate_code(prompt, execution_metadata)
    except Exception as e:
        steps.append({"step": "Cleaner generation failed", "error": str(e)})
        return {
            "clean_path": file_path,
            "steps": steps,
            "success": False,
            "error_detail": {"error_type": type(e).__name__, "error_message": str(e)}
        }

    steps.append({"step": "Generated cleaning code", "code": code})

    for attempt in range(max_retries):
        is_valid, reason = validate_code_ast(code)
        if not is_valid:
            steps.append({
                "step": f"AST validation failed (attempt {attempt + 1})",
                "error": reason
            })
            error_detail = {"error_type": "ASTValidationError", "error_message": reason}
            try:
                retry_prompt = build_retry_prompt(code, "", f"AST Blocked: {reason}")
                code = generate_code(retry_prompt, execution_metadata)
                steps.append({"step": f"Generated fixed code (attempt {attempt + 2})", "code": code})
                continue
            except Exception as e:
                steps.append({"step": "Gemini retry generation failed", "error": str(e)})
                error_detail = {"error_type": type(e).__name__, "error_message": str(e)}
                break

        result = run_code(code)
        if result["success"]:
            if not os.path.exists(clean_path):
                steps.append({
                    "step": f"Attempt {attempt + 1} completed but output file missing",
                    "error": f"{clean_path} was not created",
                    "generated_code": code
                })
                error_detail = {"error_type": "FileNotFoundError", "error_message": f"{clean_path} was not created"}
            else:
                steps.append({
                    "step": f"Code ran successfully on attempt {attempt + 1}",
                    "output": result["output"]
                })
                return {"clean_path": clean_path, "steps": steps, "success": True, "error_detail": None}
        else:
            steps.append({
                "step": f"Code failed (attempt {attempt + 1})",
                "stdout": result["output"],
                "error": result["error"]
            })
            error_detail = {"error_type": "ExecutionError", "error_message": str(result.get("error"))}
            try:
                retry_prompt = build_retry_prompt(code, result.get("output", ""), result.get("error", ""))
                code = generate_code(retry_prompt, execution_metadata)
                steps.append({"step": f"Generated fixed code (attempt {attempt + 2})", "code": code})
            except Exception as e:
                steps.append({"step": "Gemini retry generation failed", "error": str(e)})
                error_detail = {"error_type": type(e).__name__, "error_message": str(e)}
                break

    steps.append({"step": "All retries failed — returning original data"})
    return {"clean_path": file_path, "steps": steps, "success": False, "error_detail": error_detail}