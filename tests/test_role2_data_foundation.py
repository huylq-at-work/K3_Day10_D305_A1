from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
import json

import pandas as pd
import pytest

from core.config import load_settings
from ingestion.cleaning import (
    CLEAN_COLUMNS,
    build_clean_dataframe,
    write_clean_artifacts,
)
from ingestion.crossref import (
    PaperRecord,
    audit_crossref_payload,
    audit_raw_snapshot,
    fetch_source_records,
    load_raw_records,
    parse_crossref_payload,
)
from ingestion.lineage import (
    build_baseline_lineage_evidence,
    verify_or_create_source_lock,
)
from pipelines.phase1 import resolve_records


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


def test_crossref_audit_traces_rejection_reasons() -> None:
    duplicate = _item("https://doi.org/10.1000/test")
    missing_doi = {**_item(), "DOI": ""}
    invalid = {
        **_item("10.1000/invalid"),
        "abstract": "",
        "published": {"date-parts": [[2026, 99, 1]]},
    }
    payload = {"message": {"items": [_item(), duplicate, missing_doi, invalid]}}

    audit = audit_crossref_payload(payload)

    assert audit["parsed_records"] == 1
    assert audit["rejected_items"] == 3
    assert audit["reason_counts"] == {
        "duplicate_doi": 1,
        "invalid_published_date": 1,
        "missing_abstract": 1,
        "missing_doi": 1,
    }
    assert audit["parser_trace_matches_records"] is True
    assert audit["id_trace"][1]["normalized_paper_id"] == "10.1000/test"


def test_clean_schema_deduplication_and_derived_fields() -> None:
    record = parse_crossref_payload({"message": {"items": [_item()]}})[0]
    richer = replace(
        record,
        summary="<jats:p>A  longer replacement abstract.</jats:p>",
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
    report = dataframe.attrs["cleaning_report"]
    assert report["input_records"] == 3
    assert report["clean_records"] == 1
    assert report["filtered_records"] == 1
    assert report["deduplicated_records"] == 1
    assert report["reason_counts"]["duplicate_paper_id"] == 1
    assert report["reason_counts"]["invalid_published"] == 1
    assert report["reason_counts"]["missing_title"] == 0
    assert report["count_reconciled"] is True


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


def test_raw_handoff_and_clean_artifact_writers(tmp_path) -> None:
    payload = {"message": {"items": [_item()]}}
    response_path = tmp_path / "data" / "raw" / "crossref_response.json"
    records_path = tmp_path / "data" / "raw" / "crossref_records.json"
    response_path.parent.mkdir(parents=True)
    response_path.write_text(json.dumps(payload), encoding="utf-8")
    parsed = parse_crossref_payload(payload)
    records_path.write_text(
        json.dumps([record.__dict__ for record in parsed]), encoding="utf-8"
    )
    audit_path = response_path.parent / "raw_snapshot_audit.json"
    handoff_path = response_path.parent / "cleaning_handoff.json"

    audit, handoff = audit_raw_snapshot(
        response_path, records_path, audit_path, handoff_path
    )

    assert audit["passed"] is True
    assert handoff["raw_paths"]["api_response"] == "data/raw/crossref_response.json"
    assert handoff["sample_record"]["paper_id"] == "10.1000/test"
    assert handoff["cleaning_readiness"]["ready"] is True
    assert audit_path.exists() and handoff_path.exists()

    dataframe = build_clean_dataframe(parsed, datetime(2026, 8, 6, tzinfo=UTC))
    clean_dir = tmp_path / "data" / "clean"
    report = write_clean_artifacts(
        dataframe,
        clean_dir / "papers.csv",
        clean_dir / "papers.json",
        clean_dir / "cleaning_report.json",
    )
    assert report["clean_records"] == 1
    assert (clean_dir / "papers.csv").exists()
    assert (clean_dir / "papers.json").exists()


def test_baseline_lineage_and_testset_are_traceable() -> None:
    report = build_baseline_lineage_evidence(load_settings())

    assert report["lineage"]["passed"] is True
    assert report["lineage"]["checks"]["index_content_matches_text_for_embedding"]
    assert report["clean_index_checks"]["empty_text_for_embedding"] == 0
    assert report["clean_index_checks"]["duplicate_clean_paper_ids"] == 0
    assert report["clean_index_checks"]["duplicate_index_paper_ids"] == 0
    assert report["raw_clean_count_reconciliation"]["difference_explained"] is True
    assert report["artifact_validation"]["age_days_mismatch_count"] == 0
    assert report["artifact_validation"]["text_for_embedding_mismatch_count"] == 0
    assert report["artifact_validation"]["quality_report"][
        "reflects_clean_artifact"
    ] is True
    assert isinstance(
        report["artifact_validation"]["freshness_report"]["reflects_clean_artifact"],
        bool,
    )
    assert isinstance(report["baseline_answer_alignment"]["ids_match"], bool)
    assert report["test_set_audit"]["blockers"] == []
    assert report["test_set_audit"]["duplicate_sample_ids"] == 0
    assert all(
        row["raw_record_found"]
        and row["clean_record_found"]
        and row["index_document_found"]
        for row in report["test_set_audit"]["rows"]
    )
    assert report["schema_decision"]["clean_contract_change_required"] is False
    assert report["incorrect_answer_source_evidence"]
    assert all(
        item["ground_truth_matches_clean_semantically"]
        for item in report["incorrect_answer_source_evidence"]
    )
    assert all(
        item["raw_source_value"]["chars"] > 0
        for item in report["incorrect_answer_source_evidence"]
    )


def test_source_lock_detects_mid_baseline_refresh(tmp_path) -> None:
    settings = load_settings(tmp_path)
    settings.paths.raw_api_response.parent.mkdir(parents=True)
    settings.paths.raw_api_response.write_text('{"snapshot": 1}', encoding="utf-8")
    settings.paths.raw_records_json.write_text("[]", encoding="utf-8")
    lock_path = settings.paths.raw_records_json.parent / "baseline_source_lock.json"

    created = verify_or_create_source_lock(settings, lock_path)
    verified = verify_or_create_source_lock(settings, lock_path)
    assert created["status"] == "created"
    assert verified["status"] == "verified"

    settings.paths.raw_records_json.write_text('[{"changed": true}]', encoding="utf-8")
    with pytest.raises(RuntimeError, match="Baseline source changed"):
        verify_or_create_source_lock(settings, lock_path)


def test_phase1_uses_raw_snapshot_without_fetching(tmp_path, monkeypatch) -> None:
    settings = replace(load_settings(tmp_path), refresh_source=False)
    payload = {"message": {"items": [_item()]}}
    records = parse_crossref_payload(payload)
    settings.paths.raw_records_json.parent.mkdir(parents=True)
    settings.paths.raw_records_json.write_text(
        json.dumps([record.__dict__ for record in records]), encoding="utf-8"
    )

    def unexpected_fetch(_settings):
        raise AssertionError("Crossref must not be fetched while raw snapshot exists")

    monkeypatch.setattr("pipelines.phase1.fetch_source_records", unexpected_fetch)
    resolved, source_mode = resolve_records(settings)

    assert resolved == records
    assert source_mode == "raw snapshot"
