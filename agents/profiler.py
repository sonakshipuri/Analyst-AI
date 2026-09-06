# agents/profiler.py
import pandas as pd
import numpy as np
from typing import Dict, Any
import logging

logger = logging.getLogger("datalyze.profiler")

IDENTIFIER_PATTERNS = ['id', 'index', 'row', 'key', 'hash', 'serial']

def _is_identifier_column(col: str) -> bool:
    col_lower = col.lower().strip()
    return any(pattern in col_lower for pattern in IDENTIFIER_PATTERNS)


def _to_float(value) -> float:
    """
    Safely convert pandas scalar to float.
    Falls back to 0.0 if conversion fails (e.g., complex numbers).
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        # If it's a complex, take its real part
        if hasattr(value, 'real'):
            return float(value.real)
        return 0.0


class DatasetProfiler:
    def __init__(self, df: pd.DataFrame, max_categories: int = 10, max_numeric_stats: int = 5,
                 missing_threshold: int = 30, cardinality_threshold: float = 0.8):
        self.df = df
        self.max_categories = max_categories
        self.max_numeric_stats = max_numeric_stats
        self.missing_threshold = missing_threshold
        self.cardinality_threshold = cardinality_threshold
        self.profile: Dict[str, Any] = {}

    def run(self) -> Dict[str, Any]:
        self._basic_info()
        self._column_profiles()
        self._correlations()
        self._quality_insights()
        self._generate_summary_text()
        return self.profile

    def _basic_info(self):
        self.profile["shape"] = {"rows": len(self.df), "columns": len(self.df.columns)}
        self.profile["columns"] = list(self.df.columns)

    def _column_profiles(self):
        profiles = {}
        # Filter numeric columns – remove identifiers
        all_numeric = self.df.select_dtypes(include=np.number).columns.tolist()
        numeric_cols = [col for col in all_numeric if not _is_identifier_column(col)]

        # Better datetime detection
        datetime_cols = [col for col in self.df.columns if pd.api.types.is_datetime64_any_dtype(self.df[col])]
        categorical_cols = self.df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()

        numeric_to_profile = numeric_cols[:self.max_numeric_stats]

        for col in numeric_to_profile:
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            profiles[col] = {
                "type": "numeric",
                "count": len(series),
                "missing": int(self.df[col].isna().sum()),
                "missing_pct": round(_to_float(self.df[col].isna().mean() * 100), 1),
                "mean": round(_to_float(series.mean()), 2),
                "median": round(_to_float(series.median()), 2),
                "std": round(_to_float(series.std()), 2),
                "min": _to_float(series.min()),
                "max": _to_float(series.max()),
                "q1": round(_to_float(series.quantile(0.25)), 2),
                "q3": round(_to_float(series.quantile(0.75)), 2),
                "skew": round(_to_float(series.skew()), 2),
                "unique": int(series.nunique()),
            }

        for col in categorical_cols:
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            value_counts = series.value_counts()
            top_n = value_counts.head(self.max_categories).to_dict()
            total = len(series)
            top_n_pct = {k: round(v/total*100, 1) for k, v in top_n.items()}
            profiles[col] = {
                "type": "categorical",
                "count": len(series),
                "missing": int(self.df[col].isna().sum()),
                "missing_pct": round(_to_float(self.df[col].isna().mean() * 100), 1),
                "unique": int(series.nunique()),
                "top_values": top_n,
                "top_percentages": top_n_pct,
                "most_common": value_counts.index[0] if len(value_counts) > 0 else None,
            }

        for col in datetime_cols:
            series = self.df[col].dropna()
            if len(series) == 0:
                continue
            profiles[col] = {
                "type": "datetime",
                "count": len(series),
                "missing": int(self.df[col].isna().sum()),
                "missing_pct": round(_to_float(self.df[col].isna().mean() * 100), 1),
                "min": series.min().isoformat() if not series.empty else None,
                "max": series.max().isoformat() if not series.empty else None,
                "unique": int(series.nunique()),
            }

        self.profile["column_profiles"] = profiles
        self.profile["numeric_columns"] = numeric_cols
        self.profile["categorical_columns"] = categorical_cols
        self.profile["datetime_columns"] = datetime_cols

    def _correlations(self):
        numeric_cols = self.profile.get("numeric_columns", [])
        corr_cols = numeric_cols[:20]
        if len(corr_cols) >= 2:
            corr_df = self.df[corr_cols].corr().round(2)
            strong = []
            for i in range(len(corr_df.columns)):
                for j in range(i+1, len(corr_df.columns)):
                    r = corr_df.iloc[i, j]
                    if abs(r) > 0.6:
                        strong.append({
                            "col1": corr_df.columns[i],
                            "col2": corr_df.columns[j],
                            "correlation": _to_float(r)
                        })
            self.profile["strong_correlations"] = strong

    def _quality_insights(self):
        issues = []
        columns = self.profile.get("column_profiles", {})
        total_rows = self.profile["shape"]["rows"]
        for col, meta in columns.items():
            missing_pct = meta.get("missing_pct", 0)
            if missing_pct > self.missing_threshold:
                issues.append(f"Column '{col}' has {missing_pct}% missing values.")
            if meta.get("type") == "categorical":
                unique = meta.get("unique", 0)
                if unique == 1:
                    issues.append(f"Column '{col}' is constant (only one unique value).")
                elif unique == 2:
                    issues.append(f"Column '{col}' is binary (2 unique values).")
                if unique > total_rows * self.cardinality_threshold and unique > 50:
                    issues.append(f"Column '{col}' has very high cardinality ({unique} unique values) – may be an identifier.")
        self.profile["quality_issues"] = issues

    def _generate_summary_text(self):
        lines = []
        rows, cols = self.profile["shape"]["rows"], self.profile["shape"]["columns"]
        lines.append(f"The dataset has {rows} rows and {cols} columns.")
        num_cols = self.profile.get("numeric_columns", [])
        cat_cols = self.profile.get("categorical_columns", [])
        dt_cols = self.profile.get("datetime_columns", [])
        lines.append(f"Contains {len(num_cols)} numeric, {len(cat_cols)} categorical, and {len(dt_cols)} datetime columns.")
        missing_cols = [col for col, meta in self.profile.get("column_profiles", {}).items() if meta.get("missing_pct", 0) > 0]
        if missing_cols:
            lines.append("Columns with missing values: " + ", ".join(missing_cols[:5]) + ("..." if len(missing_cols) > 5 else ""))
        top_cat = []
        for col in cat_cols[:5]:
            if col in self.profile.get("column_profiles", {}):
                meta = self.profile["column_profiles"][col]
                top_vals = meta.get("top_values", {})
                if top_vals:
                    top_items = ", ".join([f"{k} ({v}%)" for k, v in meta.get("top_percentages", {}).items()])
                    top_cat.append(f"{col}: {top_items}")
        if top_cat:
            lines.append("Top categories: " + "; ".join(top_cat))
        num_highlights = []
        for col in num_cols[:5]:
            if col in self.profile.get("column_profiles", {}):
                meta = self.profile["column_profiles"][col]
                num_highlights.append(f"{col} (mean={meta.get('mean')}, min={meta.get('min')}, max={meta.get('max')})")
        if num_highlights:
            lines.append("Numeric summaries: " + "; ".join(num_highlights))
        issues = self.profile.get("quality_issues", [])
        if issues:
            lines.append("Data quality notes: " + " ".join(issues[:3]) + ("..." if len(issues) > 3 else ""))

        # Business signals
        signals = []
        for col in cat_cols[:3]:
            if col in self.profile.get("column_profiles", {}):
                meta = self.profile["column_profiles"][col]
                most_common = meta.get("most_common")
                if most_common:
                    pct = meta.get("top_percentages", {}).get(most_common, 0)
                    signals.append(f"Most common {col}: '{most_common}' ({pct}%)")
        strong_corr = self.profile.get("strong_correlations", [])
        if strong_corr:
            top_corr = max(strong_corr, key=lambda x: abs(x["correlation"]))
            signals.append(f"Strongest correlation: {top_corr['col1']} ↔ {top_corr['col2']} (r={top_corr['correlation']})")
        if signals:
            lines.append("Business signals: " + "; ".join(signals))

        self.profile["summary_text"] = "\n".join(lines)


def profile_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    profiler = DatasetProfiler(df)
    profile = profiler.run()
    return profile