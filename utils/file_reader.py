# utils/file_reader.py

import os
import re
import pandas as pd


def clean_candidate_name(col_value) -> str:
    val = str(col_value).strip().lower()
    return re.sub(r'\.\d+$', '', val)


def evaluate_probe_schema(candidate_headers: list, remaining_rows: int) -> float:
    if not candidate_headers:
        return -float('inf')
    nan_count = sum(pd.isna(v) or str(v).strip() == "" for v in candidate_headers)
    clean_headers = [
        clean_candidate_name(v) for v in candidate_headers
        if pd.notna(v) and str(v).strip() != ""
    ]
    if not clean_headers:
        return -float('inf')
    unique_headers = len(set(clean_headers))
    duplicate_count = len(clean_headers) - unique_headers
    text_header_count = sum(1 for h in clean_headers if re.search(r'[a-z]{2,}', h, re.I))
    score = 0
    score += unique_headers * 2
    score += text_header_count * 1.5
    score -= nan_count * 5
    score -= duplicate_count * 10
    score += min(remaining_rows, 5) * 0.5
    return score


def detect_header_from_probe(probe_df: pd.DataFrame, max_scan: int = 15) -> int:
    best_row = 0
    best_score = -float('inf')
    scan_limit = min(max_scan, len(probe_df))
    probe_values = probe_df.values.tolist()
    total_rows = len(probe_values)
    for row_idx in range(scan_limit):
        candidate_headers = probe_values[row_idx]
        remaining_rows = total_rows - row_idx - 1
        score = evaluate_probe_schema(candidate_headers, remaining_rows)
        if row_idx == 0:
            best_score = score
        else:
            threshold = best_score * 1.15 if best_score > 0 else best_score + 2
            if score >= threshold:
                best_score = score
                best_row = row_idx
    return best_row


def is_schema_broken(df: pd.DataFrame) -> bool:
    """Return True if > 50% of column names are garbage (Unnamed, empty, digits, etc.)."""
    if df.empty:
        return True
    cols = [str(c).strip().lower() for c in df.columns]
    bad_count = 0
    for c in cols:
        if c.startswith("unnamed") or c.startswith("column") or c.isdigit() or c in ["nan", ""]:
            bad_count += 1
    return (bad_count / len(cols)) >= 0.5


def read_csv_with_fallback(file_path: str, **kwargs) -> pd.DataFrame:
    encodings = ["utf-8", "utf-8-sig", "cp1252", "latin1", "utf-16"]
    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(file_path, encoding=enc, **kwargs)
        except (UnicodeDecodeError, pd.errors.ParserError) as e:
            last_error = e
    raise ValueError(f"Could not read CSV file {os.path.basename(file_path)}: {last_error}")


def _clean_header_row(row_data: list) -> list:
    """Convert row cells to column names, filling empty/NaN with Column_N."""
    cleaned = []
    for idx, val in enumerate(row_data):
        if pd.isna(val) or str(val).strip() == "":
            cleaned.append(f"Column_{idx}")
        else:
            cleaned.append(str(val).strip())
    return cleaned


def smart_read(file_path: str, ext: str) -> pd.DataFrame:
    """
    Intelligently read a file.
    Strategy:
    1. First try reading normally with header=0 (or default header).
    2. If the result has a good schema, return it.
    3. If the schema is broken, fall back to probe-based header detection.
    """
    try:
        # --- ATTEMPT 1: NORMAL READ with default header ---
        if ext == ".csv":
            df_normal = read_csv_with_fallback(file_path, sep=None, engine="python")
        else:
            df_normal = pd.read_excel(file_path)

        # If the normal read gives a valid schema (not broken), return it immediately.
        if not is_schema_broken(df_normal):
            # Still, ensure no Unnamed columns exist (rename only the bad ones)
            new_cols = []
            for i, col in enumerate(df_normal.columns):
                col_str = str(col).strip().lower()
                if col_str.startswith("unnamed") or col_str.startswith("column") or col_str.isdigit() or col_str in ["nan", ""]:
                    new_cols.append(f"Column_{i}")
                else:
                    new_cols.append(col)
            df_normal.columns = new_cols
            return df_normal

        # --- ATTEMPT 2: PROBE-BASED DETECTION ---
        print(f"[SMART READ] Normal read yielded broken schema. Falling back to probe detection.")

        # Probe read (optimized to 15 rows)
        if ext == ".csv":
            probe_df = read_csv_with_fallback(
                file_path,
                header=None,
                nrows=15,
                on_bad_lines="skip",
                sep=None,
                engine="python"
            )
        else:
            probe_df = pd.read_excel(file_path, header=None, nrows=15)

        if probe_df.empty:
            return pd.DataFrame()

        header_row = detect_header_from_probe(probe_df)

        # Final read skipping rows before header, header=None
        if ext == ".csv":
            df = read_csv_with_fallback(
                file_path,
                header=None,
                skiprows=header_row,
                sep=None,
                engine="python"
            )
        else:
            df = pd.read_excel(file_path, header=None, skiprows=header_row)

        if df.empty:
            return pd.DataFrame()

        # Extract header from first row
        header_cells = df.iloc[0].tolist()
        clean_headers = _clean_header_row(header_cells)
        df.columns = clean_headers
        df = df.iloc[1:].reset_index(drop=True)

        # Validate
        if is_schema_broken(df):
            print(f"[HEADER REVERT] Manual header from row {header_row} looks broken. Falling back to default read.")
            # Use the normal read we already have, but ensure columns are cleaned
            df = df_normal
            new_cols = []
            for i, col in enumerate(df.columns):
                col_str = str(col).strip().lower()
                if col_str.startswith("unnamed") or col_str.startswith("column") or col_str.isdigit() or col_str in ["nan", ""]:
                    new_cols.append(f"Column_{i}")
                else:
                    new_cols.append(col)
            df.columns = new_cols
        else:
            if header_row != 0:
                print(f"[HEADER FIX] Manually applied header from row {header_row} for {os.path.basename(file_path)}")

        return df

    except Exception as e:
        print(f"[SMART READ ERROR] {e}. Falling back to default read.")
        if ext == ".csv":
            df = read_csv_with_fallback(file_path, sep=None, engine="python")
        else:
            df = pd.read_excel(file_path)
        # Clean only the bad columns
        new_cols = []
        for i, col in enumerate(df.columns):
            col_str = str(col).strip().lower()
            if col_str.startswith("unnamed") or col_str.startswith("column") or col_str.isdigit() or col_str in ["nan", ""]:
                new_cols.append(f"Column_{i}")
            else:
                new_cols.append(col)
        df.columns = new_cols
        return df


def read_file(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".csv", ".xlsx", ".xls"]:
        return smart_read(file_path, ext)
    elif ext == ".json":
        return pd.read_json(file_path)
    elif ext == ".pdf":
        import fitz
        from io import StringIO
        from utils.llm_utils import coerce_text_content
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += coerce_text_content(page.get_text())
        try:
            return pd.read_csv(StringIO(text))
        except Exception:
            raise ValueError("Could not parse PDF as tabular data.")
    raise ValueError(f"Unsupported file type: {ext}")