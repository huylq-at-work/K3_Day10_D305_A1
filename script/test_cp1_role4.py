import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
import json
from observability.quality import run_data_quality_checks, build_freshness_report
from evaluation.testset import build_test_set
from core.config import load_settings

def test_cp1():
    print("=== ROLE 4: CP1 TESTING ===")
    settings = load_settings()
    
    clean_csv = settings.paths.clean_csv
    if not clean_csv.exists():
        print(f"Lỗi: Không tìm thấy file {clean_csv}. Role 2 chưa tạo file này.")
        return
        
    print(f"Đọc dữ liệu từ {clean_csv}...")
    df = pd.read_csv(clean_csv)
    print(f"Đã đọc {len(df)} dòng.\n")
    
    print("1. Chạy Quality Checks (Observe CP1)...")
    quality = run_data_quality_checks(df, settings, "baseline_quality")
    freshness = build_freshness_report(df, settings, settings.paths.quality_dir / "baseline_freshness.json")
    print(f"Quality Metrics: {json.dumps(quality, indent=2)}")
    print(f"Freshness Report: {json.dumps(freshness, indent=2)}\n")
    print(f"-> Đã lưu quality report đầu tiên làm evidence baseline tại {settings.paths.quality_dir}\n")
    
    print("2. Chạy Test Set Draft (Eval CP1)...")
    test_set = build_test_set(df, settings.paths.eval_testset)
    if test_set:
        print(f"Đã tạo {len(test_set)} câu hỏi nháp. Ví dụ 1 câu:")
        print(json.dumps(test_set[0], indent=2, ensure_ascii=False))
        print(f"\n-> Đã lưu test set tại {settings.paths.eval_testset}")
    else:
        print("Lỗi: Không tạo được câu hỏi nào!")

if __name__ == "__main__":
    test_cp1()
