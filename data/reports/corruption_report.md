# Corruption & Repair Comparison Report

## 1. Data Quality Comparison
| Metric | Corrupted | Repaired |
|---|---|---|
| Row Count | 23 | 24 |
| Paper ID Nulls | 0 | 0 |
| Title Nulls | 0 | 0 |

## 2. Evaluation Metrics Comparison
| Metric | Baseline | Corrupted | Repaired |
|---|---|---|---|
| Retrieval Hit Rate | 100.00% | 80.00% | 100.00% |
| Mean Token F1 | 0.1357 | 0.1057 | 0.1357 |
| Mean Judge Score | 1.50 | 1.20 | 1.20 |
