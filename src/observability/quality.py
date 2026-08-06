from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings


import os
import json

def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    row_count = len(df)
    
    paper_id_nulls = int(df["paper_id"].isnull().sum()) if "paper_id" in df.columns else row_count
    paper_id_duplicates = int(df["paper_id"].duplicated().sum()) if "paper_id" in df.columns else 0
    title_nulls = int(df["title"].isnull().sum()) if "title" in df.columns else row_count
    
    if "summary" in df.columns:
        summary_nulls = int(df["summary"].isnull().sum())
        short_summaries = int(df["summary"].fillna("").str.len().lt(10).sum())
    else:
        summary_nulls = row_count
        short_summaries = row_count
        
    stale_rows = int(df["age_days"].gt(365).sum()) if "age_days" in df.columns else 0

    quality_metrics = {
        "row_count": row_count,
        "paper_id_nulls": paper_id_nulls,
        "paper_id_duplicates": paper_id_duplicates,
        "title_nulls": title_nulls,
        "summary_nulls": summary_nulls,
        "short_summaries": short_summaries,
        "stale_rows": stale_rows,
    }
    
    os.makedirs(settings.paths.quality_dir, exist_ok=True)
    report_path = os.path.join(settings.paths.quality_dir, f"{report_name}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(quality_metrics, f, indent=2)
        
    return quality_metrics


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    if "published_date" in df.columns:
        valid_dates = pd.to_datetime(df["published_date"], errors="coerce").dropna()
        if not valid_dates.empty:
            latest = valid_dates.max().isoformat()
            oldest = valid_dates.min().isoformat()
        else:
            latest, oldest = None, None
    else:
        latest, oldest = None, None
        
    stale_rows = int(df["age_days"].gt(365).sum()) if "age_days" in df.columns else 0
    total_rows = len(df)
    is_fresh = stale_rows < (total_rows * 0.5) if total_rows > 0 else False
    
    report = {
        "latest_published": latest,
        "oldest_published": oldest,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "is_fresh": is_fresh
    }
    
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
        
    return report
