from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.book import Book, BookSection


class ExamSection(str, enum.Enum):
    """Dersin sınavda yer aldığı bölüm.

    - LGS: 8. sınıf sınavının bir bölümü (Türkçe, Matematik, Fen, T.C. İnk., Din, İng.)
    - TYT: YKS Temel Yeterlilik (herkes girer): TR, Mat, Fen, Sosyal
    - AYT_SAY/AYT_EA/AYT_SOZ/AYT_DIL: YKS Alan Yeterliği — alana göre değişir
    """
    LGS = "lgs"
    TYT = "tyt"
    AYT_SAY = "ayt_say"
    AYT_EA = "ayt_ea"
    AYT_SOZ = "ayt_soz"
    AYT_DIL = "ayt_dil"


EXAM_SECTION_LABELS: dict[ExamSection, str] = {
    ExamSection.LGS: "LGS",
    ExamSection.TYT: "TYT",
    ExamSection.AYT_SAY: "AYT (Sayısal)",
    ExamSection.AYT_EA: "AYT (Eşit Ağırlık)",
    ExamSection.AYT_SOZ: "AYT (Sözel)",
    ExamSection.AYT_DIL: "AYT (Dil)",
}


class CurriculumModel(str, enum.Enum):
    """Müfredat modeli — Türkiye'nin Maarif geçişine duyarlı.

    LGS         : 5-8 LGS müfredatı (mevcut sistem)
    KLASIK_LISE : Maarif öncesi 9-12 lise müfredatı; 2024'ten önce 9'a
                  başlamış kohortlar tarafından kullanılır.
    MAARIF_LISE : Maarif Modeli 9-12 lise müfredatı; 2024-25 öğretim
                  yılında 9'a başlayan ilk kohorttan itibaren uygulanır.

    Kohort kuralı (2026-05-08 itibariyle):
        - 2024 ve sonrası 9'a başlayan: tüm okul hayatı boyunca MAARIF_LISE
        - 2023'te 9'a başlayan: 9-10 KLASIK, 11-12 KLASIK (son nesil)
        - Eylül 2026'dan sonra 11. sınıfa kalan klasik öğrenci olamaz
        - Eylül 2027'den sonra 12. sınıfa kalan klasik öğrenci olamaz
    """
    LGS = "lgs"
    KLASIK_LISE = "klasik_lise"
    MAARIF_LISE = "maarif_lise"


CURRICULUM_MODEL_LABELS: dict[CurriculumModel, str] = {
    CurriculumModel.LGS: "LGS Müfredatı",
    CurriculumModel.KLASIK_LISE: "Klasik Lise Müfredatı",
    CurriculumModel.MAARIF_LISE: "Maarif Modeli",
}


# Maarif Modeli'nin 9. sınıfta ilk uygulandığı öğretim yılı.
# 2024-25 yılında 9'a başlayan ilk Maarif kohortu.
MAARIF_FIRST_GRADE9_YEAR = 2024


def derive_curriculum_model(
    *,
    grade_level: int | None,
    is_graduate: bool = False,
    entry_year_grade9: int | None = None,
    academic_year_start: int | None = None,
) -> CurriculumModel | None:
    """Öğrencinin müfredat modelini türetir.

    Tasarım (2026-05-08, butik dershane bağlamı):
    - Sistem koçluk/butik dershane içindir; öğrenciler ad-hoc kayıt olur
      ve geçmişleri bilinmeyebilir.
    - **Geçmişe ihtiyaç yok**: akademik yıl + şu anki sınıf zaten
      implicit olarak kohortu söyler (sınıf tekrarı yok varsayımıyla):
        • 2026-2027 + 11 → 9'a 2024'te girdi → MAARIF
        • 2026-2027 + 12 → 9'a 2023'te girdi → KLASİK (son nesil)
        • 2027-2028 + 11 → 9'a 2025'te girdi → MAARIF

    Kural sırası:
      1. 5-8 → LGS (her zaman, kohort gerek yok)
      2. 9-10 → MAARIF_LISE (2024-25'ten beri Maarif; tüm 9-10'lar
         Maarif kohortunda — geçmiş 9'lar artık 11+ oldu)
      3. 11-12 ve mezun → kohort gerekli:
         a) entry_year_grade9 verildiyse onu kullan (override)
         b) yoksa academic_year_start + grade_level'dan tahmin et:
            - mezun: entry = academic_year_start - 4 (geçen yıl 12'ydi)
            - 11/12: entry = academic_year_start - (grade - 9)
         c) hiçbiri yoksa None döndür (UI uyarı verecek)

    Returns: model veya None (yetersiz bilgi).
    """
    if grade_level is None and not is_graduate:
        return None
    if not is_graduate and grade_level is not None and grade_level <= 8:
        return CurriculumModel.LGS
    # 9-10 her zaman Maarif (geçmiş kohort artık 11+ olmuş durumda)
    if not is_graduate and grade_level in (9, 10):
        return CurriculumModel.MAARIF_LISE

    # 11, 12 veya mezun → kohort gerekli
    effective_entry = entry_year_grade9
    if effective_entry is None and academic_year_start is not None:
        if is_graduate:
            # Mezun: geçen öğretim yılında 12'ydi → 4 yıl önce 9'a girdi
            effective_entry = academic_year_start - 4
        elif grade_level is not None:
            effective_entry = academic_year_start - (grade_level - 9)

    if effective_entry is None:
        return None

    return (
        CurriculumModel.MAARIF_LISE
        if effective_entry >= MAARIF_FIRST_GRADE9_YEAR
        else CurriculumModel.KLASIK_LISE
    )


def estimate_entry_year_grade9(
    *, current_grade: int | None, academic_year_start: int
) -> int | None:
    """Mevcut sınıf ve öğretim yılı başlangıcından 9. sınıfa giriş yılını
    tahmin eder.

    `academic_year_start` = öğretim yılının Eylül-yılı (örn 2025-26 → 2025).
    9. sınıf öğrencisi öğretim yılı başında o yıla başlamış sayılır.
    """
    if current_grade is None or current_grade < 9 or current_grade > 12:
        return None
    return academic_year_start - (current_grade - 9)


class Subject(Base):
    __tablename__ = "subjects"
    # Aynı ders adı (örn "Matematik") farklı müfredat modellerinde paralel
    # yaşayabilmeli — LGS Mat, Klasik Lise Mat, Maarif Lise Mat ayrı kayıtlar.
    __table_args__ = (
        UniqueConstraint(
            "teacher_id", "name", "curriculum_model",
            name="uq_subject_teacher_name_model",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    # Dersin geçtiği seviye aralığı. NULL = belirtilmedi (tüm seviyelere aday).
    # Karar (2026-05-08): Range yaklaşımı — Mat 5-12, Felsefe 10-11, Tarih 9-12.
    min_grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Bu ders mezun YKS programında da kullanılıyor mu (12. sınıfla aynı içerik).
    available_for_graduate: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    # YKS sınavının hangi bölümünde — TYT veya AYT_X. LGS dersleri için ExamSection.LGS.
    # NULL: sınav-bağımsız (örn. ek seçmeli dersler).
    exam_section: Mapped[ExamSection | None] = mapped_column(
        Enum(ExamSection), nullable=True
    )
    # Hangi müfredat modeline ait. NULL = model-bağımsız (örn dil dersleri,
    # her modelde aynı içerik). Aynı ders adı (Matematik) farklı modellerde
    # ayrı Subject kayıtlarıyla yaşar — Topic listeleri farklıdır.
    curriculum_model: Mapped[CurriculumModel | None] = mapped_column(
        Enum(CurriculumModel), nullable=True
    )

    topics: Mapped[list["Topic"]] = relationship(
        "Topic", back_populates="subject", cascade="all, delete-orphan",
        order_by="Topic.order",
    )
    books: Mapped[list["Book"]] = relationship("Book", back_populates="subject")

    def covers_grade(self, grade: int | None, *, is_graduate: bool = False) -> bool:
        """Bu ders verilen sınıfta veya mezun için kullanılabilir mi?"""
        if is_graduate:
            return self.available_for_graduate
        if grade is None:
            return self.min_grade_level is None and self.max_grade_level is None
        if self.min_grade_level is None and self.max_grade_level is None:
            return True
        lo = self.min_grade_level if self.min_grade_level is not None else 1
        hi = self.max_grade_level if self.max_grade_level is not None else 99
        return lo <= grade <= hi

    def __repr__(self) -> str:
        return f"<Subject {self.name}>"


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Konu hangi sınıfa ait. NULL = sınıf-bağımsız (nadir; örn ortak terim listesi).
    # Mevcut seed data 8 değerine sahip; migration backfill ile geriye uyum.
    grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # Hangi müfredat modeline ait. NULL = model-bağımsız.
    # Aynı konu adı farklı modellerde ayrı kayıtlarla yaşar (içerikler farklı).
    curriculum_model: Mapped[CurriculumModel | None] = mapped_column(
        Enum(CurriculumModel), nullable=True
    )

    subject: Mapped["Subject"] = relationship("Subject", back_populates="topics")
    parent: Mapped["Topic | None"] = relationship(
        "Topic", remote_side="Topic.id", backref="children"
    )
    sections: Mapped[list["BookSection"]] = relationship("BookSection", back_populates="topic")

    def __repr__(self) -> str:
        return f"<Topic {self.name}>"
