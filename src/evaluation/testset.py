from __future__ import annotations

from typing import Any

import pandas as pd


import json
import os
import uuid

def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    if len(df) == 0:
        return []
        
    sample_size = min(len(df), 10)
    sample_df = df.sample(n=sample_size, random_state=42)
    
    test_set = []
    
    for _, row in sample_df.iterrows():
        paper_id = str(row.get("paper_id", ""))
        title = str(row.get("title", ""))
        summary = str(row.get("summary", ""))
        authors = str(row.get("authors", ""))
        published_date = str(row.get("published_date", ""))
        categories = str(row.get("categories", ""))
        
        if not paper_id or not title:
            continue
            
        if summary and summary.strip() and summary != "nan":
            test_set.append({
                "id": str(uuid.uuid4()),
                "question_type": "summary",
                "question": f"Hãy tóm tắt nội dung chính của bài báo '{title}'?",
                "ground_truth": summary,
                "ground_truth_doc_ids": [paper_id]
            })
            
        if authors and authors.strip() and authors != "nan":
            test_set.append({
                "id": str(uuid.uuid4()),
                "question_type": "authors",
                "question": f"Ai là (các) tác giả của nghiên cứu có tiêu đề '{title}'?",
                "ground_truth": authors,
                "ground_truth_doc_ids": [paper_id]
            })
            
        if published_date and published_date.strip() and published_date != "nan":
            test_set.append({
                "id": str(uuid.uuid4()),
                "question_type": "date",
                "question": f"Bài báo '{title}' được xuất bản chính thức vào thời gian nào?",
                "ground_truth": published_date,
                "ground_truth_doc_ids": [paper_id]
            })
            
        if categories and categories.strip() and categories != "nan":
            test_set.append({
                "id": str(uuid.uuid4()),
                "question_type": "categories",
                "question": f"Nghiên cứu '{title}' thuộc về (những) lĩnh vực/chuyên mục nào?",
                "ground_truth": categories,
                "ground_truth_doc_ids": [paper_id]
            })
            
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(test_set, f, indent=2, ensure_ascii=False)
        
    return test_set
