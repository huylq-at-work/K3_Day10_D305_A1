# Báo cáo vai trò thành viên — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Chí Hướng |
| MSSV | 2A202601203 |
| Khóa/Lớp | K3 — D305-A1 |
| Tên nhóm | K3_Day10_D305_A1 |
| Vai trò chính | Role 2 — Nền tảng dữ liệu & recovery |
| Repository | https://github.com/huylq-at-work/K3_Day10_D305_A1 |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Crossref ingestion | `src/ingestion/crossref.py`: `PaperRecord`, `parse_crossref_payload`, `fetch_source_records`, raw audit | Crossref Works response và `Settings` | `crossref_response.json`, `crossref_records.json`, schema raw ổn định | Hoàn thành |
| Cleaning và data modeling | `src/ingestion/cleaning.py`: `build_clean_dataframe_with_report`, `build_text_for_embedding` | Danh sách `PaperRecord`, `run_date` | `papers_clean.csv/json`, cleaning report, 16 cột clean | Hoàn thành |
| Lineage và khóa nguồn | `src/ingestion/lineage.py`, `src/ingestion/checkpoint.py` | Raw response, raw records, clean/index/test artifacts | Source lock SHA-256, raw audit, lineage evidence | Hoàn thành |
| Corruption deterministic | `src/ingestion/corruption.py`, `src/ingestion/corruption_checkpoint.py` | Clean baseline và kế hoạch corruption | Corrupted CSV/JSON, event log và validation | Hoàn thành |
| Recovery từ raw | `src/ingestion/recovery_checkpoint.py` | Raw snapshot đã khóa, corrupted artifacts | Repaired CSV/JSON, `recovery_evidence.json`, handoff report | Hoàn thành |

Đầu ra clean của tôi là contract đầu vào cho Role 3 xây embedding/index và Role 4 tạo test set, quality/freshness. Logic corruption của tôi được Role 1 gọi trong flow tích hợp. Tôi không nhận ownership cho `src/pipelines/`, retrieval, evaluation hay observability.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Đối chiếu clean → index metadata → test set | Role 3 và Role 4 | Chứng minh `paper_id`, metadata và `text_for_embedding` giữ đúng lineage; chỉ ra lỗi consumer từng đọc `published_date` thay vì `published` |
| Bàn giao raw/clean contract và sample | Các module downstream | Có `raw_snapshot_audit.json`, `cleaning_handoff.json`, `README_ROLE2.md` và sample DOI có bằng chứng nguồn |
| Kiểm tra cấu hình nhạy cảm | Toàn nhóm | `.env` bị ignore, không tracked/chưa từng commit; không phát hiện API key literal trong 97 file được quét |
| Hỗ trợ kiểm chứng flow corruption/repair | Role 1 và Role 4 | Cung cấp corruption log, repaired artifact, per-record lineage và bảng clean/corrupted/repaired |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse Crossref và lưu raw trước parse | `crossref.py`, `data/raw/crossref_response.json`, `crossref_records.json` | 24 response items → 24 `PaperRecord`; DOI chuẩn hóa làm `paper_id`; retry/backoff cho lỗi tạm thời | `python -m ingestion.checkpoint` |
| Chuẩn hóa và dựng clean schema | `cleaning.py`, `papers_clean.json`, `cleaning_report.json` | 24 raw → 24 clean; drop 0; duplicate 0; đủ 16 cột; `age_days` và embedding text hợp lệ | Đọc `cleaning_report.json`; chạy clean contract |
| Khóa snapshot và truy vết lineage | `baseline_source_lock.json`, `baseline_lineage_evidence.json` | Khóa SHA-256 cho cả raw response và raw records; DOI sample đi xuyên raw → clean → index metadata | `python -m ingestion.lineage` |
| Tạo 5 kịch bản corruption | `corruption.py`, `corruption_log.json` | Drop 3 latest, blank 2 summary, noise 2 summary, lùi 4 date, thêm 2 duplicate; mọi event có ID/tham số/count | `python -m ingestion.corruption_checkpoint` |
| Repair thực sự từ nguồn | `recovery_checkpoint.py`, `recovery_evidence.json` | Rebuild 24 repaired rows trực tiếp từ raw; không fetch ngoài, không copy baseline; 13/13 record tác động được phục hồi | `python -m ingestion.recovery_checkpoint` |
| Bổ sung test Role 2 | `tests/test_role2_data_foundation.py` | Test parse, source lock, no-fetch, corruption deterministic, lineage, recovery và secret audit | `uv run --extra dev pytest -q tests` → 14 passed |

Output tiêu biểu là `data/clean/recovery_evidence.json`. Artifact này không chỉ ghi cờ pass mà tự đối chiếu từng DOI bị corruption từ item trong raw Crossref response, qua `PaperRecord`, sang row repaired. Fingerprint repaired bằng fingerprint clean baseline `8e0e2c3f...bd800`; raw hash trước và sau repair không đổi.

Các commit chính của phần việc: `a4842e9` (raw audit/cleaning), `455dcfd` (lineage/source lock), `97126cc` (artifact validation), `9c24b36` (corruption/repair evidence), `6b7bcd1` (raw-based recovery checkpoint).

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline RAG chỉ đáng tin khi document ID ổn định, clean schema không bị suy đoán, raw source còn nguyên để phục hồi và corruption thực sự tạo tín hiệu xấu có thể quan sát. Nếu repair chỉ chép baseline hoặc sửa tay corrupted row thì metric có thể phục hồi nhưng không chứng minh được khả năng recovery. Vì vậy phần của tôi tạo chuỗi bằng chứng từ Crossref response đến repaired dataset, đồng thời khóa nguồn để không fetch lại giữa phép so sánh.

### Cách triển khai

1. `parse_crossref_payload` đọc `message.items`, chuẩn hóa DOI thành chữ thường và bỏ prefix DOI URL để tạo `paper_id`. Title, abstract, author, category, published/updated và URL được chuyển vào `PaperRecord`. Raw API response được ghi xuống đĩa trước khi parse. Fetch có tối đa 5 lần thử, exponential backoff cho `429`, `500`, `502`, `503`, `504`.
2. Cleaning chuẩn hóa whitespace/markup, authors/categories thành list không trùng và tạo thêm dạng joined. Record thiếu `paper_id`, title, summary hoặc ngày hợp lệ bị loại có reason log. Duplicate DOI giữ candidate có `updated` mới hơn, sau đó ưu tiên summary dài hơn.
3. `age_days = run_date - published`. `text_for_embedding` được dựng theo một format duy nhất gồm title, authors, categories và abstract. Clean rows được sắp theo `published DESC, paper_id ASC` để tái hiện ổn định.
4. Source lock lưu SHA-256 của `crossref_response.json` và `crossref_records.json`. Nếu `REFRESH_SOURCE=1` hoặc hash thay đổi, checkpoint dừng thay vì tiếp tục với baseline khác.
5. Corruption dùng kế hoạch deterministic, chọn ID theo quy tắc cố định và ghi từng event với `paper_ids`, parameters, before/after count. Sau khi đổi summary, `text_for_embedding` được dựng lại để corruption thực sự đi vào index input.
6. Recovery chỉ gọi `load_raw_records -> build_clean_dataframe_with_report`. Baseline và corrupted chỉ được đọc để validation. Mỗi record bị tác động được parse lại từ item Crossref tương ứng, rồi so fingerprint với repaired row và baseline row.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Crossref JSON có `message.items`; `PaperRecord`; raw snapshot; `run_date`; clean baseline khi tạo corruption |
| Output | Raw response/records; clean/corrupted/repaired CSV+JSON; cleaning, lineage, corruption và recovery evidence |
| Module phụ thuộc | `core.config.Settings`, `core.contract.CLEAN_COLUMNS`, utility ghi JSON/CSV |
| Module sử dụng output | Retrieval index, evaluation/test set, quality/freshness và hai pipeline orchestration |
| Điều kiện lỗi cần xử lý | Payload thiếu `message.items`; HTTP retryable; DOI/date/summary thiếu; duplicate DOI; schema thiếu cột; raw hash đổi; refresh ngoài ý muốn; repaired không khớp source/baseline |

### Cách xác minh

```powershell
$env:REFRESH_SOURCE = "0"
uv run python -m ingestion.recovery_checkpoint
uv run --extra dev pytest -q tests
```

- **Kết quả mong đợi:** raw hash không đổi, toàn bộ corruption event khớp log, 13 record có lineage nguồn, repaired đạt clean contract và secret audit pass.
- **Kết quả thực tế:** tất cả 7 recovery checks pass; clean/repaired 24 rows, corrupted 23 rows; 14 tests passed.
- **Artifact/log:** `data/raw/baseline_source_lock.json`, `data/results/corruption_log.json`, `data/clean/recovery_evidence.json`, `data/clean/RECOVERY_HANDOFF.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần phục hồi corrupted dataset nhưng vẫn bảo đảm phép so sánh với baseline công bằng.
- **Các phương án đã cân nhắc:** (1) sửa trực tiếp các row corrupted bằng giá trị trong baseline; (2) copy lại `papers_clean.json`; (3) khóa raw snapshot và chạy lại toàn bộ cleaning producer.
- **Phương án đã chọn:** Phương án 3 — repair từ raw snapshot đã khóa, dùng cùng `run_date` của baseline.
- **Lý do:** Hai phương án đầu làm metric đẹp lại nhưng che mất lỗi và không kiểm tra được parser/cleaner. Rebuild từ raw kiểm thử đúng năng lực recovery, giữ source cố định, tái hiện được và không cần gọi API lần nữa.
- **Bằng chứng quyết định phù hợp:** 13/13 record bị tác động khớp chuỗi Crossref response → raw record → repaired; repaired có 24 row/24 ID, fingerprint bằng baseline; raw hash trước/sau giống nhau; 4 metric đều phục hồi 100%.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Checkpoint corruption cũ có thể chỉ đọc `papers_clean_repaired.json` nếu file tồn tại; nếu file không tồn tại thì ghi `repair_validation.available = false` nhưng phần corruption vẫn có thể pass. Điều này chưa chứng minh repaired vừa được tạo lại từ raw.
- **Lệnh hoặc bước tái hiện:** Xem `build_corruption_checkpoint`: bước chính tạo corrupted artifact, còn repaired chỉ được load có điều kiện từ artifact có sẵn.
- **Nguyên nhân gốc:** Corruption validation và recovery generation bị gộp về mặt bằng chứng; validator không sở hữu bước chạy lại cleaning producer.
- **Cách xử lý:** Tạo `src/ingestion/recovery_checkpoint.py`. Checkpoint khóa nguồn, load 24 raw records, lấy đúng baseline `run_date`, chạy `build_clean_dataframe_with_report`, ghi repaired mới, kiểm tra contract, quality, secret và per-record lineage.
- **Cách xác minh sau khi sửa:** `python -m ingestion.recovery_checkpoint` trả `passed: true`; `recovery_evidence.json` ghi `external_fetch_used: false`, `baseline_used_only_for_validation: true`, `all_corrupted_records_restored_from_raw: true`.
- **Điều học được:** Validation một artifact có sẵn không đồng nghĩa chứng minh được provenance của artifact. Recovery cần kiểm tra cả producer path và nguồn đầu vào, không chỉ so output cuối.

## 7. Hiểu biết về luồng end-to-end

1. Crossref Works API trả JSON. Ingestion lưu nguyên response, parse thành `PaperRecord`, rồi cleaning tạo 16 cột và `text_for_embedding`. Role 3 dùng embedding model MiniLM để mã hóa text này và lưu document/metadata vào ba collection Chroma riêng cho baseline, corrupted và repaired.
2. Test set tạo câu hỏi summary/authors/date/categories từ clean rows. `ground_truth_doc_ids` chứa `paper_id` đúng. Retrieval hit kiểm tra tài liệu đúng có trong top-k; token F1 và judge đánh giá câu trả lời so với ground truth.
3. Quality checks đo completeness/uniqueness/validity như row count, null, duplicate và summary ngắn. Freshness monitoring tập trung vào timeliness, dùng `published`/`age_days` và ngưỡng 180 ngày để xác định stale.
4. Baseline, corrupted và repaired phải dùng cùng test set, top-k và evaluator để chỉ có một biến thay đổi là dữ liệu. Nếu đổi câu hỏi giữa các lần thì chênh lệch metric không còn quy được cho corruption/repair.
5. Repair thành công khi repaired được tạo từ raw source cố định, đạt clean contract, khôi phục ID/row/schema/quality/freshness, fingerprint khớp baseline và các metric trở về baseline. Không dùng riêng một cờ `pass` hay một metric để kết luận.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | Drop latest làm 8/40 câu mất tài liệu đúng; repair phục hồi hoàn toàn |
| `mean_token_f1` | 0.8475 | 0.6574 | 0.8475 | Summary rỗng/noise và record bị drop làm chất lượng câu trả lời giảm |
| `judge_accuracy` | 0.8000 | 0.6250 | 0.8000 | Phục hồi 100%, nhưng đây là heuristic fallback, không phải LLM judge |
| `mean_judge_score` | 4.1500 | 3.4500 | 4.1500 | Cùng hạn chế heuristic như trên |
| Quality checks | 24 rows; 0 duplicate; 0 summary rỗng | 23 rows; 2 duplicate; 2 summary rỗng | 24 rows; 0 duplicate; 0 summary rỗng | Các tín hiệu phản ánh đúng corruption log |
| Freshness status | Fresh; 0 stale | Stale; 4 stale | Fresh; 0 stale | Lùi 4 ngày xuất bản 730 ngày làm freshness fail |

### Kết luận từ số liệu

1. Drop 3 latest + blank/noise/old-date/duplicate → corrupted còn 23 rows và 21 ID duy nhất, có 2 summary rỗng và 4 stale rows → retrieval hit giảm 0.2000, token F1 giảm 0.1901 và mean judge score giảm 0.7000.
2. Rebuild cleaning từ raw snapshot → 24 rows/24 ID, duplicate/missing/stale về 0 và freshness trở lại Fresh → toàn bộ bốn metric trở đúng giá trị baseline.

Corruption ảnh hưởng rõ nhất là `drop_latest`. Ba document bị xóa khỏi corpus; hai document trong số đó được test set tham chiếu bởi tổng cộng 8 câu nên không thuật toán retrieval nào có thể lấy đúng document. Vì vậy hit rate giảm thẳng từ 1.000 xuống 0.800. Blank summary ảnh hưởng tập trung hơn: hai câu summary tương ứng giảm token F1 về 0.

Kết quả khác kỳ vọng là `text_for_embedding` không trở thành chuỗi rỗng khi summary bị blank, vì document vẫn còn title/authors/categories. Đây không phải lỗi validator; tín hiệu đúng cần theo dõi là `missing_summary`, summary ngắn và chất lượng answer. Ngoài ra judge metric phục hồi đẹp nhưng chưa chứng minh chất lượng đánh giá bằng LLM thật do môi trường thiếu API key và đang dùng fallback heuristic.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw response và parsed record phục vụ hai mục đích khác nhau: response là bằng chứng nguồn/recovery, còn `PaperRecord` là contract ổn định cho cleaning. Cần lưu cả hai và khóa hash.
2. Data quality phải tính lại từ artifact thật. Một cờ `pass` hard-code hoặc validation chỉ đọc file cũ không chứng minh được provenance và recovery.
3. Corruption dữ liệu có tác động khác nhau lên RAG: drop record gây lỗi retrieval không thể cứu ở downstream; blank/noise làm hỏng nội dung trả lời; old date và duplicate có thể chưa làm hit rate giảm ngay nhưng vẫn là vi phạm chất lượng cần chặn.

### Nếu có thêm thời gian

Tôi sẽ cải thiện category modeling vì 9/24 rows hiện dùng chung `categories_joined`, đặc biệt `posted-content` xuất hiện 7 lần. Hướng làm là giữ đồng thời Crossref subject, container-title và work type thành các trường provenance riêng thay vì fallback vào một nhãn rộng. Sau đó đo lại số category duy nhất, tỷ lệ câu categories mơ hồ và token F1 theo question type, nhưng vẫn giữ nguyên snapshot/test protocol khi so sánh.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Chí Hướng

**Ngày xác nhận:** 2026-08-06
