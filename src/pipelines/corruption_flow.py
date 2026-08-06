from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import load_settings
from core.contract import validate_clean_dataframe
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


class BaselineMissing(RuntimeError):
    """Chua co baseline day du - khong duoc chay corruption."""


class BaselineMutated(RuntimeError):
    """Corruption flow da cham vao artifact baseline."""


def freshness_path(settings, name: str) -> Path:
    """Freshness report rieng cho tung trang thai.

    `Paths` chi dinh nghia mot `freshness_report` cho baseline, nen corrupted va
    repaired duoc dat canh no trong cung `quality_dir` thay vi ghi de.
    """
    return settings.paths.quality_dir / f"freshness_{name}.json"


def require_baseline(settings) -> dict[str, Any]:
    """Chan corruption flow khi baseline chua day du.

    So sanh chi co nghia khi baseline la mot moc co that. Chay corruption trong
    khi baseline con thieu artifact thi bang so sanh cuoi cung khong chung minh
    duoc gi.
    """
    paths = settings.paths
    required = {
        "raw records": paths.raw_records_json,
        "clean json": paths.clean_json,
        "test set": paths.eval_testset,
        "baseline metrics": paths.baseline_metrics,
        "embedding manifest": paths.embeddings_json,
    }
    missing = [name for name, path in required.items() if not path.exists()]
    if missing:
        raise BaselineMissing(
            f"Thieu artifact baseline: {missing}. Chay `script/run_phase1.py` truoc."
        )
    return read_json(paths.baseline_metrics)


def snapshot_baseline(settings) -> dict[str, Any]:
    """Ghi lai dau van tay baseline de doi chieu sau khi flow chay xong."""
    paths = settings.paths
    return {
        "clean_bytes": paths.clean_json.stat().st_size,
        "metrics": read_json(paths.baseline_metrics),
        "manifest_collection": read_json(paths.embeddings_json)["collection_name"],
        "test_set_bytes": paths.eval_testset.stat().st_size,
    }


def assert_baseline_intact(settings, before: dict[str, Any]) -> None:
    """Baseline phai nguyen ven sau khi chay - neu khong, moc so sanh da mat."""
    after = snapshot_baseline(settings)
    for key in before:
        if before[key] != after[key]:
            raise BaselineMutated(
                f"Artifact baseline bi thay doi ({key}). Corruption flow phai ghi ra "
                "path va collection rieng, khong duoc dung lai cua baseline."
            )
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(settings.paths.chroma_dir))
        collection = client.get_collection(name=settings.baseline_collection_name)
        if collection.count() == 0:
            raise BaselineMutated("Collection papers-baseline rong sau khi chay corruption flow.")
    except BaselineMutated:
        raise
    except Exception as exc:
        print(f"[corruption] khong doc duoc collection baseline de kiem tra: {exc}")


def save_dataset(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def index_and_evaluate(
    settings,
    df: pd.DataFrame,
    embeddings_path: Path,
    metrics_path: Path,
    answers_path: Path,
    label: str,
) -> dict[str, Any]:
    """Rebuild index rieng cho mot trang thai roi cham bang test set CU.

    Test set, top_k va evaluator giu nguyen. Doi bat ky thu nao trong so do thi
    chenh lech metric khong con quy ve chat luong du lieu duoc nua.
    """
    print(f"[corruption] build index `{label}` ({len(df)} rows)")
    index = LocalEmbeddingIndex.build(df, settings, embeddings_output_path=embeddings_path)
    print(f"[corruption] evaluate `{label}` voi test set goc")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=metrics_path,
        answers_output_path=answers_path,
    )
    return bundle.summary


def observe(settings, df: pd.DataFrame, name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    quality = run_data_quality_checks(df, settings, report_name=name)
    freshness = build_freshness_report(df, settings, freshness_path(settings, name))
    return quality, freshness


def repair_from_raw(settings, run_date) -> pd.DataFrame:
    """Repair = clean lai tu `data/raw/`, khong va tren du lieu da hong.

    Khong fetch lai source: fetch moi se doi tap record va lam bang so sanh
    baseline/corrupted/repaired mat cong bang.
    """
    records = load_raw_records(settings.paths.raw_records_json)
    print(f"[corruption] repair tu raw snapshot: {len(records)} records")
    repaired = build_clean_dataframe(records, run_date)

    result = validate_clean_dataframe(repaired, raw_record_count=len(records), run_date=run_date)
    print(result.render())
    if not result.passed:
        # Dung han thay vi va JSON ket qua: du lieu repaired ma khong dat contract
        # thi cot "repaired" trong bang so sanh khong dang tin.
        raise RuntimeError(
            f"Du lieu repaired vi pham contract ({len(result.blockers)} blocker). "
            "Sua contract/cleaning roi chay lai, khong sua tay metrics."
        )
    return repaired


def main() -> None:
    settings = load_settings()
    paths = settings.paths
    run_date = now_utc()

    print("[corruption] 0/6 kiem baseline")
    baseline_metrics = require_baseline(settings)
    before = snapshot_baseline(settings)
    clean_df = pd.DataFrame(read_json(paths.clean_json))
    print(f"[corruption]     baseline {len(clean_df)} rows, moc so sanh da co")

    print("[corruption] 1/6 tao corrupted dataset")
    corrupted_df = corrupt_clean_dataframe(clean_df.copy(), paths.corruption_log)
    save_dataset(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    print(f"[corruption]     {len(clean_df)} -> {len(corrupted_df)} rows")

    print("[corruption] 2/6 index + evaluate corrupted")
    corrupted_metrics = index_and_evaluate(
        settings,
        corrupted_df,
        paths.corrupted_embeddings_json,
        paths.corrupted_metrics,
        paths.corrupted_answers,
        label=settings.corrupted_collection_name,
    )
    corrupted_quality, corrupted_freshness = observe(settings, corrupted_df, "corrupted")

    print("[corruption] 3/6 repair tu raw")
    repaired_df = repair_from_raw(settings, run_date)
    save_dataset(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)

    print("[corruption] 4/6 index + evaluate repaired")
    repaired_metrics = index_and_evaluate(
        settings,
        repaired_df,
        paths.repaired_embeddings_json,
        paths.repaired_metrics,
        paths.repaired_answers,
        label=settings.repaired_collection_name,
    )
    repaired_quality, repaired_freshness = observe(settings, repaired_df, "repaired")

    print("[corruption] 5/6 report so sanh")
    generate_corruption_report(
        report_path=paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    print("[corruption] 6/6 kiem baseline con nguyen ven")
    assert_baseline_intact(settings, before)

    print("\n[corruption] xong.")
    header = f"{'metric':22} {'baseline':>10} {'corrupted':>10} {'repaired':>10}"
    print(header)
    print("-" * len(header))
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        if key in baseline_metrics:
            print(
                f"{key:22} {baseline_metrics[key]:10.4f} "
                f"{corrupted_metrics[key]:10.4f} {repaired_metrics[key]:10.4f}"
            )
    print(f"\n[corruption] report: {paths.comparison_report}")
