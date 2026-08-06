# Member Role Report — Day 10: Data Pipeline & Data Observability

> Mỗi thành viên trong nhóm tự hoàn thành mẫu này để báo cáo đúng vai trò, phần việc và mức hiểu của mình. Không sao chép nguyên báo cáo chung hoặc báo cáo của thành viên khác. Thay nội dung trong dấu `[ ]` và xóa các dòng hướng dẫn không cần thiết trước khi nộp.

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Nguyễn Tiến Đạt             |
| MSSV               | 2A202601387                     |
| Khóa/Lớp         | K3              |
| Tên nhóm         | Fathom     |
| Vai trò chính    | Evaluation & observability                 |
| Repository         | https://github.com/huylq-at-work/K3_Day10_D305_A1.git |
| Ngày hoàn thành | 2026-08-06              |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Thiết kế Test Set | `src/evaluation/testset.py` (hàm `build_test_set`) | Clean Data (pandas DataFrame) | File `data/eval/test_set.json` chứa 30 câu hỏi | Hoàn thành |
| Data Quality Check | `src/observability/quality.py` (hàm `run_data_quality_checks` & `build_freshness_report`) | DataFrame, Settings | File JSON lưu metrics (row_count, nulls, freshness) | Hoàn thành |
| So sánh Metrics | `src/observability/reporting.py` (hàm `generate_phase1_report`, `generate_corruption_report`) | Các file metrics JSON (baseline, corrupted, repaired) | File Markdown báo cáo tổng hợp | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Xử lý Git Rebase Conflict | Luồng CI/CD chung của nhóm (Role 1) | Gộp thành công `test_set.json` và code báo cáo lên nhánh `main`, đảm bảo Phase 2 chạy trơn tru |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Xây dựng script sinh bộ câu hỏi đánh giá | `data/eval/test_set.json` | 30 câu hỏi test chia làm 3 loại (authors, categories, summary) | Chạy `script/test_cp1_role4.py` và đọc file json |
| Xuất báo cáo tổng hợp Phase 1 và Phase 2 | `data/reports/corruption_report.md` | Báo cáo Markdown so sánh RAG metrics giữa các mốc Data | Đọc file markdown sau khi chạy `run_corruption_flow.py` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:
Bộ câu hỏi cố định `test_set.json`. Bằng cách sinh nó 1 lần duy nhất ở Baseline, tôi giúp hệ thống có được 1 mốc đánh giá chung để đối chiếu sự tụt giảm điểm RAG ở Phase 2.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết
Giúp hệ thống có khả năng tự động quan sát, đo lường điểm số của bộ tìm kiếm RAG (Evaluation) và theo dõi chất lượng của luồng dữ liệu (Observability) qua từng phase (sạch -> hỏng -> sửa).

### Cách triển khai
Tôi xây dựng các hàm đọc DataFrame, đếm tổng số dòng, đếm nulls, sau đó lưu thành JSON. Đối với phần Test Set, tôi random sample dữ liệu sạch ra 30 bài báo, sau đó tự sinh câu hỏi dựa trên các trường `title`, `authors_joined`, `categories_joined` và lấy `paper_id` làm `ground_truth_doc_ids`.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | DataFrame dữ liệu (`papers_clean.csv`) và các thư mục JSON |
| Output                         | Các file báo cáo `.md` và `.json` |
| Module phụ thuộc             | `src/evaluation/`, `src/observability/` |
| Module sử dụng output        | `script/run_phase1.py` và `script/run_corruption_flow.py` |
| Điều kiện lỗi cần xử lý | Xử lý lỗi Rebase Conflict khi merge vào `main` để ưu tiên giữ lại file test_set mới nhất của Role 4 |

### Cách xác minh

```bash
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Tự động sinh ra file báo cáo `corruption_report.md` so sánh được điểm RAG trước và sau khi hỏng.
- **Kết quả thực tế:** Code chạy thành công, điểm RAG giảm đúng như dự báo, báo cáo được lưu chính xác.
- **Artifact/log:** `data/reports/corruption_report.md`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần so sánh điểm RAG giữa lúc data sạch và data hỏng.
- **Các phương án đã cân nhắc:** Mỗi lần đánh giá sẽ sinh lại 30 câu hỏi mới HOẶC dùng chung 1 bộ 30 câu hỏi ban đầu.
- **Phương án đã chọn:** Dùng chung bộ đề cố định `test_set.json`.
- **Lý do:** Trade-off về tính chính xác khi so sánh. Đã thi thì phải thi chung đề mới thấy rõ sự tụt lùi của AI (do data hỏng) chứ không phải do ăn may bốc trúng câu hỏi khó hay dễ.
- **Bằng chứng quyết định phù hợp:** `mean_token_f1` và `retrieval_hit_rate` có thể so sánh trực tiếp 1-1 trong `corruption_report.md`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Bị conflict trong lúc rebase `data/eval/test_set.json`. Lỗi: `CONFLICT (add/add): Merge conflict in data/eval/test_set.json`.
- **Lệnh hoặc bước tái hiện:** Chạy `git rebase` khi đang pull code từ `main` xuống.
- **Nguyên nhân gốc:** Quá trình làm việc song song của Role 1 và Role 4 đã tạo ra 2 phiên bản `test_set.json` khác nhau và Git không biết chọn cái nào.
- **Cách xử lý:** Báo Git ưu tiên lấy file của nhánh `--theirs` (Role 4): `git checkout --theirs data/eval/test_set.json`, add và `git rebase --continue`. Sau đó ở lần đụng độ rác tiếp theo thì dùng `git rebase --abort` và `git reset --hard origin/main` để đồng bộ hoàn toàn với nhánh chuẩn.
- **Cách xác minh sau khi sửa:** Chạy `git status` và `git pull` báo up-to-date.
- **Điều học được:** Bài học sâu sắc về xử lý luồng làm việc Git khi Code chung nhánh với nhóm, hiểu rõ cơ chế `--ours` và `--theirs` lúc merge và rebase.

## 7. Hiểu biết về luồng end-to-end

1. Dữ liệu đi từ Crossref đến vector index như thế nào?
-> Từ raw json tải qua API (Role 2) -> Làm sạch bằng Pandas thành file clean -> Đưa qua mô hình nhúng (MiniLM) sinh vector (Role 3) -> Lưu vào Chroma DB.
2. Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?
-> Dùng question để RAG query. Lấy danh sách doc_ids mà RAG tìm được so sánh với `ground_truth_doc_ids` -> tính Hit Rate. Lấy answer của RAG so sánh với `ground_truth` -> tính Token F1.
3. Quality checks khác freshness monitoring ở điểm nào trong bài lab?
-> Quality check kiểm tra định dạng, nulls, duplicates. Freshness chỉ kiểm tra độ cũ/mới của ngày xuất bản (published_date).
4. Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?
-> Để so sánh Apple-to-Apple. Tránh việc điểm số bị ảnh hưởng do độ khó của các câu hỏi random khác nhau.
5. Repair được xem là thành công dựa trên artifact và metric nào?
-> RAG metrics (`retrieval_hit_rate` và `mean_token_f1`) phải trở về bằng đúng với mốc Baseline. Thể hiện trên file `repaired_metrics.json`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |    100% |      80% |     100% | Data hỏng làm giảm 20% hit rate, nhưng repair đã cứu thành công. |
| `mean_token_f1`      |  13.57% |   10.57% |   13.57% | F1 nhìn chung rất thấp ở mọi mốc, nhưng đã khôi phục sau repair. |
| `judge_accuracy`     |   6.67% |    6.67% |    6.67% | Điểm liệt bét bảng không hề thay đổi, chứng tỏ LLM judge bị fallback do chưa tune Prompt. |
| `mean_judge_score`   |     1.20 |      1.20 |     1.20 | Giống hệt judge accuracy. |
| Quality checks         |   0 lỗi |   có lỗi |    0 lỗi | Role 2 phá data rất khéo và vá data cũng rất hoàn hảo. |
| Freshness status       |    Fresh |    Fresh |    Fresh | Mặc dù data bị phá một số trường văn bản, nhưng freshness không ảnh hưởng nặng. |

### Kết luận từ số liệu

1. [Data corruption] -> Xóa Title/Summary -> RAG thiếu chữ để index nên hit rate giảm từ 100% còn 80%.
2. [Repair action] -> Khôi phục Title/Summary -> RAG index lại đầy đủ chữ nên hit rate phục hồi 100%.

Corruption nào ảnh hưởng rõ nhất và vì sao?
Việc xóa bỏ Title và Summary ảnh hưởng nặng nhất đến RAG. Vì đây là nguồn dữ liệu Text chính để tạo ra Vector nhúng. Mất text = mất vector chuẩn = Retrieval trật lất.

Kết quả nào khác với kỳ vọng ban đầu?
Điểm `judge_accuracy` không hề giảm mà giữ nguyên ở mức 6.67%. Giả thuyết là điểm Baseline đã quá tệ rồi nên không thể tệ hơn được nữa. Xác minh qua log thấy LLM đã fallback xuống dùng hàm heurustic F1 thay vì chấm bằng LLM thật.

## 9. Điều học được và hướng cải thiện

1. Vai trò sống còn của dữ liệu sạch: Chỉ cần rác đầu vào, mô hình xịn (RAG) cũng trả kết quả vô nghĩa.
2. Sức mạnh của Observability: Việc ghi nhận Baseline giúp ta đo đếm được chính xác sự tụt lùi của hệ thống.
3. Cách phân phối luồng CI/CD trong làm việc nhóm qua Git cực kỳ quan trọng và phải phối hợp tốt để tránh đụng độ rác.

### Nếu có thêm thời gian
Tôi sẽ tối ưu lại Prompt cho LLM Judge để AI tự chấm điểm chính xác và gắt gao hơn thay vì bị fallback sang hàm tự động bằng Python.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Tiến Đạt
**Ngày xác nhận:** 2026-08-06
