from __future__ import annotations

from dataclasses import asdict, dataclass
from collections import Counter
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from typing import Any

import requests

from core.config import Settings
from core.utils import normalize_whitespace, write_json


CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_FETCH_ATTEMPTS = 5
INITIAL_BACKOFF_SECONDS = 1.0


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


class _TextExtractor(HTMLParser):
    """Extract text from Crossref's JATS/XML-ish abstract safely."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def normalize_crossref_text(value: Any) -> str:
    """Normalize whitespace/entities and remove Crossref JATS/HTML markup."""

    if not isinstance(value, str):
        return ""
    parser = _TextExtractor()
    try:
        # HTMLParser decodes entities in text nodes without turning an encoded
        # mathematical "<" into markup before parsing.
        parser.feed(value)
        parser.close()
        value = " ".join(parser.parts)
    except Exception:
        # Some publisher abstracts are not well-formed XML/HTML. This fallback
        # still prevents JATS tags from leaking into the embedding text.
        value = re.sub(r"<[^>]+>", " ", unescape(value))
    return normalize_whitespace(value)


# Internal alias keeps the parsing helpers concise.
_plain_text = normalize_crossref_text


def _first_text(value: Any) -> str:
    if isinstance(value, list):
        for item in value:
            text = _plain_text(item)
            if text:
                return text
        return ""
    return _plain_text(value)


def _unique_texts(value: Any) -> list[str]:
    values = value if isinstance(value, list) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _plain_text(item)
        key = text.casefold()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def normalize_doi(value: Any) -> str:
    """Normalize DOI into the stable ``paper_id`` used by every pipeline stage."""

    doi = _plain_text(value).lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


# Backward-compatible private alias for code/tests written during CP1.
_normalize_doi = normalize_doi


def _date_from_crossref(value: Any) -> str:
    """Return an ISO date, defaulting missing month/day to the first."""

    if not isinstance(value, dict):
        return ""
    date_parts = value.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts or not isinstance(date_parts[0], list):
        return ""
    parts = date_parts[0]
    if not parts:
        return ""
    try:
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else 1
        return datetime(year, month, day).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def _authors(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    seen: set[str] = set()
    for author in value:
        if not isinstance(author, dict):
            continue
        name = normalize_whitespace(
            " ".join(
                part
                for part in (_plain_text(author.get("given")), _plain_text(author.get("family")))
                if part
            )
        )
        if not name:
            name = _plain_text(author.get("name"))
        key = name.casefold()
        if name and key not in seen:
            names.append(name)
            seen.add(key)
    return names


def _categories(item: dict[str, Any]) -> list[str]:
    # Crossref subjects are ideal, but are often absent. Journal/proceedings
    # titles retain more retrieval value than the broad Crossref work type.
    return (
        _unique_texts(item.get("subject"))
        or _unique_texts(item.get("container-title"))
        or _unique_texts(item.get("type"))
    )


def _pdf_url(value: Any) -> str:
    if not isinstance(value, list):
        return ""
    fallback = ""
    for link in value:
        if not isinstance(link, dict):
            continue
        url = _plain_text(link.get("URL"))
        content_type = _plain_text(link.get("content-type")).lower()
        if not url:
            continue
        if content_type == "application/pdf":
            return url
        if not fallback and re.search(r"(?:\.pdf(?:$|[?#])|/pdf(?:$|[?#]))", url, re.IGNORECASE):
            fallback = url
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse a Crossref works response into the project's raw record contract.

    A record is valid only when it has a stable DOI, title, abstract and
    publication date. Optional scalar fields use an empty string, never None.
    """

    if not isinstance(payload, dict):
        raise TypeError("Crossref payload must be a dictionary.")
    message = payload.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("items"), list):
        raise ValueError("Crossref payload is missing message.items.")

    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in message["items"]:
        if not isinstance(item, dict):
            continue
        paper_id = normalize_doi(item.get("DOI"))
        title = _first_text(item.get("title"))
        summary = _plain_text(item.get("abstract"))
        published = (
            _date_from_crossref(item.get("published"))
            or _date_from_crossref(item.get("issued"))
            or _date_from_crossref(item.get("created"))
        )
        if not paper_id or not title or not summary or not published or paper_id in seen_ids:
            continue

        categories = _categories(item)
        publisher = _plain_text(item.get("publisher"))
        work_type = _plain_text(item.get("type"))
        comment = "; ".join(part for part in (work_type, publisher) if part)
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=_authors(item.get("author")),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=_date_from_crossref(item.get("deposited")) or published,
                abs_url=_plain_text(item.get("URL")) or f"https://doi.org/{paper_id}",
                pdf_url=_pdf_url(item.get("link")),
                comment=comment,
            )
        )
        seen_ids.add(paper_id)
    return records


def audit_crossref_payload(
    payload: dict,
    records: list[PaperRecord] | None = None,
) -> dict[str, Any]:
    """Trace each source item to a parsed ID and report every rejection reason.

    The audit intentionally mirrors :func:`parse_crossref_payload` validation.
    It does not mutate or replace the raw response; its purpose is to make
    silent filter/deduplication decisions inspectable during recovery.
    """

    if not isinstance(payload, dict):
        raise TypeError("Crossref payload must be a dictionary.")
    message = payload.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("items"), list):
        raise ValueError("Crossref payload is missing message.items.")

    parsed_records = records if records is not None else parse_crossref_payload(payload)
    traces: list[dict[str, Any]] = []
    accepted_ids: set[str] = set()
    reason_counts: Counter[str] = Counter()

    for source_index, item in enumerate(message["items"]):
        if not isinstance(item, dict):
            reasons = ["invalid_item_type"]
            raw_doi = ""
            paper_id = ""
        else:
            raw_doi = item.get("DOI") if isinstance(item.get("DOI"), str) else ""
            paper_id = normalize_doi(item.get("DOI"))
            title = _first_text(item.get("title"))
            summary = _plain_text(item.get("abstract"))
            published = (
                _date_from_crossref(item.get("published"))
                or _date_from_crossref(item.get("issued"))
                or _date_from_crossref(item.get("created"))
            )
            reasons = []
            if not paper_id:
                reasons.append("missing_doi")
            if not title:
                reasons.append("missing_title")
            if not summary:
                reasons.append("missing_abstract")
            if not published:
                reasons.append("invalid_published_date")
            if not reasons and paper_id in accepted_ids:
                reasons.append("duplicate_doi")

        accepted = not reasons
        if accepted:
            accepted_ids.add(paper_id)
        else:
            reason_counts.update(reasons)
        traces.append(
            {
                "source_index": source_index,
                "raw_doi": raw_doi,
                "normalized_paper_id": paper_id,
                "status": "parsed" if accepted else "rejected",
                "reasons": reasons,
            }
        )

    coverage: dict[str, dict[str, int]] = {}
    for field_name in PaperRecord.__dataclass_fields__:
        missing = sum(
            1
            for record in parsed_records
            if getattr(record, field_name) in (None, "", [])
        )
        coverage[field_name] = {
            "present": len(parsed_records) - missing,
            "missing": missing,
        }

    parsed_ids = [record.paper_id for record in parsed_records]
    expected_ids = [
        trace["normalized_paper_id"]
        for trace in traces
        if trace["status"] == "parsed"
    ]
    return {
        "source_items": len(message["items"]),
        "parsed_records": len(parsed_records),
        "rejected_items": sum(trace["status"] == "rejected" for trace in traces),
        "reason_counts": dict(sorted(reason_counts.items())),
        "stable_id": {
            "source_field": "DOI",
            "target_field": "paper_id",
            "normalization": "strip doi URL/prefix, trim, lowercase",
        },
        "id_trace": traces,
        "paper_record_field_coverage": coverage,
        "parser_trace_matches_records": expected_ids == parsed_ids,
    }


def audit_raw_snapshot(
    response_path: Path,
    records_path: Path,
    audit_path: Path | None = None,
    handoff_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconcile the API snapshot with stored PaperRecords and build handoff."""

    def portable_path(path: Path) -> str:
        parts = path.parts
        for index, part in enumerate(parts):
            if part.casefold() == "data":
                return Path(*parts[index:]).as_posix()
        return path.as_posix()

    payload = json.loads(response_path.read_text(encoding="utf-8"))
    reparsed_records = parse_crossref_payload(payload)
    stored_records = load_raw_records(records_path)
    audit = audit_crossref_payload(payload, reparsed_records)

    reparsed_by_id = {record.paper_id: asdict(record) for record in reparsed_records}
    stored_by_id = {record.paper_id: asdict(record) for record in stored_records}
    duplicate_stored_ids = sorted(
        paper_id
        for paper_id, count in Counter(record.paper_id for record in stored_records).items()
        if count > 1
    )
    audit["snapshot_reconciliation"] = {
        "response_path": portable_path(response_path),
        "records_path": portable_path(records_path),
        "stored_records": len(stored_records),
        "missing_from_stored_records": sorted(reparsed_by_id.keys() - stored_by_id.keys()),
        "unexpected_stored_record_ids": sorted(stored_by_id.keys() - reparsed_by_id.keys()),
        "content_mismatch_ids": sorted(
            paper_id
            for paper_id in reparsed_by_id.keys() & stored_by_id.keys()
            if reparsed_by_id[paper_id] != stored_by_id[paper_id]
        ),
        "duplicate_stored_ids": duplicate_stored_ids,
    }
    reconciliation = audit["snapshot_reconciliation"]
    audit["passed"] = bool(
        audit["parser_trace_matches_records"]
        and not reconciliation["missing_from_stored_records"]
        and not reconciliation["unexpected_stored_record_ids"]
        and not reconciliation["content_mismatch_ids"]
        and not reconciliation["duplicate_stored_ids"]
    )

    required_for_cleaning = ["paper_id", "title", "summary", "published"]
    missing_required = {
        field_name: audit["paper_record_field_coverage"][field_name]["missing"]
        for field_name in required_for_cleaning
    }

    handoff = {
        "raw_paths": {
            "api_response": portable_path(response_path),
            "parsed_records": portable_path(records_path),
        },
        "record_type": "ingestion.crossref.PaperRecord",
        "stable_id": audit["stable_id"],
        "required_for_cleaning": required_for_cleaning,
        "cleaning_readiness": {
            "ready": audit["passed"] and not any(missing_required.values()),
            "missing_required_counts": missing_required,
            "optional_missing_counts": {
                field_name: values["missing"]
                for field_name, values in audit["paper_record_field_coverage"].items()
                if field_name not in required_for_cleaning and values["missing"]
            },
            "rule": "Only paper_id/title/summary/published are required; optional fields use explicit fallbacks.",
        },
        "field_sources": {
            "paper_id": "DOI",
            "title": "title[0]",
            "summary": "abstract with JATS/HTML removed",
            "authors": "author[].given + author[].family",
            "categories": "subject; fallback container-title; fallback type",
            "primary_category": "categories[0]",
            "published": "published; fallback issued; fallback created",
            "updated": "deposited; fallback published",
            "abs_url": "URL; fallback https://doi.org/{paper_id}",
            "pdf_url": "PDF link when available; otherwise empty string",
            "comment": "type + publisher",
        },
        "field_coverage": audit["paper_record_field_coverage"],
        "sample_record": asdict(stored_records[0]) if stored_records else None,
        "snapshot_audit_passed": audit["passed"],
    }
    if audit_path is not None:
        write_json(audit_path, audit)
    if handoff_path is not None:
        write_json(handoff_path, handoff)
    return audit, handoff


def _retry_delay(response: requests.Response, backoff: float) -> float:
    retry_after = response.headers.get("Retry-After", "").strip()
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            try:
                target = parsedate_to_datetime(retry_after)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=UTC)
                return max(0.0, (target - datetime.now(UTC)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return backoff


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Fetch Crossref, persist the unmodified response, then parse and save it."""

    mailto = os.getenv("CROSSREF_MAILTO", "student@vinuni.edu.vn").strip()
    params: dict[str, Any] = {
        "query.bibliographic": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": ",".join(
            (
                "DOI",
                "title",
                "abstract",
                "author",
                "subject",
                "published",
                "issued",
                "created",
                "deposited",
                "URL",
                "link",
                "type",
                "container-title",
                "publisher",
            )
        ),
    }
    if mailto:
        params["mailto"] = mailto
    contact = f" (mailto:{mailto})" if mailto else ""
    headers = {"User-Agent": f"Day10DataObservabilityLab/0.1{contact}"}

    response: requests.Response | None = None
    backoff = INITIAL_BACKOFF_SECONDS
    last_error: Exception | None = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL,
                params=params,
                headers=headers,
                timeout=60,
            )
            if response.status_code == requests.codes.ok:
                break
            if response.status_code not in RETRYABLE_STATUS_CODES:
                response.raise_for_status()
            last_error = requests.HTTPError(
                f"Crossref returned HTTP {response.status_code} on attempt {attempt}."
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc

        if attempt == MAX_FETCH_ATTEMPTS:
            break
        delay = _retry_delay(response, backoff) if response is not None else backoff
        time.sleep(delay)
        backoff *= 2

    if response is None or response.status_code != requests.codes.ok:
        raise RuntimeError(
            f"Crossref request failed after {MAX_FETCH_ATTEMPTS} attempts."
        ) from last_error

    try:
        payload = response.json()
    except (requests.JSONDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError("Crossref returned a non-JSON response.") from exc

    # This is deliberately before parsing: even a schema/parser failure leaves
    # the source evidence available for diagnosis and recovery.
    write_json(settings.paths.raw_api_response, payload)
    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Load the parsed raw-record snapshot and enforce PaperRecord's contract."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a JSON list of raw records in {path}.")

    records: list[PaperRecord] = []
    field_names = set(PaperRecord.__dataclass_fields__)
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Raw record {index} in {path} is not an object.")
        missing = field_names - item.keys()
        if missing:
            raise ValueError(f"Raw record {index} is missing fields: {sorted(missing)}")
        if not isinstance(item["authors"], list) or not isinstance(item["categories"], list):
            raise ValueError(f"Raw record {index} authors/categories must be lists.")
        values = {name: item[name] for name in field_names}
        try:
            records.append(PaperRecord(**values))
        except TypeError as exc:
            raise ValueError(f"Raw record {index} does not match PaperRecord.") from exc
    return records
