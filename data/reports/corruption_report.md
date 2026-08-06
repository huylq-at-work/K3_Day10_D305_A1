# Corruption & Repair Comparison Report

## 1. Data Quality Comparison

Cac tin hieu duoi day la bang chung pipeline PHAT HIEN duoc du lieu hong,
va phat hien duoc no da het hong sau khi repair.

| Signal | Corrupted | Repaired | Ky vong sau repair |
|---|---|---|---|
| Row Count | 23 | 24 | ve bang baseline |
| Paper ID Nulls | 0 | 0 | 0 |
| Paper ID Duplicates | 2 | 0 | 0 |
| Title Nulls | 0 | 0 | 0 |
| Summary Missing/Empty | 2 | 0 | 0 |
| Short Summaries | 2 | 0 | 0 |
| Stale Rows | 4 | 0 | 0 |

## 2. Freshness Comparison

| Attribute | Corrupted | Repaired |
|---|---|---|
| Latest Published | 2026-07-03 | 2026-08-01 |
| Oldest Published | 2024-02-13 | 2026-02-12 |
| Stale Rows | 4 | 0 |
| Total Rows | 23 | 24 |
| Status | Stale | Fresh |

## 3. Evaluation Metrics Comparison

Ba trang thai dung chung mot test set, cung top_k va cung evaluator.

| Metric | Baseline | Corrupted | Repaired | Delta corruption | Recovered |
|---|---|---|---|---|---|
| Retrieval Hit Rate | 100.00% | 80.00% | 100.00% | -20.00% | yes |
| Mean Token F1 | 0.8475 | 0.6574 | 0.8475 | -0.1901 | yes |
| Judge Accuracy | 80.00% | 62.50% | 80.00% | -17.50% | yes |
| Mean Judge Score | 4.15 | 3.45 | 4.15 | -0.70 | yes |

Samples: 40 cau hoi cho moi trang thai.

