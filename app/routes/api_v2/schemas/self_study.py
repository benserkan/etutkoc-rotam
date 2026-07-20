"""Bağımsız çalışma kayıtları — API v2 şemaları (öğrenci + koç ortak)."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class SelfStudyEntryItem(BaseModel):
    id: int
    student_book_id: int
    book_id: int
    book_name: str
    subject_name: str
    section_id: int
    section_label: str
    test_count: int
    applied_count: int
    source: str                  # student | coach
    source_label: str
    status: str                  # pending | approved | rejected
    status_label: str
    note: str | None
    period_start: str | None     # ISO date
    period_end: str | None
    created_by_name: str | None
    created_at: str              # ISO
    reviewed_at: str | None
    review_note: str | None


class SelfStudyListResponse(BaseModel):
    items: list[SelfStudyEntryItem]
    pending_count: int


class SelfStudyCreateItem(BaseModel):
    student_book_id: int
    section_id: int
    test_count: int = Field(ge=1, le=1000)


class SelfStudyCreateBody(BaseModel):
    items: list[SelfStudyCreateItem] = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=500)
    period_start: date | None = None
    period_end: date | None = None


class SelfStudySkippedItem(BaseModel):
    section_id: int
    section_label: str
    reason: str


class SelfStudyCreateResult(BaseModel):
    created: list[SelfStudyEntryItem]
    skipped: list[SelfStudySkippedItem]
    applied_total: int           # ilerlemeye gerçekten işlenen toplam test
    pending_total: int           # onay bekleyen toplam test (öğrenci beyanı)


class SelfStudyReviewBody(BaseModel):
    approve: bool
    review_note: str | None = Field(default=None, max_length=500)


class SelfStudyDeleteResult(BaseModel):
    deleted_id: int
    reverted_count: int          # ilerlemeden geri alınan test


# --- Öğrenci beyan dialogu için kitap/bölüm seçenekleri ---


class SelfStudyOptionSection(BaseModel):
    section_id: int
    label: str
    test_count: int
    completed_count: int
    reserved_count: int
    remaining: int


class SelfStudyOptionBook(BaseModel):
    student_book_id: int
    book_id: int
    book_name: str
    subject_name: str
    book_type_label: str
    sections: list[SelfStudyOptionSection]


class SelfStudyOptionsResponse(BaseModel):
    books: list[SelfStudyOptionBook]
