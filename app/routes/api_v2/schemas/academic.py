"""API v2 — Akademik yıl + dönem + sınıf yükseltme + CSV (Dalga 3 Paket 10).

Kapsam:
  - /api/v2/teacher/academic            : Akademik yıl + faz CRUD + öğrenci atama
  - /api/v2/teacher/grade-advance       : Toplu sınıf yükseltme preview + apply +
                                          tekil reset-program (çift onay)
  - /api/v2/teacher/csv                 : CSV import (preview→commit), CSV export

Referans Jinja (dokunulmaz):
  - app/routes/teacher_years.py
  - app/routes/teacher_students.py (promote + import akışları)
  - app/services/csv_import.py (parse + bulk_create_students)
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


# =============================================================================
# Academic year + phase
# =============================================================================


PhaseKindLiteral = Literal[
    "regular", "winter_break", "summer_camp", "exam_prep",
]

ExamTargetLiteral = Literal["lgs", "yks", "none"]


class PhaseItem(BaseModel):
    id: int
    name: str
    start_date: date
    end_date: date
    kind: PhaseKindLiteral
    kind_label: str
    kind_badge: str
    notes: str | None
    capacity_multiplier: float
    is_no_school: bool


class AcademicYearListItem(BaseModel):
    id: int
    name: str
    start_year: int | None
    exam_target: ExamTargetLiteral
    exam_label: str
    is_active: bool
    phase_count: int
    student_count: int
    created_at: datetime


class AcademicYearListResponse(BaseModel):
    items: list[AcademicYearListItem]
    current_start_year: int          # Eylül-Ağustos ekseninde bugünün yılı


class AcademicYearAssignedStudent(BaseModel):
    student_id: int
    full_name: str
    grade_level: int | None
    is_graduate: bool


class AcademicYearDetailResponse(BaseModel):
    id: int
    name: str
    start_year: int | None
    exam_target: ExamTargetLiteral
    exam_label: str
    is_active: bool
    created_at: datetime
    phases: list[PhaseItem]
    assigned_students: list[AcademicYearAssignedStudent]


class AcademicYearCreateBody(BaseModel):
    """name otomatik 'YYYY-(YYYY+1)' üretilir; start_year < 2020 veya > 2050 → 422."""
    start_year: int                  # 2020..2050


class AcademicYearPatchBody(BaseModel):
    name: str | None = None
    start_year: int | None = None
    exam_target: ExamTargetLiteral | None = None
    is_active: bool | None = None


class PhaseCreateBody(BaseModel):
    name: str
    start_date: date
    end_date: date
    kind: PhaseKindLiteral = "regular"
    notes: str | None = None


class PhasePatchBody(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    kind: PhaseKindLiteral | None = None
    notes: str | None = None


class AcademicYearAssignBody(BaseModel):
    """Diff atama:
    - Listede olup şu an başka yılda olan öğrenciler bu yıla taşınır
    - Listede olmayan ama şu an bu yılda olan öğrenciler academic_year_id=NULL
    - Zaten bu yılda olanlar değişmez
    """
    student_ids: list[int]


class AcademicYearAssignResult(BaseModel):
    assigned_count: int              # bu yıla yeni eklendi/değişti
    removed_count: int               # bu yıldan çıkarıldı (NULL'a düştü)
    unchanged_count: int


class AcademicYearListChoiceItem(BaseModel):
    """Yıl seçim listesi — UI'da hızlı 'şu yılı oluştur' butonu için."""
    start_year: int
    name: str
    label: str                       # "2026-2027 · şu an"
    exists: bool


class AcademicYearChoicesResponse(BaseModel):
    items: list[AcademicYearListChoiceItem]
    current_start_year: int


# =============================================================================
# Grade advance — toplu sınıf yükseltme + tekil reset-program
# =============================================================================


GraduateModeLiteral = Literal["full_time", "dershane"]
TrackLiteral = Literal["sayisal", "ea", "sozel", "dil"]


class GradeAdvancePreviewItem(BaseModel):
    student_id: int
    full_name: str
    current_grade_level: int | None
    current_is_graduate: bool
    current_academic_year_id: int | None
    current_academic_year_name: str | None
    suggested_grade_level: int | None
    suggested_is_graduate: bool
    requires_track: bool
    has_track: bool
    has_reservations: bool           # SectionProgress.reserved_count > 0
    has_completed_progress: bool     # SectionProgress.completed_count > 0
    blocker_notes: list[str]         # UI'da uyarı şeritleri


class GradeAdvancePreviewResponse(BaseModel):
    students: list[GradeAdvancePreviewItem]
    suggested_year_id: int | None    # Bir sonraki AY (varsa)
    suggested_year_name: str | None


class GradeAdvanceApplyItem(BaseModel):
    student_id: int
    new_grade_level: int | None      # None ile mezun
    new_is_graduate: bool
    new_track: TrackLiteral | None = None
    new_graduate_mode: GraduateModeLiteral | None = None


class GradeAdvanceApplyBody(BaseModel):
    items: list[GradeAdvanceApplyItem]
    target_academic_year_id: int | None = None   # tüm öğrenciler için (set/None)


class GradeAdvanceApplyResult(BaseModel):
    advanced_count: int
    skipped_invalid: list[str]                    # öğrenci adı + sebep
    skipped_track_missing: list[str]
    preserved_reservations_count: int             # değişmedi (rezerv koruma garantisi)


class ResetProgramConfirmBody(BaseModel):
    """Geri dönülemez veri kaybı — full_name yazılarak çift onay gelir."""
    confirm_full_name: str           # öğrenci.full_name ile birebir eşleşmeli


class ResetProgramResult(BaseModel):
    student_id: int
    deleted_tasks: int
    deleted_task_book_items: int
    cleared_reservations: int
    deleted_suggestion_feedback: int


# =============================================================================
# CSV import (preview → commit) + export
# =============================================================================


class CsvParseError(BaseModel):
    row_num: int                     # 1-indexed (header hariç)
    field: str | None = None
    message: str


class CsvParsedRow(BaseModel):
    row_num: int
    full_name: str | None
    email: str | None
    grade_level: int | None
    track: TrackLiteral | None
    is_graduate: bool
    graduate_mode: GraduateModeLiteral | None
    is_valid: bool
    errors: list[str]
    warnings: list[str]
    raw: dict


class CsvPreviewResponse(BaseModel):
    rows: list[CsvParsedRow]
    valid_count: int
    invalid_count: int
    header_errors: list[str]         # fatal — commit edilemez
    total_rows: int


class CsvCommitBody(BaseModel):
    """Önizleme sırasında validate edilen CSV metni aynen gönderilir.

    Server commit aşamasında YENİDEN parse + validate eder (tampered önler);
    sadece valid satırlar yaratılır.
    """
    csv_text: str


class CsvCreatedStudent(BaseModel):
    row_num: int
    student_id: int
    full_name: str
    email: str
    grade_label: str
    temp_password: str               # Tek seferlik — UI gösterimi sonrası unutulur


class CsvCommitResult(BaseModel):
    created: list[CsvCreatedStudent]
    skipped_existing_email: list[CsvParsedRow]
    skipped_invalid: list[CsvParsedRow]
    created_count: int
    skipped_count: int
    header_errors: list[str]         # fatal (kuota vs)
