"""Audit cheo artifact baseline - Role 1.

Baseline chi coi la xong khi artifact, metrics va report KHOP NHAU, khong phai
khi run_phase1.py exit code 0. Script nay doc lai tung file da ghi va doi chieu
voi nhau, khong tin so nao do pipeline tu bao.

Chay:
    uv run python script/verify_baseline.py

Exit code 1 neu co FAIL.
"""
from __future__ import annotations

from pathlib import Path
import json
import re
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from core.config import load_settings  # noqa: E402
from core.contract import validate_clean_dataframe  # noqa: E402

CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))


def close(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


def main() -> int:
    settings = load_settings()
    paths = settings.paths

    # --- 1. Artifact ton tai va doc duoc -------------------------------------
    expected = {
        "raw response": paths.raw_api_response,
        "raw records": paths.raw_records_json,
        "clean csv": paths.clean_csv,
        "clean json": paths.clean_json,
        "embedding manifest": paths.embeddings_json,
        "test set": paths.eval_testset,
        "baseline metrics": paths.baseline_metrics,
        "baseline answers": paths.baseline_answers,
        "freshness report": paths.freshness_report,
        "phase1 report": paths.baseline_report,
    }
    for label, path in expected.items():
        exists = path.exists() and path.stat().st_size > 0
        check(f"ton tai: {label}", exists, str(path) if not exists else "")
    if not all(path.exists() for path in expected.values()):
        report()
        return 1

    clean = pd.DataFrame(json.loads(paths.clean_json.read_text(encoding="utf-8")))
    clean_csv = pd.read_csv(paths.clean_csv)
    raw_records = json.loads(paths.raw_records_json.read_text(encoding="utf-8"))
    manifest = json.loads(paths.embeddings_json.read_text(encoding="utf-8"))
    test_set = json.loads(paths.eval_testset.read_text(encoding="utf-8"))
    metrics = json.loads(paths.baseline_metrics.read_text(encoding="utf-8"))
    answers = json.loads(paths.baseline_answers.read_text(encoding="utf-8"))
    freshness = json.loads(paths.freshness_report.read_text(encoding="utf-8"))
    report_md = paths.baseline_report.read_text(encoding="utf-8")

    # --- 2. Contract van pass tren artifact da ghi ---------------------------
    contract = validate_clean_dataframe(clean, raw_record_count=len(raw_records))
    check("clean contract pass", contract.passed, "; ".join(contract.blockers))

    # --- 3. Count khop nhau giua cac tang -----------------------------------
    check("clean csv == clean json", len(clean_csv) == len(clean), f"{len(clean_csv)} vs {len(clean)}")
    check(
        "manifest documents == clean rows",
        len(manifest["documents"]) == len(clean),
        f"{len(manifest['documents'])} vs {len(clean)}",
    )
    check(
        "manifest collection == baseline collection",
        manifest["collection_name"] == settings.baseline_collection_name,
        f"{manifest['collection_name']} vs {settings.baseline_collection_name}",
    )
    check(
        "manifest model == settings model",
        manifest["embedding_model"] == settings.embedding_model,
        manifest["embedding_model"],
    )
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(paths.chroma_dir))
        collection = client.get_collection(name=settings.baseline_collection_name)
        check(
            "chroma count == clean rows",
            collection.count() == len(clean),
            f"{collection.count()} vs {len(clean)}",
        )
    except Exception as exc:
        check("chroma doc duoc", False, str(exc)[:120])

    # --- 4. Test set tro toi paper_id co that -------------------------------
    known = set(clean["paper_id"])
    dangling = [
        item["id"]
        for item in test_set
        for doc_id in item["ground_truth_doc_ids"]
        if doc_id not in known
    ]
    check("ground_truth_doc_ids deu ton tai trong clean", not dangling, f"{len(dangling)} cau hong")
    check("test set khong rong", len(test_set) > 0, "")

    # --- 5. Metrics tinh lai tu answers co khop file metrics khong ----------
    check("samples == so answers", metrics["samples"] == len(answers), f"{metrics['samples']} vs {len(answers)}")
    recomputed = {
        "retrieval_hit_rate": sum(1.0 for a in answers if a["retrieval_hit"]) / len(answers),
        "mean_token_f1": sum(a["token_f1"] for a in answers) / len(answers),
        "judge_accuracy": sum(1.0 for a in answers if a["judge"]["correct"]) / len(answers),
        "mean_judge_score": sum(a["judge"]["score"] for a in answers) / len(answers),
    }
    for key, value in recomputed.items():
        check(f"metrics khop answers: {key}", close(value, metrics[key]), f"{metrics[key]} vs {value}")

    # --- 6. Judge co that su goi LLM khong ----------------------------------
    fallback = sum(1 for a in answers if "Fallback heuristic" in a["judge"].get("reasoning", ""))
    check(
        "judge dung LLM that (khong fallback)",
        fallback == 0,
        f"{fallback}/{len(answers)} cau dung heuristic - judge_accuracy khong dung lam bang chung",
    )

    # --- 7. Freshness report phan anh du lieu that -------------------------
    published = pd.to_datetime(clean["published"], errors="coerce")
    check("freshness total_rows khop clean", freshness["total_rows"] == len(clean), "")
    check(
        "freshness latest_published khong null",
        freshness.get("latest_published") is not None,
        "report ghi null trong khi clean data co ngay hop le",
    )
    if freshness.get("latest_published"):
        check(
            "freshness latest_published dung",
            str(freshness["latest_published"])[:10] == published.max().date().isoformat(),
            f"{freshness['latest_published']} vs {published.max().date()}",
        )
    stale = int((clean["age_days"] > settings.freshness_threshold_days).sum())
    check("freshness stale_rows dung", freshness["stale_rows"] == stale, f"{freshness['stale_rows']} vs {stale}")

    # --- 8. Report markdown co chua dung so trong metrics -------------------
    # Report in ty le duoi dang phan tram ("100.00%") lan so thuong ("0.1357"),
    # nen doi chieu ca hai dang truoc khi ket luan lech.
    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", report_md)]
    for key in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy"):
        value = metrics[key]
        found = any(close(n, value, 5e-3) or close(n, value * 100, 5e-3) for n in numbers)
        check(f"report co so {key}", found, "" if found else f"khong thay {value:.4f} trong report")
    check(
        "report ghi total_records that",
        "N/A" not in report_md.split("## 2.")[0],
        "" if "N/A" not in report_md.split("## 2.")[0] else "muc Source Summary dang N/A",
    )
    check(
        "report ghi latest_published that",
        "None" not in report_md.split("## 4.")[0],
        "" if "None" not in report_md.split("## 4.")[0] else "muc Freshness dang None",
    )

    report()
    return 1 if any(not ok for _, ok, _ in CHECKS) else 0


def report() -> None:
    width = max(len(name) for name, _, _ in CHECKS)
    failed = 0
    print("=" * (width + 12))
    print("AUDIT BASELINE - Role 1")
    print("=" * (width + 12))
    for name, ok, detail in CHECKS:
        mark = "PASS" if ok else "FAIL"
        line = f"[{mark}] {name.ljust(width)}"
        if detail:
            line += f"  <- {detail}"
        print(line)
        failed += 0 if ok else 1
    print("-" * (width + 12))
    print(f"{len(CHECKS) - failed}/{len(CHECKS)} pass, {failed} fail")


if __name__ == "__main__":
    raise SystemExit(main())
