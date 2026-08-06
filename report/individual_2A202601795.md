# Báo cáo cá nhân - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Phạm Thị Liên |
| MSSV | 2A202601795 |
| Khóa/Lớp | K3 |
| Tên nhóm | Fathom |
| Vai trò chính | Role 3 - RAG & agent |
| Branch | `role3-rag-agent` |
| Repository | https://github.com/huylq-at-work/K3_Day10_D305_A1.git |
| Ngày hoàn thành | 2026-08-06 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Embedding model | `src/retrieval/embeddings.py`, `MiniLMEmbeddings` | `text_for_embedding` từ clean dataframe | Vector embeddings bằng `sentence-transformers/all-MiniLM-L6-v2` | Hoàn thành |
| Vector index | `src/retrieval/index.py`, `LocalEmbeddingIndex.build/load/search/lookup` | Clean/corrupted/repaired dataframe | Chroma collections và embedding manifests | Hoàn thành |
| Baseline RAG index | `data/clean/papers_clean.csv` | 24 clean records | `data/embeddings/papers_embeddings.json`, collection `papers-baseline` | Hoàn thành |
| Corrupted RAG index | `data/clean/papers_clean_corrupted.csv` | 23 corrupted rows | `data/embeddings/papers_embeddings_corrupted.json`, collection `papers-corrupted` | Hoàn thành |
| Repaired RAG index | `data/clean/papers_clean_repaired.csv` | 24 repaired rows | `data/embeddings/papers_embeddings_repaired.json`, collection `papers-repaired` | Hoàn thành |
| Search/lookup evidence | `LocalEmbeddingIndex.search`, `LocalEmbeddingIndex.lookup` | Query và `paper_id` mẫu | Bằng chứng so sánh baseline/corrupted/repaired | Hoàn thành |
| Agent behavior | `src/retrieval/agent.py`, `src/retrieval/qa.py` | Index và test questions | Câu trả lời dựa trên retrieval/tool output | Hoàn thành ở mức verification |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra clean schema trước khi index | Role 2 - data foundation | Xác nhận clean data có đủ cột bắt buộc, `paper_id` unique, `text_for_embedding` không rỗng |
| Đối chiếu `ground_truth_doc_ids` | Role 4 - evaluation | 40 samples dùng cùng test set, ground-truth IDs trỏ tới document có thật trong index |
| Cung cấp evidence cho comparison report | Role 1/Role 4 | Chỉ ra case `10.2118/234689-pa` mất ở corrupted và được khôi phục ở repaired |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Kiểm tra contract clean data | `data/clean/papers_clean.csv`, `LocalEmbeddingIndex._build_documents` | Build được 24 documents, metadata đủ cột | Đọc CSV/JSON và build documents từ dataframe |
| Build baseline index | `LocalEmbeddingIndex.build`, `data/embeddings/papers_embeddings.json` | Collection `papers-baseline`, 24 docs | Manifest có `collection_name=papers-baseline`, `documents=24` |
| Build corrupted index | `data/embeddings/papers_embeddings_corrupted.json` | Collection `papers-corrupted`, 23 docs | Manifest có `collection_name=papers-corrupted`, `documents=23` |
| Build repaired index | `data/embeddings/papers_embeddings_repaired.json` | Collection `papers-repaired`, 24 docs | Manifest có `collection_name=papers-repaired`, `documents=24` |
| So sánh retrieval impact | `data/results/*_metrics.json`, search/lookup | Corrupted làm `retrieval_hit_rate` giảm 1.0 -> 0.8 | Đối chiếu metrics và query top-k |
| Xác minh repair | `data/clean/recovery_evidence.json`, `data/results/repaired_metrics.json` | Repaired phục hồi metrics về baseline | Repaired `retrieval_hit_rate=1.0`, F1/judge match baseline |

Output cụ thể của Role 3 là ba embedding manifest và ba Chroma collection riêng biệt. Các collection này là cầu nối giữa clean data và evaluation: Role 4 dùng retrieval results/answers để tính metrics, còn Role 1 đưa các metrics vào report so sánh.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần biến dataset bài báo đã clean thành một corpus có thể truy xuất bằng semantic search và exact lookup. Nếu index sai schema, ghi đè collection, hoặc metadata thiếu `paper_id`, evaluation sẽ không chứng minh được corruption làm RAG kém đi hay repair có khôi phục không.

### Cách triển khai

Role 3 dùng `LocalEmbeddingIndex` làm abstraction chính:

1. `_build_documents(df)` biến mỗi dòng clean dataframe thành document có `record_id`, `paper_id`, `title`, `content` và `metadata`.
2. `MiniLMEmbeddings` encode cột `text_for_embedding` bằng model `sentence-transformers/all-MiniLM-L6-v2`.
3. `chromadb.PersistentClient` tạo collection riêng theo trạng thái:
   - `papers-baseline`
   - `papers-corrupted`
   - `papers-repaired`
4. `collection.add(...)` ghi embeddings, document text và metadata vào Chroma.
5. Manifest JSON ghi lại backend, model, persist path, collection name và documents để các bước sau load lại được.

Metadata đưa vào Chroma gồm:

```text
paper_id
title
published
authors_joined
categories_joined
summary
abs_url
pdf_url
```

Quyết định quan trọng là mỗi trạng thái dữ liệu phải có collection riêng. Nếu corrupted/repaired ghi đè baseline thì không còn mốc đối chiếu.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `papers_clean.csv`, `papers_clean_corrupted.csv`, `papers_clean_repaired.csv` |
| Output | `papers_embeddings.json`, `papers_embeddings_corrupted.json`, `papers_embeddings_repaired.json`; Chroma collections |
| Module phụ thuộc | `core.config.Settings`, clean schema của Role 2 |
| Module sử dụng output | `evaluation.metrics`, `retrieval.qa`, `retrieval.agent`, reporting/comparison flow |
| Điều kiện lỗi cần xử lý | Thiếu cột clean schema, `text_for_embedding` rỗng, `paper_id` trùng, collection không tồn tại, manifest trỏ đến path local sai |

### Cách xác minh

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe script\run_phase1.py
.\.venv\Scripts\python.exe script\run_corruption_flow.py
```

- **Kết quả mong đợi:** có đủ ba manifest embedding, ba collection riêng, metrics baseline/corrupted/repaired đọc được.
- **Kết quả thực tế:** baseline 24 docs, corrupted 23 docs, repaired 24 docs; metrics cho thấy corrupted giảm và repaired phục hồi.
- **Artifact/log:** `data/embeddings/`, `data/results/`, `data/reports/corruption_report.md`, `data/clean/recovery_evidence.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** cần lưu vector store sao cho baseline, corrupted và repaired có thể so sánh công bằng.
- **Các phương án đã cân nhắc:** dùng chung một Chroma collection và rebuild mỗi lần; hoặc dùng ba collection riêng.
- **Phương án đã chọn:** dùng ba collection riêng `papers-baseline`, `papers-corrupted`, `papers-repaired`.
- **Lý do:** tránh ghi đè baseline, giữ được ba trạng thái để audit và demo. Cách này làm artifact lớn hơn một chút nhưng reproducibility tốt hơn.
- **Bằng chứng quyết định phù hợp:** sau corruption, `papers-corrupted` có 23 docs và lookup `10.2118/234689-pa` không tìm thấy; sau repair, `papers-repaired` có 24 docs và lookup record này tìm thấy lại. Metrics cũng phục hồi về baseline.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi:** sau khi pull/rebuild trên máy khác, manifest embedding có thể chưa đúng với local Chroma path hoặc collection local chưa tồn tại.
- **Bước tái hiện:** load collection từ manifest rồi search/lookup; nếu Chroma store local chưa có collection sẽ gặp lỗi collection not found.
- **Nguyên nhân gốc:** `data/chroma/` không nên commit vì là store nặng; manifest trước đó có nguy cơ chứa path tuyệt đối theo máy.
- **Cách xử lý:** rebuild local collection từ CSV tương ứng, và giữ manifest dùng `persist_path=data/chroma` thay vì path tuyệt đối.
- **Cách xác minh sau khi sửa:** manifest hiện có `persist_path=data/chroma`; ba manifest lần lượt có 24/23/24 documents.
- **Điều học được:** artifact có thể đọc được trên Git chưa đủ, path trong artifact phải portable thì thành viên khác mới tái lập được.

## 7. Hiểu biết về luồng end-to-end

1. Crossref được Role 2 fetch/parse thành raw records trong `data/raw/`, sau đó clean thành `papers_clean.csv/json`. Role 3 đọc cột `text_for_embedding`, encode bằng MiniLM và nạp vào Chroma để tạo vector index.
2. Evaluation set gồm question, ground truth và `ground_truth_doc_ids`. Khi trả lời, retrieval lấy top-k document; nếu retrieved IDs chứa ground-truth ID thì tính là retrieval hit.
3. Quality checks bắt các lỗi schema/data như null, duplicate, summary rỗng; freshness monitoring tập trung vào tuổi dữ liệu dựa trên `published`/`age_days`.
4. Phải dùng cùng test set cho baseline, corrupted và repaired vì nếu đổi câu hỏi giữa các lần chạy thì metric thay đổi không còn quy được về corruption.
5. Repair thành công khi repaired data khớp baseline về row count/ID/schema, Chroma collection có đủ document, và metrics repaired trở về baseline trên cùng evaluation set.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | Corruption làm mất/làm hỏng document nên retrieval hit giảm; repair khôi phục hoàn toàn |
| `mean_token_f1` | 0.8475 | 0.6574 | 0.8475 | Answer quality giảm theo retrieval/data quality, sau repair quay lại baseline |
| `judge_accuracy` | 0.8000 | 0.6250 | 0.8000 | Judge cũng cho thấy corrupted làm chất lượng câu trả lời kém đi |
| `mean_judge_score` | 4.1500 | 3.4500 | 4.1500 | Điểm trung bình phục hồi đúng về baseline |
| Quality checks | clean | duplicate, missing summary, stale rows | clean | Quality signal bắt được data corruption |
| Freshness status | fresh | stale | fresh | Old-date corruption làm freshness xấu đi, repair đưa về fresh |

### Kết luận từ số liệu

1. Data corruption làm thay đổi trực tiếp chất lượng RAG. Cụ thể, corrupted data có 23 rows, 21 unique IDs, 2 duplicate IDs và 2 summary rỗng. `retrieval_hit_rate` giảm từ 1.0 xuống 0.8, `mean_token_f1` giảm từ 0.8475 xuống 0.6574.
2. Repair chạy lại từ locked raw snapshot khôi phục row count về 24, unique paper IDs về 24 và metrics về đúng baseline. `repaired_metrics.json` khớp baseline ở retrieval hit rate, token F1, judge accuracy và mean judge score.

Corruption ảnh hưởng rõ nhất với Role 3 là `drop_latest`. Paper `10.2118/234689-pa` bị drop nên exact lookup trong `papers-corrupted` trả về not found. Sau repair, record này xuất hiện lại trong `papers-repaired` và lookup thành công.

Kết quả đáng chú ý là có một query không thay đổi top-3 giữa ba trạng thái: `agentic retrieval augmented generation`. Điều này cho thấy không phải mọi corruption đều làm mọi query xấu đi; cần xem cả metrics toàn test set và case-level evidence.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. RAG pipeline phụ thuộc rất mạnh vào contract clean schema. Chỉ cần thiếu `paper_id` hoặc `text_for_embedding`, cả index và evaluation đều mất ý nghĩa.
2. Data observability không chỉ là report đẹp; nó phải bắt đúng các lỗi làm retrieval/answer metrics xấu đi.
3. Repair chỉ đáng tin khi có artifact chứng minh lineage từ raw source và metrics repaired được đo trên cùng test set với baseline/corrupted.

### Nếu có thêm thời gian

Tôi muốn thêm một script nhỏ riêng cho Role 3 để audit ba collection: đọc manifest, load collection, check count, check metadata keys và chạy một bộ query cố định. Script này sẽ giảm việc phải copy/paste command thủ công và giúp bắt sớm lỗi manifest path/collection mismatch.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi "đã chạy thành công" cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Phạm Thị Liên  
**Ngày xác nhận:** 2026-08-06
