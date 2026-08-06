# Group Report — Day 10: Data Pipeline & Data Observability

> **Trạng thái: hoàn tất.** Baseline, corruption và repair đều đã chạy end-to-end. Mọi số trong
> báo cáo này đọc trực tiếp từ artifact trong `data/`, kiểm chéo bằng
> [`script/verify_baseline.py`](../script/verify_baseline.py).

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K3 — D305-A1              |
| Tên nhóm         | K3_Day10_D305_A1           |
| Repository         | https://github.com/huylq-at-work/K3_Day10_D305_A1 |
| Ngày hoàn thành | 2026-08-06                 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Lê Quang Huy | 2A202601821 | Role 1 — Điều phối pipeline (cấu hình, orchestration, release, demo) | `src/core/`, `src/pipelines/`, `script/`, `.env.example` |
| 2 | Nguyễn Chí Hướng | 2A202601203 | Role 2 — Nền tảng dữ liệu & recovery (Crossref, clean schema, corruption, repair) | `src/ingestion/`, `data/raw/`, `data/clean/` |
| 3 | Phạm Thị Liên | 2A202601795 | Role 3 — RAG & agent (MiniLM, Chroma, search, lookup) | `src/retrieval/`, `data/embeddings/`, `data/chroma/` |
| 4 | Nguyễn Tiến Đạt | 2A202601387 | Role 4 — Evaluation & observability (test set, metrics, quality, freshness, reports) | `src/evaluation/`, `src/observability/`, `data/eval/`, `data/quality/`, `data/reports/` |

Chi tiết quy tắc sở hữu file, branch và thứ tự merge: [`TEAMMATES.md`](../TEAMMATES.md).

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**

Nhóm hoàn thành cả ba pha. Baseline lấy 24 bài báo từ Crossref, làm sạch còn đúng 24 dòng
(drop 0), index vào Chroma `papers-baseline`, và chấm trên 40 câu hỏi thuộc 4 loại
(summary/authors/date/categories). Artifact đầy đủ ở `data/raw/`, `data/clean/`,
`data/embeddings/`, `data/eval/`, `data/results/`, `data/quality/` và `data/reports/`.

Corruption chạy 5 kịch bản có chủ đích và deterministic: xoá 3 bài mới nhất, xoá rỗng 2 summary,
chèn nhiễu 2 bài, lùi ngày 4 bài về 730 ngày trước, nhân bản 2 dòng. Kịch bản gây hại rõ nhất là
**xoá 3 bài mới nhất** — làm 8 câu hỏi mất hoàn toàn tài liệu đúng, kéo `retrieval_hit_rate` từ
1.000 xuống 0.800. Xoá rỗng summary tuy chỉ chạm 2 bài nhưng đưa `token_f1` của chính hai câu đó
từ 0.257 và 0.178 về 0.000.

Repair clean lại từ `data/raw/` và **khôi phục hoàn toàn cả 4 metric lẫn 5 tín hiệu quality** về
đúng giá trị baseline. Toàn bộ 120 câu (40 × 3 trạng thái) được `gpt-4o-mini` chấm thật, không có câu nào rơi về
heuristic fallback, và `script/verify_baseline.py` đạt **33/33**. Giới hạn quan trọng nhất còn
lại: `retrieval_hit_rate` bị bão hoà ở 1.000 vì mọi câu hỏi đều trích nguyên tiêu đề bài báo, nên
chỉ số này chưa đo được chất lượng retrieval theo nghĩa chặt.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

Nhóm giữ nguyên luồng của starter:

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

Điểm bàn giao giữa hai role là **file trên đĩa, không phải object trong RAM**. `data/raw/` là
nguồn duy nhất để repair ở phase 2, nên sau khi lưu thì không ai được ghi đè.

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API | Fetch theo `source_query`/`source_filter`, retry-backoff cho `429`/`503`, lưu raw **trước** khi parse, `parse_crossref_payload` → `PaperRecord` | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Nguyễn Chí Hướng |
| Cleaning          | `data/raw/crossref_records.json` | Normalize title/summary/authors/categories, parse date, tính `age_days`, dựng `text_for_embedding`, drop duplicate + row xấu | `data/clean/papers_clean.csv`, `papers_clean.json` | Nguyễn Chí Hướng |
| Embedding/index   | `data/clean/papers_clean.*` | MiniLM `all-MiniLM-L6-v2`, Chroma persistent client, cosine space, collection `papers-baseline` | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Phạm Thị Liên |
| Evaluation        | clean df + index | `build_test_set` sinh câu hỏi summary/authors/date/categories; `evaluate_pipeline` chấm hit-rate, token-F1, LLM judge | `data/eval/test_set.json`, `data/results/baseline_metrics.json`, `baseline_answers.json` | Nguyễn Tiến Đạt |
| Observability     | clean df | Row count, `paper_id` null/unique, `title` null, độ dài `summary`, freshness theo `age_days` | `data/quality/`, `data/quality/freshness_report.json` | Nguyễn Tiến Đạt |
| Corruption/repair | clean df + `data/raw/` | Drop latest records, blank summary, inject noise, truncate title, làm cũ date, thêm duplicate; repair = clean lại từ raw | `data/clean/papers_clean_corrupted.*`, `papers_clean_repaired.*`, `data/results/corruption_log.json` | Nguyễn Chí Hướng (corruption logic) + Lê Quang Huy (ghép flow) |
| Orchestration     | Toàn bộ module trên | `phase1.py`: raw→clean→index→testset→evaluate→quality→report→demo. `corruption_flow.py`: corrupt→re-index→evaluate→repair→evaluate→compare | `data/reports/phase1_report.md`, `data/reports/corruption_report.md`, `data/results/*_metrics.json` | Lê Quang Huy |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `openai` |
| `LLM_MODEL`                | `gpt-4o-mini` |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | `max_results=24`, nhận về đúng 24 |
| Retrieval `top_k`           | `4` |
| Freshness threshold          | `180` ngày (`source_filter` cũng lọc `from-pub-date` theo mốc này) |
| Random seed, nếu có        | Corruption deterministic (`deterministic: true` trong `corruption_log.json`), không dùng RNG |

Các giá trị trên đọc từ `load_settings()` trong `src/core/config.py`, không hard-code lại trong
report. Không dán nội dung API key hoặc file `.env` vào báo cáo.

### Lệnh cài đặt

Nhóm dùng `uv` (theo `uv.lock`):

```bash
uv sync
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Corruption flow (chỉ chạy sau khi baseline xanh):

```bash
uv run python script/run_corruption_flow.py
```

Kiểm tra môi trường trước khi code:

```bash
uv run python -c "import core.config, ingestion.crossref, retrieval.index, evaluation.metrics, observability.quality, pipelines.phase1; print('OK')"
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| `uv sync` | Thành công | 2026-08-06 | `.venv` với Python 3.13.14 |
| Baseline pipeline | Thành công | 2026-08-06 | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công | 2026-08-06 | `data/results/corruption_log.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` |
| `script/verify_baseline.py` | **33/33 check pass** | 2026-08-06 | Bao gồm check judge không dùng heuristic fallback |
| `pytest tests/` | 14/14 pass | 2026-08-06 | — |

**Ghi chú môi trường:** Python hệ thống là 3.14, nằm ngoài khoảng `>=3.11,<3.14` của
`pyproject.toml`, nên `uv` tự tải 3.13 vào `.venv`. Lần đầu `uv sync` có thể báo
`Missing expected target directory for Python minor version link` — chạy lại là qua.

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`settings.source_api`) |
| Query/filter                | query `agentic retrieval augmented generation large language model`; filter `from-pub-date:<hôm nay - 180 ngày>,has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-08-06, lưu snapshot tại `data/raw/crossref_response.json` |
| Số record nhận được    | 24/24 |
| Cơ chế retry/backoff      | Kế hoạch: retry có backoff cho `429`/`503` trong `fetch_source_records`; raw response ghi xuống đĩa **trước** khi parse |

### Raw và clean schema

Schema dưới đây chốt theo `PaperRecord` (`src/ingestion/crossref.py`) và các cột mà
`LocalEmbeddingIndex._build_documents` bắt buộc phải có — đây là **contract R2 không được đổi
một mình**, vì R3 và R4 đọc thẳng các cột này.

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | str | Có | Khóa ổn định, dựng từ DOI | Không có DOI → loại record |
| `title` | str | Có | Tiêu đề bài báo | Rỗng → loại record |
| `summary` | str | Có | Abstract đã normalize | Rỗng → loại record (đây cũng là tín hiệu corruption ở phase 2) |
| `authors_joined` | str | Có | Tác giả nối chuỗi, dùng làm ground truth câu hỏi authors | Thiếu → chuỗi rỗng, quality check bắt |
| `categories_joined` | str | Có | Subject nối chuỗi | Thiếu → chuỗi rỗng |
| `published` | str (ISO date) | Có | Ngày xuất bản, ground truth câu hỏi date | Không parse được → loại record |
| `age_days` | int | Có | Tuổi bản ghi tính từ `run_date` | Dùng cho freshness check |
| `text_for_embedding` | str | Có | Text đưa vào MiniLM | Dựng lại sau mọi thao tác sửa dữ liệu, kể cả corruption |
| `abs_url`, `pdf_url` | str | Không | Link tham chiếu trong metadata | Thiếu → chuỗi rỗng |

Giải thích cách nhóm tạo `text_for_embedding`, document ID và `age_days`:

`paper_id` = DOI đã normalize (viết thường, bỏ tiền tố `doi:` / `https://doi.org/`). Chọn DOI vì
đây là định danh ổn định giữa các lần fetch — điều kiện để `ground_truth_doc_ids` còn khớp sau khi
re-index ở phase 2. `age_days` = ngày chạy trừ `published`. `text_for_embedding` ghép có nhãn
title + authors_joined + categories_joined + summary, và **được dựng lại sau mọi thao tác sửa dữ
liệu**, kể cả corruption — nếu không, index sẽ không phản ánh dữ liệu hỏng và cả phase 2 mất ý nghĩa.

Một ràng buộc phát sinh từ dữ liệu thật: Crossref trả `subject: []` ở **cả 24/24 bài**, nên
`categories` phải fallback theo thứ tự `subject → container-title → type`. Hệ quả được ghi ở mục 12.

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Loại record thiếu DOI/title/summary | Completeness | 0 | 24 raw → 24 clean, `dropped: 0` trong `data/quality/clean_contract.json` |
| Loại record không parse được `published` | Validity | 0 | 24/24 dòng có `published` dạng ISO |
| Drop duplicate theo `paper_id` | Uniqueness | 0 | `paper_id_duplicates: 0` trong `data/quality/baseline.json` |
| Strip JATS/XML khỏi abstract | Consistency | 20/24 | Contract chặn markup: 0 dòng còn tag `<...>` sau clean |
| Normalize whitespace title/summary | Consistency | toàn bộ | Đối chiếu raw ↔ clean |

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 40 (10 mỗi loại) |
| Các `question_type`                    | `summary`, `authors`, `date`, `categories` (khớp nhánh nhận diện trong `_extract_answer` của `src/retrieval/qa.py`) |
| Ground-truth document ID                 | Lấy trực tiếp từ `paper_id` trong `papers_clean.csv`, **không tự bịa ID** |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | Chroma persistent tại `data/chroma/`; collection `papers-baseline` / `papers-corrupted` / `papers-repaired` |
| Retrieval `top_k`                       | `4` |
| LLM provider/model                       | `openai` / `gpt-4o-mini`, endpoint `https://api.openai.com/v1` |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

Giải thích vì sao test set được giữ nguyên khi đánh giá baseline, corrupted và repaired:

Ba trạng thái phải khác nhau **đúng một biến là chất lượng dữ liệu**. Nếu test set đổi giữa các
lần đo thì chênh lệch metric không còn quy được về corruption — có thể chỉ là do bộ câu hỏi mới
dễ hay khó hơn, và toàn bộ bảng so sánh ở mục 10 mất giá trị làm bằng chứng. Vì vậy `test_set.json`
sinh một lần ở baseline và chỉ tạo lại khi đặt `REFRESH_TEST_SET=1`.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/crossref_response.json`, `crossref_records.json` | Có | 24 items, snapshot khoá bằng SHA-256 |
| Cleaned dataset          | `data/clean/papers_clean.csv`, `.json` | Có | 24 dòng, 16 cột |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Có | collection `papers-baseline`, 24 documents |
| Evaluation set           | `data/eval/test_set.json` | Có | 40 câu, 4 loại |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | kèm `baseline_answers.json` |
| Quality/freshness        | `data/quality/baseline.json`, `freshness_report.json` | Có | thêm `clean_contract.json` |
| Baseline report          | `data/reports/phase1_report.md` | Có | số khớp JSON, kiểm bằng `verify_baseline.py` |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` | 1.0000 | 40/40 câu lấy đúng tài liệu. **Chỉ số này bão hoà** — xem mục 12 |
| `mean_token_f1`      | 0.8475 | authors/date/categories đạt 1.000; summary 0.390 |
| `judge_accuracy`     | 0.7750 | Do `gpt-4o-mini` chấm, 0/40 câu dùng heuristic fallback |
| `mean_judge_score`   | 4.3250 | như trên |
| Ragas, nếu có        | Không chạy | Mặc định tắt; bật bằng `RUN_RAGAS=1` |

Vì sao `mean_token_f1` không đạt 1.000: câu hỏi loại summary có ground truth là cả abstract, còn
`qa.py` chỉ trả về `first_sentence(summary)`. Trùng một phần là **đúng thiết kế của starter**,
không phải lỗi. Ba loại còn lại đều khớp tuyệt đối.

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| Row count | Completeness | = số record raw | Pass — 24 | `data/quality/baseline.json` |
| `paper_id` không null | Completeness | 0 | Pass — 0 | như trên |
| `paper_id` unique | Uniqueness | 0 trùng | Pass — 0 | như trên |
| `title` không null | Completeness | 0 | Pass — 0 | như trên |
| `summary` thiếu/rỗng | Completeness | 0 | Pass — 0 | như trên |
| `summary` quá ngắn (<10 ký tự) | Validity | 0 | Pass — 0 | như trên |
| Dòng quá hạn (`age_days` > 180) | Timeliness | 0 | Pass — 0 | `freshness_report.json` |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | `data/clean/papers_clean.json`, cột `age_days` dẫn xuất từ `published` |
| Timestamp mới nhất       | 2026-08-01 (cũ nhất 2026-02-12) |
| Ngưỡng freshness         | 180 ngày, đọc từ `settings.freshness_threshold_days` |
| Trạng thái baseline      | Fresh |
| Lý do                     | 0/24 dòng vượt ngưỡng; `age_days` nằm trong khoảng 5–175 |

## 9. Corruption scenarios và repair

Corruption **deterministic** (`deterministic: true`), không dùng RNG nên tái hiện được y hệt.
Trước khi corrupt, `raw_source_guard` hash SHA-256 hai file raw và xác nhận `verified` — đảm bảo
nguồn để repair không bị đổi giữa chừng.

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| `drop_latest` | Xoá 3 bài `published` mới nhất | 3 | Row count giảm, freshness lùi | Row 24→23; `latest_published` 2026-08-01→2026-07-03; **8 câu hỏi mất tài liệu đúng** | Clean lại từ raw |
| `missing_summary` | Đặt `summary = ""` | 2 | `summary_nulls` tăng | `summary_nulls` 0→2, `short_summaries` 0→2; 2 câu summary rơi từ 0.257/0.178 xuống 0.000 | Clean lại từ raw |
| `noise_injection` | Chèn `__CORRUPTED_NOISE__` ×12 | 2 | Chất lượng retrieval giảm | Nhiễu vào `text_for_embedding`; `token_f1` loại summary giảm | Clean lại từ raw |
| `old_published_date` | Lùi `published` 730 ngày | 4 | Freshness stale | `stale_rows` 0→4, `is_fresh` true→**false**; 1 câu date từ 1.000 xuống 0.000 | Clean lại từ raw |
| `duplicate_rows` | Nhân bản 2 dòng | 2 | Uniqueness fail | `paper_id_duplicates` 0→2; 23 dòng nhưng chỉ 21 `paper_id` duy nhất | Drop duplicate khi clean lại |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Đủ. Mỗi sự kiện ghi `sequence`, `type`, `paper_ids` và `parameters` (số lượng, token
  nhiễu, số ngày lùi…). Có thêm `fingerprint_sha256` của cả baseline lẫn corrupted và cờ
  `different_from_baseline: true` để chứng minh dữ liệu thật sự đổi.

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

Repair **không** sửa trên `papers_clean_corrupted.*`. Flow gọi lại `build_clean_dataframe` từ
`data/raw/crossref_records.json` — file được ghi một lần ở phase 1, hash đã khoá và không ai chạm
vào. Dữ liệu repaired vì vậy là dẫn xuất từ nguồn gốc, không phải bản vá đè lên dữ liệu hỏng. Sau
đó `corruption_flow.py` chạy `validate_clean_dataframe` lên dữ liệu repaired; nếu không đạt
contract thì **dừng hẳn** chứ không sửa tay metrics. Index cũng dựng lại từ đầu vào collection
`papers-repaired` riêng.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | 1.0000 | 0.8000 | 1.0000 | −0.2000 | 100% | 8/40 câu mất tài liệu đúng |
| `mean_token_f1`        | 0.8475 | 0.6574 | 0.8475 | −0.1901 | 100% | — |
| `judge_accuracy`       | 0.7750 | 0.6500 | 0.7750 | −0.1250 | 100% | LLM judge `gpt-4o-mini` |
| `mean_judge_score`     | 4.3250 | 3.8250 | 4.3250 | −0.5000 | 100% | như trên |
| `paper_id` trùng | 0 | 2 | 0 | +2 | 100% | — |
| `summary` thiếu/rỗng | 0 | 2 | 0 | +2 | 100% | — |
| Dòng quá hạn | 0 | 4 | 0 | +4 | 100% | — |
| Freshness status         | Fresh | **Stale** | Fresh | lật trạng thái | 100% | — |
| Row count | 24 | 23 | 24 | −1 | 100% | Xoá 3, thêm 2 bản sao |

`token_f1` tách theo loại câu hỏi: authors 1.000→0.800, categories 1.000→0.822, date 1.000→0.700,
summary 0.390→0.307.

Nêu ít nhất hai kết luận có quan hệ nhân quả được hỗ trợ bởi artifacts:

1. **Xoá bản ghi → row count và freshness đổi → retrieval hỏng.** `drop_latest` xoá
   `10.2118/234689-pa` và `10.1007/s10278-026-02086-9`; `data/quality/corrupted.json` ghi
   `row_count: 23`. Đúng 8 câu hỏi về hai bài này chuyển từ `retrieval_hit: true` sang `false`,
   và agent trả lời bằng bài khác. Ví dụ câu hỏi tác giả của `10.2118/234689-pa`: baseline trả
   đúng *"Qianwen Cao, Chiyu Zhang, Junxiong Ning, Gongru Li"* (`token_f1` 1.000), sau corruption
   trả *"Dr. Sumalatha P, Manoj Kumar"* — tác giả của một bài hoàn toàn khác (`token_f1` 0.000).
2. **Xoá rỗng summary → `summary_nulls` tăng → câu trả lời rỗng.** `missing_summary` chạm
   `10.21203/rs.3.rs-10012178/v1` và `10.1093/sleep/zsag091.0346`; `summary_nulls` đi từ 0 lên 2.
   Hai bài này **vẫn nằm trong corpus và vẫn được retrieve đúng**, nhưng câu trả lời thành chuỗi
   rỗng, `token_f1` từ 0.257 và 0.178 xuống 0.000. Đây là bằng chứng mạnh hơn kết luận 1, vì nó
   cho thấy chất lượng **nội dung** ảnh hưởng tới câu trả lời ngay cả khi retrieval vẫn đúng.
3. **Repair từ raw → mọi signal và metric trở lại baseline.** Cả 4 metric lẫn 5 tín hiệu quality
   ở cột repaired trùng khít cột baseline, vì cả hai cùng dẫn xuất từ `data/raw/` không đổi.

Điểm phải nói rõ, không tô đẹp: `retrieval_hit_rate` giảm **chủ yếu do bản ghi bị xoá**, không
phải do embedding kém đi. `noise_injection` chèn nhiễu vào 2 bài nhưng hai bài đó vẫn được
retrieve đúng — nghĩa là ở quy mô 24 tài liệu, nhiễu văn bản chưa đủ để đánh bật thứ hạng. Không
kết luận "corruption làm hỏng retrieval" theo nghĩa ngữ nghĩa.

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Baseline chạy xong, exit code 0, nhưng `mean_token_f1` chỉ 0.1357 và
  `judge_accuracy` 0.0667. Tách theo loại câu hỏi thì `token_f1` của authors đúng bằng **0.000**.
- **Nguyên nhân:** Ba lỗi chồng nhau ở ranh giới giữa các module. (1) `qa.py::_extract_answer`
  chọn field trả lời bằng cách dò cụm tiếng Anh (`"who authored"`, `"when was"`…), trong khi test
  set sinh câu hỏi tiếng Việt — nên mọi câu rơi về nhánh mặc định `first_sentence(summary)`.
  (2) `testset.py` lấy ground truth từ cột list `authors`/`categories` thay vì cột đã join, nên
  `token_f1` đếm cả dấu ngoặc và dấu nháy. (3) `testset.py` đọc `row.get("published_date")` —
  cột không tồn tại trong clean schema (tên đúng là `published`) — nên **toàn bộ loại câu hỏi
  `date` bị bỏ qua**, test set chỉ có 3 loại thay vì 4.
- **Cách xử lý:** Router trong `qa.py` nhận thêm cụm tiếng Việt (cộng thêm, giữ nguyên tiếng
  Anh); `testset.py` chuyển sang dùng `authors_joined` / `categories_joined` / `published`.
- **Cách xác minh:** `REFRESH_TEST_SET=1 uv run python script/run_phase1.py` rồi
  `uv run python script/verify_baseline.py`. Test set từ 30 lên 40 câu (đủ 4 loại),
  `mean_token_f1` 0.1357 → 0.8475, `judge_accuracy` 0.0667 → 0.8000, audit từ 29/32 lên 32/33.

Một lỗi cùng loại ở phía observability: `build_freshness_report` đọc `df["published_date"]` và
hard-code ngưỡng stale 365 ngày thay vì đọc `settings.freshness_threshold_days` (180). Hậu quả là
`latest_published` luôn `null`, và khi thử làm cũ 24 dòng lên 200 ngày thì report vẫn báo
`stale_rows: 0`, `is_fresh: true`. Nếu không phát hiện, kịch bản corruption "làm cũ dữ liệu" sẽ
**hoàn toàn tàng hình** và nhóm sẽ kết luận nhầm là pipeline không phát hiện được. Cùng lúc,
`summary_nulls` dùng `isnull()` nên không đếm chuỗi rỗng — kịch bản "summary rỗng" cũng không để
lại dấu vết nào.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| ~~Chưa có API key LLM~~ **Đã xử lý** | Đã nạp key OpenAI, chạy lại cả ba trạng thái. 0/40 câu dùng fallback ở mỗi trạng thái; `verify_baseline.py` từ 32/33 lên **33/33** | — |
| `retrieval_hit_rate` bão hoà ở 1.000 | Mọi câu hỏi đều trích nguyên tiêu đề trong dấu nháy đơn, mà `answer_question` bắt tiêu đề bằng regex rồi lookup chính xác — tài liệu đúng luôn được chèn lên đầu bất kể embedding tốt hay xấu | Thêm câu hỏi **không** chứa nguyên văn tiêu đề, rồi so lại hit rate ba trạng thái |
| Crossref trả `subject: []` ở 24/24 bài | `categories` phải fallback sang `container-title`/`type`; 9/24 dòng dùng chung giá trị (7 bài cùng `posted-content`) nên câu hỏi loại categories không phân biệt được bài | Sinh câu hỏi categories chỉ từ 15 bài có giá trị duy nhất, hoặc đổi nguồn category |
| Corpus chỉ 24 tài liệu | Vài câu sai đã làm metric dao động mạnh; khó tách tác động corruption khỏi nhiễu nền | Ghi rõ cỡ mẫu cạnh mỗi metric; tăng `max_results` nếu Crossref trả đủ |
| Ragas mặc định tắt | Thiếu faithfulness và context recall | Bật `RUN_RAGAS=1` sau khi có API key |
| `noise_injection` chưa đủ mạnh để đổi thứ hạng | Không kết luận được về ảnh hưởng của nhiễu văn bản lên retrieval | Tăng tỉ lệ nhiễu hoặc thay bằng nhiễu ngữ nghĩa, rồi đo lại hit rate |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp — `run_phase1.py` rồi `run_corruption_flow.py`.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set — `corruption_flow.py` luôn truyền `settings.paths.eval_testset`.
- [x] Bảng metrics khớp với các file trong `data/results/` — `verify_baseline.py` tính lại từ `baseline_answers.json` và đối chiếu.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng. Quy ước đặt tên: `report/individual_<MSSV>.md`.
  Đủ 4/4: Nguyễn Chí Hướng (`individual_2A202601203.md`), Nguyễn Tiến Đạt (`individual_2A202601387.md`),
  Phạm Thị Liên (`individual_2A202601795.md`), Lê Quang Huy (`individual_2A202601821.md`).
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh — đã quét `sk-`, `AIza`, `ghp_`, `sk-ant-`.
- [x] Không hard-code path tuyệt đối — `persist_path` trong embedding manifest đã chuyển sang tương đối.
