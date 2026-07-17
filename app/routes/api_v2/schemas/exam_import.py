"""Deneme PDF içe aktarma — API v2 şemaları (önizleme taslağı + onay)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ImportDraftRow(BaseModel):
    """Önizleme tablosunun bir soru satırı — her alan düzenlenebilir."""
    exam_part: str | None = None          # birleşik belgede oturum: tyt|ayt
    subject_raw: str | None = None
    subject_id: int | None = None
    subject_name: str | None = None
    question_no: int | None = None
    topic_raw: str | None = None
    topic_id: int | None = None
    topic_name: str | None = None
    topic_source: str | None = None       # alias|auto|ai|none
    correct_answer: str | None = None
    student_answer: str | None = None
    result: str | None = None             # dogru|yanlis|bos (None → şüpheli)
    is_suspect: bool = False


class ImportDraftSubject(BaseModel):
    name: str
    part: str | None = None               # birleşik belgede oturum: tyt|ayt
    questions: int
    correct: int
    wrong: int
    blank: int
    net: float
    doc_net: float | None = None          # belge kendi neti (çapraz kıyas)


class ImportPart(BaseModel):
    """Birleşik belgede (TG kitapçığı) bir sınav oturumu — koç birini seçip
    kaydeder; ikisini isterse iki ayrı içe aktarma yapar (kredi 1 kez düşer,
    çünkü analiz tek)."""
    part: str | None = None               # tyt|ayt (tek sınavlı belgede None)
    section: str
    section_label: str
    question_count: int


class ImportCheck(BaseModel):
    code: str
    label: str
    ok: bool
    detail: str | None = None


class ImportMatchStats(BaseModel):
    alias: int
    auto: int
    ai: int
    none: int


class SectionChoice(BaseModel):
    value: str
    label: str


class TopicChoice(BaseModel):
    """Önizlemede konu düzeltme seçicisinin adayları (evrenin resmi konuları)."""
    id: int
    name: str
    subject_name: str


class ExamImportDraft(BaseModel):
    """analyze çıktısı — önizleme ekranının tamamı."""
    title: str | None
    exam_date: str | None
    grade_hint: int | None
    universe: str                          # tyt|ayt|lgs|okul
    section: str
    section_label: str
    scope: str                             # full|brans
    confidence: str                        # high|medium|low
    parts: list[ImportPart]                # >1 ise birleşik belge (oturum seçici)
    subjects: list[ImportDraftSubject]
    rows: list[ImportDraftRow]
    checks: list[ImportCheck]
    suspect_count: int
    match_stats: ImportMatchStats
    duplicate_exam_id: int | None
    score_info: dict[str, Any] | None
    topic_choices: list[TopicChoice]       # konu düzeltme seçicisi adayları
    section_choices: list[SectionChoice]   # tür seçici (düşük güvende öne çıkar)
    credits_charged: int


class ConfirmRow(BaseModel):
    """Onay gövdesindeki satır — önizlemede düzeltilmiş hali."""
    subject_raw: str | None = None
    question_no: int | None = None
    topic_raw: str | None = None
    topic_id: int | None = None
    correct_answer: str | None = Field(default=None, max_length=8)
    student_answer: str | None = Field(default=None, max_length=8)
    result: str                            # dogru|yanlis|bos
    is_suspect: bool = False
    manually_edited: bool = False


class ExamImportConfirmBody(BaseModel):
    title: str
    exam_date: str                         # ISO YYYY-MM-DD
    section: str
    scope: str | None = None
    grade_hint: int | None = None
    note: str | None = Field(default=None, max_length=500)
    force: bool = False                    # mükerrer uyarısına rağmen kaydet
    score_info: dict[str, Any] | None = None
    rows: list[ConfirmRow]


class ExamImportConfirmResult(BaseModel):
    exam_id: int
    title: str
    exam_date: str
    section: str
    section_label: str
    net: float
    total_correct: int
    total_wrong: int
    total_blank: int
    question_count: int
    matched_topic_count: int               # konuya bağlanan soru (birikime girer)
    wrong_topic_ids: list[int]             # Faz 3 YSA köprüsü için hazır veri
