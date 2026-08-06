# DANH SÁCH THÀNH VIÊN NHÓM

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
