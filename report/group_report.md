# Group Report — Day 10: Data Pipeline & Data Observability

> **Trạng thái: Checkpoint 0 (kickoff).** Các mục về kết quả chạy thật (2, 5 số liệu, 7–12)
> chưa điền được vì pipeline chưa implement. Những ô đó ghi rõ `Chưa có — CP0` thay vì điền số
> giả. Cập nhật lại sau mỗi checkpoint.

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K3 — D305-A1              |
| Tên nhóm         | K3_Day10_D305_A1           |
| Repository         | https://github.com/huylq-at-work/K3_Day10_D305_A1 |
| Ngày hoàn thành | [Điền khi nộp]           |

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

Chưa có — CP0. Ở checkpoint này nhóm mới hoàn thành phần chuẩn bị: dựng được môi trường chạy
(Python 3.13.14 qua `uv sync`, import được cả 6 package trong `src/`), chốt phân công theo thư
mục sở hữu để bốn người làm song song không conflict, và chốt danh sách artifact cùng đường dẫn
lấy nguyên từ `Paths` trong `src/core/config.py`. Toàn bộ 24 chỗ `TODO(student)` đã được rà và
gán cho từng người. Baseline pipeline chưa chạy nên chưa có artifact, chưa có metrics, và chưa
có kết luận nào về tác động của corruption. Blocker duy nhất hiện tại là `GOOGLE_API_KEY` chưa
được điền vào `.env` — thiếu key thì `_judge_answer` trong `src/evaluation/metrics.py` rơi về
heuristic fallback, và `judge_accuracy` sẽ không dùng được làm bằng chứng.

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
| `LLM_PROVIDER`             | `gemini` |
| `LLM_MODEL`                | `gemini-2.5-flash` |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | `max_results=24` (giá trị starter, chưa fetch thật) |
| Retrieval `top_k`           | `4` |
| Freshness threshold          | `180` ngày (`source_filter` cũng lọc `from-pub-date` theo mốc này) |
| Random seed, nếu có        | Chưa đặt — cần chốt ở corruption để tái hiện được |

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
| Import 6 package | Thành công | 2026-08-06 | Lệnh kiểm tra ở trên in `OK` |
| Baseline pipeline | Thất bại có chủ đích | 2026-08-06 | `NotImplementedError: Student task: implement phase1 pipeline.` — đúng trạng thái starter, chưa phải lỗi setup |
| Corruption flow   | Chưa chạy | — | Phụ thuộc baseline |

**Ghi chú môi trường:** Python hệ thống là 3.14, nằm ngoài khoảng `>=3.11,<3.14` của
`pyproject.toml`, nên `uv` tự tải 3.13 vào `.venv`. Lần đầu `uv sync` có thể báo
`Missing expected target directory for Python minor version link` — chạy lại là qua.

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`settings.source_api`) |
| Query/filter                | query `agentic retrieval augmented generation large language model`; filter `from-pub-date:<hôm nay - 180 ngày>,has-abstract:true` |
| Thời điểm lấy dữ liệu | Chưa có — CP0 |
| Số record nhận được    | Chưa có — CP0 (`max_results=24`) |
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

Chưa chạy nên chưa có số liệu; quy ước đã chốt ở CP0: `paper_id` lấy từ DOI (định danh ổn định,
không đổi giữa các lần fetch — điều kiện để `ground_truth_doc_ids` của R4 còn khớp sau khi
re-index); `age_days` = `run_date` trừ `published`; `text_for_embedding` ghép title + summary +
authors + categories và **phải dựng lại mỗi khi dữ liệu bị sửa**, nếu không index sẽ không phản
ánh corruption và phase 2 mất ý nghĩa.

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Loại record thiếu DOI/title/summary | Completeness | Chưa có — CP0 | So `len(raw_records)` với số dòng `papers_clean.csv` |
| Loại record không parse được `published` | Validity | Chưa có — CP0 | Quality check null trên `published` |
| Drop duplicate theo `paper_id` | Uniqueness | Chưa có — CP0 | Check `paper_id` unique trong `run_data_quality_checks` |
| Normalize whitespace title/summary | Consistency | Chưa có — CP0 | Đối chiếu raw ↔ clean trên vài sample |

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | Chưa có — CP0 |
| Các `question_type`                    | `summary`, `authors`, `date`, `categories` (khớp nhánh nhận diện trong `_extract_answer` của `src/retrieval/qa.py`) |
| Ground-truth document ID                 | Lấy trực tiếp từ `paper_id` trong `papers_clean.csv`, **không tự bịa ID** |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | Chroma persistent tại `data/chroma/`; collection `papers-baseline` / `papers-corrupted` / `papers-repaired` |
| Retrieval `top_k`                       | `4` |
| LLM provider/model                       | `gemini` / `gemini-2.5-flash` |
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
| Raw response/records     | `data/raw/crossref_response.json`, `crossref_records.json` | Thiếu | R2 — chưa chạy |
| Cleaned dataset          | `data/clean/papers_clean.csv`, `.json` | Thiếu | R2 — chưa chạy |
| Embedding manifest/index | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Thiếu | R3 — chưa chạy |
| Evaluation set           | `data/eval/test_set.json` | Thiếu | R4 — chưa chạy |
| Baseline metrics         | `data/results/baseline_metrics.json` | Thiếu | R4 — chưa chạy |
| Quality/freshness        | `data/quality/`, `freshness_report.json` | Thiếu | R4 — chưa chạy |
| Baseline report          | `data/reports/phase1_report.md` | Thiếu | R4 — chưa chạy |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` | Chưa có — CP0 | — |
| `mean_token_f1`      | Chưa có — CP0 | — |
| `judge_accuracy`     | Chưa có — CP0 | — |
| `mean_judge_score`   | Chưa có — CP0 | — |
| Ragas, nếu có        | Chưa chạy | Mặc định tắt; bật bằng `RUN_RAGAS=1` |

## 8. Data quality và freshness

### Quality checks

Bộ check dự kiến (theo docstring `run_data_quality_checks`), ngưỡng cụ thể R4 chốt ở CP1:

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| Row count | Completeness | > 0, sát `max_results=24` | Chưa có — CP0 | `data/quality/` |
| `paper_id` not null & unique | Uniqueness / Completeness | 100% | Chưa có — CP0 | `data/quality/` |
| `title` not null | Completeness | 100% | Chưa có — CP0 | `data/quality/` |
| Độ dài `summary` | Validity | Chưa chốt | Chưa có — CP0 | `data/quality/` |
| Freshness theo `age_days` | Timeliness | `age_days <= 180` | Chưa có — CP0 | `data/quality/freshness_report.json` |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Cleaned dataset (`papers_clean.csv`), cột `age_days` dẫn xuất từ `published` |
| Timestamp mới nhất       | Chưa có — CP0 |
| Ngưỡng freshness         | 180 ngày |
| Trạng thái baseline      | Unknown — chưa chạy |
| Lý do                     | Chưa có số liệu |

## 9. Corruption scenarios và repair

Sáu kịch bản theo docstring `corrupt_clean_dataframe`; tham số cụ thể R2 chốt ở CP2.

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| Mất bản ghi mới | Drop một số record `published` gần nhất | Chưa có — CP0 | Row count giảm, freshness stale | Chưa có — CP0 | Clean lại từ `data/raw/` |
| Summary rỗng | Blank `summary` một số dòng | Chưa có — CP0 | Completeness fail | Chưa có — CP0 | Clean lại từ `data/raw/` |
| Text nhiễu | Chèn noise vào `text_for_embedding` | Chưa có — CP0 | Chất lượng retrieval giảm | Chưa có — CP0 | Clean lại từ `data/raw/` |
| Title bị cắt | Truncate `title` | Chưa có — CP0 | `lookup()` theo title miss | Chưa có — CP0 | Clean lại từ `data/raw/` |
| Ngày bị làm cũ | Lùi `published` | Chưa có — CP0 | Freshness stale | Chưa có — CP0 | Clean lại từ `data/raw/` |
| Duplicate | Nhân bản một số dòng | Chưa có — CP0 | Uniqueness fail | Chưa có — CP0 | Drop duplicate khi clean lại |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Thiếu — CP0
- Nhận xét: Chưa có. Yêu cầu đã chốt: log phải ghi đủ **loại corruption, danh sách/số record bị
  tác động và tham số dùng để tạo** — thiếu tham số thì không tái hiện được lần chạy.

Giải thích cách repair đảm bảo dữ liệu được phục hồi từ nguồn đáng tin cậy thay vì chỉ che kết quả lỗi:

Repair **không** sửa trên `papers_clean_corrupted.csv`. Flow chạy lại `build_clean_dataframe` từ
`data/raw/crossref_records.json` — file được ghi một lần ở phase 1 và không ai chạm vào sau đó.
Nhờ vậy dữ liệu repaired là dẫn xuất từ nguồn gốc, không phải bản vá đè lên dữ liệu hỏng. Sau khi
mọi corruption bị ghi đè, mọi cột dẫn xuất (`age_days`, `text_for_embedding`) và index đều dựng
lại từ đầu.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   | Chưa có | Chưa có | Chưa có | — | — | CP0 |
| `mean_token_f1`        | Chưa có | Chưa có | Chưa có | — | — | CP0 |
| `judge_accuracy`       | Chưa có | Chưa có | Chưa có | — | — | CP0 |
| `mean_judge_score`     | Chưa có | Chưa có | Chưa có | — | — | CP0 |
| Quality checks pass/fail | Chưa có | Chưa có | Chưa có | — | — | CP0 |
| Freshness status         | Chưa có | Chưa có | Chưa có | — | — | CP0 |

Nêu ít nhất hai kết luận có quan hệ nhân quả được hỗ trợ bởi artifacts:

1. Chưa có — CP0. Nhóm chưa chạy pipeline nên chưa được phép kết luận corruption có tác động.
2. Chưa có — CP0.

## 11. Vấn đề tích hợp quan trọng

Vấn đề đã gặp ở CP0 (setup, chưa phải tích hợp module):

- **Triệu chứng:** `uv sync` dừng với `error: Missing expected target directory for Python minor version link at ...\cpython-3.13.14-windows-x86_64-none`.
- **Nguyên nhân:** Python hệ thống là 3.14, ngoài khoảng `>=3.11,<3.14` của `pyproject.toml`, nên `uv` phải tải Python 3.13; lần tải đầu tạo symlink phiên bản minor không thành công.
- **Cách xử lý:** Chạy lại `uv sync` — thư mục đã giải nén sẵn, lần hai tạo được link.
- **Cách xác minh:** `uv run python -c "import sys; print(sys.version)"` in `3.13.14`, và lệnh import 6 package in `OK`.

Vấn đề tích hợp giữa các module: chưa có — cập nhật ở checkpoint sau.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| `GOOGLE_API_KEY` chưa điền | `_judge_answer` rơi về heuristic fallback; `judge_accuracy` và `mean_judge_score` không dùng được làm bằng chứng | Điền key rồi chạy lại; đối chiếu `reasoning` trong `baseline_answers.json` — nếu còn chuỗi "Fallback heuristic judge" là chưa gọi được LLM |
| Corruption chưa chốt random seed | Hai lần chạy cho ra tập record bị corrupt khác nhau → bảng so sánh không tái hiện được | Chốt seed cố định và ghi vào `corruption_log.json` |
| `max_results=24` — corpus nhỏ | Vài câu hỏi sai đã làm metric dao động mạnh; khó phân biệt tác động corruption với nhiễu | Ghi rõ cỡ mẫu cạnh mỗi metric; cân nhắc tăng `max_results` nếu Crossref trả đủ |
| Ragas mặc định tắt | Thiếu faithfulness/context recall | Bật `RUN_RAGAS=1` sau khi baseline ổn định |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [ ] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [ ] Baseline, corrupted và repaired dùng cùng evaluation set.
- [ ] Bảng metrics khớp với các file trong `data/results/`.
- [ ] Quality/freshness conclusions khớp với `data/quality/`.
- [ ] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
