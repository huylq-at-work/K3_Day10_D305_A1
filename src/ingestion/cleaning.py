from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.contract import CLEAN_COLUMNS as CONTRACT_CLEAN_COLUMNS
from core.utils import normalize_whitespace, write_csv, write_json
from ingestion.crossref import PaperRecord, normalize_crossref_text, normalize_doi


# Role 1 owns the consumer contract. Role 2 imports it so producer and gate
# cannot silently drift apart. Keep a list alias for existing callers/tests.
CLEAN_COLUMNS = list(CONTRACT_CLEAN_COLUMNS)
DROP_REASONS = (
    "missing_paper_id",
    "missing_title",
    "missing_summary",
    "missing_published",
    "invalid_published",
    "duplicate_paper_id",
)
NORMALIZATION_REASONS = (
    "authors_fallback_unknown",
    "categories_fallback_unknown",
    "primary_category_repaired",
    "updated_fallback_published",
)


def _complete_counts(counter: Counter[str], known_reasons: tuple[str, ...]) -> dict[str, int]:
    keys = set(known_reasons) | set(counter)
    return {reason: int(counter[reason]) for reason in sorted(keys)}


def _clean_text(value: Any) -> str:
    return normalize_whitespace(value) if isinstance(value, str) else ""


def _clean_list(value: Any, fallback: str) -> list[str]:
    if not isinstance(value, (list, tuple)):
        value = []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = _clean_text(item)
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result or [fallback]


def _iso_date(value: Any) -> str:
    if value is None or value == "":
        return ""
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return ""
    return parsed.date().isoformat()


def _run_date(run_date: datetime) -> datetime:
    if run_date.tzinfo is None:
        return run_date.replace(tzinfo=UTC)
    return run_date.astimezone(UTC)


def _embedding_text(
    title: str,
    summary: str,
    authors_joined: str,
    categories_joined: str,
) -> str:
    return (
        f"Title: {title}\n"
        f"Authors: {authors_joined}\n"
        f"Categories: {categories_joined}\n"
        f"Abstract: {summary}"
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw records into the stable, embedding-ready clean schema.

    Required fields are paper_id, title, summary and a valid published date.
    Duplicate DOI values retain the row with the newest update and longest
    summary. Missing authors/categories become the explicit value ``Unknown``;
    optional URLs/comment remain empty strings.
    """

    dataframe, report = build_clean_dataframe_with_report(records, run_date)
    dataframe.attrs["cleaning_report"] = report
    return dataframe


def build_clean_dataframe_with_report(
    records: list[PaperRecord],
    run_date: datetime,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build clean data plus an explainable filter/deduplication report."""

    normalized_run_date = _run_date(run_date)
    as_of = normalized_run_date.date()
    rows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    normalizations: Counter[str] = Counter()
    for source_index, record in enumerate(records):
        paper_id = normalize_doi(record.paper_id)
        title = normalize_crossref_text(record.title)
        summary = normalize_crossref_text(record.summary)
        published = _iso_date(record.published)
        reasons: list[str] = []
        if not paper_id:
            reasons.append("missing_paper_id")
        if not title:
            reasons.append("missing_title")
        if not summary:
            reasons.append("missing_summary")
        if not published:
            reasons.append(
                "missing_published" if not _clean_text(record.published) else "invalid_published"
            )
        if reasons:
            reason_counts.update(reasons)
            events.append(
                {
                    "source_index": source_index,
                    "raw_paper_id": _clean_text(record.paper_id),
                    "normalized_paper_id": paper_id,
                    "action": "filtered",
                    "reasons": reasons,
                }
            )
            continue

        authors = _clean_list(record.authors, "Unknown")
        categories = _clean_list(record.categories, "Unknown")
        if authors == ["Unknown"]:
            normalizations["authors_fallback_unknown"] += 1
        if categories == ["Unknown"]:
            normalizations["categories_fallback_unknown"] += 1
        primary_category = _clean_text(record.primary_category)
        if primary_category.casefold() not in {item.casefold() for item in categories}:
            primary_category = categories[0]
            normalizations["primary_category_repaired"] += 1
        parsed_updated = _iso_date(record.updated)
        updated = parsed_updated or published
        if not parsed_updated:
            normalizations["updated_fallback_published"] += 1
        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        published_date = datetime.fromisoformat(published).date()

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "age_days": (as_of - published_date).days,
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": len(summary),
                "text_for_embedding": _embedding_text(
                    title, summary, authors_joined, categories_joined
                ),
                "_source_index": source_index,
            }
        )

    filtered_count = len(records) - len(rows)
    if not rows:
        dataframe = pd.DataFrame(columns=CLEAN_COLUMNS)
        report = {
            "run_date": normalized_run_date.isoformat(),
            "input_records": len(records),
            "candidate_records": 0,
            "clean_records": 0,
            "filtered_records": filtered_count,
            "deduplicated_records": 0,
            "duplicate_groups": 0,
            "reason_counts": _complete_counts(reason_counts, DROP_REASONS),
            "normalization_counts": _complete_counts(
                normalizations, NORMALIZATION_REASONS
            ),
            "events": events,
            "count_reconciled": len(records) == filtered_count,
        }
        dataframe.attrs["cleaning_report"] = report
        return dataframe, report

    candidates = pd.DataFrame(rows)
    ranked = candidates.sort_values(
        ["paper_id", "updated", "summary_chars"],
        ascending=[True, False, False],
        kind="stable",
    )
    duplicate_mask = ranked.duplicated(subset=["paper_id"], keep="first")
    duplicate_rows = ranked.loc[duplicate_mask]
    kept_source_by_id = {
        row["paper_id"]: int(row["_source_index"])
        for _, row in ranked.loc[~duplicate_mask].iterrows()
    }
    for _, row in duplicate_rows.iterrows():
        reason_counts["duplicate_paper_id"] += 1
        events.append(
            {
                "source_index": int(row["_source_index"]),
                "raw_paper_id": _clean_text(records[int(row["_source_index"])].paper_id),
                "normalized_paper_id": row["paper_id"],
                "action": "deduplicated",
                "reasons": ["duplicate_paper_id"],
                "kept_source_index": kept_source_by_id[row["paper_id"]],
            }
        )

    deduplicated_count = int(duplicate_mask.sum())
    duplicate_groups = int(duplicate_rows["paper_id"].nunique())
    dataframe = ranked.loc[~duplicate_mask, CLEAN_COLUMNS]
    dataframe = dataframe.sort_values(
        ["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
    report = {
        "run_date": normalized_run_date.isoformat(),
        "input_records": len(records),
        "candidate_records": len(candidates),
        "clean_records": len(dataframe),
        "filtered_records": filtered_count,
        "deduplicated_records": deduplicated_count,
        "duplicate_groups": duplicate_groups,
        "reason_counts": _complete_counts(reason_counts, DROP_REASONS),
        "normalization_counts": _complete_counts(
            normalizations, NORMALIZATION_REASONS
        ),
        "events": sorted(events, key=lambda event: event["source_index"]),
        "count_reconciled": (
            len(records) == filtered_count + deduplicated_count + len(dataframe)
        ),
    }
    dataframe.attrs["cleaning_report"] = report
    return dataframe, report


def write_clean_artifacts(
    dataframe: pd.DataFrame,
    csv_path: Path,
    json_path: Path,
    report_path: Path,
    report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist the clean dataset and the report explaining row-count changes."""

    cleaning_report = report or dataframe.attrs.get("cleaning_report")
    if not isinstance(cleaning_report, dict):
        raise ValueError(
            "Cleaning report is missing. Build the dataframe with "
            "build_clean_dataframe or pass report explicitly."
        )
    write_csv(dataframe, csv_path)
    write_json(json_path, dataframe.to_dict(orient="records"))
    write_json(report_path, cleaning_report)
    return cleaning_report
