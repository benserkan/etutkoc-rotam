"""Yanlış Soru Arşivi — API v2 şemaları."""
from __future__ import annotations

from pydantic import BaseModel, Field


class WrongQuestionImageRef(BaseModel):
    id: int
    kind: str                 # question | solution
    content_type: str
    size_bytes: int


class WrongQuestionItem(BaseModel):
    id: int
    status: str               # acik | kapandi
    source_kind: str          # gorev | deneme | diger
    error_type: str | None
    error_type_label: str | None
    subject_id: int | None
    subject_name: str | None
    topic_id: int | None
    topic_name: str | None
    book_name: str | None
    section_label: str | None
    note: str | None
    coach_note: str | None
    ai_question_text: str | None
    ai_hint: str | None
    ai_tagged_at: str | None      # ISO — AI etiketlendi mi (buton gizlemek için)
    difficulty_guess: str | None
    correct_streak: int
    attempts_count: int
    due_at: str | None        # ISO — vade
    is_due: bool
    closed_at: str | None
    created_at: str
    images: list[WrongQuestionImageRef]


class WrongQuestionCountsOut(BaseModel):
    total: int
    open: int
    closed: int
    due: int


class WrongQuestionListResponse(BaseModel):
    items: list[WrongQuestionItem]
    counts: WrongQuestionCountsOut
    error_type_labels: dict[str, str]   # UI çipleri için sabit sözlük


class WrongQuestionCreateBody(BaseModel):
    """multipart olmayan (fotosuz) hızlı kayıt için JSON gövde."""
    source_kind: str | None = None
    book_section_id: int | None = None
    task_id: int | None = None
    exam_result_id: int | None = None
    subject_id: int | None = None
    topic_id: int | None = None
    error_type: str | None = None
    note: str | None = Field(default=None, max_length=2000)


class WrongQuestionUpdateBody(BaseModel):
    subject_id: int | None = None
    topic_id: int | None = None
    error_type: str | None = None
    note: str | None = Field(default=None, max_length=2000)
    clear_note: bool = False


class WrongQuestionAttemptBody(BaseModel):
    rating: int = Field(ge=1, le=4)   # 1=yine yanlış 2=zor 3=çözdüm 4=kolay


class CoachNoteBody(BaseModel):
    coach_note: str | None = Field(default=None, max_length=4000)


class TopicAccumulationOut(BaseModel):
    topic_id: int
    topic_name: str
    subject_name: str | None
    open_count: int
    closed_count: int


class AiTagResult(BaseModel):
    """AI etiketleme sonucu — kayıt + ne değiştiği."""
    item: WrongQuestionItem
    matched_topic: bool          # AI konuyu eşleyebildi mi
    hint_created: bool           # Sokratik ipucu üretildi mi
    credits_charged: int


class WrongQuestionSummaryResponse(BaseModel):
    counts: WrongQuestionCountsOut
    by_topic: list[TopicAccumulationOut]
    by_error_type: dict[str, int]
    error_type_labels: dict[str, str]
    closed_last_30d: int
    added_last_30d: int
