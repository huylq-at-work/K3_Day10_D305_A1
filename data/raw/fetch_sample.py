"""Lay raw Crossref response bang dung tham so trong Settings cua lab.

Chi fetch va luu raw. Khong parse, khong clean - do la phan cua Role 2.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

from core.config import load_settings

OUT_DIR = Path(sys.argv[1])
ENDPOINT = "https://api.crossref.org/works"
MAX_ATTEMPTS = 5
MAILTO = "student@vinuni.edu.vn"  # polite pool cua Crossref, giam rate limit


def fetch(settings) -> dict:
    params = {
        "query.bibliographic": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "select": ",".join(
            [
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
                "score",
            ]
        ),
        "mailto": MAILTO,
    }
    headers = {"User-Agent": f"Day10DataLab/0.1 (mailto:{MAILTO})"}

    delay = 2.0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        response = requests.get(ENDPOINT, params=params, headers=headers, timeout=60)
        print(f"  attempt {attempt}: HTTP {response.status_code}")
        if response.status_code == 200:
            return response.json()
        if response.status_code in {429, 500, 502, 503, 504}:
            retry_after = response.headers.get("Retry-After")
            wait = float(retry_after) if retry_after and retry_after.isdigit() else delay
            print(f"  retry sau {wait}s")
            time.sleep(wait)
            delay *= 2
            continue
        response.raise_for_status()
    raise RuntimeError(f"Crossref khong tra 200 sau {MAX_ATTEMPTS} lan thu.")


def main() -> None:
    settings = load_settings()
    print(f"query : {settings.source_query}")
    print(f"filter: {settings.source_filter}")
    print(f"rows  : {settings.max_results}")

    payload = fetch(settings)
    items = payload.get("message", {}).get("items", [])
    print(f"nhan duoc {len(items)} items (total-results={payload.get('message', {}).get('total-results')})")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUT_DIR / "crossref_response.json"
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"da luu {target} ({target.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
