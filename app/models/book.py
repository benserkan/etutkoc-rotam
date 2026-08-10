from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.curriculum import Subject, Topic
    from app.models.progress import StudentBook
    from app.models.user import User


class BookType(str, enum.Enum):
    SORU_BANKASI = "soru_bankasi"
    FASIKUL = "fasikul"
    KONU_ANLATIMLI = "konu_anlatimli"
    BRANS_DENEMESI = "brans_denemesi"
    GENEL_DENEME = "genel_deneme"


BOOK_TYPE_LABELS: dict[BookType, str] = {
    BookType.SORU_BANKASI: "Soru Bankası",
    BookType.FASIKUL: "Fasikül",
    BookType.KONU_ANLATIMLI: "Konu Anlatımlı",
    BookType.BRANS_DENEMESI: "Branş Denemesi",
    BookType.GENEL_DENEME: "Genel Deneme",
}


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[BookType] = mapped_column(Enum(BookType), nullable=False)
    avg_questions_per_test: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Kitabın hedef sınıf seviyesi aralığı. NULL = belirtilmedi (genel kullanım).
    # Karar (2026-05-08): Range yaklaşımı — "9-10 ortak" gibi yaygın senaryolar.
    target_grade_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_grade_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Mezun YKS hazırlığında da kullanılabilir mi (genelde 12. sınıf kitapları).
    target_graduate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(
        "User", back_populates="owned_books", foreign_keys=[teacher_id]
    )
    subject: Mapped["Subject"] = relationship("Subject", back_populates="books")
    sections: Mapped[list["BookSection"]] = relationship(
        "BookSection", back_populates="book", cascade="all, delete-orphan",
        order_by="BookSection.order",
    )
    student_books: Mapped[list["StudentBook"]] = relationship(
        "StudentBook", back_populates="book", cascade="all, delete-orphan"
    )

    @property
    def total_tests(self) -> int:
        return sum(s.test_count for s in self.sections)

    def targets_grade(self, grade: int | None, *, is_graduate: bool = False) -> bool:
        """Kitap verilen sınıf veya mezun için uygun mu?

        - Hiç hedef belirtilmemişse (hepsi NULL/False) → her seviyeye uygun.
        - is_graduate=True ise sadece target_graduate=True olan kitaplar.
        - Sayısal sınıf için min/max aralığı kontrol edilir.
        """
        no_targets = (
            self.target_grade_min is None
            and self.target_grade_max is None
            and not self.target_graduate
        )
        if no_targets:
            return True
        if is_graduate:
            return self.target_graduate
        if grade is None:
            return False
        lo = self.target_grade_min if self.target_grade_min is not None else 1
        hi = self.target_grade_max if self.target_grade_max is not None else 99
        return lo <= grade <= hi

    def __repr__(self) -> str:
        return f"<Book {self.name} ({self.type.value})>"


class BookSection(Base):
    __tablename__ = "book_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    test_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    book: Mapped["Book"] = relationship("Book", back_populates="sections")
    topic: Mapped["Topic | None"] = relationship("Topic", back_populates="sections")

    def __repr__(self) -> str:
        return f"<BookSection {self.label} x{self.test_count}>"


class BookSet(Base):
    __tablename__ = "book_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hedef sınıf seviyesi — Book modelindekiyle aynı semantik. NULL/NULL/False
    # birleşimi = "Tüm seviyeler" (set tüm sınıflar için uygundur).
    # Set bir kitap koleksiyonu olduğundan içindeki kitapların kendi hedefleri
    # ayrı (bu alan üst-set'e koçun "8. sınıf paketi" gibi etiket vermesi için).
    target_grade_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_grade_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_graduate: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list["BookSetItem"]] = relationship(
        "BookSetItem",
        back_populates="set",
        cascade="all, delete-orphan",
        order_by="BookSetItem.order",
    )

    def __repr__(self) -> str:
        return f"<BookSet {self.name}>"


class BookSetItem(Base):
    __tablename__ = "book_set_items"
    __table_args__ = (
        UniqueConstraint("set_id", "book_id", name="uq_book_set_item"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_id: Mapped[int] = mapped_column(
        ForeignKey("book_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[int] = mapped_column(
        ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    set: Mapped["BookSet"] = relationship("BookSet", back_populates="items")
    book: Mapped["Book"] = relationship("Book")


# Ortak Kitap Kataloğu durumları (catalog_status; NULL = kişisel şablon).
# pending  : koç katkısı — süper admin onayı bekler, koçlara GÖRÜNMEZ
# verified : yayında — tüm koçlar arayıp tek tıkla kullanır
# hidden   : yayından kaldırıldı (geri alınabilir)
CATALOG_STATUS_PENDING = "pending"
CATALOG_STATUS_VERIFIED = "verified"
CATALOG_STATUS_HIDDEN = "hidden"
CATALOG_STATUSES = (
    CATALOG_STATUS_PENDING, CATALOG_STATUS_VERIFIED, CATALOG_STATUS_HIDDEN,
)

CATALOG_SOURCE_ADMIN_SEED = "admin_seed"
CATALOG_SOURCE_COACH = "coach_contribution"
CATALOG_SOURCE_AI_READ = "ai_read"


class BookTemplate(Base):
    """Yeniden kullanılabilir kitap yapı şablonu (ünite isimleri + default test sayıları).

    Yeni bir kitap eklerken sıfırdan ünite girmek yerine bir şablona uygulanarak
    hızla doldurulabilir. AI önerileri de bu modele "is_ai_generated=True" ile
    kaydedilir; kullanıcı düzenleyip "is_verified=True"a yükselttiğinde
    güvenilir şablon olur.

    İKİ KİMLİK (2026-08-11, Ortak Kitap Kataloğu):
    - Kişisel şablon: teacher_id dolu + catalog_status NULL (eski davranış).
    - Katalog kaydı : teacher_id NULL + catalog_status dolu (pending/verified/
      hidden). Yayınevi kitabının GERÇEK yapısı (ünite + birebir test sayısı +
      builtin müfredat eşleştirmesi) bir kez tanımlanır, tüm koçlar kullanır.
      Kişisel sorgular teacher_id filtresini korur → katalog satırı sızmaz.
    """

    __tablename__ = "book_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    publisher: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[BookType] = mapped_column(Enum(BookType), nullable=False)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    target_grade_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_grade_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_graduate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    avg_questions_per_test: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI tarafından oluşturuldu mu? UI'da "doğrulanmadı" rozetiyle gösterilir
    # ta ki kullanıcı düzenleme/onayla aksiyonu yapana dek.
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # --- Ortak Kitap Kataloğu alanları (NULL = kişisel şablon) -------------
    catalog_status: Mapped[str | None] = mapped_column(
        String(16), nullable=True, index=True
    )
    source: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # Eşleştirme-arama anahtarları (curriculum_mapping.normalize ile üretilir)
    name_normalized: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    publisher_normalized: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    # Denetim izi — koçlara ANONİM gösterilir (yalnız admin görür)
    contributed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Kaç koç bu kayıttan kitap oluşturdu (arama sıralama sinyali)
    usage_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def is_catalog(self) -> bool:
        return self.catalog_status is not None

    sections: Mapped[list["BookTemplateSection"]] = relationship(
        "BookTemplateSection",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="BookTemplateSection.order",
    )

    def __repr__(self) -> str:
        return f"<BookTemplate {self.name}>"


class BookTemplateSection(Base):
    __tablename__ = "book_template_sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("book_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Katalog kayıtlarında müfredat eşleştirmesi de taşınır (yalnız BUILTIN
    # topic bağlanır — herkes için geçerli). Kişisel şablonlarda NULL kalır.
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    default_test_count: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    template: Mapped["BookTemplate"] = relationship("BookTemplate", back_populates="sections")
    topic: Mapped["Topic | None"] = relationship("Topic")

    def __repr__(self) -> str:
        return f"<BookTemplateSection {self.label} x{self.default_test_count}>"
