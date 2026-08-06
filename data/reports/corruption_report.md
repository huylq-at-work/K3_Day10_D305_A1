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
| Mean Token F1 | 0.8475 | 0.6574 | 0.8475 |
| Mean Judge Score | 4.15 | 3.45 | 4.15 |
