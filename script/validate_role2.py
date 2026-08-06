"""Build and validate Role 2 raw -> clean artifacts for checkpoint CP1."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json

from core.config import load_settings
from core.utils import write_csv, write_json
from ingestion.cleaning import CLEAN_COLUMNS, build_clean_dataframe
from ingestion.crossref import parse_crossref_payload


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-date",
        help="UTC date used for age_days (YYYY-MM-DD); default: today.",
    )
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    settings = load_settings()
    run_date = (
        datetime.fromisoformat(args.run_date).replace(tzinfo=UTC)
        if args.run_date
        else datetime.now(UTC)
    )

    payload = json.loads(settings.paths.raw_api_response.read_text(encoding="utf-8"))
    source_items = payload.get("message", {}).get("items", [])
    records = parse_crossref_payload(payload)
    dataframe = build_clean_dataframe(records, run_date)

    checks = {
        "clean_schema_exact": dataframe.columns.tolist() == CLEAN_COLUMNS,
        "has_clean_rows": len(dataframe) > 0,
        "paper_id_complete": bool(dataframe["paper_id"].ne("").all()),
        "paper_id_unique": bool(dataframe["paper_id"].is_unique),
        "title_complete": bool(dataframe["title"].ne("").all()),
        "summary_complete": bool(dataframe["summary"].ne("").all()),
        "published_iso_date": bool(
            dataframe["published"].str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
        ),
        "authors_complete": bool(dataframe["authors_joined"].ne("").all()),
        "categories_complete": bool(dataframe["categories_joined"].ne("").all()),
        "embedding_text_complete": bool(dataframe["text_for_embedding"].ne("").all()),
        "jats_removed": not bool(
            dataframe["summary"].str.contains("<jats:", case=False, regex=False).any()
        ),
        "age_days_consistent": bool(
            dataframe.apply(
                lambda row: row["age_days"]
                == (run_date.date() - datetime.fromisoformat(row["published"]).date()).days,
                axis=1,
            ).all()
        ),
    }
    report = {
        "status": "passed" if all(checks.values()) else "failed",
        "run_date": run_date.date().isoformat(),
        "source_items": len(source_items),
        "parsed_records": len(records),
        "clean_records": len(dataframe),
        "dropped_during_parse": len(source_items) - len(records),
        "dropped_during_cleaning": len(records) - len(dataframe),
        "checks": checks,
    }

    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    write_csv(dataframe, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, dataframe.to_dict(orient="records"))
    validation_path = settings.paths.clean_json.parent / "cp1_validation.json"
    write_json(validation_path, report)

    print(json.dumps(report, indent=2))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
