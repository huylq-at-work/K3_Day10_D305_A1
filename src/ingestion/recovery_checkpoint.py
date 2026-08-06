"""Role 2 recovery proof: rebuild clean data from the locked raw snapshot."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.contract import CLEAN_COLUMNS, validate_clean_dataframe
from core.utils import read_json, write_csv, write_json, write_text
from ingestion.cleaning import build_clean_dataframe, build_clean_dataframe_with_report
from ingestion.corruption import (
    validate_corruption_against_log,
    validate_repair_against_baseline,
)
from ingestion.crossref import (
    PaperRecord,
    load_raw_records,
    normalize_doi,
    parse_crossref_payload,
)
from ingestion.lineage import verify_or_create_source_lock


SENSITIVE_NAMES = (
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "CUSTOM_LLM_API_KEY",
)
SECRET_PREFIX_PATTERN = re.compile(
    r"(?:AIza[0-9A-Za-z_-]{35}|sk-(?:proj-)?[0-9A-Za-z_-]{20,}"
    r"|sk-ant-[0-9A-Za-z_-]{20,}|gh[pousr]_[0-9A-Za-z]{20,})"
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD))"
    r"\s*=\s*['\"]?([^'\"\s#]+)",
    re.MULTILINE,
)
SAFE_EXAMPLE_VALUES = {
    "",
    "none",
    "null",
    "changeme",
    "replace_me",
    "your_key_here",
}


def _sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git(project_dir: Path, *args: str, allow_no_match: bool = False) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=project_dir,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode and not (allow_no_match and result.returncode == 1):
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def audit_git_secrets(project_dir: Path) -> dict[str, Any]:
    """Check tracked files/config for likely credentials without logging values."""

    tracked = [
        item
        for item in _git(project_dir, "ls-files", "-z").split("\0")
        if item
    ]
    findings: list[dict[str, Any]] = []
    for relative in tracked:
        path = project_dir / relative
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if SECRET_PREFIX_PATTERN.search(line):
                findings.append(
                    {"file": relative, "line": line_number, "kind": "secret_prefix"}
                )
            match = SECRET_ASSIGNMENT_PATTERN.match(line)
            if match:
                variable, value = match.groups()
                normalized = value.strip().strip("'\"").lower()
                if (
                    normalized not in SAFE_EXAMPLE_VALUES
                    and not normalized.startswith("${")
                    and not normalized.startswith("%")
                ):
                    findings.append(
                        {
                            "file": relative,
                            "line": line_number,
                            "kind": "literal_assignment",
                            "variable": variable,
                        }
                    )

    tracked_env = ".env" in tracked
    env_ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".env"], cwd=project_dir, check=False
    ).returncode == 0
    env_history = [
        commit
        for commit in _git(
            project_dir, "log", "--all", "--format=%H", "--", ".env"
        ).splitlines()
        if commit
    ]
    config_text = (project_dir / "src" / "core" / "config.py").read_text(
        encoding="utf-8"
    )
    config_from_environment = {
        name: f'os.getenv("{name}")' in config_text for name in SENSITIVE_NAMES
    }
    checks = {
        "env_is_ignored": env_ignored,
        "env_is_not_tracked": not tracked_env,
        "env_never_committed": not env_history,
        "no_hardcoded_secret_findings": not findings,
        "config_reads_sensitive_values_from_environment": all(
            config_from_environment.values()
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "checked_tracked_files": len(tracked),
        "checked_variables": config_from_environment,
        "findings": findings,
        "historical_env_commit_count": len(env_history),
        "note": "Findings contain locations only; credential values are never logged.",
    }


def build_quality_signal(
    dataframe: pd.DataFrame,
    settings: Settings,
    raw_record_count: int,
    run_date: datetime,
) -> dict[str, Any]:
    """Compute transparent quality signals from dataframe values, not pass flags."""

    def missing(column: str) -> int:
        if column not in dataframe:
            return len(dataframe)
        series = dataframe[column]
        return int((series.isna() | series.fillna("").astype(str).str.strip().eq("")).sum())

    contract = validate_clean_dataframe(
        dataframe, raw_record_count=raw_record_count, run_date=run_date
    )
    return {
        "row_count": len(dataframe),
        "unique_paper_ids": int(dataframe["paper_id"].nunique())
        if "paper_id" in dataframe
        else 0,
        "paper_id_duplicates": int(dataframe["paper_id"].duplicated().sum())
        if "paper_id" in dataframe
        else 0,
        "missing_title": missing("title"),
        "missing_summary": missing("summary"),
        "empty_text_for_embedding": missing("text_for_embedding"),
        "stale_rows": int(
            dataframe.get("age_days", pd.Series(dtype=int))
            .gt(settings.freshness_threshold_days)
            .sum()
        ),
        "schema_exact": list(dataframe.columns) == list(CLEAN_COLUMNS),
        "contract_passed": contract.passed,
        "contract_blockers": contract.blockers,
        "contract_warnings": contract.warnings,
    }


def build_repair_lineage_evidence(
    raw_records: list[PaperRecord],
    raw_api_response: dict[str, Any],
    baseline: pd.DataFrame,
    corrupted: pd.DataFrame,
    repaired: pd.DataFrame,
    corruption_log: dict[str, Any],
    run_date: datetime,
) -> dict[str, Any]:
    """Trace every deliberately damaged ID back to raw and into repaired clean."""

    raw_by_id = {
        normalize_doi(record.paper_id): (source_index, record)
        for source_index, record in enumerate(raw_records)
    }
    response_items = raw_api_response.get("message", {}).get("items", [])
    response_by_id = {
        normalize_doi(item.get("DOI")): (source_index, item)
        for source_index, item in enumerate(response_items)
        if isinstance(item, dict) and normalize_doi(item.get("DOI"))
    }
    evidence: list[dict[str, Any]] = []
    for event in corruption_log["events"]:
        event_type = event["type"]
        for paper_id in event["paper_ids"]:
            raw_item = raw_by_id.get(paper_id)
            response_item = response_by_id.get(paper_id)
            baseline_rows = baseline.loc[baseline["paper_id"] == paper_id]
            corrupted_rows = corrupted.loc[corrupted["paper_id"] == paper_id]
            repaired_rows = repaired.loc[repaired["paper_id"] == paper_id]
            source_match = False
            raw_matches_response = False
            source: dict[str, Any] = {"present": raw_item is not None}
            if raw_item is not None:
                source_index, record = raw_item
                raw_payload = asdict(record)
                rebuilt = build_clean_dataframe([record], run_date)
                source_match = (
                    len(rebuilt) == 1
                    and len(repaired_rows) == 1
                    and _sha256(rebuilt.iloc[0].to_dict())
                    == _sha256(repaired_rows.iloc[0].to_dict())
                )
                source = {
                    "present": True,
                    "raw_source_index": source_index,
                    "raw_record_sha256": _sha256(raw_payload),
                    "raw_paper_id": record.paper_id,
                    "title": record.title,
                    "published": record.published,
                    "summary_chars": len(record.summary),
                    "summary_sha256": hashlib.sha256(
                        record.summary.encode("utf-8")
                    ).hexdigest(),
                }
                if response_item is not None:
                    response_index, api_item = response_item
                    parsed = parse_crossref_payload(
                        {"message": {"items": [api_item]}}
                    )
                    raw_matches_response = (
                        len(parsed) == 1 and asdict(parsed[0]) == raw_payload
                    )
                    source.update(
                        {
                            "raw_api_response_item_index": response_index,
                            "raw_api_response_item_sha256": _sha256(api_item),
                            "raw_record_matches_api_response_item": raw_matches_response,
                        }
                    )

            restored_to_baseline = (
                len(baseline_rows) == 1
                and len(repaired_rows) == 1
                and _sha256(baseline_rows.iloc[0].to_dict())
                == _sha256(repaired_rows.iloc[0].to_dict())
            )
            if event_type == "drop_latest":
                corruption_observed = len(corrupted_rows) == 0
            elif event_type == "missing_summary":
                corruption_observed = len(corrupted_rows) == 1 and not str(
                    corrupted_rows.iloc[0]["summary"]
                ).strip()
            elif event_type == "noise_injection":
                token = event["parameters"]["token"]
                repetitions = int(event["parameters"]["repetitions"])
                corruption_observed = len(corrupted_rows) == 1 and str(
                    corrupted_rows.iloc[0]["summary"]
                ).count(token) == repetitions
            elif event_type == "old_published_date":
                corruption_observed = (
                    len(corrupted_rows) == 1
                    and len(baseline_rows) == 1
                    and corrupted_rows.iloc[0]["published"]
                    != baseline_rows.iloc[0]["published"]
                    and int(corrupted_rows.iloc[0]["age_days"])
                    != int(baseline_rows.iloc[0]["age_days"])
                )
            elif event_type == "duplicate_rows":
                corruption_observed = len(corrupted_rows) == 2
            else:
                corruption_observed = False

            checks = {
                "raw_record_present": raw_item is not None,
                "raw_api_response_item_present": response_item is not None,
                "raw_record_matches_api_response_item": raw_matches_response,
                "baseline_record_present_once": len(baseline_rows) == 1,
                "corruption_observed": corruption_observed,
                "repaired_record_present_once": len(repaired_rows) == 1,
                "repaired_matches_single_record_raw_rebuild": source_match,
                "repaired_matches_baseline": restored_to_baseline,
            }
            evidence.append(
                {
                    "paper_id": paper_id,
                    "corruption_type": event_type,
                    "source": source,
                    "corrupted_occurrences": len(corrupted_rows),
                    "repaired_row_sha256": _sha256(repaired_rows.iloc[0].to_dict())
                    if len(repaired_rows) == 1
                    else None,
                    "checks": checks,
                    "passed": all(checks.values()),
                }
            )
    return {
        "passed": bool(evidence) and all(item["passed"] for item in evidence),
        "record_count": len(evidence),
        "records": evidence,
    }


def _handoff_markdown(evidence: dict[str, Any]) -> str:
    quality = evidence["comparison"]
    lines = [
        "# Role 2 recovery handoff",
        "",
        "Repair was rebuilt with `load_raw_records -> build_clean_dataframe`; baseline and "
        "corrupted artifacts were read only for comparison.",
        "",
        "## Source and security gates",
        "",
        f"- Overall checkpoint: **{'PASS' if evidence['passed'] else 'FAIL'}**",
        f"- Raw snapshot unchanged: `{evidence['raw_snapshot']['unchanged']}`",
        f"- External fetch used: `{evidence['repair']['external_fetch_used']}`",
        f"- Tracked-secret audit: **{'PASS' if evidence['secret_audit']['passed'] else 'FAIL'}**",
        f"- Repaired clean contract: **{'PASS' if quality['repaired']['contract_passed'] else 'FAIL'}**",
        f"- Repaired non-blocking contract warnings: `{len(quality['repaired']['contract_warnings'])}`",
        "",
        "## Clean / corrupted / repaired",
        "",
        "| Signal | Clean | Corrupted | Repaired |",
        "| :-- | --: | --: | --: |",
    ]
    for label, key in (
        ("Rows", "row_count"),
        ("Unique paper IDs", "unique_paper_ids"),
        ("Duplicate IDs", "paper_id_duplicates"),
        ("Missing summaries", "missing_summary"),
        ("Empty embedding text", "empty_text_for_embedding"),
        ("Stale rows", "stale_rows"),
    ):
        lines.append(
            f"| {label} | {quality['clean'][key]} | {quality['corrupted'][key]} "
            f"| {quality['repaired'][key]} |"
        )
    lines.extend(
        [
            "",
            "## Lineage proof",
            "",
            f"All `{evidence['lineage']['record_count']}` deliberately damaged record "
            f"occurrences were found in raw and restored: `{evidence['lineage']['passed']}`.",
            "",
            "| Corruption | Paper IDs |",
            "| :-- | :-- |",
        ]
    )
    by_type: dict[str, list[str]] = {}
    for record in evidence["lineage"]["records"]:
        by_type.setdefault(record["corruption_type"], []).append(record["paper_id"])
    for corruption_type, paper_ids in by_type.items():
        lines.append(f"| `{corruption_type}` | {', '.join(f'`{item}`' for item in paper_ids)} |")
    lines.extend(
        [
            "",
            "Machine-readable evidence: `data/clean/recovery_evidence.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def run_recovery_checkpoint(settings: Settings) -> dict[str, Any]:
    paths = settings.paths
    lock_path = paths.raw_records_json.parent / "baseline_source_lock.json"
    lock_before = verify_or_create_source_lock(settings, lock_path)
    cleaning_report_path = paths.clean_json.parent / "cleaning_report.json"
    run_date = datetime.fromisoformat(read_json(cleaning_report_path)["run_date"])

    raw_records = load_raw_records(paths.raw_records_json)
    raw_api_response = read_json(paths.raw_api_response)
    repaired, repaired_cleaning_report = build_clean_dataframe_with_report(
        raw_records, run_date
    )
    write_csv(repaired, paths.repaired_clean_csv)
    write_json(paths.repaired_clean_json, repaired.to_dict(orient="records"))
    lock_after = verify_or_create_source_lock(settings, lock_path)

    baseline = pd.DataFrame(read_json(paths.clean_json))
    corrupted = pd.DataFrame(read_json(paths.corrupted_clean_json))
    corruption_log = read_json(paths.corruption_log)
    corruption_validation = validate_corruption_against_log(
        baseline, corrupted, corruption_log
    )
    lineage = build_repair_lineage_evidence(
        raw_records,
        raw_api_response,
        baseline,
        corrupted,
        repaired,
        corruption_log,
        run_date,
    )
    repair_validation = validate_repair_against_baseline(
        baseline,
        repaired,
        corruption_log["lineage_repair_candidate"]["paper_id"],
    )
    comparison = {
        "clean": build_quality_signal(
            baseline, settings, len(raw_records), run_date
        ),
        "corrupted": build_quality_signal(
            corrupted, settings, len(raw_records), run_date
        ),
        "repaired": build_quality_signal(
            repaired, settings, len(raw_records), run_date
        ),
    }
    secret_audit = audit_git_secrets(paths.project_dir)
    raw_unchanged = lock_before["sha256"] == lock_after["sha256"]
    checks = {
        "raw_snapshot_unchanged": raw_unchanged,
        "corruption_artifact_matches_log": corruption_validation["passed"],
        "all_corrupted_records_restored_from_raw": lineage["passed"],
        "repaired_matches_baseline": repair_validation["passed"],
        "repaired_contract_passed": comparison["repaired"]["contract_passed"],
        "repaired_quality_clean": all(
            comparison["repaired"][key] == 0
            for key in (
                "paper_id_duplicates",
                "missing_title",
                "missing_summary",
                "empty_text_for_embedding",
                "stale_rows",
            )
        ),
        "tracked_secret_audit_passed": secret_audit["passed"],
    }
    evidence = {
        "version": 1,
        "passed": all(checks.values()),
        "checks": checks,
        "raw_snapshot": {
            "mode": "locked raw snapshot",
            "path": "data/raw/crossref_records.json",
            "record_count": len(raw_records),
            "sha256": lock_after["sha256"],
            "unchanged": raw_unchanged,
        },
        "repair": {
            "producer": "load_raw_records -> build_clean_dataframe_with_report",
            "run_date": run_date.isoformat(),
            "run_date_source": "data/clean/cleaning_report.json",
            "external_fetch_used": False,
            "baseline_used_only_for_validation": True,
            "corrupted_used_only_for_validation": True,
            "cleaning_report": repaired_cleaning_report,
            "validation": repair_validation,
        },
        "corruption_validation": corruption_validation,
        "lineage": lineage,
        "comparison": comparison,
        "secret_audit": secret_audit,
    }
    evidence_path = paths.clean_json.parent / "recovery_evidence.json"
    handoff_path = paths.clean_json.parent / "RECOVERY_HANDOFF.md"
    write_json(evidence_path, evidence)
    write_text(handoff_path, _handoff_markdown(evidence))
    return evidence


def main() -> None:
    evidence = run_recovery_checkpoint(load_settings())
    summary = {
        "passed": evidence["passed"],
        "checks": evidence["checks"],
        "comparison": evidence["comparison"],
        "secret_audit": evidence["secret_audit"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if not evidence["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
