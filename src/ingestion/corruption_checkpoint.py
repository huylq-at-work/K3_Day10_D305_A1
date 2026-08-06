"""Create and validate Role 2 corrupted clean artifacts without external fetch."""

from __future__ import annotations

import json

import pandas as pd

from core.config import Settings, load_settings
from core.utils import read_json, write_csv, write_json
from ingestion.corruption import (
    corrupt_clean_dataframe,
    validate_corruption_against_log,
    validate_repair_against_baseline,
)
from ingestion.lineage import verify_or_create_source_lock


def build_corruption_checkpoint(settings: Settings) -> dict:
    paths = settings.paths
    lock_path = paths.raw_records_json.parent / "baseline_source_lock.json"
    source_before = verify_or_create_source_lock(settings, lock_path)
    baseline = pd.DataFrame(read_json(paths.clean_json))

    corrupted = corrupt_clean_dataframe(baseline, paths.corruption_log)
    write_csv(corrupted, paths.corrupted_clean_csv)
    write_json(paths.corrupted_clean_json, corrupted.to_dict(orient="records"))

    log = read_json(paths.corruption_log)
    validation = validate_corruption_against_log(baseline, corrupted, log)
    source_after = verify_or_create_source_lock(settings, lock_path)
    validation["raw_source_unchanged"] = (
        source_before["sha256"] == source_after["sha256"]
    )
    validation["source_mode"] = "raw snapshot; no Crossref request"
    validation["passed"] = validation["passed"] and validation["raw_source_unchanged"]
    if paths.repaired_clean_json.exists():
        repaired = pd.DataFrame(read_json(paths.repaired_clean_json))
        lineage_id = log["lineage_repair_candidate"]["paper_id"]
        repair_validation = validate_repair_against_baseline(
            baseline, repaired, lineage_id
        )
        validation["repair_validation"] = repair_validation
        validation["passed"] = validation["passed"] and repair_validation["passed"]
    else:
        validation["repair_validation"] = {
            "available": False,
            "reason": "papers_clean_repaired.json has not been generated yet",
        }
    validation_path = paths.clean_json.parent / "corruption_validation.json"
    write_json(validation_path, validation)
    return validation


def main() -> None:
    validation = build_corruption_checkpoint(load_settings())
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    if not validation["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
