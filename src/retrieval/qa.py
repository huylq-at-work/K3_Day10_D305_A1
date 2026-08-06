from __future__ import annotations

from dataclasses import dataclass
import re

from core.config import Settings
from core.utils import first_sentence
from retrieval.index import LocalEmbeddingIndex, SearchResult


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_contexts: list[str]
    retrieved_titles: list[str]


# Test set cua lab duoc sinh bang tieng Viet, nen router phai nhan ca hai ngon ngu.
# Chi nhan dien them - moi cum tieng Anh cu deu giu nguyen.
_AUTHOR_CUES = ("who authored", "list the authors", "tac gia", "tác giả")
_DATE_CUES = ("when was", "publication date", "published on", "xuat ban", "xuất bản", "ngay cong bo", "ngày công bố")
_CATEGORY_CUES = ("what categories", "linh vuc", "lĩnh vực", "chuyen muc", "chuyên mục", "danh muc", "danh mục")


def _extract_answer(question: str, top_result: SearchResult) -> str:
    lowered = question.lower()
    metadata = top_result.metadata
    if any(cue in lowered for cue in _AUTHOR_CUES):
        return metadata["authors_joined"]
    if any(cue in lowered for cue in _DATE_CUES):
        return metadata["published"]
    if any(cue in lowered for cue in _CATEGORY_CUES):
        return metadata["categories_joined"]
    return first_sentence(metadata["summary"])


def answer_question(question: str, settings: Settings, index: LocalEmbeddingIndex, top_k: int | None = None) -> AnswerResult:
    title_match = re.search(r"'([^']+)'", question)
    exact = index.lookup(title_match.group(1)) if title_match else None
    retrieved = index.search(question, top_k=top_k)
    if exact:
        exact_result = SearchResult(
            paper_id=exact["paper_id"],
            title=exact["title"],
            score=1.0,
            content=exact["content"],
            metadata=exact["metadata"],
        )
        deduped = [exact_result] + [item for item in retrieved if item.paper_id != exact_result.paper_id]
        retrieved = deduped[: (top_k or settings.top_k)]
    if not retrieved:
        answer = "I don't know from the indexed corpus."
    else:
        answer = _extract_answer(question, retrieved[0])
    return AnswerResult(
        question=question,
        answer=answer,
        retrieved_doc_ids=[item.paper_id for item in retrieved],
        retrieved_contexts=[item.content for item in retrieved],
        retrieved_titles=[item.title for item in retrieved],
    )
