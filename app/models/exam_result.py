"""ExamResult — öğrencinin girdiği deneme sınavı sonucu (KP4 — Akademik Çıktı).

Koç (öğretmen) öğrencisinin deneme sonucunu girer: doğru/yanlış/boş sayıları +
opsiyonel ders kırılımı. Net, sınav türüne göre otomatik hesaplanır.

Net hesabı (Türk sınav sistemi):
- LGS: 3 yanlış 1 doğruyu götürür → net = D - Y/3
- YKS (TYT/AYT_*): 4 yanlış 1 doğruyu götürür → net = D - Y/4

Tasarım kararları (2026-05-20):
- subject_nets: JSON metin (ders kırılımı listesi). Native JSON yerine Text —
  audit_logs.details_json deseni; serialize/deserialize servis katmanında.
- created_by_id NULL olabilir (öğretmen silinirse kayıt korunur, SET NULL).
- student_id CASCADE: öğrenci silinince deneme geçmişi de gider.
- net float olarak saklanır (D - Y/penalty); kurum panosu (KP4b) bunu agregeler.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, deferred, mapped_column, relationship

from app.database import Base
from app.models.curriculum import ExamSection

if TYPE_CHECKING:
    from app.models.curriculum import Subject, Topic
    from app.models.user import User


def section_penalty(section: ExamSection) -> int:
    """Yanlış cezası katsayısı: kaç yanlış 1 doğruyu götürür.

    LGS → 3, YKS (TYT/AYT) → 4. OKUL denemesi de 4 varsayılır (lise okul
    denemeleri YKS provasıdır); PDF içe aktarmada belge kendi netini
    veriyorsa o esas alınır, formül yalnız doğrulamadır.
    """
    return 3 if section == ExamSection.LGS else 4


def compute_net(correct: int, wrong: int, section: ExamSection) -> float:
    """net = doğru - yanlış/ceza. Negatife düşmez (taban 0)."""
    raw = correct - (wrong / section_penalty(section))
    return round(max(raw, 0.0), 2)


class ExamResult(Base):
    __tablename__ = "exam_results"
    __table_args__ = (
        Index("ix_exam_result_student_date", "student_id", "exam_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    exam_date: Mapped[date] = mapped_column(Date, nullable=False)
    section: Mapped[ExamSection] = mapped_column(Enum(ExamSection), nullable=False)

    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_wrong: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_blank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Ders kırılımı — JSON metin: [{"name", "correct", "wrong", "blank", "net"}]
    subject_nets: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- PDF içe aktarma izleri (2026-07-16; manuel kayıtlarda hepsi NULL) ---
    # import_source: "pdf_import" — Gemini ile PDF'ten okundu.
    import_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    import_pdf_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    import_pdf_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Belge kanıt olarak saklanır (support_attachments deseni) — deferred:
    # liste/detay sorgularında yüklenmez.
    import_pdf_data: Mapped[bytes | None] = deferred(
        mapped_column(LargeBinary, nullable=True)
    )
    # JSON metin: evren/kapsam, puan-sıralama, doğrulama sonuçları, güven bilgisi.
    analysis_meta: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship(
        "User", foreign_keys=[student_id]
    )
    questions: Mapped[list["ExamResultQuestion"]] = relationship(
        "ExamResultQuestion", back_populates="exam",
        cascade="all, delete-orphan", passive_deletes=True,
        order_by="ExamResultQuestion.id",
    )

    def __repr__(self) -> str:
        return f"<ExamResult s={self.student_id} {self.section.value} net={self.net}>"


# --- Soru sonucu sabitleri (düz VARCHAR — enum migration'sız) ---
EQ_RESULT_DOGRU = "dogru"
EQ_RESULT_YANLIS = "yanlis"
EQ_RESULT_BOS = "bos"
EQ_RESULTS = (EQ_RESULT_DOGRU, EQ_RESULT_YANLIS, EQ_RESULT_BOS)

ALIAS_SOURCE_AI = "ai"
ALIAS_SOURCE_COACH = "coach"

# İçe aktarma evrenleri (hangi müfredat omurgasına normalize edilir)
EXAM_UNIVERSE_TYT = "tyt"
EXAM_UNIVERSE_AYT = "ayt"
EXAM_UNIVERSE_LGS = "lgs"
EXAM_UNIVERSE_OKUL = "okul"
EXAM_UNIVERSES = (
    EXAM_UNIVERSE_TYT, EXAM_UNIVERSE_AYT, EXAM_UNIVERSE_LGS, EXAM_UNIVERSE_OKUL,
)


class ExamResultQuestion(Base):
    """İçe aktarılan denemenin TEK sorusu — konu-bazlı hata birikiminin ham verisi.

    subject/topic çifte saklanır: ham (belgede yazan) + normalize (bizim
    müfredat). Normalize edilemeyen soru ham etiketiyle yaşar; konu-bazlı
    birikime girmez (kirletmez), koç sonradan bağlayınca katılır.
    """

    __tablename__ = "exam_result_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    exam_result_id: Mapped[int] = mapped_column(
        ForeignKey("exam_results.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    subject_name_raw: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_label_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )

    correct_answer: Mapped[str | None] = mapped_column(String(8), nullable=True)
    student_answer: Mapped[str | None] = mapped_column(String(8), nullable=True)
    result: Mapped[str] = mapped_column(String(8), nullable=False, default=EQ_RESULT_YANLIS)

    # Çift okuma/çapraz sağlama uyuşmazlığı — önizlemede sarı gösterildi
    is_suspect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Koç/öğrenci önizlemede veya sonradan elle düzeltti
    manually_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    exam: Mapped["ExamResult"] = relationship("ExamResult", back_populates="questions")
    subject: Mapped["Subject | None"] = relationship("Subject", foreign_keys=[subject_id])
    topic: Mapped["Topic | None"] = relationship("Topic", foreign_keys=[topic_id])

    def __repr__(self) -> str:
        return f"<ExamResultQuestion e={self.exam_result_id} no={self.question_no} {self.result}>"


class ExamTopicAlias(Base):
    """Evren-anahtarlı ÖĞRENEN eşleme sözlüğü: yayınevi konu etiketi → resmi Topic.

    Anahtar = (scope[evren] + subject_id[etiketin görüldüğü normalize ders] +
    label_key[kanonik etiket]). Bir kez kurulan eşleme her içe aktarmada AYNI
    çözülür → konu birikimi tutarlı kalır + AI maliyeti zamanla düşer.
    Koç düzeltmesi (source=coach) AI eşleşmesini (source=ai) EZER; tersi ezemez.
    """

    __tablename__ = "exam_topic_aliases"
    __table_args__ = (
        UniqueConstraint("scope", "subject_id", "label_key",
                         name="uq_exam_topic_alias_scope_subject_label"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=True
    )
    label_key: Mapped[str] = mapped_column(String(200), nullable=False)
    label_raw: Mapped[str | None] = mapped_column(String(200), nullable=True)
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(8), nullable=False, default=ALIAS_SOURCE_AI)
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    topic: Mapped["Topic"] = relationship("Topic", foreign_keys=[topic_id])

    def __repr__(self) -> str:
        return f"<ExamTopicAlias {self.scope}:{self.label_key} -> t{self.topic_id} ({self.source})>"
