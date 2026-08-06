from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings


import os
import json

def _missing(df: pd.DataFrame, column: str, fallback: int) -> int:
    """Dem o thieu: ca null LAN chuoi rong.

    `isnull()` khong bat chuoi rong, ma corruption "summary rong" ghi "" chu khong
    ghi NaN - neu chi dem null thi kich ban do di qua quality check ma khong de
    lai dau vet nao.
    """
    if column not in df.columns:
        return fallback
    series = df[column]
    return int(series.isnull().sum() + (series.fillna("").astype(str).str.strip() == "").sum())


def _stale_rows(df: pd.DataFrame, settings: Settings) -> int:
    """Dem dong qua han theo nguong trong Settings, khong hard-code."""
    if "age_days" not in df.columns:
        return 0
    return int(df["age_days"].gt(settings.freshness_threshold_days).sum())


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    row_count = len(df)
    
    paper_id_nulls = _missing(df, "paper_id", row_count)
    paper_id_duplicates = int(df["paper_id"].duplicated().sum()) if "paper_id" in df.columns else 0
    title_nulls = _missing(df, "title", row_count)

    summary_nulls = _missing(df, "summary", row_count)
    if "summary" in df.columns:
        short_summaries = int(df["summary"].fillna("").str.len().lt(10).sum())
    else:
        short_summaries = row_count

    stale_rows = _stale_rows(df, settings)

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
    # Cot trong clean contract ten la `published`, khong phai `published_date`.
    if "published" in df.columns:
        valid_dates = pd.to_datetime(df["published"], errors="coerce").dropna()
        if not valid_dates.empty:
            latest = valid_dates.max().date().isoformat()
            oldest = valid_dates.min().date().isoformat()
        else:
            latest, oldest = None, None
    else:
        latest, oldest = None, None

    stale_rows = _stale_rows(df, settings)
    total_rows = len(df)
    # Chi mot dong qua han cung la du lieu khong con tuoi. Nguong "< 50% so dong"
    # truoc day khien 11/24 dong stale van bao Fresh - corruption "lam cu du lieu"
    # se khong tao ra signal nao.
    is_fresh = total_rows > 0 and stale_rows == 0
    
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
