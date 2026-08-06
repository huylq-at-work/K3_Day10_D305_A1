from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.utils import normalize_whitespace
from ingestion.crossref import PaperRecord


CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "text_for_embedding",
]


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

    as_of = _run_date(run_date).date()
    rows: list[dict[str, Any]] = []
    for record in records:
        paper_id = _clean_text(record.paper_id).lower()
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
        published = _iso_date(record.published)
        if not paper_id or not title or not summary or not published:
            continue

        authors = _clean_list(record.authors, "Unknown")
        categories = _clean_list(record.categories, "Unknown")
        primary_category = _clean_text(record.primary_category)
        if primary_category.casefold() not in {item.casefold() for item in categories}:
            primary_category = categories[0]
        updated = _iso_date(record.updated) or published
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
            }
        )

    if not rows:
        return pd.DataFrame(columns=CLEAN_COLUMNS)

    dataframe = pd.DataFrame(rows, columns=CLEAN_COLUMNS)
    dataframe = dataframe.sort_values(
        ["paper_id", "updated", "summary_chars"],
        ascending=[True, False, False],
        kind="stable",
    ).drop_duplicates(subset=["paper_id"], keep="first")
    return dataframe.sort_values(
        ["published", "paper_id"], ascending=[False, True], kind="stable"
    ).reset_index(drop=True)
