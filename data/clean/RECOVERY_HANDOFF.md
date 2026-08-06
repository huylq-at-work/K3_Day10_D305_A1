# Role 2 recovery handoff

Repair was rebuilt with `load_raw_records -> build_clean_dataframe`; baseline and corrupted artifacts were read only for comparison.

## Source and security gates

- Overall checkpoint: **PASS**
- Raw snapshot unchanged: `True`
- External fetch used: `False`
- Tracked-secret audit: **PASS**
- Repaired clean contract: **PASS**
- Repaired non-blocking contract warnings: `1`

## Clean / corrupted / repaired

| Signal | Clean | Corrupted | Repaired |
| :-- | --: | --: | --: |
| Rows | 24 | 23 | 24 |
| Unique paper IDs | 24 | 21 | 24 |
| Duplicate IDs | 0 | 2 | 0 |
| Missing summaries | 0 | 2 | 0 |
| Empty embedding text | 0 | 0 | 0 |
| Stale rows | 0 | 4 | 0 |

## Lineage proof

All `13` deliberately damaged record occurrences were found in raw and restored: `True`.

| Corruption | Paper IDs |
| :-- | :-- |
| `drop_latest` | `10.2118/234689-pa`, `10.1007/s10278-026-02086-9`, `10.21203/rs.3.rs-10178277/v1` |
| `missing_summary` | `10.21203/rs.3.rs-10012178/v1`, `10.1093/sleep/zsag091.0346` |
| `noise_injection` | `10.1111/exsy.70341`, `10.1148/radiol.251581` |
| `old_published_date` | `10.20944/preprints202602.0996.v1`, `10.20944/preprints202604.0339.v1`, `10.21079/11681/50309`, `10.21203/rs.3.rs-9882260/v1` |
| `duplicate_rows` | `10.2196/preprints.106157`, `10.3390/app16052244` |

Machine-readable evidence: `data/clean/recovery_evidence.json`.
