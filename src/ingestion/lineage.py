"""Read-only lineage and evidence checks across baseline data artifacts."""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from core.config import Settings, load_settings
from core.contract import CHROMA_METADATA_COLUMNS, CLEAN_COLUMNS, MARKUP
from core.utils import write_json
from ingestion.crossref import normalize_doi


REQUIRED_TEST_FIELDS = (
    "id",
    "question_type",
    "question",
    "ground_truth",
    "ground_truth_doc_ids",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _portable_path(path: Path, project_dir: Path) -> str:
    try:
        return path.resolve().relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _text_evidence(value: Any, preview_chars: int = 240) -> dict[str, Any]:
    text = "" if value is None else str(value)
    return {
        "chars": len(text),
        "sha256": _sha256_text(text),
        "preview": text[:preview_chars],
    }


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not isinstance(value, str):
        return []
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        parsed = None
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


def _expected_clean_value(question_type: str, clean_record: dict[str, Any]) -> Any:
    if question_type == "summary":
        return clean_record["summary"]
    if question_type == "authors":
        return clean_record["authors"]
    if question_type == "categories":
        return clean_record["categories"]
    if question_type == "date":
        return clean_record["published"]
    return None


def _raw_source_value(question_type: str, source_item: dict[str, Any]) -> Any:
    if question_type == "summary":
        return source_item.get("abstract")
    if question_type == "authors":
        return source_item.get("author")
    if question_type == "categories":
        return (
            source_item.get("subject")
            or source_item.get("container-title")
            or source_item.get("type")
        )
    if question_type == "date":
        return (
            source_item.get("published")
            or source_item.get("issued")
            or source_item.get("created")
        )
    return None


def _json_evidence(value: Any) -> dict[str, Any]:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return _text_evidence(value)


def _semantically_equal(question_type: str, left: Any, right: Any) -> bool:
    if question_type in {"authors", "categories"}:
        return [item.casefold() for item in _as_list(left)] == [
            item.casefold() for item in _as_list(right)
        ]
    return str(left).strip() == str(right).strip()


def verify_or_create_source_lock(settings: Settings, lock_path: Path) -> dict[str, Any]:
    """Fingerprint baseline source artifacts and reject mid-baseline replacement."""

    source_paths = {
        "raw_api_response": settings.paths.raw_api_response,
        "raw_records": settings.paths.raw_records_json,
    }
    missing = [name for name, path in source_paths.items() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Cannot lock missing baseline source artifacts: {missing}")

    current_hashes = {name: _sha256_file(path) for name, path in source_paths.items()}
    current = {
        "version": 1,
        "source_mode": "raw snapshot",
        "refresh_source_required": False,
        "refresh_source_setting": settings.refresh_source,
        "paths": {
            name: _portable_path(path, settings.paths.project_dir)
            for name, path in source_paths.items()
        },
        "sha256": current_hashes,
    }
    if settings.refresh_source:
        raise RuntimeError(
            "REFRESH_SOURCE is enabled. Disable it before auditing the fixed baseline."
        )

    if lock_path.exists():
        locked = _read_json(lock_path)
        if locked.get("sha256") != current_hashes:
            raise RuntimeError(
                f"Baseline source changed after it was locked; inspect {lock_path}."
            )
        current["status"] = "verified"
        current["matches_existing_lock"] = True
    else:
        current["status"] = "created"
        current["matches_existing_lock"] = True
        write_json(lock_path, current)
    return current


def build_baseline_lineage_evidence(
    settings: Settings,
    paper_id: str | None = None,
) -> dict[str, Any]:
    """Audit one ID end-to-end and all clean/index/test-set invariants."""

    paths = settings.paths
    payload = _read_json(paths.raw_api_response)
    raw_records = _read_json(paths.raw_records_json)
    clean_records = _read_json(paths.clean_json)
    embedding_manifest = _read_json(paths.embeddings_json)
    test_set = _read_json(paths.eval_testset)
    baseline_answers = (
        _read_json(paths.baseline_answers) if paths.baseline_answers.exists() else []
    )

    raw_by_id = {normalize_doi(record.get("paper_id")): record for record in raw_records}
    clean_by_id = {normalize_doi(record.get("paper_id")): record for record in clean_records}
    documents = embedding_manifest.get("documents", [])
    document_by_id = {
        normalize_doi(document.get("paper_id")): document for document in documents
    }
    test_ids = [
        normalize_doi(doc_id)
        for sample in test_set
        for doc_id in sample.get("ground_truth_doc_ids", [])
    ]
    selected_id = normalize_doi(paper_id) if paper_id else next(
        (item for item in test_ids if item in clean_by_id),
        next(iter(clean_by_id), ""),
    )
    if not selected_id:
        raise ValueError("No paper_id is available for lineage tracing.")

    raw_items = payload.get("message", {}).get("items", [])
    source_index = next(
        (
            index
            for index, item in enumerate(raw_items)
            if isinstance(item, dict) and normalize_doi(item.get("DOI")) == selected_id
        ),
        None,
    )
    source_item = raw_items[source_index] if source_index is not None else None
    raw_record = raw_by_id.get(selected_id)
    clean_record = clean_by_id.get(selected_id)
    index_document = document_by_id.get(selected_id)
    if not raw_record or not clean_record or not index_document or not source_item:
        raise ValueError(
            f"paper_id {selected_id!r} is not present in every raw/clean/index layer."
        )

    metadata = index_document.get("metadata", {})
    metadata_matches = {
        field: metadata.get(field) == clean_record.get(field)
        for field in CHROMA_METADATA_COLUMNS
    }
    lineage_checks = {
        "raw_doi_normalizes_to_paper_id": normalize_doi(source_item.get("DOI"))
        == selected_id,
        "raw_record_paper_id_matches": normalize_doi(raw_record.get("paper_id"))
        == selected_id,
        "clean_paper_id_matches": normalize_doi(clean_record.get("paper_id"))
        == selected_id,
        "index_document_paper_id_matches": normalize_doi(index_document.get("paper_id"))
        == selected_id,
        "index_metadata_paper_id_matches": normalize_doi(metadata.get("paper_id"))
        == selected_id,
        "index_content_matches_text_for_embedding": index_document.get("content")
        == clean_record.get("text_for_embedding"),
        "all_index_metadata_matches_clean": all(metadata_matches.values()),
    }

    clean_ids = [normalize_doi(record.get("paper_id")) for record in clean_records]
    index_ids = [normalize_doi(document.get("paper_id")) for document in documents]
    missing_clean_columns = sorted(
        set(CLEAN_COLUMNS) - set(clean_records[0] if clean_records else {})
    )
    missing_index_metadata = sorted(
        set(CHROMA_METADATA_COLUMNS) - set(metadata)
    )
    clean_index_checks = {
        "clean_rows": len(clean_records),
        "index_documents": len(documents),
        "empty_text_for_embedding": sum(
            not str(record.get("text_for_embedding", "")).strip()
            for record in clean_records
        ),
        "duplicate_clean_paper_ids": len(clean_ids) - len(set(clean_ids)),
        "duplicate_index_paper_ids": len(index_ids) - len(set(index_ids)),
        "empty_index_content": sum(
            not str(document.get("content", "")).strip() for document in documents
        ),
        "clean_and_index_id_sets_match": set(clean_ids) == set(index_ids),
        "missing_clean_contract_columns": missing_clean_columns,
        "missing_index_metadata_fields": missing_index_metadata,
    }

    category_counts = Counter(record.get("categories_joined", "") for record in clean_records)
    test_rows: list[dict[str, Any]] = []
    test_blockers: list[str] = []
    test_warnings: list[str] = []
    type_counts: Counter[str] = Counter()
    test_sample_ids = [str(sample.get("id", "")) for sample in test_set]
    duplicate_test_sample_ids = len(test_sample_ids) - len(set(test_sample_ids))
    if duplicate_test_sample_ids:
        test_blockers.append(
            f"test_set_has_{duplicate_test_sample_ids}_duplicate_sample_ids"
        )
    for sample_index, sample in enumerate(test_set):
        question_type = str(sample.get("question_type", ""))
        type_counts[question_type] += 1
        required_missing = [field for field in REQUIRED_TEST_FIELDS if field not in sample]
        ids = [normalize_doi(value) for value in sample.get("ground_truth_doc_ids", [])]
        doc_id = ids[0] if len(ids) == 1 else ""
        selected_clean = clean_by_id.get(doc_id)
        raw_record_found = doc_id in raw_by_id
        index_document_found = doc_id in document_by_id
        row_issues: list[str] = []
        row_warnings: list[str] = []
        if required_missing:
            row_issues.append(f"missing_test_fields:{required_missing}")
        if len(ids) != 1:
            row_issues.append("ground_truth_doc_ids_must_have_exactly_one_id")
        if selected_clean is None:
            row_issues.append("ground_truth_doc_id_not_in_clean")
            expected = None
            ground_truth_matches = False
        else:
            if not raw_record_found:
                row_issues.append("ground_truth_doc_id_not_in_raw_records")
            if not index_document_found:
                row_issues.append("ground_truth_doc_id_not_in_index_manifest")
            expected = _expected_clean_value(question_type, selected_clean)
            if expected is None:
                row_issues.append("unsupported_question_type")
                ground_truth_matches = False
            else:
                ground_truth_matches = _semantically_equal(
                    question_type, sample.get("ground_truth"), expected
                )
                if not ground_truth_matches:
                    row_issues.append("ground_truth_does_not_match_clean")
            if not str(selected_clean.get("text_for_embedding", "")).strip():
                row_issues.append("selected_clean_embedding_text_empty")
            if MARKUP.search(str(selected_clean.get("summary", ""))):
                row_issues.append("selected_clean_summary_contains_markup")
            if str(selected_clean.get("title", "")) not in str(sample.get("question", "")):
                row_issues.append("question_does_not_reference_clean_title")
            if question_type == "categories":
                shared_count = category_counts[selected_clean.get("categories_joined", "")]
                if shared_count > 1:
                    row_warnings.append(
                        f"category_ground_truth_shared_by_{shared_count}_clean_rows"
                    )
            if question_type in {"authors", "categories"} and isinstance(
                sample.get("ground_truth"), str
            ) and sample["ground_truth"].lstrip().startswith("["):
                row_warnings.append("ground_truth_serialized_as_python_list_string")

        test_blockers.extend(
            f"row_{sample_index}:{issue}" for issue in row_issues
        )
        test_warnings.extend(
            f"row_{sample_index}:{warning}" for warning in row_warnings
        )
        test_rows.append(
            {
                "sample_index": sample_index,
                "id": sample.get("id"),
                "question_type": question_type,
                "paper_id": doc_id,
                "raw_record_found": raw_record_found,
                "clean_record_found": selected_clean is not None,
                "index_document_found": index_document_found,
                "ground_truth_matches_clean_semantically": ground_truth_matches,
                "issues": row_issues,
                "warnings": row_warnings,
            }
        )

    if type_counts["date"] == 0:
        test_warnings.append(
            "No date questions were generated although clean schema provides `published`; "
            "the test-set consumer must read `published`, not `published_date`."
        )

    answer_by_id = {answer.get("id"): answer for answer in baseline_answers}
    incorrect_evidence: list[dict[str, Any]] = []
    trace_by_id = {
        normalize_doi(item.get("DOI")): index
        for index, item in enumerate(raw_items)
        if isinstance(item, dict)
    }
    for sample in test_set:
        answer = answer_by_id.get(sample.get("id"))
        if not answer:
            continue
        judge_correct = bool(answer.get("judge", {}).get("correct"))
        token_f1 = float(answer.get("token_f1", 0.0))
        if judge_correct and token_f1 >= 0.999:
            continue
        question_type = str(sample.get("question_type", ""))
        ids = [normalize_doi(value) for value in sample.get("ground_truth_doc_ids", [])]
        doc_id = ids[0] if len(ids) == 1 else ""
        selected_clean = clean_by_id.get(doc_id, {})
        expected = _expected_clean_value(question_type, selected_clean) if selected_clean else None
        actual_answer = answer.get("answer", "")
        answer_source_index = trace_by_id.get(doc_id)
        answer_source_item = (
            raw_items[answer_source_index] if answer_source_index is not None else {}
        )
        incorrect_evidence.append(
            {
                "question_id": sample.get("id"),
                "question_type": question_type,
                "paper_id": doc_id,
                "raw_source_pointer": {
                    "path": _portable_path(paths.raw_api_response, paths.project_dir),
                    "message_item_index": answer_source_index,
                    "source_field": {
                        "summary": "abstract",
                        "authors": "author",
                        "categories": "subject/container-title/type",
                        "date": "published/issued/created",
                    }.get(question_type),
                },
                "raw_source_value": _json_evidence(
                    _raw_source_value(question_type, answer_source_item)
                ),
                "ground_truth_matches_clean_semantically": (
                    _semantically_equal(question_type, sample.get("ground_truth"), expected)
                    if expected is not None
                    else False
                ),
                "answer_matches_clean_semantically": (
                    _semantically_equal(question_type, actual_answer, expected)
                    if expected is not None
                    else False
                ),
                "ground_truth": _text_evidence(sample.get("ground_truth")),
                "clean_expected": _text_evidence(expected),
                "actual_answer": _text_evidence(actual_answer),
                "retrieved_doc_ids": answer.get("retrieved_doc_ids", []),
                "retrieval_hit": bool(answer.get("retrieval_hit")),
                "token_f1": token_f1,
                "judge": answer.get("judge", {}),
            }
        )

    lineage = {
        "paper_id": selected_id,
        "passed": all(lineage_checks.values()),
        "checks": lineage_checks,
        "metadata_field_matches": metadata_matches,
        "raw": {
            "path": _portable_path(paths.raw_api_response, paths.project_dir),
            "message_item_index": source_index,
            "doi": source_item.get("DOI"),
            "title": source_item.get("title"),
        },
        "raw_record": {
            "path": _portable_path(paths.raw_records_json, paths.project_dir),
            "paper_id": raw_record.get("paper_id"),
        },
        "clean": {
            "path": _portable_path(paths.clean_json, paths.project_dir),
            "paper_id": clean_record.get("paper_id"),
            "text_for_embedding": _text_evidence(clean_record.get("text_for_embedding")),
        },
        "index_manifest": {
            "path": _portable_path(paths.embeddings_json, paths.project_dir),
            "collection_name": embedding_manifest.get("collection_name"),
            "paper_id": index_document.get("paper_id"),
            "record_id": index_document.get("record_id"),
            "content": _text_evidence(index_document.get("content")),
            "metadata": metadata,
        },
        "test_set_references": [
            sample.get("id")
            for sample in test_set
            if selected_id
            in [normalize_doi(value) for value in sample.get("ground_truth_doc_ids", [])]
        ],
    }
    schema_decision = {
        "clean_contract_change_required": bool(missing_clean_columns or missing_index_metadata),
        "missing_clean_contract_columns": missing_clean_columns,
        "missing_index_metadata_fields": missing_index_metadata,
        "decision": (
            "No schema change: index consumes all contracted fields. The missing date "
            "questions are a test-set consumer bug (`published_date` vs `published`)."
            if not missing_clean_columns and not missing_index_metadata
            else "Contract/producer alignment requires repair before indexing."
        ),
    }
    return {
        "status": "passed"
        if lineage["passed"]
        and not test_blockers
        and not any(
            clean_index_checks[key]
            for key in (
                "empty_text_for_embedding",
                "duplicate_clean_paper_ids",
                "duplicate_index_paper_ids",
                "empty_index_content",
            )
        )
        else "failed",
        "lineage": lineage,
        "clean_index_checks": clean_index_checks,
        "test_set_audit": {
            "samples": len(test_set),
            "duplicate_sample_ids": duplicate_test_sample_ids,
            "question_type_counts": dict(sorted(type_counts.items())),
            "blockers": test_blockers,
            "warnings": test_warnings,
            "rows": test_rows,
        },
        "incorrect_answer_source_evidence": incorrect_evidence,
        "schema_decision": schema_decision,
    }


def write_baseline_evidence(
    settings: Settings,
    paper_id: str | None = None,
) -> dict[str, Any]:
    """Verify source lock and write all Role 2 CP3 evidence under owned paths."""

    lock_path = settings.paths.raw_records_json.parent / "baseline_source_lock.json"
    lock = verify_or_create_source_lock(settings, lock_path)
    report = build_baseline_lineage_evidence(settings, paper_id=paper_id)
    report["source_lock"] = lock
    report_path = settings.paths.clean_json.parent / "baseline_lineage_evidence.json"
    write_json(report_path, report)
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-id", help="Stable ID to trace; default: first test-set paper.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = write_baseline_evidence(load_settings(), paper_id=args.paper_id)
    summary = {
        "status": report["status"],
        "paper_id": report["lineage"]["paper_id"],
        "lineage_passed": report["lineage"]["passed"],
        "clean_index_checks": report["clean_index_checks"],
        "test_set_blockers": len(report["test_set_audit"]["blockers"]),
        "test_set_warnings": len(report["test_set_audit"]["warnings"]),
        "incorrect_answer_evidence": len(report["incorrect_answer_source_evidence"]),
        "schema_decision": report["schema_decision"],
        "source_lock": report["source_lock"]["status"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
