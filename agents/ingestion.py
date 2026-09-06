# agents/ingestion.py
import pandas as pd
from utils.file_reader import read_file
from utils.llm_utils import get_llm, invoke_llm_with_backoff
from pandas.api.types import (
    is_numeric_dtype,
    is_datetime64_any_dtype,
    is_object_dtype,
    is_bool_dtype,
)

# Centralized LLM initialization
llm = get_llm("ingestion")


def _is_valid_numeric_column(df: pd.DataFrame, col: str) -> bool:
    """
    Check if a numeric column actually contains meaningful numeric data.
    Prevents treating corrupted text columns (all NaN) as valid numerics.
    """
    if not is_numeric_dtype(df[col]):
        return False
    # If more than 80% of values are null/NaN, it's likely corrupted text
    null_pct = df[col].isna().mean()
    if null_pct > 0.8:
        return False
    # If the column has very few unique values, it might be corrupted
    # (e.g., all NaN, or only a single value)
    if df[col].nunique() <= 2:
        return False
    return True


def generate_schema_profile(df: pd.DataFrame) -> dict:
    """
    Build a structural profile of the DataFrame for the Analyst.

    Detects numeric, datetime, and categorical columns.
    Also detects common year/period columns that are stored as strings.
    """
    # Only keep numeric columns that are not corrupted
    num_cols = [col for col in df.columns if _is_valid_numeric_column(df, col)]
    dt_cols = [col for col in df.columns if is_datetime64_any_dtype(df[col])]

    # Detect year/period columns (often stored as strings)
    temporal_keywords = {"year", "release_year", "period", "season"}
    for col in df.columns:
        col_lower = col.lower()
        if col_lower in temporal_keywords:
            try:
                # Attempt conversion; if it works, treat as datetime
                pd.to_datetime(df[col], errors="coerce")
                if col not in dt_cols:
                    dt_cols.append(col)
            except Exception:
                pass  # Not convertible, keep as categorical

    cat_cols = []
    for col in df.columns:
        dtype_str = str(df[col].dtype).lower()
        if (
            is_object_dtype(df[col])
            or dtype_str == "str"
            or "string" in dtype_str
            or isinstance(df[col].dtype, pd.CategoricalDtype)
            or is_bool_dtype(df[col])
        ):
            cat_cols.append(col)

    return {
        "numeric_columns": num_cols,
        "datetime_columns": dt_cols,
        "categorical_columns": cat_cols,
        "total_columns": len(df.columns),
        "has_numeric": len(num_cols) > 0,
        "has_datetime": len(dt_cols) > 0,
        "has_categorical": len(cat_cols) > 0,
    }


def describe_dataset(df: pd.DataFrame) -> str:
    """Use Gemini to generate a natural‑language description of the dataset."""
    all_columns = df.columns.tolist()
    dtypes = str(df.dtypes.to_dict())
    shape = str(df.shape)

    sample_df = df.head(5).iloc[:, :20].copy()
    for col in sample_df.columns:
        if sample_df[col].dtype == "object":
            sample_df[col] = sample_df[col].astype(str).str.slice(0, 100)

    sample = sample_df.to_string()

    prompt = f"""
You are a data analyst.

Look at this dataset sample and describe what it contains.

Shape: {shape}

Columns ({len(all_columns)} total):
{all_columns}

Column Types:
{dtypes}

Sample Data (first 20 columns shown):
{sample}

In 2-3 sentences, describe:
- what this dataset is about
- what time period or entities it covers
- what key metrics are present

Be specific and factual.
Do not make up data.
"""
    response = invoke_llm_with_backoff(llm, prompt)
    return response.content


def run_ingestion(file_path: str) -> dict:
    """
    Main entry point for the Ingestion Agent.

    Returns:
        dict: Contains DataFrame, schema, description, and optional error details.
    """
    df = read_file(file_path)

    schema = {
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "shape": df.shape,
        "nulls": df.isnull().sum().to_dict(),
        "sample": df.head(3).to_dict(orient="records"),
    }

    description = "Dataset description unavailable."
    error_detail = None

    try:
        description = describe_dataset(df)
    except Exception as e:
        print(f"[Ingestion Gemini Error] {str(e)}")
        error_detail = {"error_type": type(e).__name__, "error_message": str(e)}
        description = f"Dataset description unavailable: {str(e)}"

    return {
        "df": df,
        "schema": schema,
        "description": description,
        "error_detail": error_detail,
    }