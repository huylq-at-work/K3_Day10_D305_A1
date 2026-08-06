from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json

import pandas as pd

from core.config import load_settings
from ingestion.cleaning import CLEAN_COLUMNS, build_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records, parse_crossref_payload


def _item(doi: str = "10.1000/Test") -> dict:
    return {
        "DOI": doi,
        "title": ["  Useful   Paper "],
        "abstract": "<jats:p>An &amp; abstract.</jats:p>",
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "subject": [],
        "container-title": ["Journal of Tests"],
        "type": "journal-article",
        "published": {"date-parts": [[2026, 7]]},
        "deposited": {"date-parts": [[2026, 7, 3]]},
        "URL": "https://doi.org/10.1000/Test",
        "link": [{"URL": "https://example.test/paper.pdf", "content-type": "application/pdf"}],
        "publisher": "Test Press",
    }


def test_parse_normalizes_crossref_fields() -> None:
    records = parse_crossref_payload({"message": {"items": [_item()]}})

    assert records == [
        PaperRecord(
            paper_id="10.1000/test",
            title="Useful Paper",
            summary="An & abstract.",
            authors=["Ada Lovelace"],
            categories=["Journal of Tests"],
            primary_category="Journal of Tests",
            published="2026-07-01",
            updated="2026-07-03",
            abs_url="https://doi.org/10.1000/Test",
            pdf_url="https://example.test/paper.pdf",
            comment="journal-article; Test Press",
        )
    ]


def test_parse_drops_invalid_and_duplicate_doi() -> None:
    duplicate = _item("https://doi.org/10.1000/test")
    missing_summary = {**_item("10.1000/missing"), "abstract": ""}
    records = parse_crossref_payload(
        {"message": {"items": [_item(), duplicate, missing_summary, "bad-item"]}}
    )
    assert [record.paper_id for record in records] == ["10.1000/test"]


def test_clean_schema_deduplication_and_derived_fields() -> None:
    record = parse_crossref_payload({"message": {"items": [_item()]}})[0]
    richer = replace(
        record,
        summary="A longer replacement abstract.",
        authors=[],
        categories=[],
        primary_category="",
        updated="2026-07-04",
    )
    invalid = replace(record, paper_id="10.1000/invalid", published="not-a-date")

    dataframe = build_clean_dataframe(
        [record, richer, invalid], datetime(2026, 8, 6, tzinfo=UTC)
    )

    assert dataframe.columns.tolist() == CLEAN_COLUMNS
    assert len(dataframe) == 1
    row = dataframe.iloc[0]
    assert row["summary"] == "A longer replacement abstract."
    assert row["authors"] == ["Unknown"]
    assert row["categories"] == ["Unknown"]
    assert row["age_days"] == 36
    assert row["summary_chars"] == len(row["summary"])
    assert row["text_for_embedding"] == (
        "Title: Useful Paper\nAuthors: Unknown\nCategories: Unknown\n"
        "Abstract: A longer replacement abstract."
    )


def test_fetch_retries_persists_and_loads(tmp_path, monkeypatch) -> None:
    class Response:
        def __init__(self, status_code: int, payload: dict, retry_after: str = "") -> None:
            self.status_code = status_code
            self._payload = payload
            self.headers = {"Retry-After": retry_after} if retry_after else {}

        def json(self) -> dict:
            return self._payload

        def raise_for_status(self) -> None:
            raise AssertionError("raise_for_status should not be called for retryable responses")

    payload = {"message": {"items": [_item()]}}
    responses = iter([Response(429, {}, "0"), Response(503, {}), Response(200, payload)])
    sleeps: list[float] = []
    monkeypatch.setattr("ingestion.crossref.requests.get", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr("ingestion.crossref.time.sleep", sleeps.append)

    settings = load_settings(tmp_path)
    records = fetch_source_records(settings)

    assert len(records) == 1
    assert sleeps == [0.0, 2.0]
    assert json.loads(settings.paths.raw_api_response.read_text()) == payload
    assert load_raw_records(settings.paths.raw_records_json) == records


def test_cp1_snapshot_parses_and_cleans_without_jats() -> None:
    settings = load_settings()
    payload = json.loads(settings.paths.raw_api_response.read_text(encoding="utf-8"))
    records = parse_crossref_payload(payload)
    dataframe = build_clean_dataframe(records, datetime(2026, 8, 6, tzinfo=UTC))

    assert len(records) == 24
    assert len(dataframe) == 24
    assert dataframe["paper_id"].is_unique
    assert not dataframe["summary"].str.contains("<jats:", regex=False).any()
    assert dataframe["authors_joined"].ne("").all()
    assert dataframe["categories_joined"].ne("").all()
    assert pd.api.types.is_integer_dtype(dataframe["age_days"])
