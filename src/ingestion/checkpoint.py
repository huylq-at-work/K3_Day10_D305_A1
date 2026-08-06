"""Generate Role 2 raw-audit, handoff, and clean artifacts for a checkpoint."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json

from core.config import Settings, load_settings
from core.contract import validate_clean_dataframe
from ingestion.cleaning import build_clean_dataframe_with_report, write_clean_artifacts
from ingestion.crossref import audit_raw_snapshot, load_raw_records


def build_checkpoint_artifacts(
    settings: Settings,
    run_date: datetime,
) -> dict:
    """Audit raw snapshots, hand them off, then generate clean outputs and log."""

    raw_dir = settings.paths.raw_records_json.parent
    clean_dir = settings.paths.clean_json.parent
    audit_path = raw_dir / "raw_snapshot_audit.json"
    handoff_path = raw_dir / "cleaning_handoff.json"
    cleaning_report_path = clean_dir / "cleaning_report.json"

    audit, handoff = audit_raw_snapshot(
        response_path=settings.paths.raw_api_response,
        records_path=settings.paths.raw_records_json,
        audit_path=audit_path,
        handoff_path=handoff_path,
    )
    if not audit["passed"]:
        raise RuntimeError(f"Raw snapshot reconciliation failed; inspect {audit_path}.")

    records = load_raw_records(settings.paths.raw_records_json)
    dataframe, cleaning_report = build_clean_dataframe_with_report(records, run_date)
    contract = validate_clean_dataframe(
        dataframe,
        raw_record_count=len(records),
        run_date=run_date,
    )
    cleaning_report["clean_contract"] = {
        "passed": contract.passed,
        "stats": contract.stats,
        "blockers": contract.blockers,
        "warnings": contract.warnings,
    }
    write_clean_artifacts(
        dataframe=dataframe,
        csv_path=settings.paths.clean_csv,
        json_path=settings.paths.clean_json,
        report_path=cleaning_report_path,
        report=cleaning_report,
    )
    if not contract.passed:
        raise RuntimeError(f"Clean contract failed; inspect {cleaning_report_path}.")

    return {
        "status": "passed",
        "run_date": run_date.isoformat(),
        "raw_audit": {
            "path": str(audit_path),
            "source_items": audit["source_items"],
            "parsed_records": audit["parsed_records"],
            "rejected_items": audit["rejected_items"],
        },
        "handoff": {
            "path": str(handoff_path),
            "sample_paper_id": (
                handoff["sample_record"]["paper_id"] if handoff["sample_record"] else None
            ),
        },
        "clean": {
            "csv_path": str(settings.paths.clean_csv),
            "json_path": str(settings.paths.clean_json),
            "report_path": str(cleaning_report_path),
            "input_records": cleaning_report["input_records"],
            "clean_records": cleaning_report["clean_records"],
            "filtered_records": cleaning_report["filtered_records"],
            "deduplicated_records": cleaning_report["deduplicated_records"],
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-date",
        help="UTC date used for age_days (YYYY-MM-DD); default: today.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    run_date = (
        datetime.fromisoformat(args.run_date).replace(tzinfo=UTC)
        if args.run_date
        else datetime.now(UTC)
    )
    summary = build_checkpoint_artifacts(load_settings(), run_date)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
