from __future__ import annotations

from typing import Any


import os

def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    md = f"""# Phase 1: Baseline Evaluation Report

## 1. Source Summary
- **Total Records:** {source_summary.get('total_records', 'N/A')}

## 2. Data Quality
- **Row Count:** {quality.get('row_count', 'N/A')}
- **Paper ID Nulls:** {quality.get('paper_id_nulls', 'N/A')}
- **Paper ID Duplicates:** {quality.get('paper_id_duplicates', 'N/A')}
- **Title Nulls:** {quality.get('title_nulls', 'N/A')}

## 3. Freshness
- **Latest Published:** {freshness.get('latest_published', 'N/A')}
- **Oldest Published:** {freshness.get('oldest_published', 'N/A')}
- **Stale Rows:** {freshness.get('stale_rows', 'N/A')}
- **Is Fresh:** {'Yes' if freshness.get('is_fresh') else 'No'}

## 4. Evaluation Metrics
- **Samples Evaluated:** {metrics.get('samples', 'N/A')}
- **Retrieval Hit Rate:** {metrics.get('retrieval_hit_rate', 0):.2%}
- **Mean Token F1:** {metrics.get('mean_token_f1', 0):.4f}
- **Judge Accuracy:** {metrics.get('judge_accuracy', 0):.2%}
- **Mean Judge Score:** {metrics.get('mean_judge_score', 0):.2f}/5.0
"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    md = f"""# Corruption & Repair Comparison Report

## 1. Data Quality Comparison
| Metric | Corrupted | Repaired |
|---|---|---|
| Row Count | {corrupted_quality.get('row_count', 'N/A')} | {repaired_quality.get('row_count', 'N/A')} |
| Paper ID Nulls | {corrupted_quality.get('paper_id_nulls', 'N/A')} | {repaired_quality.get('paper_id_nulls', 'N/A')} |
| Title Nulls | {corrupted_quality.get('title_nulls', 'N/A')} | {repaired_quality.get('title_nulls', 'N/A')} |

## 2. Evaluation Metrics Comparison
| Metric | Baseline | Corrupted | Repaired |
|---|---|---|---|
| Retrieval Hit Rate | {baseline_metrics.get('retrieval_hit_rate', 0):.2%} | {corrupted_metrics.get('retrieval_hit_rate', 0):.2%} | {repaired_metrics.get('retrieval_hit_rate', 0):.2%} |
| Mean Token F1 | {baseline_metrics.get('mean_token_f1', 0):.4f} | {corrupted_metrics.get('mean_token_f1', 0):.4f} | {repaired_metrics.get('mean_token_f1', 0):.4f} |
| Mean Judge Score | {baseline_metrics.get('mean_judge_score', 0):.2f} | {corrupted_metrics.get('mean_judge_score', 0):.2f} | {repaired_metrics.get('mean_judge_score', 0):.2f} |
"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
