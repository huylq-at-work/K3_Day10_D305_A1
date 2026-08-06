from __future__ import annotations

from dataclasses import asdict, dataclass
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


def _plain_text(value: Any) -> str:
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


def _normalize_doi(value: Any) -> str:
    doi = _plain_text(value).lower()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi.strip()


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
        paper_id = _normalize_doi(item.get("DOI"))
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
