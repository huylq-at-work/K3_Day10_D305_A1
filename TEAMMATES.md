# BÁO CÁO NHÓM — DAY 10

> Day 10 — Data Pipeline & Data Observability · Đại học VinUni
> Repo: `K3_Day10_LeQuangHuy` · Thư mục làm việc: [`src/`](src/)

## 1. Thành viên

| STT | Họ và tên | Mã sinh viên |
| :-: | :-- | :-- |
| 1 | Nguyễn Chí Hướng | 2A202601203 |
| 2 | Nguyễn Tiến Đạt | 2A202601387 |
| 3 | Phạm Thị Liên | 2A202601795 |
| 4 | Lê Quang Huy | 2A202601821 |

## 2. Phân công vai trò & Branch

Chia theo **thư mục sở hữu** để bốn người chạy song song mà không conflict, và để mỗi
artifact trong `data/` truy được về đúng người tạo ra nó.

| Thành viên | Vai trò | Branch | Thư mục sở hữu (chỉ người này được sửa) |
| :-- | :-- | :-- | :-- |
| Lê Quang Huy | Role 1 — Điều phối pipeline (cấu hình, orchestration, release, demo) | `role1-pipeline-orchestration` | `src/core/`, `src/pipelines/`, `script/`, `.env.example` |
| Nguyễn Chí Hướng | Role 2 — Nền tảng dữ liệu & recovery (Crossref, clean schema, corruption, repair) | `role2-data-foundation` | `src/ingestion/`, `data/raw/`, `data/clean/` |
| Phạm Thị Liên | Role 3 — RAG & agent (MiniLM, Chroma, search, lookup) | `role3-rag-agent` | `src/retrieval/`, `data/embeddings/` |
| Nguyễn Tiến Đạt | Role 4 — Evaluation & observability (test set, metrics, quality, freshness, reports) | `role4-eval-observability` | `src/evaluation/`, `src/observability/`, `data/eval/`, `data/quality/`, `data/reports/` |

### Việc phải xong trong mốc này

**Role 1 — Lê Quang Huy**

1. Chốt người phụ trách, branch, tiêu chí hoàn thành và tên/path artifact.
2. Kiểm tra Python 3.11–3.13, dependencies, provider config và `.env` cục bộ.
3. Lập sơ đồ handoff `raw → clean → index → evaluate → report`.

**Role 2 — Nguyễn Chí Hướng**

1. Đọc Crossref payload và `PaperRecord`; xác định field tạo stable `paper_id`.
2. Hoàn thiện `parse_crossref_payload` và fetch/load theo contract `Settings`.
3. Lưu raw API response **trước** khi parse; thêm retry/backoff cho `429`/`503`.
4. Đọc target clean schema; chốt rule null, date, duplicate, authors/categories.
5. Chỉ ra field tạo `text_for_embedding` và `age_days`.
6. Chuẩn bị sample validation `raw → clean` để chạy ở CP1.

**Role 3 — Phạm Thị Liên**

1. Đọc `LocalEmbeddingIndex`, embeddings, agent để biết input/đầu ra cần có.
2. Chốt embedding model, collection naming và metadata tối thiểu.
3. Chuẩn bị smoke query/lookup sẽ dùng sau khi index.

**Role 4 — Nguyễn Tiến Đạt**

1. Đọc `testset.py`, `qa.py`, `metrics.py` để hiểu format answer và metric.
2. Thiết kế question summary/authors/date/categories từ dữ liệu thật.
3. Nêu `ground_truth_doc_ids` lấy từ `paper_id` clean, **không tự bịa ID**.
4. Liệt kê artifact phải có sau baseline và corruption flow.
5. Định nghĩa tín hiệu: row count, null, duplicate, `age_days`, nguồn timestamp.
6. Phác thảo report chứng minh data xấu làm RAG kém đi.

## 2b. Checkpoint 0 — kết quả Role 1 (Lê Quang Huy)

### (1) Tiêu chí hoàn thành & artifact bàn giao

Mỗi role coi là xong khi **file artifact tồn tại đúng path dưới đây** và mở ra đọc được —
không tính "code chạy không lỗi". Path lấy nguyên từ `Paths` trong
[`src/core/config.py`](src/core/config.py), **không ai được tự đặt tên khác**.

| Role | Artifact phải có | Tiêu chí hoàn thành |
| :-- | :-- | :-- |
| R2 | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Raw lưu **trước** khi parse; retry `429`/`503` có thật |
| R2 | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` | Đủ cột `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `text_for_embedding`; `paper_id` unique, không null |
| R3 | `data/embeddings/papers_embeddings.json`, `data/chroma/` | Manifest có `collection_name`, `embedding_model`, `documents`; `search()` và `lookup()` trả kết quả trên corpus thật |
| R4 | `data/eval/test_set.json` | Mỗi row đủ `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids`; **mọi `ground_truth_doc_ids` phải tồn tại trong `papers_clean.csv`** |
| R4 | `data/results/baseline_metrics.json`, `baseline_answers.json` | Có `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score` |
| R4 | `data/quality/`, `data/quality/freshness_report.json` | Freshness có `latest_published`, `oldest_published`, `stale_rows`, `total_rows`, `is_fresh` |
| R4 | `data/reports/phase1_report.md` | Số trong report khớp artifact thật |
| R1 | `data/results/corruption_log.json`, `corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` | Chạy được `run_phase1.py` rồi `run_corruption_flow.py` liên tiếp trên máy sạch |

### (2) Kiểm tra môi trường — đã chạy trên máy R1

| Hạng mục | Trạng thái | Ghi chú |
| :-- | :-- | :-- |
| Python | ✅ 3.13.14 | `pyproject.toml` yêu cầu `>=3.11,<3.14`. Python hệ thống là 3.14 (ngoài khoảng) nên `uv` tự tải 3.13 vào `.venv` |
| Dependencies | ✅ `uv sync` | Cài theo `uv.lock`. Lần đầu có thể lỗi `Missing expected target directory for Python minor version link` — **chạy lại `uv sync` là qua** |
| Import package | ✅ | `core`, `ingestion`, `retrieval`, `evaluation`, `observability`, `pipelines` import được (nhờ `pip install -e .` / `uv sync`, không phải `requirements.txt`) |
| `.env` | ✅ tạo từ `.env.example` | Đã nằm trong `.gitignore` |
| Provider config | ⚠️ thiếu key | `LLM_PROVIDER=gemini`, `LLM_MODEL=gemini-2.5-flash`, nhưng `GOOGLE_API_KEY` rỗng → `require_llm_credentials()` raise |
| Starter TODO | ✅ 24 chỗ | Xem bảng phân bổ dưới |

**Việc mỗi người phải tự làm:** điền `GOOGLE_API_KEY` vào `.env` của máy mình (hoặc đổi
`LLM_PROVIDER` sang provider có key). Thiếu key thì `_judge_answer` rơi về heuristic fallback
và `judge_accuracy` **không dùng được làm bằng chứng**.

Lệnh dựng môi trường (một lần, tại thư mục gốc repo):

```bash
uv sync
```

Kiểm tra nhanh trước khi bắt đầu code:

```bash
uv run python -c "import core.config, ingestion.crossref, retrieval.index, evaluation.metrics, observability.quality, pipelines.phase1; print('OK')"
```

**Phân bổ 24 chỗ `TODO(student)`/`NotImplementedError`:**

| File | Số chỗ | Role |
| :-- | :-: | :-- |
| `src/ingestion/crossref.py` | 6 | R2 |
| `src/ingestion/cleaning.py` | 2 | R2 |
| `src/ingestion/corruption.py` | 2 | R2 |
| `src/observability/quality.py` | 4 | R4 |
| `src/observability/reporting.py` | 4 | R4 |
| `src/evaluation/testset.py` | 2 | R4 |
| `src/pipelines/phase1.py` | 2 | R1 |
| `src/pipelines/corruption_flow.py` | 2 | R1 |

`src/retrieval/` **không có TODO** — `LocalEmbeddingIndex`, `MiniLMEmbeddings`, `agent.py`,
`qa.py` đã viết sẵn. Phần của R3 là đọc hiểu và chốt tham số, không phải viết lại.

### (3) Sơ đồ handoff

#### Phase 1 — baseline

```text
   [R2]              [R2]                [R2]                  [R3]
Crossref API ──► data/raw/           ──► data/clean/       ──► data/chroma/
   fetch          crossref_response      papers_clean.csv      + data/embeddings/
   retry 429/503  crossref_records       papers_clean.json       papers_embeddings.json
                       │                        │                       │
                  NGUON REPAIR                  │                       │
                  (khong ghi de)                ▼                       │
                                          [R4] data/eval/               │
                                              test_set.json ────────────┤
                                                                        ▼
                                                              [R4] evaluate
                                                            data/results/
                                                            baseline_metrics.json
                                                            baseline_answers.json
                                       [R4] data/quality/              │
                    papers_clean ─────► quality checks ────────────────┤
                                        freshness_report.json          │
                                                                       ▼
                                                            [R4] data/reports/
                                                              phase1_report.md

════════ [R1] ghep toan bo: src/pipelines/phase1.py ← script/run_phase1.py ════════
```

`test_set.json` sinh **từ `papers_clean`** và đi **vào** bước evaluate — không phải sinh ra từ
metrics. Quality checks đọc thẳng `papers_clean`, chạy song song với evaluate, cả hai cùng đổ
vào report cuối.

#### Phase 2 — corruption / repair

```text
                    ┌─── [R2] corrupt ──► papers_clean_corrupted ──► re-index ──► corrupted_metrics
papers_clean ───────┤                     corruption_log.json                     corrupted_answers
  (baseline)        │
                    └─── giu nguyen ────► baseline_metrics (da co tu phase 1)

data/raw/ ─────────────► [R2] clean lai ─► papers_clean_repaired ──► re-index ──► repaired_metrics
(khong bao gio sua)                                                               repaired_answers
                                                                                        │
                                            CUNG MOT test_set.json cho ca 3 trang thai   │
                                                                                        ▼
                                                                        [R4] data/reports/
                                                                          corruption_report.md
```

#### Hợp đồng bàn giao

| # | Từ | Đến | File bàn giao | Người sau chỉ được đọc, không sửa |
| :-: | :-- | :-- | :-- | :-- |
| 1 | R2 | R2 | `data/raw/crossref_records.json` | R2 giữ nguyên sau khi ghi |
| 2 | R2 | R3, R4 | `data/clean/papers_clean.csv` / `.json` | R3 index, R4 sinh test set + quality |
| 3 | R3 | R4 | `data/embeddings/papers_embeddings.json` + `data/chroma/` | R4 chỉ query, không rebuild |
| 4 | R4 | R4, R1 | `data/eval/test_set.json` | Cố định cho cả 3 trạng thái |
| 5 | R4 | R1 | `data/results/*_metrics.json` | R1 đưa vào report so sánh |

Điểm bàn giao giữa hai role là **file trên đĩa, không phải object trong RAM**. Ai xong phần
mình thì commit artifact tương ứng để người sau chạy được ngay, không phải chờ chạy lại từ đầu.

Ba ràng buộc không được vi phạm:

1. **`data/raw/` là nguồn duy nhất để repair.** R2 lưu raw xong thì không được ghi đè — phase 2
   phục hồi bằng cách clean lại từ chính raw đó. Mất raw là mất luôn khả năng chứng minh repair.
2. **Một `test_set.json` duy nhất cho baseline / corrupted / repaired.** Đổi test set giữa các
   lần đo thì chênh lệch metric không quy được về corruption, bảng so sánh mất giá trị.
3. **Mỗi trạng thái một collection riêng** (`papers-baseline` / `papers-corrupted` /
   `papers-repaired`). Ghi đè chung một collection là mất baseline để đối chiếu.

## 2c. Checkpoint 1 — kết quả Role 1 (Lê Quang Huy)

### (1) Clean contract đã chốt

Contract nằm ở [`src/core/contract.py`](src/core/contract.py) — **cố ý đặt trong `core/`, không
đặt trong `ingestion/`**. Nếu để cùng chỗ với code cleaning thì người implement vừa viết code
vừa tự định nghĩa tiêu chí đúng/sai cho chính mình, và gate ở `phase1` không còn độc lập.

| Hạng mục | Chốt |
| :-- | :-- |
| Input | `list[PaperRecord]` từ `data/raw/crossref_records.json` + `run_date` |
| Đầu ra | `pandas.DataFrame` đúng 16 cột theo `CLEAN_COLUMNS`, đúng thứ tự |
| Tên file | `data/clean/papers_clean.csv` và `papers_clean.json` (path lấy từ `Paths`, không tự đặt) |
| Kết quả kiểm | `data/quality/clean_contract.json` |

**Điều kiện dừng** — pipeline raise `ContractViolation` và **không index, không sinh test set**
khi vi phạm bất kỳ điều nào:

| # | Blocker | Vì sao chặn |
| :-: | :-- | :-- |
| 1 | Thiếu cột trong `CLEAN_COLUMNS` | R3/R4 đọc thẳng tên cột, thiếu là vỡ ở tận bước index |
| 2 | < 5 dòng clean | Corpus quá nhỏ, metric vô nghĩa |
| 3 | Null/rỗng ở `paper_id`, `title`, `summary`, `published`, `authors_joined`, `categories_joined`, `text_for_embedding` | Đây đều là nguồn ground truth hoặc đầu vào embedding |
| 4 | `paper_id` trùng | `ground_truth_doc_ids` của R4 thành mơ hồ |
| 5 | `published` không phải ISO `YYYY-MM-DD` | Ground truth câu hỏi date và freshness đều dựa vào |
| 6 | Còn `None` ở cột metadata Chroma | Chroma từ chối metadata `None` |
| 7 | `summary` còn tag markup | JATS lọt vào embedding và vào câu trả lời |
| 8 | `age_days` lệch `published`, hoặc âm | Freshness report sai theo |

Cảnh báo (**không** chặn, nhưng ghi vào report): summary quá ngắn, và nhiều dòng dùng chung
`categories_joined`.

### (2) Rà soát raw → clean

Rà soát **độc lập** trên artifact của branch `role2-data-foundation` (commit `e8d0e04`), không
lấy số R2 tự báo.

| Chỉ số | Giá trị | Kết luận |
| :-- | :-: | :-- |
| Raw items từ Crossref | 24 | |
| Parsed records | 24 | Không mất record khi parse |
| Clean rows | 24 | **Drop = 0** |
| `paper_id` unique | 24/24 | Đạt |
| Tag markup còn sót | 0/24 | JATS đã strip sạch |
| `age_days` lệch `published` | 0/24 | Khớp |
| `published` lệch năm so với raw | 0/24 | Không bịa ngày |
| `authors_joined` = "Unknown" | 0/24 | Không phải điền bù |
| `summary` ngắn nhất | 228 ký tự | Trên ngưỡng 50 |
| `age_days` | 5–175 | Trong ngưỡng freshness 180 |

Chạy `validate_clean_dataframe` trên chính data đó: **PASS, 0 blocker, 1 warning.**

#### Blocker ghi nhận

Không có blocker chặn pipeline. Một vấn đề mức **cảnh báo nhưng cần cả nhóm quyết**:

> **`categories_joined` bị dùng chung ở 9/24 dòng.** Cụ thể: 7 paper cùng giá trị
> `posted-content`, 2 paper cùng `PeerJ Computer Science`.

**Bằng chứng:** Crossref trả `subject: []` ở **cả 24/24 item** — kiểm cả bằng `select=subject`
lẫn gọi thẳng record đầy đủ, không phải lỗi query. R2 buộc phải fallback
`subject → container-title → type`; 8 dòng rơi xuống tận `type`, mà `type` chỉ có 3 giá trị
(`journal-article`, `posted-content`, `report`) nên không phải "category" theo nghĩa nào cả.

**Tác động:** với `question_type=categories`, câu hỏi về paper X có `ground_truth_doc_ids=[X]`
nhưng 7 paper khác cùng đáp án `posted-content`. Retrieval trả về paper khác trong nhóm đó thì
`token_f1` vẫn cao trong khi `retrieval_hit_rate` bị tính là miss — hai metric mâu thuẫn nhau
trên cùng một câu. Ở phase 2 điều này còn tệ hơn: nhiễu sẵn có làm khó tách tác động của
corruption ra khỏi nhiễu nền.

**Đề xuất xử lý (R4 quyết, R1 và R2 đồng bộ theo):** sinh câu hỏi `categories` **chỉ từ các
paper có `categories_joined` duy nhất** (15/24 dòng còn lại), hoặc bỏ `question_type` này và
tăng số câu ở ba loại còn lại. Đừng để nguyên rồi giải thích sau trong report.

### (3) Gate trước index/test set

`src/pipelines/phase1.py` chạy theo thứ tự: load raw → clean → **kiểm contract** → index →
test set → evaluate → quality → report → demo. Bước 3 raise `ContractViolation` là dừng hẳn.

Lý do không cho chạy tiếp khi contract fail: index dựng trên clean data hỏng thì
`baseline_metrics.json` không dùng làm mốc so sánh được, và toàn bộ phase 2
(baseline vs corrupted vs repaired) mất ý nghĩa — nhưng pipeline vẫn "chạy xong" nên rất dễ
tưởng là ổn.

Đã kiểm gate bằng data hỏng mô phỏng (rỗng summary, sai định dạng date, sót tag, trùng
`paper_id`): bắt đủ **4 blocker** và chặn đúng.

## 2d. Checkpoint 2 — kết quả Role 1 (Lê Quang Huy)

Phase 1 đã đủ code để chạy thật (chỉ còn `corruption.py` và `corruption_flow.py` là TODO), nên
CP2 được kiểm bằng **một lần chạy end-to-end thật**, không kiểm trên giấy.

### (1) Khoá clean schema, điều phối handoff clean → test set/index

Schema khoá tại [`src/core/contract.py`](src/core/contract.py) từ CP1. Gate chạy thật trên
dữ liệu R2: **PASS, 0 blocker, 1 warning**, 24 raw → 24 clean, drop 0. Handoff đi đúng thứ tự
`clean → contract → index → test set → evaluate`; index và test set **chỉ chạy sau khi contract
pass**, đúng ràng buộc đã chốt.

### (2) Collection/path baseline tách riêng, tái lập được

| Kiểm | Kết quả |
| :-- | :-- |
| 3 collection khác nhau | `papers-baseline` / `papers-corrupted` / `papers-repaired` — đạt |
| Path clean tách riêng | `papers_clean` / `_corrupted` / `_repaired` — đạt |
| Path embeddings tách riêng | đạt |
| Path metrics tách riêng | đạt |
| Chroma thực tế | chỉ có `papers-baseline`, 24 documents — chưa ghi đè gì |
| Manifest audit được | có `collection_name`, `embedding_model`, `persist_path`, 24 documents |

Smoke test đạt: `semantic_search` trả 3 kết quả có score giảm dần (0.605 → 0.481 → 0.434),
`lookup` theo `paper_id` và theo `title` đều trúng, `lookup` ID không tồn tại trả `None`.

### (3) Blocker phải xử lý trước khi chạy end-to-end

Baseline chạy xong nhưng **số liệu không dùng được**. Chạy được ≠ đúng:

```
retrieval_hit_rate: 1.0000     mean_token_f1: 0.1357
judge_accuracy:     0.0667     mean_judge_score: 1.2000
```

Tách theo `question_type` thì lộ ngay chỗ hỏng:

| question_type | n | retrieval_hit | mean token_f1 |
| :-- | :-: | :-: | --: |
| summary | 10 | 1.00 | 0.390 |
| authors | 10 | 1.00 | **0.000** |
| categories | 10 | 1.00 | **0.017** |

**BLOCKER 1 — test set tiếng Việt không khớp router tiếng Anh trong `qa.py`. (chặn)**

`retrieval/qa.py::_extract_answer` chọn field trả lời bằng cách dò cụm tiếng Anh trong câu hỏi:
`"who authored"`, `"list the authors"`, `"when was"`, `"publication date"`, `"published on"`,
`"what categories"`. Test set của R4 sinh câu hỏi **tiếng Việt** ("Ai là (các) tác giả của…",
"…thuộc về (những) lĩnh vực/chuyên mục nào?"), nên không nhánh nào khớp và **mọi câu đều rơi
xuống nhánh mặc định** `first_sentence(summary)`.

Bằng chứng — câu hỏi authors nhưng câu trả lời là abstract:

```
Q : Ai là (các) tác giả của nghiên cứu có tiêu đề '...'?
GT: ['Audrey Rah', 'Sven Hahues']
AN: Abstract Enterprise adoption of artificial intelligence (AI) systems...
```

Vì vậy `token_f1` của authors đúng bằng 0.000. Đây là lý do `mean_token_f1` tổng chỉ 0.136.
Cách xử lý — **R4 quyết**: hoặc sinh câu hỏi bằng tiếng Anh dùng đúng các cụm trên, hoặc R3 mở
rộng `_extract_answer` để nhận thêm tiếng Việt. Không sửa cả hai cùng lúc.

**BLOCKER 2 — `ground_truth` đang là list Python, không phải chuỗi. (chặn)**

`GT: ['Audrey Rah', 'Sven Hahues']` — dấu ngoặc vuông và dấu nháy bị `_token_f1` đếm thành
token, trong khi metadata phía index là chuỗi `authors_joined`. Kể cả sau khi sửa Blocker 1 thì
F1 vẫn bị kéo xuống oan. `ground_truth` phải là chuỗi đã join, khớp dạng của `authors_joined` /
`categories_joined`.

**BLOCKER 3 — `retrieval_hit_rate` bão hoà ở 1.00, không đo được gì. (cảnh báo, phải ghi vào report)**

`answer_question` bắt title trong dấu nháy đơn bằng regex `'([^']+)'` rồi `lookup` chính xác,
mà mọi câu hỏi của R4 đều trích nguyên title vào dấu nháy — nên tài liệu đúng **luôn** được
chèn lên đầu, bất kể embedding tốt hay xấu. Hệ quả ở phase 2: corruption làm hỏng
`text_for_embedding` sẽ **không** kéo `retrieval_hit_rate` xuống, và nhóm dễ kết luận nhầm là
"corruption không ảnh hưởng retrieval". Cần ít nhất vài câu hỏi **không** chứa nguyên văn title
để metric này có ý nghĩa.

**BLOCKER 4 — judge metrics chưa dùng được. (chặn việc kết luận, không chặn pipeline)**

Chưa có API key nên `_judge_answer` chạy heuristic fallback; `judge_accuracy=0.0667` và
`mean_judge_score=1.20` chỉ phản ánh token overlap chứ không phải đánh giá của LLM. Kiểm bằng
cách tìm chuỗi `"Fallback heuristic judge"` trong `data/results/baseline_answers.json`.
Agent demo cũng bị bỏ qua vì lý do này.

**BLOCKER 5 — `categories_joined` mơ hồ (đã nêu ở CP1, nay có bằng chứng end-to-end).**

Ground truth của câu hỏi categories là `['posted-content']` — 7 paper dùng chung. Kể cả sửa
xong Blocker 1 và 2 thì loại câu hỏi này vẫn không phân biệt được paper.

### Chốt lại

Ba điều kiện pass của CP2 (`test_set.json` + embedding manifest + collection baseline tồn tại;
search, lookup, agent trả kết quả có nguồn) đã **đạt về mặt artifact**, nhưng **agent chưa chạy
được** vì thiếu key, và **evaluation chưa cho số liệu tin được** vì Blocker 1–2.

Không chuyển sang phase 2 trước khi xử lý xong Blocker 1, 2 và 4 — chạy corruption trên baseline
sai thì bảng so sánh ở mục 10 của report không chứng minh được điều gì.

## 2e. Checkpoint 3 — kết quả Role 1 (Lê Quang Huy)

> Cảnh báo của BTC ở mốc này: *"Baseline chỉ hoàn tất khi artifacts, metrics và report khớp
> nhau — không phải chỉ khi script exit code 0."*

### (1) `phase1.py` theo đúng luồng

Đã implement từ CP1, thứ tự: raw → clean → **contract gate** → index → test set → evaluate →
quality/freshness → report → demo.

### (2) Chạy baseline end-to-end

Chạy được hết 8 bước, exit code 0. Metrics và 5 blocker đã ghi ở [mục 2d](#2d-checkpoint-2--kết-quả-role-1-lê-quang-huy).
Agent demo vẫn bị bỏ qua vì thiếu API key (`GOOGLE_API_KEY is required when LLM_PROVIDER=gemini`).

### (3) Kiểm artifact — không tin terminal

Viết [`script/verify_baseline.py`](script/verify_baseline.py): đọc lại từng file đã ghi và đối
chiếu chéo, **không dùng số nào do pipeline tự báo**. Chạy:

```bash
uv run python script/verify_baseline.py
```

32 check, chia 8 nhóm: artifact tồn tại và đọc được · contract còn pass trên file đã ghi ·
count khớp giữa các tầng (clean CSV ↔ clean JSON ↔ manifest ↔ Chroma) · `ground_truth_doc_ids`
tồn tại thật · metrics tính lại từ answers có khớp file metrics · judge có gọi LLM thật không ·
freshness phản ánh dữ liệu thật · report chứa đúng số.

**Kết quả: 29/32 pass, 3 fail.**

Những gì audit xác nhận đúng: 24 raw → 24 clean → 24 manifest documents → 24 Chroma documents,
collection đúng `papers-baseline`, model đúng MiniLM, 0/30 câu hỏi trỏ tới `paper_id` không tồn
tại, và cả 4 metric tính lại từ `baseline_answers.json` đều khớp `baseline_metrics.json`.

#### Hai lỗi audit bắt được là của chính Role 1 — đã sửa

- `phase1.py` truyền `raw_records` nhưng `generate_phase1_report` đọc key `total_records`, nên
  mục Source Summary của report in `N/A`. Đã sửa ở phía caller.
- Bản audit đầu tiên báo nhầm `retrieval_hit_rate` "không có trong report", vì report in dạng
  phần trăm `100.00%` còn metrics lưu `1.0`. Lỗi của script audit, đã sửa để đối chiếu cả hai dạng.

#### BLOCKER 6 — `build_freshness_report` đọc sai tên cột (chặn)

`src/observability/quality.py` đọc `df["published_date"]`, nhưng cột trong clean contract tên là
**`published`**. Cột đó không tồn tại nên hàm luôn rơi vào nhánh `latest, oldest = None, None`.

**Bằng chứng:** `data/quality/freshness_report.json` ghi `latest_published: null`,
`oldest_published: null` trong khi 24/24 dòng có `published` hợp lệ. Report cũng in
`**Latest Published:** None`.

#### BLOCKER 7 — ngưỡng freshness hard-code 365, không đọc `Settings` (chặn)

Cùng hàm đó dùng `df["age_days"].gt(365)`, trong khi `settings.freshness_threshold_days = 180`.
Và `is_fresh` được định nghĩa là "stale < 50% tổng số dòng".

**Bằng chứng — mô phỏng đúng kịch bản corruption của phase 2:**

| Tình huống | `stale_rows` báo về | Đúng phải là | `is_fresh` |
| :-- | :-: | :-: | :-: |
| Làm cả 24 dòng cũ đi 200 ngày (vượt ngưỡng 180) | **0** | 24 | **True** (sai) |
| 11/24 dòng cũ 400 ngày | 11 | 11 | **True** (sai) |

Đây là lỗi nguy hiểm nhất tới giờ, vì nó **im lặng**: corruption "làm cũ dữ liệu" là một trong
sáu kịch bản bắt buộc của phase 2, mà freshness check sẽ báo `is_fresh: true` như không có gì
xảy ra. Nhóm sẽ kết luận "corruption không bị phát hiện" trong khi thực ra là **checker hỏng**,
không phải pipeline không phát hiện được.

#### BLOCKER 4 (nhắc lại) — judge vẫn 30/30 dùng heuristic fallback

Audit xác nhận lại bằng cách đếm chuỗi `"Fallback heuristic"` trong `baseline_answers.json`.

### Chốt lại

Baseline **chưa hoàn tất** theo tiêu chí của BTC: artifact đầy đủ và nhất quán, nhưng report
không khớp dữ liệu thật ở mục Freshness, và judge metrics chưa có giá trị bằng chứng.

Thứ tự xử lý đề xuất trước khi sang phase 2:

1. **R4** sửa Blocker 6 + 7 (`published_date` → `published`; dùng `settings.freshness_threshold_days`
   thay 365; xem lại định nghĩa `is_fresh`). Không sửa cái này thì phase 2 không đo được gì.
2. **R4 + R3** chốt cách xử lý Blocker 1 (ngôn ngữ test set) và Blocker 2 (`ground_truth` dạng list).
3. **R1** điền API key, chạy lại `run_phase1.py` rồi `verify_baseline.py` cho tới khi 32/32 pass.

## 2f. Checkpoint 4 — baseline checklist trước giờ nghỉ (Role 1)

Mốc này là **nghỉ 15 phút**. Việc của Role 1: chốt checklist baseline và blocker còn lại để
quay lại làm phase 2 ngay, không phải dò lại từ đầu.

### Baseline checklist — trạng thái tại giờ nghỉ

Chạy lại `uv run python script/verify_baseline.py` sau khi rebase: **29/32 pass**.

| # | Hạng mục | Trạng thái |
| :-: | :-- | :-- |
| 1 | 10 artifact bắt buộc tồn tại và đọc được | ✅ |
| 2 | Clean contract còn pass trên file đã ghi | ✅ 0 blocker |
| 3 | Count khớp xuyên tầng: 24 raw → 24 clean → 24 manifest → 24 Chroma | ✅ |
| 4 | Collection `papers-baseline`, model MiniLM khớp `Settings` | ✅ |
| 5 | 3 trạng thái dùng collection và path riêng | ✅ chưa ghi đè gì |
| 6 | 30/30 `ground_truth_doc_ids` tồn tại trong clean data | ✅ |
| 7 | 4 metric tính lại từ answers khớp file metrics | ✅ |
| 8 | Report chứa đúng số của metrics, Source Summary có số thật | ✅ |
| 9 | Freshness phản ánh dữ liệu thật | ❌ `latest/oldest_published: null` |
| 10 | Judge gọi LLM thật | ❌ 30/30 heuristic fallback |
| 11 | Agent demo chạy được | ❌ thiếu API key |
| 12 | `retrieval_hit_rate` đo được chất lượng retrieval | ❌ bão hoà 1.00 |

### Blocker còn lại — ưu tiên số 1 khi quay lại

**Ngưỡng freshness hard-code 365 (Blocker 7).** Sau rebase kiểm lại: chưa sửa, và tệ hơn dự
đoán ban đầu — `df["age_days"].gt(365)` xuất hiện ở **cả hai** hàm trong
`src/observability/quality.py`: `run_data_quality_checks` (dòng 27) và `build_freshness_report`
(dòng 58). `settings.freshness_threshold_days` là **180**.

Chọn đây làm blocker số 1 vì phase 2 sẽ bắt đầu bằng corruption, mà "làm cũ dữ liệu" là một
trong sáu kịch bản bắt buộc. Với ngưỡng 365, làm 24 dòng cũ đi 200 ngày vẫn cho `stale_rows: 0`
và `is_fresh: true` ở **cả hai** report. Nhóm sẽ ghi vào báo cáo "corruption không bị phát hiện"
trong khi thực tế là checker hỏng.

Việc quay lại làm ngay, theo thứ tự:

1. **R4** — `published_date` → `published`; thay `365` bằng `settings.freshness_threshold_days`
   ở cả hai hàm; xem lại `is_fresh` (hiện là "stale < 50%", nên 11/24 dòng cũ 400 ngày vẫn báo fresh).
2. **R4 + R3** — chốt Blocker 1 (test set tiếng Việt vs router tiếng Anh trong `qa.py`) và
   Blocker 2 (`ground_truth` của authors/categories đang là list). Kiểm lại sau rebase:
   `ground_truth` của câu summary đã là `str`, nhưng câu hỏi vẫn tiếng Việt.
3. **R1** — điền API key, chạy lại `run_phase1.py` → `verify_baseline.py` tới khi 32/32 pass,
   **rồi mới** chạy corruption.

Ràng buộc không đổi khi sang phase 2: giữ nguyên `test_set.json`, `top_k`, evaluator; ba trạng
thái dùng ba collection riêng; repair chạy lại từ `data/raw/`, không sửa tay metrics.

## 2g. Checkpoint 5 — kết quả Role 1 (Lê Quang Huy)

> Cảnh báo BTC: *"Lỗi data phải có chủ đích, có log và đo được tác động; không tạo corruption
> chỉ để có file."*

### (1) Implement `corruption_flow.py`

[`src/pipelines/corruption_flow.py`](src/pipelines/corruption_flow.py) — 7 bước:

```
0. kiem baseline    -> BaselineMissing neu thieu artifact
1. corrupt          -> corrupted clean CSV/JSON + corruption_log.json
2. index + evaluate -> papers-corrupted, test set GOC
3. repair tu raw    -> contract gate, FAIL la dung han
4. index + evaluate -> papers-repaired, test set GOC
5. comparison report
6. kiem baseline nguyen ven -> BaselineMutated neu bi cham
```

Ba chốt chặn được cài sẵn:

- **Bước 0** — không có đủ baseline artifact thì raise `BaselineMissing`. So sánh chỉ có nghĩa
  khi baseline là mốc có thật.
- **Bước 3** — dữ liệu repaired phải qua `validate_clean_dataframe`. Không đạt thì raise, **không
  vá JSON kết quả** (đúng yêu cầu ý 3 của mốc này).
- **Bước 6** — chụp dấu vân tay baseline (kích thước `clean.json`, nội dung `baseline_metrics`,
  tên collection trong manifest, kích thước test set) trước khi chạy, đối chiếu lại sau khi
  chạy; lệch là raise `BaselineMutated`.

Repair đọc `data/raw/crossref_records.json`, **không fetch lại source** — fetch mới sẽ đổi tập
record và làm bảng so sánh mất công bằng.

### (2) Kiểm path/collection riêng — đã chạy thật

`corrupt_clean_dataframe` của R2 còn là TODO nên chưa chạy được bằng dữ liệu thật. Để kiểm
orchestration, Role 1 chạy thử flow với **stub corruption tạm trong scratchpad** (drop 3 record
mới nhất, blank 2 summary, làm cũ 4 dòng, thêm 2 duplicate). Stub **không commit** và toàn bộ
artifact do nó sinh ra **đã xoá sạch** sau khi kiểm — repo hiện chỉ còn artifact baseline thật.

Kết quả kiểm:

| Kiểm | Kết quả |
| :-- | :-- |
| `baseline_metrics.json` sau khi chạy | giống hệt trước khi chạy |
| Chroma sau khi chạy | `papers-baseline` 24 · `papers-corrupted` 23 · `papers-repaired` 24 |
| clean / embeddings / metrics / answers | đủ 3 bản riêng biệt, không ghi đè |
| quality + freshness | file riêng cho từng trạng thái |
| Contract gate ở bước repair | PASS, 24 record khôi phục đủ |

Flow chạy thông cả 7 bước và tạo ra đúng chuỗi nhân quả mà bài lab cần:

| metric | baseline | corrupted | repaired |
| :-- | --: | --: | --: |
| `retrieval_hit_rate` | 1.0000 | **0.8000** | 1.0000 |
| `mean_token_f1` | 0.1357 | **0.1202** | 0.1357 |

Repaired khớp baseline tuyệt đối — đúng như kỳ vọng, vì cả hai cùng dẫn xuất từ một
`data/raw/` không đổi.

### (3) Blocker mới phát hiện khi chạy thử

**BLOCKER 8 — `summary_nulls` không đếm chuỗi rỗng. (chặn)**

Stub blank 2 summary thành `""`, nhưng `data/quality/corrupted.json` báo `summary_nulls: 0`.
Nguyên nhân: `run_data_quality_checks` dùng `df["summary"].isnull()`, mà chuỗi rỗng **không
phải** null trong pandas.

"Summary rỗng" là một trong sáu kịch bản corruption bắt buộc. Với check hiện tại, kịch bản đó
chạy xong mà quality report vẫn báo 0 — nhóm không chứng minh được là pipeline **phát hiện**
được lỗi. Cần đếm cả `.fillna("").str.strip() == ""`.

**Blocker 7 nặng hơn ước tính.** Stub cố tình làm cũ 4 dòng lên **400 ngày** thì mới bị bắt
(`stale_rows: 4`), vì ngưỡng hard-code là 365. Nếu R2 làm cũ theo ngưỡng thật của lab (180 ngày,
ví dụ 200–300 ngày) thì `stale_rows` sẽ là **0** và corruption "làm cũ dữ liệu" hoàn toàn tàng
hình. Ngoài ra `freshness_corrupted.json` vẫn ghi `is_fresh: true` dù có 4 dòng stale và 2
`paper_id` trùng — vì `is_fresh` định nghĩa là "stale < 50% số dòng".

### Việc còn lại của mốc này

- **R2** — implement `corrupt_clean_dataframe`, log đủ `type`, `paper_ids`, tham số và
  before/after count cho từng kịch bản.
- **R4** — Blocker 6, 7, 8 đều nằm trong `src/observability/quality.py`. Không sửa thì corruption
  chạy xong vẫn không có signal nào đổi, và mục 10 của report không kết luận được gì.
- **R1** — sau khi R2 xong: chạy `run_corruption_flow.py` thật, rồi `verify_baseline.py` để chắc
  baseline chưa bị đụng.

## 2h. Bảng blocker — thuộc checkpoint nào, đã xử lý chưa

Ánh xạ theo đúng việc ghi trong file phân công của BTC. Cột "Việc gốc" trích nguyên văn.

| # | Blocker | Của | CP gốc | Việc gốc | Đáng lẽ bị bắt ở | Trạng thái |
| :-: | :-- | :-: | :-: | :-- | :-: | :-- |
| 1 | Test set tiếng Việt không khớp router tiếng Anh trong `qa.py` | R3/R4 | CP2 | *"Implement `build_test_set` với id, type, question, ground_truth…"* | CP3 | ✅ đã sửa |
| 2 | `ground_truth` authors/categories là repr của list | R4 | CP2 | như trên | CP3 | ✅ đã sửa |
| 3 | `retrieval_hit_rate` bão hoà 1.00 | R4 | CP2 | *"Tạo question từ cleaned data"* | CP3 | ⚠️ còn |
| 4 | Judge 40/40 dùng heuristic fallback | R4 | CP5 | *"Kiểm tra evaluator không silently fallback thành success giả"* | CP5 | ⚠️ cần API key |
| 5 | `categories_joined` mơ hồ (7 paper chung giá trị) | R2/R4 | CP1 | *"chốt rule null, date, duplicate, authors/categories"* | CP1 | ⚠️ còn |
| 6 | Freshness đọc `published_date`, cột thật là `published` | R4 | CP1 | *"Tạo freshness input từ published/age_days…"* | CP3 | ✅ đã sửa |
| 7 | Ngưỡng stale hard-code 365 thay vì `Settings` | R4 | CP1 | như trên | CP3 | ✅ đã sửa |
| 8 | `summary_nulls` không đếm chuỗi rỗng | R4 | CP1 | *"Implement check row count, paper_id unique, title/summary missing…"* | CP5 | ✅ đã sửa |

**CP3 là chỗ lẽ ra phải chặn lại.** Việc số 2 của `observe` ở CP3 ghi rõ: *"Đối chiếu report với
JSON/CSV thật trước khi coi baseline hoàn tất."* Đối chiếu là thấy ngay `latest_published: null`
trong khi CSV có đủ 24 ngày hợp lệ. Bước đó bị bỏ qua nên Blocker 6 và 7 trôi tới CP5.

### Đã xử lý — 5 blocker quá hạn từ CP1–CP2

Đây là việc **đã quá hạn**, không phải việc CP5 của người khác. Phần CP5 của R2
(`corrupt_clean_dataframe`) và của R4 (chạy quality/report cho corrupted) giữ nguyên.

| File | Sửa gì |
| :-- | :-- |
| `src/observability/quality.py` | `published_date` → `published`; ngưỡng stale đọc `settings.freshness_threshold_days`; `_missing()` đếm cả null lẫn chuỗi rỗng; `is_fresh` đổi từ "stale < 50%" thành "stale == 0" |
| `src/evaluation/testset.py` | dùng `authors_joined` / `categories_joined` / `published` thay cho cột list và cột `published_date` không tồn tại |
| `src/retrieval/qa.py` | router nhận thêm cụm tiếng Việt (tác giả / xuất bản / lĩnh vực…), **cộng thêm**, giữ nguyên toàn bộ cụm tiếng Anh cũ |
| `src/ingestion/lineage.py` | `_semantically_equal` chấp nhận thêm dạng joined — xem ghi chú dưới |

Thay đổi ở `testset.py` làm gãy test `test_baseline_lineage_and_testset_are_traceable` của R2.
Nguyên nhân: `_as_list` tách chuỗi joined theo dấu phẩy, nhưng một category có thể **tự nó chứa
dấu phẩy** — `"Innovative economy: information, analytics, forecasts"` bị tách thành 3 phần rồi
so lệch với list 1 phần tử. Đã sửa tối thiểu: so thêm dạng joined trước khi kết luận lệch.
Toàn bộ 10 test pass. Đây là sửa hệ quả từ thay đổi của Role 1, không phải làm phần CP5 của R2.

Phát hiện phụ khi sửa: `testset.py` đọc `row.get("published_date")` — cột không tồn tại nên trả
chuỗi rỗng, và **toàn bộ `question_type=date` bị bỏ qua**. Đó là lý do test set cũ chỉ có 3 loại
câu hỏi thay vì 4 như thiết kế.

#### Kết quả sau khi sửa

| Metric | Trước | Sau |
| :-- | --: | --: |
| Số câu hỏi | 30 (3 loại) | **40 (4 loại)** |
| `mean_token_f1` | 0.1357 | **0.8475** |
| `judge_accuracy` | 0.0667 | **0.8000** |
| `mean_judge_score` | 1.20 | **4.15** |
| `verify_baseline.py` | 29/32 | **32/33** |

Tách theo loại câu hỏi: authors, categories, date đều đạt `token_f1 = 1.000`. Riêng summary giữ
0.390 — đây **không phải lỗi**: `qa.py` trả về `first_sentence(summary)` còn ground truth là cả
abstract, nên trùng một phần là đúng thiết kế.

Kiểm lại đúng ba kịch bản đã dùng làm bằng chứng ở CP4 và CP5:

| Kịch bản | Trước | Sau |
| :-- | :-- | :-- |
| 24 dòng cũ 200 ngày (vượt ngưỡng 180) | `stale_rows=0`, `is_fresh=true` | `stale_rows=24`, `is_fresh=false` |
| 11/24 dòng cũ 400 ngày | `stale_rows=11`, `is_fresh=true` | `stale_rows=11`, `is_fresh=false` |
| Blank 2 summary thành `""` | `summary_nulls=0` | `summary_nulls=2` |

#### Còn lại

- **Blocker 4** — cần API key thật, Role 1 không tự điền được vào `.env` của người khác.
- **Blocker 3** — `retrieval_hit_rate` vẫn 1.00. Sửa được nhưng phải thêm câu hỏi **không trích
  nguyên title**, tức là đổi test set. Để R4 quyết, và phải chốt **trước** khi chạy corruption
  vì test set phải cố định cho cả ba trạng thái.
- **Blocker 5** — categories mơ hồ, cần R2 và R4 thống nhất nguồn thay `subject`.

## 2i. Checkpoint 6 — kết quả Role 1 (Lê Quang Huy)

> Cảnh báo BTC: *"Ưu tiên evidence: report phải khớp artifact thật, không tô đẹp số liệu để demo."*

### (1) Điều phối repair/comparison, freeze scope, chia phần demo

`corruption_flow.py` đã sẵn từ CP5. **Scope freeze:** không thêm tính năng mới, chỉ còn đóng
blocker và chạy lại. Phần demo chia theo đúng vai: R2 trình diff clean/corrupted/repaired,
R3 trình 3 collection tách biệt, R4 trình bảng comparison và giới hạn kết luận, R1 dựng trang
demo và chạy checklist cuối.

### (2) Checklist cuối

| Kiểm | Kết quả |
| :-- | :-- |
| `.env` có bị track không | ✅ không, `git ls-files` sạch |
| Secret trong file đã track (`sk-`, `AIza`, `ghp_`, `sk-ant-`) | ✅ không có |
| Hard-code path trong `src/` và `script/` | ✅ không có |
| Path tuyệt đối lọt vào artifact JSON | ❌ **có** — xem dưới |
| Test suite | ✅ 10/10 pass |
| `verify_baseline.py` | ✅ 32/33 (còn đúng blocker API key) |

**BLOCKER 9 — `persist_path` tuyệt đối trong `papers_embeddings.json`. (đã sửa)**

Manifest được commit lên Git nhưng ghi `"persist_path": "D:\\VinUni\\Lab10\\..."` — đường dẫn
của đúng một máy. `LocalEmbeddingIndex.load()` đọc thẳng giá trị này, nên trên máy người khác nó
trỏ vào thư mục không tồn tại. Đây chính là mục *"no hard-code path"* của checklist CP6.

Sửa trong `src/retrieval/index.py`: `build()` ghi path **tương đối** so với project
(`data/chroma`), `load()` chỉ dùng path trong manifest khi nó thực sự tồn tại, còn lại lấy từ
`Settings` — nên manifest cũ vẫn đọc được, không phá bản của ai.

### (3) Chỉ công bố recovery khi số liệu chứng minh

Chưa công bố. `corrupt_clean_dataframe` của R2 vẫn là TODO nên **chưa có artifact
corrupted/repaired thật**. `data/results/` hiện chỉ có baseline.

Đã chạy thử flow bằng stub corruption của Role 1 (drop 3 record mới nhất, blank 2 summary, chèn
noise 2 dòng, cắt title 2 dòng, làm cũ 4 dòng lên 483 ngày, thêm 2 duplicate) để kiểm demo và
orchestration. Kết quả stub:

| metric | baseline | corrupted | repaired |
| :-- | --: | --: | --: |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 |
| `mean_token_f1` | 0.8475 | 0.6279 | 0.8475 |
| `judge_accuracy` | 0.8000 | 0.5750 | 0.8000 |
| `mean_judge_score` | 4.1500 | 3.3000 | 4.1500 |

**Toàn bộ 17 artifact do stub sinh ra đã xoá**, 2 collection tạm đã drop, repo chỉ còn artifact
baseline thật. Số trong bảng trên **không được đưa vào `report/group_report.md`** — đó là số của
stub, không phải corruption thật của R2.

### Trang demo

[`script/build_demo.py`](script/build_demo.py) sinh `data/reports/demo.html` — một file HTML tự
chứa, đọc thẳng từ `data/clean/`, `data/results/`, `data/quality/`. Bốn phần:

1. **Chất lượng trả lời** — 4 metric, mỗi thẻ hiện baseline, delta khi corrupted, và có khôi phục
   được không.
2. **Dòng nào hỏng, hỏng ở đâu** — diff theo từng `paper_id` và từng trường: giá trị gốc gạch
   ngang, giá trị sau corruption tô màu. Bản chạy thử cho 13/24 dòng bị tác động.
3. **Corruption log** — đọc từ `corruption_log.json` để đối chiếu với bảng diff.
4. **Tín hiệu data quality** — baseline / corrupted / repaired cạnh nhau.

Thiếu artifact nào thì trang ghi rõ là thiếu kèm lệnh cần chạy, **không bịa số**. Chạy lại sau
khi R2 xong là ra bản thật:

```bash
uv run python script/run_corruption_flow.py && uv run python script/build_demo.py
```

### Quy tắc sở hữu file — đọc kỹ

**Chỉ R1 được sửa `src/core/config.py` và `src/pipelines/`.** Ba role còn lại implement
hàm trong thư mục của mình theo đúng contract `Settings`/`Paths` mà R1 chốt; nếu cần thêm
config thì báo R1, không tự thêm field.

**Không ai sửa file trong `data/` do người khác sinh ra.** `data/raw/` là nguồn duy nhất để
repair — R2 phải giữ nguyên raw response sau khi lưu, kể cả khi corruption flow chạy hỏng.

R4 đo metric trên artifact do R2 và R3 sinh ra, nên **không được sửa clean data hay index**
để "cho số đẹp". Nếu số liệu sai, báo đúng người sở hữu.

## 3. Quy trình Git

**Không ai commit thẳng vào `main`** — mọi thay đổi vào `main` phải đi qua Pull Request và
được R1 review.

| Branch | Người dùng |
| :-- | :-- |
| `role1-pipeline-orchestration` | Lê Quang Huy |
| `role2-data-foundation` | Nguyễn Chí Hướng |
| `role3-rag-agent` | Phạm Thị Liên |
| `role4-eval-observability` | Nguyễn Tiến Đạt |

**Tạo/lấy branch của mình (lần đầu):**

```bash
git fetch origin && git checkout -b role2-data-foundation origin/main
```

*(đổi tên branch theo bảng trên)*

**Trong lúc làm — lấy code mới nhất từ main vào branch của mình:**

```bash
git pull origin main
```

**Làm xong — đẩy lên branch của mình:**

```bash
git add . && git commit -m "Role X: mo ta ngan" && git push -u origin HEAD
```

**Mở Pull Request:**

```bash
gh pr create --base main --title "Role 2: Crossref ingestion + clean schema" --body "Doi gi va vi sao"
```

**R1 review và merge:**

```bash
gh pr merge <so PR> --merge --delete-branch=false
```

Giữ branch lại vì mỗi người còn dùng tiếp cho phase 2.

### Thứ tự merge bắt buộc

Pipeline là chuỗi phụ thuộc `raw → clean → index → evaluate → report`, nên merge theo đúng
thứ tự đó:

1. PR của **R2** (`src/ingestion/crossref.py`, `cleaning.py`) merge trước — không có clean
   data thì R3 không index được.
2. PR của **R3** (`src/retrieval/`) merge tiếp.
3. PR của **R4** (`src/evaluation/`, `src/observability/`) merge sau cùng — test set phải
   trỏ tới `paper_id` có thật trong clean data đã merge.
4. **R1** `git pull origin main` rồi chạy `script/run_phase1.py` end-to-end. Chỉ khi
   baseline xanh mới mở phase 2 (corruption/repair).

### Xử lý conflict

Bảng sở hữu ở mục 2 được thiết kế để **không có conflict**. Nếu vẫn conflict, nghĩa là ai đó
đã sửa file không thuộc phần mình — dừng lại, hỏi trong nhóm, đừng tự resolve. File hay bị
đụng nhất là `data/reports/*.md` vì cả nhóm cùng viết; quy ước: mỗi người chỉ sửa đúng mục
của mình, pull `main` ngay trước khi viết.

## 4. Không commit

`.env`, API key dưới mọi dạng, `.venv/`, `__pycache__/`, ChromaDB store và các artifact
nặng trong `data/` mà `.gitignore` đã loại.
Kiểm tra bằng `git status` trước mỗi lần commit.
