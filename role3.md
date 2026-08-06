# Role 3 - RAG & Agent Progress

Nguoi phu trach: Pham Thi Lien  
Branch: `role3-rag-agent`  
Pham vi so huu: `src/retrieval/`, `data/embeddings/`

## Muc tieu Role 3

- Build embedding index bang `sentence-transformers/all-MiniLM-L6-v2`.
- Quan ly cac Chroma collections: `papers-baseline`, `papers-corrupted`, `papers-repaired`.
- Dam bao semantic search, exact lookup va agent/RAG question answering hoat dong tren corpus da index.
- Ban giao embedding manifest va smoke-test evidence cho Role 1/Role 4 dung trong pipeline, evaluation va report.

## Contract Can Tu Role Khac

### Can tu Role 2 - Data foundation

- [x] `data/clean/papers_clean.csv`
- [x] `data/clean/papers_clean.json`
- [x] Clean dataframe co cac cot bat buoc:
  - [x] `paper_id`
  - [x] `title`
  - [x] `text_for_embedding`
  - [x] `published`
  - [x] `authors_joined`
  - [x] `categories_joined`
  - [x] `summary`
  - [x] `abs_url`
  - [x] `pdf_url`
- [x] `paper_id` unique va on dinh.
- [x] `text_for_embedding` khong rong.

### Can tu Role 4 - Evaluation & observability

- [x] `data/eval/test_set.json`
- [x] Moi `ground_truth_doc_ids` trong test set deu ton tai trong index.
- [x] Giup doi chieu retrieval hit/miss bang artifact thuc te.

### Can tu Role 1 - Pipeline orchestration

- [ ] `src/pipelines/phase1.py` goi dung `LocalEmbeddingIndex.build()`.
- [ ] `src/pipelines/corruption_flow.py` build index rieng cho corrupted va repaired.
- [ ] Khong ghi de collection/artifact baseline khi chay phase 2.

## Artifact Role 3 Ban Giao

- [x] `data/embeddings/papers_embeddings.json`
- [ ] `data/embeddings/papers_embeddings_corrupted.json`
- [ ] `data/embeddings/papers_embeddings_repaired.json`
- [x] Chroma collection `papers-baseline`
- [ ] Chroma collection `papers-corrupted`
- [ ] Chroma collection `papers-repaired`
- [x] Smoke-test query/lookup evidence cho baseline
- [ ] Smoke-test query/lookup evidence cho corrupted, repaired

## Checkpoint 0 - 00:00-00:30

Muc tieu: Khoi dong, doc contract, hieu input/output cua retrieval.

### Viec can lam

- [ ] Doc `src/retrieval/index.py`.
- [ ] Doc `src/retrieval/embeddings.py`.
- [ ] Doc `src/retrieval/agent.py`.
- [ ] Doc `src/retrieval/qa.py`.
- [ ] Doc `src/retrieval/llm.py`.
- [ ] Xac nhan embedding model: `sentence-transformers/all-MiniLM-L6-v2`.
- [ ] Xac nhan collection names:
  - [ ] baseline: `papers-baseline`
  - [ ] corrupted: `papers-corrupted`
  - [ ] repaired: `papers-repaired`
- [ ] Chuan bi smoke query se dung sau khi co index.
- [ ] Chuan bi lookup sample bang `paper_id` hoac exact title sau khi co clean data.

### Da lam

- [ ] Da doc code retrieval.
- [ ] Da thong nhat contract voi Role 2.
- [ ] Da thong nhat artifact/path voi Role 1.
- [ ] Da thong nhat nhu cau test set voi Role 4.

### Evidence / ghi chu

```text
Ghi tai day:
- Smoke query du kien:
- Lookup sample du kien:
- Blocker:
```

## Checkpoint 1 - 00:30-01:05

Muc tieu: Kiem tra clean schema san sang cho indexing.

### Viec co the lam ngay

- [x] Kiem tra `_build_documents()` trong `index.py` co dung clean schema khong.
- [x] Xac dinh metadata se dua vao Chroma:
  - [x] `paper_id`
  - [x] `title`
  - [x] `published`
  - [x] `authors_joined`
  - [x] `categories_joined`
  - [x] `summary`
  - [x] `abs_url`
  - [x] `pdf_url`
- [x] Chuan bi cach test `search()`.
- [x] Chuan bi cach test `lookup()`.

### Viec phai cho Role 2

- [x] Cho Role 2 ban giao clean CSV/JSON.
- [x] Cho Role 2 xac nhan `paper_id` unique.
- [x] Cho Role 2 xac nhan `text_for_embedding` khong rong.

### Da lam

- [x] Da kiem tra clean artifact ton tai.
- [x] Da doc thu mot vai row clean data.
- [x] Da bao blocker neu clean schema thieu field.

### Evidence / ghi chu

```text
Clean file: data/clean/papers_clean.csv, data/clean/papers_clean.json
Validation file: data/clean/cp1_validation.json
Validation status: passed
Row count: 24
Source items: 24
Parsed records: 24
Clean records: 24
Dropped during parse: 0
Dropped during cleaning: 0
Columns: paper_id, title, summary, authors, categories, primary_category, published, updated, age_days, abs_url, pdf_url, comment, authors_joined, categories_joined, summary_chars, text_for_embedding
Missing required fields for Role 3: 0 for paper_id, title, text_for_embedding, published, authors_joined, categories_joined, summary, abs_url
pdf_url empty rows: 12; accepted because Role 2 contract marks pdf_url optional string, never null
Duplicate paper_id: 0
_build_documents() check: passed
Document count from _build_documents(): 24
Empty document content: 0
Empty paper_id: 0
First sample paper_id: 10.2118/234689-pa
First sample title: SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation
Blocker: none for CP1; ready to start CP2 baseline embedding build
```

## Checkpoint 2 - 01:05-01:35

Muc tieu: Build RAG index va smoke test agent/search/lookup.

### Dieu kien bat dau

- [x] Role 2 da co clean data hop le.
- [x] Clean data co du field cho `LocalEmbeddingIndex._build_documents()`.

### Viec can lam

- [x] Build baseline index tu clean dataframe.
- [x] Tao `data/embeddings/papers_embeddings.json`.
- [x] Xac nhan collection `papers-baseline` ton tai.
- [x] Chay semantic search voi smoke query.
- [x] Chay exact lookup bang `paper_id`.
- [x] Chay exact lookup bang title neu co sample tot.
- [x] Kiem tra result co:
  - [x] `paper_id`
  - [x] `title`
  - [x] `score`
  - [x] `content`
  - [x] `metadata`
- [x] Ho tro Role 4 doi chieu test set doc IDs voi index.

### Da lam

- [x] Da build baseline embedding.
- [x] Da search thanh cong.
- [x] Da lookup thanh cong.
- [x] Da xac nhan manifest khop collection baseline.

### Evidence / ghi chu

```text
Manifest path: data/embeddings/papers_embeddings.json
Collection: papers-baseline
Document count: 24
Persist path: data/chroma
Embedding model: sentence-transformers/all-MiniLM-L6-v2
Smoke query: retrieval augmented generation safety report
Search top_k: 3
Search result count: 3
Top 1: 10.54254/2753-8818/2026.dl34055 | score 0.4631 | Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, a
Top 2: 10.70121/001c.158711 | score 0.4286 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language
Top 3: 10.2118/234689-pa | score 0.4231 | SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safet
Lookup input paper_id: 10.2118/234689-pa
Lookup by paper_id: found
Lookup by exact title: found
Lookup result title: SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation
QA smoke question: What does SafeRAG do for safety report generation?
QA smoke answer: Summary In high-risk industrial settings, leveraging large language models (LLMs) for automated accident analysis and generating safety reports has emerged as an efficient workflow.
QA retrieved_doc_ids: 10.2118/234689-pa, 10.3390/buildings16132637, 10.21203/rs.3.rs-10012178/v1, 10.21079/11681/50309
QA status: passed
LLM agent smoke: not run yet because local `.env` is absent; build_agent requires an LLM provider credential unless using a configured local provider.
Role 4 test set: data/eval/test_set.json
Test set samples: 30
Ground truth doc IDs checked: 30
Samples without ground_truth_doc_ids: 0
Ground truth IDs missing from baseline index: 0
Ground truth validation status: passed
Blocker: none for CP2
```

## Checkpoint 3 - 01:35-02:00

Muc tieu: Baseline pipeline chay end-to-end va co report.

### Dieu kien bat dau

- [x] Role 1 da ghep `phase1.py`.
- [x] Role 2 clean data da on.
- [x] Role 4 test set/metrics da san sang.
- [x] Role 3 baseline index da build duoc.

### Viec can lam

- [x] Xac nhan `script/run_phase1.py` build/load dung index baseline.
- [x] Xac nhan `papers-baseline` khop clean dataset.
- [x] Demo mot semantic search cho team.
- [x] Demo mot exact lookup cho team.
- [x] Kiem tra agent tra loi dua tren tool result.
- [x] Neu evaluation miss, xac dinh loi thuoc retrieval, test set hay clean data.

### Da lam

- [x] Da xac nhan baseline index trong phase1.
- [x] Da demo search/lookup.
- [x] Da ho tro Role 4 doc hit/miss. Retrieval hit rate is 1.0, so no retrieval miss in baseline answers.

### Evidence / ghi chu

```text
Baseline audit command: .\.venv\Scripts\python.exe script\verify_baseline.py
Baseline audit result: 29/32 pass, 3 fail
Phase1 index step: src/pipelines/phase1.py step 4/8 calls LocalEmbeddingIndex.build(clean_df, settings, embeddings_output_path=paths.embeddings_json)
Baseline index status: papers-baseline, 24 docs, Chroma count == clean rows
Embedding manifest: data/embeddings/papers_embeddings.json
Manifest collection: papers-baseline
Manifest model: sentence-transformers/all-MiniLM-L6-v2
Manifest documents: 24
Test set samples: 30
Baseline answers: 30
Retrieval hit rate: 1.0
Mean token F1: 0.13571145889885564
Judge accuracy: 0.06666666666666667
Mean judge score: 1.2
Search demo query: agentic retrieval augmented generation
Search demo top 1: 10.63646/kpqm1958 | score 0.5772 | The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Search demo top 2: 10.7717/peerj-cs.3882 | score 0.5550 | A large language model-driven scientific literature surveys generation framework based on multi-agents and retrieval-aug
Search demo top 3: 10.36227/techrxiv.177272838.89432844/v1 | score 0.5479 | A Survey of (Deep RAG) Deep Retrieval Augmented Generation and Reasoning in Large Language Models
Search demo top 4: 10.70121/001c.158711 | score 0.4883 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language Models
Lookup demo input: 10.2118/234689-pa
Lookup demo result: found | SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation
Retrieval hit/miss case: no retrieval miss found in baseline; metrics/answers show retrieval_hit_rate 1.0 across 30 samples
Agent demo artifact: data/results/agent_demo_answers.json still stale from previous run and says GOOGLE_API_KEY is required.
Manual agent demo after `.env` update: passed with provider=openai and temporary LLM_MODEL=gpt-4o-mini because `.env` does not define LLM_MODEL.
Manual agent question: Which indexed paper is most relevant to agentic retrieval augmented generation?
Manual agent trace: MESSAGE_COUNT=4, TOOL_CALLS=1, TOOL_RESULTS=1
Manual agent answer top paper: The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Baseline audit blockers not owned by Role 3:
- judge uses fallback heuristic for 30/30 samples, so judge_accuracy is not reliable evidence until LLM credentials/provider are configured
- freshness latest_published is null while clean data has dates
- phase1 report writes Latest Published/Oldest Published as None
Role 3 blocker: none for index/search/lookup/retrieval metrics/agent tool-call behavior
Config note: `.env` has LLM_PROVIDER=openai and OPENAI_API_KEY set, but LLM_MODEL is missing; code falls back to gemini-2.5-flash unless LLM_MODEL is set in environment.
```

## Checkpoint 4 - 02:00-02:15

Muc tieu: Nghi 15 phut, giu lai query de so sanh phase 2.

### Viec can lam

- [x] Ghi lai query baseline tot.
- [x] Ghi lai lookup sample tot.
- [x] Ghi lai ket qua baseline de so voi corrupted/repaired.

### Evidence / ghi chu

```text
Baseline manifest: data/embeddings/papers_embeddings.json
Baseline collection: papers-baseline
Baseline document count: 24
Baseline embedding model: sentence-transformers/all-MiniLM-L6-v2
Baseline persist path: data/chroma

Baseline metrics artifact: data/results/baseline_metrics.json
Samples: 30
Retrieval hit rate: 1.0
Mean token F1: 0.13571145889885564
Judge accuracy: 0.03333333333333333
Mean judge score: 1.5

Baseline query 1: agentic retrieval augmented generation
Query 1 top 1: 10.63646/kpqm1958 | score 0.5772 | The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Query 1 top 2: 10.7717/peerj-cs.3882 | score 0.5550 | A large language model-driven scientific literature surveys generation framework based on multi-agents and retrieval-augmented generation
Query 1 top 3: 10.36227/techrxiv.177272838.89432844/v1 | score 0.5479 | A Survey of (Deep RAG) Deep Retrieval Augmented Generation and Reasoning in Large Language Models

Baseline query 2: retrieval augmented generation safety report
Query 2 top 1: 10.54254/2753-8818/2026.dl34055 | score 0.4631 | Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation
Query 2 top 2: 10.70121/001c.158711 | score 0.4286 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language Models
Query 2 top 3: 10.2118/234689-pa | score 0.4231 | SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation

Baseline lookup sample: 10.2118/234689-pa
Lookup status: found
Lookup title: SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation

Use these same queries and lookup sample in CP5 and CP6 to compare baseline vs corrupted vs repaired.
```

## Checkpoint 5 - 02:15-03:15

Muc tieu: Build corrupted index va do impact.

### Dieu kien bat dau

- [x] Baseline da hoan tat.
- [x] Role 2 da tao corrupted clean data.
- [x] Role 1 da ghep corruption flow.
- [x] Role 4 giu nguyen test set baseline.

### Viec can lam

- [x] Build corrupted index tu corrupted clean data.
- [x] Tao `data/embeddings/papers_embeddings_corrupted.json`.
- [x] Xac nhan collection `papers-corrupted` ton tai.
- [x] Chay lai smoke query baseline tren corrupted index.
- [x] So sanh top result baseline vs corrupted.
- [x] Xac nhan `papers-baseline` khong bi ghi de.
- [x] Ho tro Role 4 tim mot case retrieval xau di co evidence.

### Da lam

- [x] Da build corrupted embedding.
- [x] Da search tren corrupted collection.
- [x] Da xac nhan baseline collection van con.
- [x] Da ghi evidence impact.

### Evidence / ghi chu

```text
Corruption log: data/results/corruption_log.json
Corruption plan: drop_latest=3, missing_summary=2, noise=2, old_date=4, duplicate=2
Dropped latest paper_ids: 10.2118/234689-pa, 10.1007/s10278-026-02086-9, 10.21203/rs.3.rs-10178277/v1

Baseline clean rows: 24
Corrupted clean rows: 23
Corrupted unique paper_ids: 21
Corrupted duplicate IDs: 2
Corrupted empty summary rows: 2
Corrupted empty text_for_embedding rows: 0

Corrupted manifest: data/embeddings/papers_embeddings_corrupted.json
Corrupted collection: papers-corrupted
Corrupted document count: 23
Corrupted embedding model: sentence-transformers/all-MiniLM-L6-v2
Corrupted persist path: data/chroma
Metadata status: present with paper_id, title, published, authors_joined, categories_joined, summary, abs_url, pdf_url

Baseline collection still available: papers-baseline, 24 docs

Baseline metrics: data/results/baseline_metrics.json
Baseline retrieval_hit_rate: 1.0
Baseline mean_token_f1: 0.13571145889885564
Corrupted metrics: data/results/corrupted_metrics.json
Corrupted retrieval_hit_rate: 0.8
Corrupted mean_token_f1: 0.10574274526524473
Observed metric impact: retrieval_hit_rate dropped by 0.2; mean_token_f1 dropped by about 0.03

Same query 1: agentic retrieval augmented generation
Baseline top 1: 10.63646/kpqm1958 | score 0.5772 | The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Corrupted top 1: 10.63646/kpqm1958 | score 0.5772 | The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Observed query 1 impact: top-3 unchanged, this query was not strongly affected by selected corruptions.

Same query 2: retrieval augmented generation safety report
Baseline top 1: 10.54254/2753-8818/2026.dl34055 | score 0.4631 | Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation
Baseline top 2: 10.70121/001c.158711 | score 0.4286 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language Models
Baseline top 3: 10.2118/234689-pa | score 0.4231 | SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation
Corrupted top 1: 10.54254/2753-8818/2026.dl34055 | score 0.4631 | Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation
Corrupted top 2: 10.1093/sleep/zsag091.0346 | score 0.4287 | 0346 Retrieval Augmented Generation Improves Large Language Model Performance in Sleep Medicine
Corrupted top 3: 10.70121/001c.158711 | score 0.4286 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language Models
Observed query 2 impact: SafeRAG disappeared from corrupted top-3 because 10.2118/234689-pa was dropped by corruption.

Lookup impact sample: 10.2118/234689-pa
Baseline lookup: found
Corrupted lookup: not found
Observed lookup impact: exact lookup fails in corrupted collection for dropped latest record.

Blocker: none for CP5 Role 3. Ready for CP6 repaired comparison.
```

## Checkpoint 6 - 03:15-04:00

Muc tieu: Build repaired index, so sanh 3 trang thai, chuan bi demo.

### Dieu kien bat dau

- [x] Role 2 da repair tu raw/source dang tin.
- [x] Role 4 san sang evaluate repaired voi test set cu.
- [x] Role 1 da co comparison flow/report path.

### Viec can lam

- [x] Build repaired index tu repaired clean data.
- [x] Tao `data/embeddings/papers_embeddings_repaired.json`.
- [x] Xac nhan collection `papers-repaired` ton tai.
- [x] Chay lai smoke query baseline tren repaired index.
- [x] So sanh baseline vs corrupted vs repaired.
- [x] Kiem tra agent/retrieval tren repaired data.
- [x] Cung team xac nhan report dung artifact that.
- [x] Dam bao khong commit `.env`, API key, Chroma store nang neu `.gitignore` da loai.

### Da lam

- [x] Da build repaired embedding.
- [x] Da search tren repaired collection.
- [x] Da so sanh 3 trang thai.
- [x] Da chuan bi demo evidence.

### Evidence / ghi chu

```text
Recovery evidence: data/clean/recovery_evidence.json
Recovery status: passed
Recovery source: locked raw snapshot, no external fetch
Repaired validation: repaired_matches_baseline=true, repaired_contract_passed=true, repaired_quality_clean=true

Baseline rows: 24
Corrupted rows: 23
Repaired rows: 24
Baseline unique paper_ids: 24
Corrupted unique paper_ids: 21
Repaired unique paper_ids: 24
Repaired duplicate IDs: 0
Repaired empty summary rows: 0
Repaired empty text_for_embedding rows: 0

Repaired manifest: data/embeddings/papers_embeddings_repaired.json
Repaired collection: papers-repaired
Repaired document count: 24
Repaired embedding model: sentence-transformers/all-MiniLM-L6-v2
Repaired persist path: data/chroma
Metadata status: present with paper_id, title, published, authors_joined, categories_joined, summary, abs_url, pdf_url

Collections rebuilt/checked locally:
- papers-baseline: 24 docs
- papers-corrupted: 23 docs
- papers-repaired: 24 docs

Baseline metrics: data/results/baseline_metrics.json
Baseline retrieval_hit_rate: 1.0
Baseline mean_token_f1: 0.8474978798884274
Baseline judge_accuracy: 0.8
Corrupted metrics: data/results/corrupted_metrics.json
Corrupted retrieval_hit_rate: 0.8
Corrupted mean_token_f1: 0.6573626145044891
Corrupted judge_accuracy: 0.625
Repaired metrics: data/results/repaired_metrics.json
Repaired retrieval_hit_rate: 1.0
Repaired mean_token_f1: 0.8474978798884274
Repaired judge_accuracy: 0.8
Metric recovery: repaired metrics match baseline for retrieval_hit_rate, mean_token_f1, and judge_accuracy.

Same query 1: agentic retrieval augmented generation
Baseline top 1: 10.63646/kpqm1958 | score 0.5772 | The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Corrupted top 1: 10.63646/kpqm1958 | score 0.5772 | The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Repaired top 1: 10.63646/kpqm1958 | score 0.5772 | The Age of Autonomous Agents: A Bibliometric Review of Agentic AI Architectures, Applications, and Emerging Challenges
Query 1 conclusion: no visible retrieval change across states.

Same query 2: retrieval augmented generation safety report
Baseline top 1: 10.54254/2753-8818/2026.dl34055 | score 0.4631 | Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation
Baseline top 2: 10.70121/001c.158711 | score 0.4286 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language Models
Baseline top 3: 10.2118/234689-pa | score 0.4231 | SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation
Corrupted top 1: 10.54254/2753-8818/2026.dl34055 | score 0.4631 | Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation
Corrupted top 2: 10.1093/sleep/zsag091.0346 | score 0.4287 | 0346 Retrieval Augmented Generation Improves Large Language Model Performance in Sleep Medicine
Corrupted top 3: 10.70121/001c.158711 | score 0.4286 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language Models
Repaired top 1: 10.54254/2753-8818/2026.dl34055 | score 0.4631 | Hallucination in Large Language Models and Retrieval-Augmented Generation: Mechanisms, Mitigation, and Evaluation
Repaired top 2: 10.70121/001c.158711 | score 0.4286 | The Role of Retrieval-Augmented Generation in Improving Factual Accuracy for Medical Large Language Models
Repaired top 3: 10.2118/234689-pa | score 0.4231 | SafeRAG: A Large-Language-Model-Based Multistage Retrieval-Augmented Framework for Oil and Gas Safety Report Generation
Query 2 conclusion: repaired restores the same top-3 ordering as baseline; SafeRAG returns after being dropped in corrupted data.

Lookup impact sample: 10.2118/234689-pa
Baseline lookup: found
Corrupted lookup: not found
Repaired lookup: found
Lookup conclusion: repair restores exact lookup for dropped latest record.

Lineage repair sample: 10.21203/rs.3.rs-10012178/v1
Baseline lookup: found
Corrupted lookup: found, but summary was blanked by corruption
Repaired lookup: found, summary/text restored according to recovery_evidence.json

Report artifact: data/reports/corruption_report.md
Conclusion: CP6 Role 3 passed. Baseline -> corrupted shows retrieval degradation; corrupted -> repaired restores collection size, lookup behavior, and metrics back to baseline.
Blocker: none
```

## Checklist Truoc Khi PR

- [ ] Dang o branch `role3-rag-agent`.
- [ ] Chi sua file trong pham vi Role 3.
- [ ] `data/embeddings/` co manifest can thiet.
- [ ] Search baseline chay duoc.
- [ ] Lookup baseline chay duoc.
- [ ] Corrupted/repaired collection tach rieng neu da sang phase 2.
- [ ] Khong commit `.env`.
- [ ] Khong commit API key.
- [ ] Chay `git status` va kiem tra file truoc khi commit.

## Lenh Tham Khao

```powershell
git status --short --branch
git switch role3-rag-agent
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
```
