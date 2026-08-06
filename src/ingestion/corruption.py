from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from core.config import load_settings
from core.utils import write_json
from ingestion.cleaning import CLEAN_COLUMNS, build_text_for_embedding
from ingestion.lineage import verify_or_create_source_lock


@dataclass(frozen=True)
class CorruptionPlan:
    latest_drop_count: int = 3
    missing_summary_count: int = 2
    noise_count: int = 2
    noise_token: str = "__CORRUPTED_NOISE__"
    noise_repetitions: int = 12
    old_date_count: int = 4
    old_date_days: int = 730
    duplicate_count: int = 2


def _frame_fingerprint(dataframe: pd.DataFrame) -> str:
    payload = json.dumps(
        dataframe.to_dict(orient="records"),
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text_snapshot(value: Any) -> dict[str, Any]:
    text = "" if value is None else str(value)
    return {
        "chars": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "preview": text[:120],
    }


def _source_guard(output_log_path: Path) -> dict[str, Any]:
    """Verify the fixed raw source when called from the real project layout."""

    resolved = output_log_path.resolve()
    try:
        project_dir = resolved.parents[2]
    except IndexError:
        return {"status": "not_available", "reason": "log path has no project root"}
    lock_path = project_dir / "data" / "raw" / "baseline_source_lock.json"
    if not lock_path.exists():
        return {
            "status": "not_available",
            "reason": "baseline_source_lock.json not found for this isolated run",
        }
    settings = load_settings(project_dir)
    verified = verify_or_create_source_lock(settings, lock_path)
    return {
        "status": "verified",
        "source_mode": "raw snapshot",
        "refresh_source_setting": settings.refresh_source,
        "sha256": verified["sha256"],
    }


def _lineage_paper_id(output_log_path: Path, available_ids: set[str]) -> str:
    try:
        project_dir = output_log_path.resolve().parents[2]
    except IndexError:
        return sorted(available_ids)[0]
    lineage_path = project_dir / "data" / "clean" / "baseline_lineage_evidence.json"
    if lineage_path.exists():
        payload = json.loads(lineage_path.read_text(encoding="utf-8"))
        candidate = str(payload.get("lineage", {}).get("paper_id", ""))
        if candidate in available_ids:
            return candidate
    return sorted(available_ids)[0]


def _select_ids(
    available_ids: list[str],
    count: int,
    excluded: set[str],
    preferred: str | None = None,
) -> list[str]:
    selected: list[str] = []
    if preferred and preferred in available_ids and preferred not in excluded:
        selected.append(preferred)
    selected.extend(
        paper_id
        for paper_id in sorted(available_ids)
        if paper_id not in excluded and paper_id not in selected
    )
    result = selected[:count]
    if len(result) != count:
        raise ValueError(
            f"Not enough distinct records for deterministic corruption: requested {count}, "
            f"available {len(result)}."
        )
    return result


def corrupt_clean_dataframe(
    df: pd.DataFrame,
    output_log_path,
    plan: CorruptionPlan | None = None,
) -> pd.DataFrame:
    """Apply deterministic, logged corruption to a copy of clean baseline data.

    Raw source fingerprints are verified when ``output_log_path`` belongs to the
    project ``data/results`` directory. The input dataframe is never mutated.
    """

    corruption_plan = plan or CorruptionPlan()
    log_path = Path(output_log_path)
    source_guard = _source_guard(log_path)

    missing_columns = sorted(set(CLEAN_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Cannot corrupt dataframe missing clean columns: {missing_columns}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty clean dataframe.")
    if df["paper_id"].isna().any() or df["paper_id"].duplicated().any():
        raise ValueError("Baseline paper_id must be complete and unique before corruption.")

    baseline = df.loc[:, CLEAN_COLUMNS].copy(deep=True).reset_index(drop=True)
    corrupted = baseline.copy(deep=True)
    baseline_fingerprint = _frame_fingerprint(baseline)
    events: list[dict[str, Any]] = []

    # 1. Remove the latest publications. Tie-break by stable ID for repeatability.
    ranked_latest = corrupted.assign(
        _published_sort=pd.to_datetime(corrupted["published"], errors="coerce")
    ).sort_values(
        ["_published_sort", "paper_id"], ascending=[False, True], kind="stable"
    )
    drop_ids = ranked_latest.head(corruption_plan.latest_drop_count)["paper_id"].tolist()
    before_count = len(corrupted)
    drop_before = [
        {
            "paper_id": paper_id,
            "published": str(
                corrupted.loc[corrupted["paper_id"] == paper_id, "published"].iloc[0]
            ),
        }
        for paper_id in drop_ids
    ]
    corrupted = corrupted.loc[~corrupted["paper_id"].isin(drop_ids)].copy()
    events.append(
        {
            "sequence": 1,
            "type": "drop_latest",
            "paper_ids": drop_ids,
            "parameters": {
                "count": corruption_plan.latest_drop_count,
                "sort": "published DESC, paper_id ASC",
            },
            "before_count": before_count,
            "after_count": len(corrupted),
            "changes": drop_before,
        }
    )

    remaining_ids = corrupted["paper_id"].astype(str).tolist()
    lineage_id = _lineage_paper_id(log_path, set(remaining_ids))
    touched: set[str] = set()

    # 2. Missing summaries, including the explicit lineage/repair candidate.
    missing_ids = _select_ids(
        remaining_ids,
        corruption_plan.missing_summary_count,
        touched,
        preferred=lineage_id,
    )
    missing_changes: list[dict[str, Any]] = []
    for paper_id in missing_ids:
        row_index = corrupted.index[corrupted["paper_id"] == paper_id][0]
        before = corrupted.at[row_index, "summary"]
        corrupted.at[row_index, "summary"] = ""
        corrupted.at[row_index, "summary_chars"] = 0
        missing_changes.append(
            {
                "paper_id": paper_id,
                "field": "summary",
                "before": _text_snapshot(before),
                "after": _text_snapshot(""),
            }
        )
    touched.update(missing_ids)
    events.append(
        {
            "sequence": 2,
            "type": "missing_summary",
            "paper_ids": missing_ids,
            "parameters": {"replacement": "", "count": len(missing_ids)},
            "before_count": len(corrupted),
            "after_count": len(corrupted),
            "changes": missing_changes,
        }
    )

    # 3. Inject deterministic noise into otherwise valid summaries.
    noise_ids = _select_ids(remaining_ids, corruption_plan.noise_count, touched)
    noise_suffix = " " + " ".join(
        [corruption_plan.noise_token] * corruption_plan.noise_repetitions
    )
    noise_changes: list[dict[str, Any]] = []
    for paper_id in noise_ids:
        row_index = corrupted.index[corrupted["paper_id"] == paper_id][0]
        before = str(corrupted.at[row_index, "summary"])
        after = before + noise_suffix
        corrupted.at[row_index, "summary"] = after
        corrupted.at[row_index, "summary_chars"] = len(after)
        noise_changes.append(
            {
                "paper_id": paper_id,
                "field": "summary",
                "before": _text_snapshot(before),
                "after": _text_snapshot(after),
            }
        )
    touched.update(noise_ids)
    events.append(
        {
            "sequence": 3,
            "type": "noise_injection",
            "paper_ids": noise_ids,
            "parameters": {
                "token": corruption_plan.noise_token,
                "repetitions": corruption_plan.noise_repetitions,
                "count": len(noise_ids),
            },
            "before_count": len(corrupted),
            "after_count": len(corrupted),
            "changes": noise_changes,
        }
    )

    # 4. Make dates stale while keeping age_days internally consistent.
    old_date_ids = _select_ids(remaining_ids, corruption_plan.old_date_count, touched)
    old_date_changes: list[dict[str, Any]] = []
    for paper_id in old_date_ids:
        row_index = corrupted.index[corrupted["paper_id"] == paper_id][0]
        before_published = str(corrupted.at[row_index, "published"])
        before_age = int(corrupted.at[row_index, "age_days"])
        after_published = (
            date.fromisoformat(before_published)
            - timedelta(days=corruption_plan.old_date_days)
        ).isoformat()
        corrupted.at[row_index, "published"] = after_published
        corrupted.at[row_index, "age_days"] = before_age + corruption_plan.old_date_days
        old_date_changes.append(
            {
                "paper_id": paper_id,
                "fields": ["published", "age_days"],
                "before": {"published": before_published, "age_days": before_age},
                "after": {
                    "published": after_published,
                    "age_days": before_age + corruption_plan.old_date_days,
                },
            }
        )
    touched.update(old_date_ids)
    events.append(
        {
            "sequence": 4,
            "type": "old_published_date",
            "paper_ids": old_date_ids,
            "parameters": {
                "days_shifted_back": corruption_plan.old_date_days,
                "count": len(old_date_ids),
            },
            "before_count": len(corrupted),
            "after_count": len(corrupted),
            "changes": old_date_changes,
        }
    )

    # 5. Append exact duplicate rows from records untouched by other scenarios.
    duplicate_ids = _select_ids(remaining_ids, corruption_plan.duplicate_count, touched)
    before_count = len(corrupted)
    duplicate_rows = corrupted.loc[corrupted["paper_id"].isin(duplicate_ids)].copy()
    corrupted = pd.concat([corrupted, duplicate_rows], ignore_index=True)
    events.append(
        {
            "sequence": 5,
            "type": "duplicate_rows",
            "paper_ids": duplicate_ids,
            "parameters": {
                "copies_added_per_id": 1,
                "count": len(duplicate_ids),
            },
            "before_count": before_count,
            "after_count": len(corrupted),
            "changes": [
                {
                    "paper_id": paper_id,
                    "before_occurrences": 1,
                    "after_occurrences": 2,
                }
                for paper_id in duplicate_ids
            ],
        }
    )

    # Rebuild every document so summary corruption reaches the embedding input.
    corrupted["text_for_embedding"] = corrupted.apply(
        lambda row: build_text_for_embedding(
            str(row["title"]),
            str(row["summary"]),
            str(row["authors_joined"]),
            str(row["categories_joined"]),
        ),
        axis=1,
    )
    corrupted = corrupted.loc[:, CLEAN_COLUMNS].reset_index(drop=True)

    log = {
        "version": 1,
        "deterministic": True,
        "raw_source_guard": source_guard,
        "plan": asdict(corruption_plan),
        "baseline": {
            "rows": len(baseline),
            "unique_paper_ids": int(baseline["paper_id"].nunique()),
            "fingerprint_sha256": baseline_fingerprint,
        },
        "lineage_repair_candidate": {
            "paper_id": lineage_id,
            "corruption_type": "missing_summary",
            "repair_source": "data/raw/crossref_records.json",
        },
        "events": events,
        "result": {
            "rows": len(corrupted),
            "unique_paper_ids": int(corrupted["paper_id"].nunique()),
            "duplicate_rows": int(corrupted["paper_id"].duplicated().sum()),
            "fingerprint_sha256": _frame_fingerprint(corrupted),
            "different_from_baseline": _frame_fingerprint(corrupted)
            != baseline_fingerprint,
        },
    }
    write_json(log_path, log)
    return corrupted


def validate_corruption_against_log(
    baseline: pd.DataFrame,
    corrupted: pd.DataFrame,
    log: dict[str, Any],
) -> dict[str, Any]:
    """Independently prove that corrupted data matches every logged event."""

    baseline_by_id = baseline.set_index("paper_id", drop=False)
    checks: dict[str, bool] = {
        "baseline_fingerprint_matches_log": _frame_fingerprint(
            baseline.loc[:, CLEAN_COLUMNS].reset_index(drop=True)
        )
        == log["baseline"]["fingerprint_sha256"],
        "corrupted_fingerprint_matches_log": _frame_fingerprint(
            corrupted.loc[:, CLEAN_COLUMNS].reset_index(drop=True)
        )
        == log["result"]["fingerprint_sha256"],
        "dataset_differs_from_baseline": log["result"]["different_from_baseline"],
    }
    event_results: list[dict[str, Any]] = []
    previous_count = len(baseline)
    for event in log["events"]:
        event_type = event["type"]
        paper_ids = event["paper_ids"]
        if event_type == "drop_latest":
            expected_after_count = event["before_count"] - len(paper_ids)
        elif event_type == "duplicate_rows":
            expected_after_count = event["before_count"] + len(paper_ids)
        else:
            expected_after_count = event["before_count"]
        event_checks = {
            "before_count_chains": event["before_count"] == previous_count,
            "logged_count_delta_matches_type": event["after_count"]
            == expected_after_count,
        }
        if event_type == "drop_latest":
            event_checks["ids_absent"] = not corrupted["paper_id"].isin(paper_ids).any()
        elif event_type == "missing_summary":
            rows = corrupted.loc[corrupted["paper_id"].isin(paper_ids)]
            event_checks["summaries_blank"] = bool(rows["summary"].eq("").all())
            event_checks["summary_chars_zero"] = bool(rows["summary_chars"].eq(0).all())
        elif event_type == "noise_injection":
            token = event["parameters"]["token"]
            repetitions = int(event["parameters"]["repetitions"])
            rows = corrupted.loc[corrupted["paper_id"].isin(paper_ids)]
            event_checks["noise_token_count_matches"] = bool(
                rows["summary"].map(lambda value: str(value).count(token) == repetitions).all()
            )
        elif event_type == "old_published_date":
            days = int(event["parameters"]["days_shifted_back"])
            event_checks["dates_and_age_shift_match"] = all(
                date.fromisoformat(
                    str(corrupted.loc[corrupted["paper_id"] == paper_id, "published"].iloc[0])
                )
                == date.fromisoformat(str(baseline_by_id.at[paper_id, "published"]))
                - timedelta(days=days)
                and int(
                    corrupted.loc[corrupted["paper_id"] == paper_id, "age_days"].iloc[0]
                )
                == int(baseline_by_id.at[paper_id, "age_days"]) + days
                for paper_id in paper_ids
            )
        elif event_type == "duplicate_rows":
            event_checks["two_occurrences_per_id"] = all(
                int((corrupted["paper_id"] == paper_id).sum()) == 2
                for paper_id in paper_ids
            )
        previous_count = int(event["after_count"])
        if event_type == "duplicate_rows":
            event_checks["final_stage_count_matches_dataset"] = previous_count == len(
                corrupted
            )
        event_results.append(
            {
                "sequence": event["sequence"],
                "type": event["type"],
                "paper_ids": paper_ids,
                "checks": event_checks,
                "passed": all(event_checks.values()),
            }
        )

    expected_text = corrupted.apply(
        lambda row: build_text_for_embedding(
            str(row["title"]),
            str(row["summary"]),
            str(row["authors_joined"]),
            str(row["categories_joined"]),
        ),
        axis=1,
    )
    checks.update(
        {
            "final_row_count_matches_log": len(corrupted) == log["result"]["rows"],
            "duplicate_count_matches_log": int(corrupted["paper_id"].duplicated().sum())
            == log["result"]["duplicate_rows"],
            "all_embedding_text_rebuilt": bool(
                corrupted["text_for_embedding"].eq(expected_text).all()
            ),
            "raw_source_guard_verified": log["raw_source_guard"]["status"]
            in {"verified", "not_available"},
        }
    )
    return {
        "passed": all(checks.values()) and all(item["passed"] for item in event_results),
        "checks": checks,
        "events": event_results,
        "baseline_rows": len(baseline),
        "corrupted_rows": len(corrupted),
        "row_delta": len(corrupted) - len(baseline),
        "lineage_repair_candidate": log["lineage_repair_candidate"],
    }


def validate_repair_against_baseline(
    baseline: pd.DataFrame,
    repaired: pd.DataFrame,
    lineage_paper_id: str | None = None,
) -> dict[str, Any]:
    """Prove that a dataset rebuilt from raw records restores the clean baseline."""

    expected_columns = list(CLEAN_COLUMNS)
    columns_match = list(repaired.columns) == expected_columns
    baseline_columns_match = list(baseline.columns) == expected_columns
    comparable = columns_match and baseline_columns_match

    baseline_view = (
        baseline.loc[:, expected_columns].reset_index(drop=True)
        if baseline_columns_match
        else baseline.reset_index(drop=True)
    )
    repaired_view = (
        repaired.loc[:, expected_columns].reset_index(drop=True)
        if columns_match
        else repaired.reset_index(drop=True)
    )
    baseline_ids = set(baseline.get("paper_id", pd.Series(dtype=str)).astype(str))
    repaired_ids = set(repaired.get("paper_id", pd.Series(dtype=str)).astype(str))

    checks: dict[str, bool] = {
        "clean_schema_exact": comparable,
        "row_count_restored": len(repaired) == len(baseline),
        "paper_id_set_restored": repaired_ids == baseline_ids,
        "paper_ids_unique": "paper_id" in repaired
        and not repaired["paper_id"].isna().any()
        and not repaired["paper_id"].duplicated().any(),
        "records_exactly_match_baseline": comparable
        and _frame_fingerprint(repaired_view) == _frame_fingerprint(baseline_view),
        "text_for_embedding_nonempty": "text_for_embedding" in repaired
        and bool(repaired["text_for_embedding"].fillna("").astype(str).str.strip().ne("").all()),
    }

    lineage: dict[str, Any] = {"paper_id": lineage_paper_id, "checked": False}
    if lineage_paper_id is not None:
        baseline_lineage = baseline.loc[baseline["paper_id"] == lineage_paper_id]
        repaired_lineage = repaired.loc[repaired["paper_id"] == lineage_paper_id]
        lineage_checks = {
            "present_once": len(baseline_lineage) == 1 and len(repaired_lineage) == 1,
            "summary_restored": False,
            "text_for_embedding_restored": False,
        }
        if lineage_checks["present_once"]:
            lineage_checks["summary_restored"] = (
                repaired_lineage.iloc[0]["summary"] == baseline_lineage.iloc[0]["summary"]
            )
            lineage_checks["text_for_embedding_restored"] = (
                repaired_lineage.iloc[0]["text_for_embedding"]
                == baseline_lineage.iloc[0]["text_for_embedding"]
            )
        lineage = {
            "paper_id": lineage_paper_id,
            "checked": True,
            "checks": lineage_checks,
            "passed": all(lineage_checks.values()),
        }
        checks["lineage_record_restored"] = lineage["passed"]

    return {
        "available": True,
        "passed": all(checks.values()),
        "checks": checks,
        "baseline_rows": len(baseline),
        "repaired_rows": len(repaired),
        "baseline_fingerprint_sha256": _frame_fingerprint(baseline_view),
        "repaired_fingerprint_sha256": _frame_fingerprint(repaired_view),
        "missing_paper_ids": sorted(baseline_ids - repaired_ids),
        "unexpected_paper_ids": sorted(repaired_ids - baseline_ids),
        "lineage": lineage,
    }
