"""Clean data contract — chot boi Role 1, moi role khac phai tuan theo.

Day la ranh gioi giua Role 2 (sinh clean data) va Role 3/4 (tieu thu).
Contract nam o `core/` chu khong nam trong `ingestion/` co chu y: neu de trong
`ingestion/` thi nguoi implement vua viet code vua tu dinh nghia tieu chi
dung/sai cho chinh minh, va gate o phase1 khong con doc lap.

Dieu kien dung (stop condition): pipeline KHONG duoc goi build index hay
build test set khi contract chua pass. Index tu clean data hong nghia la
baseline metrics khong dung lam moc so sanh duoc, va toan bo phase 2 mat y nghia.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re

import pandas as pd

# Cot bat buoc, dung thu tu. Nguon goc yeu cau:
#   - `LocalEmbeddingIndex._build_documents` doc: paper_id, title, text_for_embedding,
#     published, authors_joined, categories_joined, summary, abs_url, pdf_url
#   - `retrieval/qa.py::_extract_answer` doc: authors_joined, published,
#     categories_joined, summary
#   - `observability/quality.py` doc: age_days, summary
CLEAN_COLUMNS: tuple[str, ...] = (
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "text_for_embedding",
)

# Cot khong duoc null/rong o bat ky dong nao.
NON_EMPTY_COLUMNS: tuple[str, ...] = (
    "paper_id",
    "title",
    "summary",
    "published",
    "authors_joined",
    "categories_joined",
    "text_for_embedding",
)

# Cot metadata day thang vao Chroma — Chroma khong nhan None.
CHROMA_METADATA_COLUMNS: tuple[str, ...] = (
    "paper_id",
    "title",
    "published",
    "authors_joined",
    "categories_joined",
    "summary",
    "abs_url",
    "pdf_url",
)

MIN_CLEAN_ROWS = 5
MIN_SUMMARY_CHARS = 50
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
MARKUP = re.compile(r"<[a-zA-Z/][^>]*>")


@dataclass
class ContractResult:
    """Ket qua kiem contract. `blockers` chan pipeline, `warnings` thi khong."""

    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.blockers

    def render(self) -> str:
        lines = [f"clean contract: {'PASS' if self.passed else 'FAIL'}"]
        for key, value in self.stats.items():
            lines.append(f"  {key}: {value}")
        for item in self.blockers:
            lines.append(f"  [BLOCKER] {item}")
        for item in self.warnings:
            lines.append(f"  [WARN]    {item}")
        return "\n".join(lines)


def validate_clean_dataframe(
    df: pd.DataFrame,
    raw_record_count: int | None = None,
    run_date: datetime | None = None,
) -> ContractResult:
    """Kiem clean dataframe truoc khi cho phep index/test set.

    `raw_record_count` de doi chieu raw -> clean; bo qua neu khong truyen.
    """
    result = ContractResult()
    result.stats["clean_rows"] = int(len(df))
    if raw_record_count is not None:
        result.stats["raw_records"] = raw_record_count
        result.stats["dropped"] = raw_record_count - len(df)

    missing = [column for column in CLEAN_COLUMNS if column not in df.columns]
    if missing:
        result.blockers.append(f"thieu cot bat buoc: {missing}")
        return result  # thieu cot thi cac check sau vo nghia

    if len(df) < MIN_CLEAN_ROWS:
        result.blockers.append(f"chi co {len(df)} dong clean, toi thieu {MIN_CLEAN_ROWS}")

    for column in NON_EMPTY_COLUMNS:
        empty = int(df[column].isna().sum() + (df[column].astype(str).str.strip() == "").sum())
        if empty:
            result.blockers.append(f"cot `{column}` co {empty} dong null/rong")

    duplicated = int(df["paper_id"].duplicated().sum())
    if duplicated:
        result.blockers.append(f"`paper_id` trung {duplicated} dong - ground_truth_doc_ids se mo ho")

    bad_dates = df.loc[~df["published"].astype(str).str.match(ISO_DATE), "paper_id"].tolist()
    if bad_dates:
        result.blockers.append(f"`published` khong phai ISO YYYY-MM-DD o {len(bad_dates)} dong: {bad_dates[:3]}")

    for column in CHROMA_METADATA_COLUMNS:
        if df[column].isna().any():
            result.blockers.append(f"cot `{column}` con None - Chroma se tu choi metadata")

    with_markup = df.loc[df["summary"].astype(str).str.contains(MARKUP, na=False), "paper_id"].tolist()
    if with_markup:
        result.blockers.append(f"`summary` con tag markup o {len(with_markup)} dong: {with_markup[:3]}")

    if run_date is not None:
        # `errors="coerce"` de validator khong chet khi gap date hong - dong do
        # da bi bat o check ISO ben tren roi, o day chi bo qua.
        parsed = pd.to_datetime(df["published"], format="%Y-%m-%d", errors="coerce")
        comparable = parsed.notna()
        expected = (pd.Timestamp(run_date.date()) - parsed[comparable]).dt.days
        drift = int((expected != df.loc[comparable, "age_days"]).sum())
        if drift:
            result.blockers.append(f"`age_days` lech voi `published` o {drift} dong")

    negative_age = int((df["age_days"] < 0).sum())
    if negative_age:
        result.blockers.append(f"`age_days` am o {negative_age} dong - ngay xuat ban o tuong lai")

    # Canh bao: khong chan pipeline nhung anh huong do tin cay cua metric.
    short = int((df["summary"].astype(str).str.len() < MIN_SUMMARY_CHARS).sum())
    if short:
        result.warnings.append(f"{short} dong co summary < {MIN_SUMMARY_CHARS} ky tu")

    shared = df["categories_joined"].value_counts()
    shared = shared[shared > 1]
    if not shared.empty:
        affected = int(shared.sum())
        result.warnings.append(
            f"{affected}/{len(df)} dong dung chung gia tri `categories_joined` "
            f"({dict(shared.head(3))}) - cau hoi question_type=categories cua R4 se mo ho"
        )

    result.stats["unique_categories"] = int(df["categories_joined"].nunique())
    result.stats["blockers"] = len(result.blockers)
    result.stats["warnings"] = len(result.warnings)
    return result
