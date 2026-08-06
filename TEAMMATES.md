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
