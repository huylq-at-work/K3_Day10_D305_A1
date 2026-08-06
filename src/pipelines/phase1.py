from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import load_settings
from core.contract import validate_clean_dataframe
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import PaperRecord, fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

DEMO_QUESTIONS = [
    "Which indexed paper is most relevant to agentic retrieval augmented generation?",
    "Summarize what the corpus says about evaluating large language model retrieval.",
]


class ContractViolation(RuntimeError):
    """Clean data khong dat contract - dung pipeline truoc khi index."""


def resolve_records(settings) -> tuple[list[PaperRecord], str]:
    """Dung raw snapshot neu co; chi goi API khi thieu hoac REFRESH_SOURCE=1.

    `data/raw/` la nguon duy nhat de repair o phase 2 nen mac dinh khong ghi de.
    """
    raw_path = settings.paths.raw_records_json
    if raw_path.exists() and not settings.refresh_source:
        return load_raw_records(raw_path), "raw snapshot"
    return fetch_source_records(settings), "Crossref API"


def save_clean_dataset(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def enforce_clean_contract(df: pd.DataFrame, raw_count: int, run_date, settings) -> dict[str, Any]:
    """Gate giua cleaning va index/test set.

    Index dung tren clean data hong thi baseline metrics khong lam moc so sanh
    duoc, va ca phase 2 mat y nghia. Nen o day dung han thay vi chay tiep.
    """
    result = validate_clean_dataframe(df, raw_record_count=raw_count, run_date=run_date)
    print(result.render())
    write_json(
        settings.paths.quality_dir / "clean_contract.json",
        {
            "passed": result.passed,
            "stats": result.stats,
            "blockers": result.blockers,
            "warnings": result.warnings,
            "run_date": run_date.isoformat(),
        },
    )
    if not result.passed:
        raise ContractViolation(
            f"Clean data vi pham contract ({len(result.blockers)} blocker). "
            "Khong index va khong sinh test set. Xem data/quality/clean_contract.json."
        )
    return result.stats


def resolve_test_set(df: pd.DataFrame, settings) -> list[dict[str, Any]]:
    """Giu nguyen test set giua cac lan chay de metric con so sanh duoc."""
    path = settings.paths.eval_testset
    if path.exists() and not settings.refresh_test_set:
        return read_json(path)
    return build_test_set(df, path)


def run_agent_demo(settings, index) -> None:
    """Demo agent tren vai cau hoi. Loi provider khong duoc lam hong baseline."""
    try:
        from retrieval.agent import build_agent, run_agent_question

        agent = build_agent(settings, index)
        answers = [
            {"question": question, "answer": run_agent_question(agent, question)}
            for question in DEMO_QUESTIONS
        ]
    except Exception as exc:
        answers = [{"error": f"Agent demo skipped: {exc}"}]
        print(f"[phase1] agent demo bo qua: {exc}")
    write_json(settings.paths.demo_answers, answers)


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()

    print("[phase1] 1/8 load source records")
    records, source_mode = resolve_records(settings)
    print(f"[phase1]     {len(records)} records tu {source_mode}")

    print("[phase1] 2/8 clean")
    clean_df = build_clean_dataframe(records, run_date)
    save_clean_dataset(clean_df, paths.clean_csv, paths.clean_json)
    print(f"[phase1]     {len(clean_df)} rows -> {paths.clean_csv.name}")

    print("[phase1] 3/8 kiem clean contract (gate truoc index)")
    contract_stats = enforce_clean_contract(clean_df, len(records), run_date, settings)

    print("[phase1] 4/8 build index")
    index = LocalEmbeddingIndex.build(clean_df, settings, embeddings_output_path=paths.embeddings_json)

    print("[phase1] 5/8 test set")
    test_set = resolve_test_set(clean_df, settings)
    print(f"[phase1]     {len(test_set)} cau hoi")

    print("[phase1] 6/8 evaluate")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=paths.eval_testset,
        metrics_output_path=paths.baseline_metrics,
        answers_output_path=paths.baseline_answers,
    )

    print("[phase1] 7/8 quality + freshness")
    quality = run_data_quality_checks(clean_df, settings, report_name="baseline")
    freshness = build_freshness_report(clean_df, settings, paths.freshness_report)

    print("[phase1] 8/8 report + demo")
    source_summary = {
        "source_api": settings.source_api,
        "source_mode": source_mode,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "max_results": settings.max_results,
        "raw_records": len(records),
        "clean_rows": int(len(clean_df)),
        "clean_contract": contract_stats,
        "embedding_model": settings.embedding_model,
        "collection_name": settings.baseline_collection_name,
        "top_k": settings.top_k,
        "run_date": run_date.isoformat(),
    }
    generate_phase1_report(
        report_path=paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    run_agent_demo(settings, index)

    print("[phase1] xong. Metrics:")
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        if key in bundle.summary:
            print(f"[phase1]     {key}: {bundle.summary[key]:.4f}")
    print(f"[phase1] report: {paths.baseline_report}")
