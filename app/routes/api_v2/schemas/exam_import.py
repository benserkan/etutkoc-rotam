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
    # okul-müfredat sınavında SUNUM grubu (sınıf dersinin adı — "TDE 21 +
    # TYT Türkçe 9" bölünmesi yerine tek "Türk Dili ve Edebiyatı"); None = yok
    display_subject: str | None = None
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


class AnalysisSectionOption(BaseModel):
    value: str
    label: str
    count: int                             # soru-satırlı deneme sayısı


class AnalysisExamMeta(BaseModel):
    id: int
    title: str
    exam_date: str
    net: float


class AnalysisCell(BaseModel):
    """Isı haritası hücresi — bir konunun BİR denemedeki performansı."""
    exam_id: int
    total: int
    correct: int
    wrong: int
    blank: int
    accuracy: float                        # 0..1


class AnalysisTopicRow(BaseModel):
    topic_id: int
    topic_name: str
    subject_name: str
    total: int
    correct: int
    wrong: int
    blank: int
    accuracy: float
    exams_seen: int
    cells: list[AnalysisCell]


class AnalysisOpportunity(BaseModel):
    """Net fırsatı: bu konu kapanırsa deneme başına kazanılabilecek net."""
    topic_id: int
    topic_name: str
    subject_name: str
    total: int
    wrong: int
    blank: int
    accuracy: float
    net_gain_per_exam: float


class AnalysisTrendTopic(BaseModel):
    """Unutulan/gelişen konu — ilk yarı ↔ son yarı doğruluk kıyası."""
    topic_id: int
    topic_name: str
    subject_name: str
    first_accuracy: float
    last_accuracy: float


class ExamTopicAnalysisResponse(BaseModel):
    section: str | None
    section_label: str | None
    section_options: list[AnalysisSectionOption]
    exams: list[AnalysisExamMeta]
    topics: list[AnalysisTopicRow]         # ısı haritası satırları (soru sayısı DESC)
    opportunities: list[AnalysisOpportunity]
    forgotten: list[AnalysisTrendTopic]
    improved: list[AnalysisTrendTopic]
    unmatched_questions: int
    analyzed_question_count: int


class WrongBridgeResult(BaseModel):
    """Deneme → Yanlış Soru Arşivi köprüsü sonucu (Faz 3, idempotent)."""
    created: int
    skipped_existing: int                  # daha önce aktarılmış (mükerrer değil)
    skipped_no_topic: int                  # konusuz satır (önce 'Satırları düzelt')
    total_wrong: int


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
