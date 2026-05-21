"""Hedef ağacı veriden besleme servisi.

Bu modül "öğrencinin gerçek soru çözüm verisi → hedef ağacındaki ilerleme"
köprüsünü kurar. Mantığı:

- **TOPIC seviyesi** (BookSection bazlı hedef): öğrencinin o bölümden çözdüğü
  test sayısı (`SectionProgress.completed_count`) / hedef test sayısı
  (`BookSection.test_count` varsa o, yoksa `DEFAULT_TOPIC_TARGET = 50` soru
  yerine `DEFAULT_TOPIC_TESTS = 5` test). Çıktı 0-100 yüzde.

- **SUBJECT seviyesi** (Ders bazlı): o derse ait kitapların `SectionProgress`
  verisinden toplu hesap. Bölüm bazlı tamamlama oranlarının ağırlıklı
  ortalaması (her bölümün test_count'una göre ağırlık).

Mevcut sistem zaten:
- Görev tamamlanınca `task_service.complete_task` → `SectionProgress.completed_count` artar
- `SectionProgress` öğrenci × kitap_bölümü kanonik tablo
- `BookSection.test_count` bölümdeki toplam test sayısı (kitap envanterinden)

Bu yüzden goal tree'de `current_value` elle form yerine bu hesaplamadan gelir.
Sonuç: 'Türkçe %72 tamam' demek 'müfredat test havuzunun %72'si bitti' demek;
herhangi bir uydurma `target=20 net` ile karışmıyor.

Önemli: bu servis hedef değerlerini *hesaplar*; veritabanına yazmaz. Build_tree
çağırırken on-demand çağrılır. Performansa darboğaz olursa cache eklenebilir.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    User,
)


logger = logging.getLogger(__name__)


# Bölüm test sayısı tanımlı değilse varsayılan eşik
DEFAULT_SECTION_TESTS = 5  # ~50 soru ≈ test başına ortalama 10 soru


@dataclass
class TopicProgress:
    """Tek BookSection için ilerleme — TOPIC hedefi için kullanılır."""
    section_id: int
    section_label: str
    book_id: int
    book_name: str
    subject_id: int | None
    subject_name: str | None
    completed_tests: int
    target_tests: int

    @property
    def progress_pct(self) -> int:
        if self.target_tests <= 0:
            return 0
        return min(100, round(100 * self.completed_tests / self.target_tests))


@dataclass
class SubjectProgress:
    """Ders bazlı ilerleme — SUBJECT hedefi için kullanılır.

    Bir öğrencinin o dersteki tüm BookSection'larının ağırlıklı ortalaması.
    """
    subject_id: int
    subject_name: str
    topics: list[TopicProgress]

    @property
    def total_completed(self) -> int:
        return sum(t.completed_tests for t in self.topics)

    @property
    def total_target(self) -> int:
        return sum(t.target_tests for t in self.topics)

    @property
    def progress_pct(self) -> int:
        if self.total_target <= 0:
            return 0
        return min(100, round(100 * self.total_completed / self.total_target))


def _section_target(section: BookSection) -> int:
    """Bir bölümün hedef test sayısı.

    `BookSection.test_count` envanterden gelir (kitabın gerçek test havuzu);
    sıfır veya çok düşükse `DEFAULT_SECTION_TESTS` kullanılır (kitap envanteri
    henüz girilmemiş olabilir).
    """
    if section.test_count and section.test_count > 0:
        return section.test_count
    return DEFAULT_SECTION_TESTS


def list_active_topic_progress(
    db: Session, *, student_id: int,
) -> list[TopicProgress]:
    """Öğrencinin aktif `BookSection`'larındaki ilerleme listesi.

    "Aktif" = öğrenci o bölüme bağlı en az bir Task verilmiş veya
    `SectionProgress` kaydı oluşmuş bölümler. Henüz programa girmemiş
    kitap bölümleri ağaca düşmez (kalabalıklık yapmasın).
    """
    # 1) SectionProgress'ı olan tüm bölümler (öğrenci kitap atamış + en az 1
    #    test rezerve veya tamamlamış)
    sp_rows = (
        db.query(SectionProgress, StudentBook, Book, BookSection, Subject)
        .join(StudentBook, SectionProgress.student_book_id == StudentBook.id)
        .join(Book, StudentBook.book_id == Book.id)
        .join(BookSection, SectionProgress.book_section_id == BookSection.id)
        .join(Subject, Book.subject_id == Subject.id)
        .filter(StudentBook.student_id == student_id)
        .all()
    )

    # Aynı section birden fazla kitapta görünebilir; section_id bazında topla.
    by_section: dict[int, TopicProgress] = {}
    for sp, sb, book, section, subject in sp_rows:
        target = _section_target(section)
        completed = sp.completed_count
        if completed <= 0 and sp.reserved_count <= 0:
            # Tamamen boş kayıtlar — gizle
            continue
        existing = by_section.get(section.id)
        if existing is not None:
            existing.completed_tests += completed
            existing.target_tests += target
        else:
            by_section[section.id] = TopicProgress(
                section_id=section.id,
                section_label=section.label,
                book_id=book.id,
                book_name=book.name,
                subject_id=subject.id if subject else None,
                subject_name=subject.name if subject else None,
                completed_tests=completed,
                target_tests=target,
            )

    # 2) Görev verilmiş ama SectionProgress oluşturulmamış bölümler
    #    (genelde olmuyor — task_service her görev için _get_progress
    #    çağırıyor; yine de defansif)
    task_rows = (
        db.query(TaskBookItem, Book, BookSection, Subject)
        .join(Task, TaskBookItem.task_id == Task.id)
        .join(Book, TaskBookItem.book_id == Book.id)
        .join(BookSection, TaskBookItem.book_section_id == BookSection.id)
        .join(Subject, Book.subject_id == Subject.id)
        .filter(Task.student_id == student_id)
        .all()
    )
    for item, book, section, subject in task_rows:
        if section.id in by_section:
            continue
        target = _section_target(section)
        by_section[section.id] = TopicProgress(
            section_id=section.id,
            section_label=section.label,
            book_id=book.id,
            book_name=book.name,
            subject_id=subject.id if subject else None,
            subject_name=subject.name if subject else None,
            completed_tests=item.completed_count,
            target_tests=target,
        )

    return sorted(
        by_section.values(),
        key=lambda t: (t.subject_name or "", t.section_label),
    )


def compute_subject_progress(
    topics: Iterable[TopicProgress],
) -> list[SubjectProgress]:
    """TOPIC listesini ders bazlı grupla, her ders için toplam ilerleme."""
    by_subject: dict[int, SubjectProgress] = {}
    for t in topics:
        if t.subject_id is None:
            continue
        sp = by_subject.get(t.subject_id)
        if sp is None:
            sp = SubjectProgress(
                subject_id=t.subject_id,
                subject_name=t.subject_name or "(ders)",
                topics=[],
            )
            by_subject[t.subject_id] = sp
        sp.topics.append(t)
    # subject_name'e göre alfabetik
    return sorted(by_subject.values(), key=lambda s: s.subject_name)


def compute_overall_progress(subjects: Iterable[SubjectProgress]) -> int:
    """Tüm derslerin ortalaması — sınav genel ilerlemesi."""
    pcts = [s.progress_pct for s in subjects if s.total_target > 0]
    if not pcts:
        return 0
    return round(sum(pcts) / len(pcts))
