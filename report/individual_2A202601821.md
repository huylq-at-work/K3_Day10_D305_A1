# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Lê Quang Huy |
| MSSV               | 2A202601821 |
| Khóa/Lớp         | K3 |
| Tên nhóm         | Fathom |
| Vai trò chính    | Điều phối pipeline (cấu hình, orchestration, release, demo) |
| Repository         | https://github.com/huylq-at-work/K3_Day10_D305_A1.git |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| ------------------ | --------------------- | ---------------- | ----------------- | ------------ |
| Clean data contract | `src/core/contract.py` — `validate_clean_dataframe`, `CLEAN_COLUMNS` | Clean dataframe của R2 | `data/quality/clean_contract.json`; raise khi vi phạm | Hoàn thành |
| Baseline orchestration | `src/pipelines/phase1.py` — `main`, `enforce_clean_contract`, `resolve_records` | Toàn bộ module của R2/R3/R4 | `phase1_report.md`, `baseline_metrics.json` | Hoàn thành |
| Corruption/repair orchestration | `src/pipelines/corruption_flow.py` — `main`, `require_baseline`, `assert_baseline_intact`, `repair_from_raw` | Clean baseline + `data/raw/` | `corrupted_metrics.json`, `repaired_metrics.json`, `corruption_report.md` | Hoàn thành |
| Cấu hình & provider | `src/core/config.py` — `resolve_llm`, `has_llm_credentials`; `.env.example` | Biến môi trường | `Settings` dùng chung cho cả nhóm | Hoàn thành |
| Audit artifact | `script/verify_baseline.py` | Toàn bộ artifact trong `data/` | 33 check, exit code 1 nếu fail | Hoàn thành |
| Trang demo | `script/build_demo.py` | Artifact 3 trạng thái | `data/reports/demo.html` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| ------------ | ------------------------------ | --------- |
| Lấy sample raw payload từ Crossref và ghi chú 4 điểm dễ vấp | Nguyễn Chí Hướng (`src/ingestion/`) | Gói zip kèm ghi chú: `subject` rỗng 24/24, abstract là XML JATS, `date-parts` có 2 hoặc 3 phần tử, `pdf_url` thiếu 15/24 |
| Sửa 5 blocker quá hạn từ CP1–CP2 | R3 (`qa.py`), R4 (`quality.py`, `testset.py`) | `mean_token_f1` 0.1357 → 0.8475; chi tiết ở mục 6 |
| Sửa hệ quả test lineage gãy sau thay đổi của mình | Nguyễn Chí Hướng (`src/ingestion/lineage.py`) | Test suite trở lại xanh (nay 14/14) |
| Dựng branch, thứ tự merge, bảng sở hữu file | Cả nhóm | `TEAMMATES.md` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --------------------------- | ----------------------------- | ------------------ | --------------- |
| Chốt clean contract 16 cột, 8 điều kiện dừng | `src/core/contract.py` | `data/quality/clean_contract.json` | Chạy trên data thật: PASS, 0 blocker, 1 warning |
| Gate chặn index/test set khi clean data hỏng | `phase1.py::enforce_clean_contract` | `ContractViolation` | Thử với data hỏng mô phỏng: bắt đủ 4 blocker và dừng |
| Ghép baseline 8 bước | `script/run_phase1.py` | 10 artifact trong `data/` | `verify_baseline.py` → 33/33 |
| Ghép corruption flow 7 bước | `script/run_corruption_flow.py` | 3 bộ metrics/answers/quality | Baseline nguyên vẹn sau khi chạy |
| Audit chéo artifact | `script/verify_baseline.py` | 33 check | Phát hiện 3 lỗi thật + 2 lỗi của chính mình |
| Trang demo | `script/build_demo.py` | `data/reports/demo.html` | 13/24 dòng bị tác động hiển thị đúng |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

`script/verify_baseline.py` là output tôi thấy có giá trị nhất. Nó đọc lại từng file đã ghi và
đối chiếu chéo — **không dùng số nào do pipeline tự báo**. Nhờ nó mà nhóm phát hiện
`freshness_report.json` ghi `latest_published: null` trong khi CSV có đủ 24 ngày hợp lệ, dù
`run_phase1.py` vẫn exit code 0. Đúng cảnh báo của đề bài: baseline hoàn tất không phải là khi
script chạy xong.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Bốn người viết bốn module độc lập, bàn giao cho nhau qua file trên đĩa. Phần của tôi là làm sao
để (a) mỗi module biết chính xác phải nhận vào và trả ra cái gì, (b) pipeline **dừng đúng chỗ**
khi dữ liệu sai thay vì chạy tiếp và tạo ra artifact trông có vẻ hợp lệ, và (c) baseline không bị
corruption flow ghi đè — vì mất baseline là mất mốc so sánh, mà toàn bộ bài lab dựa trên so sánh.

### Cách triển khai

**Contract đặt ở `core/`, không đặt trong `ingestion/`.** Đây là quyết định có chủ ý. Nếu để
contract cùng chỗ với code cleaning thì người viết cleaning vừa viết code vừa tự định nghĩa tiêu
chí đúng/sai cho chính mình, và gate không còn độc lập. Tách ra thì R2 phải viết code thoả một
tiêu chí do người khác giữ.

Contract phân biệt **blocker** (chặn pipeline) và **warning** (ghi nhận, không chặn). 8 blocker
gồm: thiếu cột, dưới 5 dòng, null/rỗng ở 7 cột bắt buộc, `paper_id` trùng, `published` sai định
dạng ISO, còn `None` ở cột metadata Chroma, `summary` còn tag markup, `age_days` lệch `published`
hoặc âm.

**Ba chốt chặn trong `corruption_flow.py`:**

1. `require_baseline` — thiếu artifact baseline thì raise, vì so sánh với một mốc không tồn tại
   là vô nghĩa.
2. Contract gate ở bước repair — dữ liệu repaired không đạt contract thì dừng hẳn, **không vá
   JSON kết quả**.
3. `assert_baseline_intact` — chụp dấu vân tay baseline (kích thước `clean.json`, nội dung
   `baseline_metrics`, tên collection, kích thước test set) trước khi chạy, đối chiếu sau khi
   chạy. Lệch là raise `BaselineMutated`.

**Fallback provider.** `resolve_llm` trả về **cả provider lẫn model**. Lúc đầu tôi chỉ fallback
provider, nhưng test thì thấy chuyển từ Gemini sang OpenAI mà vẫn gửi `LLM_MODEL=gemini-2.5-flash`
thì OpenAI báo model không tồn tại. Fallback in cảnh báo một lần, không im lặng — vì
`judge_accuracy` chấm bởi hai model khác nhau là hai con số không so sánh được.

### Input, output và contract

| Thành phần | Mô tả |
| ------------ | ------- |
| Input | `list[PaperRecord]` từ `data/raw/`; clean dataframe 16 cột từ R2; index của R3; test set của R4 |
| Output | `Settings`/`Paths` dùng chung; `clean_contract.json`; `phase1_report.md`; `corruption_report.md`; 3 bộ metrics |
| Module phụ thuộc | `ingestion.crossref`, `ingestion.cleaning`, `ingestion.corruption`, `retrieval.index`, `evaluation.*`, `observability.*` |
| Module sử dụng output | Tất cả — mọi module đọc path từ `Paths`, không tự đặt tên file |
| Điều kiện lỗi cần xử lý | Thiếu artifact baseline; clean data vi phạm contract; repaired data vi phạm contract; baseline bị ghi đè; thiếu API key |

### Cách xác minh

```bash
uv run python script/run_phase1.py
uv run python script/verify_baseline.py
uv run python script/run_corruption_flow.py
uv run python script/build_demo.py
```

- **Kết quả mong đợi:** baseline tạo đủ 10 artifact và audit pass; corruption flow tạo 3 bộ
  metrics mà không đụng baseline.
- **Kết quả thực tế:** đúng như vậy. Sau khi nạp API key và chạy lại cả ba trạng thái, audit đạt
  **33/33**, 0/40 câu dùng heuristic fallback ở mỗi trạng thái, agent demo chạy được. `pytest` 14/14 pass.
- **Artifact/log:** `data/quality/clean_contract.json`, `data/results/*_metrics.json`,
  `data/reports/`. Không chứa secret.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi ghép `phase1.py`, phải chọn xem pipeline nên làm gì khi clean data không đạt
  contract.
- **Các phương án đã cân nhắc:**
  1. Ghi cảnh báo rồi chạy tiếp, để bước sau tự xử lý.
  2. Dừng hẳn bằng exception, không index và không sinh test set.
  3. Tự động sửa dữ liệu cho hợp lệ rồi chạy tiếp.
- **Phương án đã chọn:** Phương án 2.
- **Lý do:** Phương án 1 nguy hiểm nhất vì pipeline vẫn "chạy xong", sinh ra
  `baseline_metrics.json` trông bình thường, và không ai biết mốc so sánh đã hỏng — sang phase 2
  thì cả bảng baseline/corrupted/repaired mất giá trị mà vẫn có vẻ hợp lệ. Phương án 3 còn tệ hơn:
  nó che mất đúng thứ bài lab yêu cầu phải phát hiện được. Phương án 2 đánh đổi sự tiện lợi lấy
  việc lỗi lộ ra ngay tại chỗ phát sinh.
- **Bằng chứng quyết định phù hợp:** Thử với dữ liệu hỏng mô phỏng (summary rỗng, `published` sai
  định dạng, sót tag markup, `paper_id` trùng), gate bắt đủ 4 blocker và dừng trước bước index.
  Cùng nguyên tắc áp cho bước repair trong `corruption_flow.py`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Baseline chạy xong, exit code 0, nhưng
  `mean_token_f1: 0.1357`, `judge_accuracy: 0.0667`. Tách theo loại câu hỏi thì `token_f1` của
  authors đúng bằng **0.000** trong khi `retrieval_hit_rate` là 1.000 — retrieval hoàn hảo mà trả
  lời sai hết.
- **Lệnh hoặc bước tái hiện:** `uv run python script/run_phase1.py`, rồi nhóm
  `data/results/baseline_answers.json` theo `question_type`.
- **Nguyên nhân gốc:** Ba lỗi chồng nhau ở ranh giới module.
  1. `retrieval/qa.py::_extract_answer` chọn field trả lời bằng cách dò cụm tiếng Anh
     (`"who authored"`, `"when was"`, `"what categories"`), trong khi `testset.py` sinh câu hỏi
     tiếng Việt — không nhánh nào khớp nên **mọi câu rơi về nhánh mặc định**
     `first_sentence(summary)`. Hỏi tác giả nhưng trả về abstract, nên F1 bằng 0.
  2. `testset.py` lấy ground truth từ cột list `authors`/`categories` thay vì cột đã join, nên
     `_token_f1` đếm cả dấu ngoặc vuông và dấu nháy.
  3. `testset.py` đọc `row.get("published_date")` — cột không tồn tại (tên đúng là `published`)
     — nên trả chuỗi rỗng và **toàn bộ loại câu hỏi `date` bị bỏ qua**; test set chỉ có 3 loại
     thay vì 4.
- **Cách xử lý:** Router trong `qa.py` nhận thêm cụm tiếng Việt theo hướng **cộng thêm**, giữ
  nguyên toàn bộ cụm tiếng Anh để không phá thứ đang chạy; `testset.py` chuyển sang
  `authors_joined` / `categories_joined` / `published`.
- **Cách xác minh sau khi sửa:** `REFRESH_TEST_SET=1 uv run python script/run_phase1.py` rồi
  `uv run python script/verify_baseline.py`. Test set 30 → 40 câu (đủ 4 loại),
  `mean_token_f1` 0.1357 → 0.8475, `judge_accuracy` 0.0667 → 0.8000, audit 29/32 → 32/33.
  Sau đó `pytest tests/` phát hiện một test lineage gãy do thay đổi này: `_as_list` tách chuỗi
  joined theo dấu phẩy, mà `"Innovative economy: information, analytics, forecasts"` tự nó có dấu
  phẩy. Đã sửa tối thiểu trong `lineage.py`, test suite trở lại xanh.
- **Điều học được:** Hai chỉ số mâu thuẫn nhau là tín hiệu đáng tin hơn một chỉ số xấu.
  `retrieval_hit_rate = 1.000` cùng `token_f1 = 0.000` không thể cùng đúng — chính chỗ mâu thuẫn
  đó chỉ ra lỗi nằm ở bước sau retrieval. Nếu chỉ nhìn `mean_token_f1` tổng là 0.1357 thì rất dễ
  kết luận nhầm là "embedding kém" và đi sửa nhầm chỗ.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. **Crossref → vector index.** `fetch_source_records` gọi Crossref với query và filter trong
   `Settings`, **lưu raw response xuống đĩa trước khi parse** — bước này quan trọng vì
   `data/raw/` là nguồn duy nhất để repair sau này. Parse thành `PaperRecord`, rồi
   `build_clean_dataframe` normalize text, strip JATS, parse ngày, tính `age_days` và dựng
   `text_for_embedding`. Clean data qua contract rồi mới được MiniLM encode và nạp vào collection
   `papers-baseline` của Chroma.
2. **Test set và ground-truth doc ID.** Câu hỏi sinh từ chính clean data, mỗi câu ghi
   `ground_truth` (đáp án dạng chuỗi) và `ground_truth_doc_ids` (lấy từ `paper_id` có thật, không
   bịa). Khi chấm, `retrieval_hit` đúng khi tài liệu retrieve được nằm trong
   `ground_truth_doc_ids` — đo **retrieval**; còn `token_f1` so đáp án của agent với
   `ground_truth` — đo **chất lượng câu trả lời**. Hai chỉ số này tách bạch nên khi chúng lệch
   nhau ta biết lỗi nằm ở đâu.
3. **Quality checks khác freshness monitoring.** Quality check đo **tính đúng đắn về cấu trúc**
   tại một thời điểm: thiếu giá trị, trùng khoá, giá trị quá ngắn — sai là sai ngay. Freshness đo
   **quan hệ giữa dữ liệu và thời gian**: dữ liệu có thể hoàn toàn hợp lệ về cấu trúc nhưng đã cũ
   180 ngày và không còn phản ánh thực tế. Trong lab này thấy rõ: sau `old_published_date`, mọi
   quality check về null và duplicate vẫn xanh, chỉ freshness lật sang stale.
4. **Vì sao cùng một test set cho ba trạng thái.** Để chỉ còn **đúng một biến thay đổi** là chất
   lượng dữ liệu. Nếu đổi test set giữa các lần đo thì chênh lệch metric có thể chỉ do bộ câu hỏi
   mới dễ hoặc khó hơn, và không quy được về corruption. Cùng lý do đó, `top_k` và evaluator cũng
   phải giữ nguyên — `corruption_flow.py` luôn truyền `settings.paths.eval_testset`, không sinh
   lại.
5. **Repair thành công dựa trên gì.** Bốn metric và các tín hiệu quality ở cột repaired phải trở
   về đúng giá trị baseline, và dữ liệu repaired phải **đến từ `data/raw/`** chứ không phải vá
   trên bản hỏng. Trong lần chạy của nhóm: cả 4 metric trùng khít baseline, `paper_id` trùng
   2 → 0, summary rỗng 2 → 0, dòng quá hạn 4 → 0, freshness stale → fresh.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ----------------------- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | 8/40 câu mất tài liệu đúng. Nhưng chỉ số này **bão hoà**, xem phần dưới |
| `mean_token_f1` | 0.8475 | 0.6574 | 0.8475 | Chỉ số phản ánh trung thực nhất trong bộ này |
| `judge_accuracy` | 0.7750 | 0.6500 | 0.7750 | Do `gpt-4o-mini` chấm thật, 0/40 câu fallback |
| `mean_judge_score` | 4.3250 | 3.8250 | 4.3250 | như trên |
| Quality checks | 0 lỗi | dup 2, summary rỗng 2, stale 4 | 0 lỗi | Phát hiện đủ cả 3 loại |
| Freshness status | Fresh | Stale | Fresh | Chỉ lật được sau khi sửa ngưỡng, xem mục 6 |

### Kết luận từ số liệu

1. `missing_summary` xoá rỗng summary của 2 bài → `summary_nulls` 0 → 2 trong
   `data/quality/corrupted.json` → hai câu hỏi tương ứng có `token_f1` rơi từ 0.257 và 0.178
   xuống **0.000**, dù cả hai bài **vẫn được retrieve đúng**.
2. Repair clean lại từ `data/raw/` → `summary_nulls` về 0, `stale_rows` về 0, freshness về Fresh
   → cả 4 metric về đúng giá trị baseline, sai số bằng 0.

Corruption nào ảnh hưởng rõ nhất và vì sao?

Về độ lớn thì `drop_latest` mạnh nhất: xoá 3 bài mới nhất làm 8 câu hỏi mất hoàn toàn tài liệu
đúng và kéo `retrieval_hit_rate` từ 1.000 xuống 0.800. Nhưng theo tôi `missing_summary` mới là
kịch bản **đáng nói hơn**, vì nó cho thấy retrieval vẫn đúng mà câu trả lời vẫn rỗng — tức là
chất lượng nội dung ảnh hưởng trực tiếp tới người dùng cuối kể cả khi hệ thống tìm đúng tài liệu.
`drop_latest` chỉ chứng minh điều hiển nhiên là mất dữ liệu thì không trả lời được.

Kết quả nào khác với kỳ vọng ban đầu?

`noise_injection` chèn `__CORRUPTED_NOISE__` 12 lần vào 2 bài, tôi nghĩ nó sẽ đánh tụt thứ hạng
retrieval của hai bài đó. Thực tế cả hai **vẫn được retrieve đúng**. Giả thuyết của tôi là ở quy
mô 24 tài liệu, khoảng cách cosine giữa các bài đủ xa nên nhiễu chưa đủ đổi thứ tự; thêm nữa mọi
câu hỏi đều trích nguyên tiêu đề nên `answer_question` lookup chính xác và luôn chèn đúng bài lên
đầu. Tôi kiểm bằng cách xem `corrupted_answers.json` của hai `paper_id` đó — `retrieval_hit` vẫn
`true`. Vì vậy nhóm **không** kết luận corruption làm hỏng retrieval theo nghĩa ngữ nghĩa.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Pipeline chạy xong không có nghĩa là chạy đúng.** Baseline của nhóm exit code 0 ngay từ lần
   đầu, nhưng `mean_token_f1` chỉ 0.1357 và freshness report toàn `null`. Cái cứu được là viết
   `verify_baseline.py` đọc lại artifact và đối chiếu chéo thay vì tin dòng log cuối cùng.
2. **Checker hỏng nguy hiểm hơn checker không có.** `build_freshness_report` đọc sai tên cột và
   hard-code ngưỡng 365 thay vì 180. Nếu không phát hiện, kịch bản "làm cũ dữ liệu" sẽ chạy xong
   mà mọi tín hiệu vẫn xanh, và nhóm sẽ viết vào báo cáo "corruption không bị phát hiện" —
   một kết luận sai hoàn toàn về hệ thống. Tôi kiểm bằng cách mô phỏng: làm 24 dòng cũ 200 ngày,
   report vẫn báo `stale_rows: 0`, `is_fresh: true`.
3. **Metric có thể đúng số nhưng vô nghĩa.** `retrieval_hit_rate` của nhóm là 1.000 tuyệt đối,
   trông rất đẹp, nhưng chỉ vì mọi câu hỏi đều trích nguyên tiêu đề vào dấu nháy đơn và
   `answer_question` lookup chính xác — tài liệu đúng luôn được chèn lên đầu bất kể embedding tốt
   hay xấu. Một chỉ số không bao giờ giảm thì không đo được gì.

### Nếu có thêm thời gian

Sửa chính điểm 3: thêm khoảng 10 câu hỏi **không** chứa nguyên văn tiêu đề (hỏi theo chủ đề hoặc
theo tác giả), rồi đo lại `retrieval_hit_rate` trên cả ba trạng thái. Cách đo cải thiện: nếu chỉ
số này ở baseline tụt xuống dưới 1.000 và ở corrupted tụt sâu hơn baseline một cách rõ rệt, thì
lúc đó nó mới thật sự đo được chất lượng retrieval, và mới kết luận được về ảnh hưởng của
`noise_injection`. Phải làm **trước** khi chạy corruption vì test set bắt buộc cố định cho cả ba
trạng thái.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Lê Quang Huy
**Ngày xác nhận:** 2026-08-06
