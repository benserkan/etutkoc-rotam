"""API v2 — Öğretmen kitap kütüphanesi (Dalga 3 Paket 8).

Kapsam:
  - Kitap CRUD + bölüm (section) yönetimi
  - AI ünite önerisi (Anthropic claude entegrasyonu, kredi denetimli)
  - Şablon CRUD + uygulama
  - Kitap seti (book set) CRUD
  - Öğrenci atama (toplu diff)
  - Yardımcı: erişilebilir konu/ders listeleri

Referans Jinja (dokunulmaz):
  - app/routes/teacher_books.py
  - app/routes/teacher_book_sets.py
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# =============================================================================
# Ortak tipler
# =============================================================================

BookTypeLiteral = Literal[
    "soru_bankasi",
    "fasikul",
    "konu_anlatimli",
    "brans_denemesi",
    "genel_deneme",
]


# =============================================================================
# Yardımcı listeleme (dropdown'lar için)
# =============================================================================


class SubjectRef(BaseModel):
    id: int
    name: str
    is_builtin: bool
    curriculum_model: str | None  # CurriculumModel.value veya None
    exam_section: str | None = None  # ExamSection.value (TYT/AYT_*) veya None
    min_grade_level: int | None
    max_grade_level: int | None
    available_for_graduate: bool


class SubjectListResponse(BaseModel):
    items: list[SubjectRef]


class TopicRef(BaseModel):
    id: int
    name: str
    subject_id: int
    is_builtin: bool
    order: int


class TopicListResponse(BaseModel):
    items: list[TopicRef]


# =============================================================================
# Müfredat eşleştirme (Faz 0) — kitap ünitesi → resmi konu
# =============================================================================


class MappingSuggestionRow(BaseModel):
    section_id: int
    label: str
    order: int
    current_topic_id: int | None = None
    current_topic_name: str | None = None
    suggested_topic_id: int | None = None
    suggested_topic_name: str | None = None
    source: str                        # "mapped" | "auto" | "ai" | "none"
    confidence: str | None = None      # "high" | "medium" | "low"


class MappingSuggestionsResponse(BaseModel):
    book_id: int
    book_name: str
    subject_name: str | None = None
    total_sections: int
    mapped_count: int                  # current_topic_id dolu olanlar
    suggested_count: int               # öneri üretilenler (auto+ai)
    ai_used: bool
    candidate_topics: list[TopicRef]   # eşleştirme için resmi konu listesi
    rows: list[MappingSuggestionRow]


class ApplyMappingItem(BaseModel):
    section_id: int
    topic_id: int | None = None        # None → eşlemeyi kaldır


class ApplyMappingBody(BaseModel):
    items: list[ApplyMappingItem]


class ApplyMappingResult(BaseModel):
    changed: int
    mapped_count: int
    total_sections: int


# =============================================================================
# Kitap listeleme + detay
# =============================================================================


class BookListItem(BaseModel):
    """Kitap listesi satırı — kart görünümünde göstermek için kompakt."""
    id: int
    name: str
    publisher: str | None
    type: BookTypeLiteral
    subject_id: int
    subject_name: str | None
    avg_questions_per_test: int | None
    target_grade_min: int | None
    target_grade_max: int | None
    target_graduate: bool
    section_count: int
    total_tests: int          # sum(test_count) — UI başlığı
    assigned_student_count: int
    created_at: datetime


class BookListResponse(BaseModel):
    items: list[BookListItem]
    total: int


class BookSectionItem(BaseModel):
    id: int
    label: str
    test_count: int
    order: int
    topic_id: int | None
    topic_name: str | None
    reserved_total: int           # tüm öğrencilerin rezervi toplamı
    completed_total: int          # tüm öğrencilerin tamamladığı toplamı
    has_progress: bool            # silinebilir mi (False → silinemez)


class AssignedStudentRef(BaseModel):
    student_id: int
    full_name: str
    has_progress: bool            # bu kitapta ilerlemesi var mı


class BookDetailResponse(BaseModel):
    id: int
    name: str
    publisher: str | None
    type: BookTypeLiteral
    subject_id: int
    subject_name: str | None
    avg_questions_per_test: int | None
    target_grade_min: int | None
    target_grade_max: int | None
    target_graduate: bool
    created_at: datetime
    sections: list[BookSectionItem]
    assigned_students: list[AssignedStudentRef]
    total_tests: int


# =============================================================================
# Kitap yazma body'leri
# =============================================================================


class BookCreateBody(BaseModel):
    name: str
    subject_id: int
    type: BookTypeLiteral
    publisher: str | None = None
    avg_questions_per_test: int | None = None
    target_grade_min: int | None = None
    target_grade_max: int | None = None
    target_graduate: bool = False
    template_id: int | None = None   # verilirse şablonun section'ları kopyalanır


class BookPatchBody(BaseModel):
    """None geçilen alanlar değişmez."""
    name: str | None = None
    publisher: str | None = None
    type: BookTypeLiteral | None = None
    subject_id: int | None = None
    avg_questions_per_test: int | None = None
    target_grade_min: int | None = None
    target_grade_max: int | None = None
    target_graduate: bool | None = None


# =============================================================================
# Section yazma body'leri
# =============================================================================


class SectionCreateBody(BaseModel):
    label: str
    test_count: int                  # ≥1
    topic_id: int | None = None


class SectionPatchBody(BaseModel):
    """Test sayısı rezerv+tamam altına düşemez (422 invalid_section_count)."""
    label: str | None = None
    test_count: int | None = None
    topic_id: int | None = None


class BulkCatalogTopicItem(BaseModel):
    topic_id: int
    test_count: int                  # ≥1; verilmezse book.avg_questions_per_test


class SectionsBulkFromCatalogBody(BaseModel):
    items: list[BulkCatalogTopicItem]


class BulkCatalogResult(BaseModel):
    added_count: int
    skipped_existing_count: int      # zaten ekli topic'ler atlandı


# =============================================================================
# AI suggest
# =============================================================================


class AiSuggestBody(BaseModel):
    """Mevcut Jinja akışıyla aynı: grade_hint opsiyonel; default kitabın target'ından türetilir."""
    grade_hint: str | None = None


class AiSuggestResult(BaseModel):
    added_section_count: int
    template_id: int                 # AI draft şablon olarak kaydedildi
    suggestions: list[BookSectionItem]   # eklenen bölümler (ID'li)


# =============================================================================
# Atamalar
# =============================================================================


class AssignmentsPatchBody(BaseModel):
    """Hedef öğrenci ID listesi — diff alınır:
    - Eksik olanlar atanır (StudentBook + SectionProgress satırları kurulur)
    - Listede olmayanlar (rezerv yok ise) atamadan çıkarılır
    - Rezerv olan ataması korunur, "skipped_with_progress" döner
    """
    student_ids: list[int]


class AssignmentsResult(BaseModel):
    assigned_count: int
    removed_count: int
    skipped_with_progress: list[int]   # rezervden ötürü kaldırılamayan öğrenci ID'leri


# =============================================================================
# Şablonlar
# =============================================================================


class BookTemplateListItem(BaseModel):
    id: int
    name: str
    type: BookTypeLiteral
    publisher: str | None
    subject_id: int | None
    subject_name: str | None
    target_grade_min: int | None
    target_grade_max: int | None
    target_graduate: bool
    is_ai_generated: bool
    is_verified: bool
    section_count: int
    created_at: datetime


class BookTemplateListResponse(BaseModel):
    items: list[BookTemplateListItem]
    total: int


class SaveAsTemplateBody(BaseModel):
    template_name: str | None = None   # boşsa book.name kullanılır


class ApplyTemplateBody(BaseModel):
    template_id: int
    overwrite: bool = False            # True ise mevcut sections silinir
                                       # (rezerv varsa 409 has_reservations)


class ApplyTemplateResult(BaseModel):
    added_count: int
    overwrote: bool


# =============================================================================
# Kitap setleri
# =============================================================================


class BookSetMemberRef(BaseModel):
    book_id: int
    book_name: str
    book_type: BookTypeLiteral
    subject_id: int
    subject_name: str | None
    order: int


class BookSetGradeBucket(BaseModel):
    """Bir kitap setinin atandığı öğrencilerin sınıf dağılımı (chip için).

    `grade_level` mezunlar için None, kayıtlı öğrenciler için 5-12. `label_tr`
    UI'da doğrudan gösterilir (ör. "8. sınıf", "Mezun").
    """
    grade_level: int | None
    is_graduate: bool
    label_tr: str
    student_count: int


class BookSetListItem(BaseModel):
    id: int
    name: str
    notes: str | None
    book_count: int
    student_count: int                            # distinct öğrenci sayısı
    grade_distribution: list[BookSetGradeBucket]  # sınıf bazlı sayım
    # Set'in hedef sınıf seviyesi (Book modelindekiyle aynı semantik;
    # NULL/NULL/False = "Tüm seviyeler")
    target_grade_min: int | None
    target_grade_max: int | None
    target_graduate: bool
    target_grade_label_tr: str                    # "5-8. sınıf" / "Lise (9-12)" / "Mezun" / "Tüm seviyeler"
    created_at: datetime


class BookSetListResponse(BaseModel):
    items: list[BookSetListItem]
    total: int


class BookSetAssignedStudent(BaseModel):
    """Bir setin detay sayfasında listelenen, set'teki kitaplardan en az birine
    atanmış öğrenci. `assigned_book_count` öğrencinin set'teki kaç kitabı
    aldığını gösterir; setin tamamı atalıysa `book_count` ile eşit.
    """
    student_id: int
    full_name: str
    grade_level: int | None
    is_graduate: bool
    is_active: bool
    grade_label_tr: str
    assigned_book_count: int


class BookSetDetailResponse(BaseModel):
    id: int
    name: str
    notes: str | None
    items: list[BookSetMemberRef]
    assigned_students: list[BookSetAssignedStudent]
    grade_distribution: list[BookSetGradeBucket]
    target_grade_min: int | None
    target_grade_max: int | None
    target_graduate: bool
    target_grade_label_tr: str
    created_at: datetime


class BookSetCreateBody(BaseModel):
    name: str
    notes: str | None = None
    target_grade_min: int | None = None
    target_grade_max: int | None = None
    target_graduate: bool = False


class BookSetPatchBody(BaseModel):
    name: str | None = None
    notes: str | None = None
    # Patch'te None ile "değiştirme"; min/max'i temizlemek isteyen
    # frontend ayrıca `clear_target_grade=True` gönderebilir (basit tutuldu,
    # öncelikle yeni değer ile overwrite kalıbı).
    target_grade_min: int | None = None
    target_grade_max: int | None = None
    target_graduate: bool | None = None
    clear_target_grade: bool = False


class AddBooksToSetBody(BaseModel):
    book_ids: list[int]


class AddBooksToSetResult(BaseModel):
    added_count: int
    skipped_existing_count: int


# =============================================================================
# Basit OK dönüşleri
# =============================================================================


class DeletedRef(BaseModel):
    deleted: bool
    id: int
