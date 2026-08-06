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

Cac tin hieu duoi day la bang chung pipeline PHAT HIEN duoc du lieu hong,
va phat hien duoc no da het hong sau khi repair.

| Signal | Corrupted | Repaired | Ky vong sau repair |
|---|---|---|---|
| Row Count | {corrupted_quality.get('row_count', 'N/A')} | {repaired_quality.get('row_count', 'N/A')} | ve bang baseline |
| Paper ID Nulls | {corrupted_quality.get('paper_id_nulls', 'N/A')} | {repaired_quality.get('paper_id_nulls', 'N/A')} | 0 |
| Paper ID Duplicates | {corrupted_quality.get('paper_id_duplicates', 'N/A')} | {repaired_quality.get('paper_id_duplicates', 'N/A')} | 0 |
| Title Nulls | {corrupted_quality.get('title_nulls', 'N/A')} | {repaired_quality.get('title_nulls', 'N/A')} | 0 |
| Summary Missing/Empty | {corrupted_quality.get('summary_nulls', 'N/A')} | {repaired_quality.get('summary_nulls', 'N/A')} | 0 |
| Short Summaries | {corrupted_quality.get('short_summaries', 'N/A')} | {repaired_quality.get('short_summaries', 'N/A')} | 0 |
| Stale Rows | {corrupted_quality.get('stale_rows', 'N/A')} | {repaired_quality.get('stale_rows', 'N/A')} | 0 |

## 2. Freshness Comparison

| Attribute | Corrupted | Repaired |
|---|---|---|
| Latest Published | {corrupted_freshness.get('latest_published', 'N/A')} | {repaired_freshness.get('latest_published', 'N/A')} |
| Oldest Published | {corrupted_freshness.get('oldest_published', 'N/A')} | {repaired_freshness.get('oldest_published', 'N/A')} |
| Stale Rows | {corrupted_freshness.get('stale_rows', 'N/A')} | {repaired_freshness.get('stale_rows', 'N/A')} |
| Total Rows | {corrupted_freshness.get('total_rows', 'N/A')} | {repaired_freshness.get('total_rows', 'N/A')} |
| Status | {'Fresh' if corrupted_freshness.get('is_fresh') else 'Stale'} | {'Fresh' if repaired_freshness.get('is_fresh') else 'Stale'} |

## 3. Evaluation Metrics Comparison

Ba trang thai dung chung mot test set, cung top_k va cung evaluator.

| Metric | Baseline | Corrupted | Repaired | Delta corruption | Recovered |
|---|---|---|---|---|---|
| Retrieval Hit Rate | {baseline_metrics.get('retrieval_hit_rate', 0):.2%} | {corrupted_metrics.get('retrieval_hit_rate', 0):.2%} | {repaired_metrics.get('retrieval_hit_rate', 0):.2%} | {corrupted_metrics.get('retrieval_hit_rate', 0) - baseline_metrics.get('retrieval_hit_rate', 0):+.2%} | {'yes' if abs(repaired_metrics.get('retrieval_hit_rate', 0) - baseline_metrics.get('retrieval_hit_rate', 0)) < 1e-9 else 'no'} |
| Mean Token F1 | {baseline_metrics.get('mean_token_f1', 0):.4f} | {corrupted_metrics.get('mean_token_f1', 0):.4f} | {repaired_metrics.get('mean_token_f1', 0):.4f} | {corrupted_metrics.get('mean_token_f1', 0) - baseline_metrics.get('mean_token_f1', 0):+.4f} | {'yes' if abs(repaired_metrics.get('mean_token_f1', 0) - baseline_metrics.get('mean_token_f1', 0)) < 1e-9 else 'no'} |
| Judge Accuracy | {baseline_metrics.get('judge_accuracy', 0):.2%} | {corrupted_metrics.get('judge_accuracy', 0):.2%} | {repaired_metrics.get('judge_accuracy', 0):.2%} | {corrupted_metrics.get('judge_accuracy', 0) - baseline_metrics.get('judge_accuracy', 0):+.2%} | {'yes' if abs(repaired_metrics.get('judge_accuracy', 0) - baseline_metrics.get('judge_accuracy', 0)) < 1e-9 else 'no'} |
| Mean Judge Score | {baseline_metrics.get('mean_judge_score', 0):.2f} | {corrupted_metrics.get('mean_judge_score', 0):.2f} | {repaired_metrics.get('mean_judge_score', 0):.2f} | {corrupted_metrics.get('mean_judge_score', 0) - baseline_metrics.get('mean_judge_score', 0):+.2f} | {'yes' if abs(repaired_metrics.get('mean_judge_score', 0) - baseline_metrics.get('mean_judge_score', 0)) < 1e-9 else 'no'} |

Samples: {baseline_metrics.get('samples', 'N/A')} cau hoi cho moi trang thai.

"""
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
