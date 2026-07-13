"""Yanlış Soru Arşivi — öğrencinin yanlış/boş sorularını yaşayan bir kapanış
döngüsüne bağlayan model katmanı.

Tasarım ilkeleri (ihtiyaç analizi 2026-07-13):
- Sıfır sürtünme: fotoğraf + (varsa) bağlam; zorunlu alan minimumu.
- Bağlamdan otomatik etiket: görev/kitap-bölümden geliyorsa subject/topic
  kendiliğinden dolar; bağlamsız fotoğrafta AI önerir (Faz 3), öğrenci onaylar.
- Kapanış mekaniği: yanlış soru statik arşive değil FSRS kuyruğuna girer;
  aralıklı 2 başarılı yeniden çözüm → "kapandı"; tekrar yanlış → yeniden açılır.
- Gizlilik: fotoğraflar yalnız öğrenci + koçun erişimindedir; veli görmez.
  Görüntü verisi DB'de saklanır (support_attachments deseni — LargeBinary
  deferred; liste sorguları yüklemez), öğrenci silebilir, hesapla CASCADE.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# --- Sabitler (düz VARCHAR — enum migration'sız genişletilebilir) ---

WQ_SOURCE_GOREV = "gorev"      # Rotam görevinden (task bağlamıyla) eklendi
WQ_SOURCE_DENEME = "deneme"    # deneme sınavı yanlışı (exam_result bağlı olabilir)
WQ_SOURCE_DIGER = "diger"      # serbest ekleme (okul yaprak test vb.)
WQ_SOURCES = (WQ_SOURCE_GOREV, WQ_SOURCE_DENEME, WQ_SOURCE_DIGER)

WQ_ERROR_BILGI = "bilgi"       # bilgi/kavram eksiği
WQ_ERROR_ISLEM = "islem"       # işlem hatası
WQ_ERROR_DIKKAT = "dikkat"     # dikkatsizlik / soruyu yanlış okuma
WQ_ERROR_SURE = "sure"         # süre yetmedi / boş bırakıldı
WQ_ERROR_YORUM = "yorum"       # yorumlayamadı / soruya yaklaşamadı
WQ_ERROR_DIGER = "diger"
WQ_ERROR_TYPES = (
    WQ_ERROR_BILGI, WQ_ERROR_ISLEM, WQ_ERROR_DIKKAT,
    WQ_ERROR_SURE, WQ_ERROR_YORUM, WQ_ERROR_DIGER,
)
WQ_ERROR_LABELS_TR = {
    WQ_ERROR_BILGI: "Bilgi eksiği",
    WQ_ERROR_ISLEM: "İşlem hatası",
    WQ_ERROR_DIKKAT: "Dikkatsizlik",
    WQ_ERROR_SURE: "Süre yetmedi",
    WQ_ERROR_YORUM: "Yorumlayamadım",
    WQ_ERROR_DIGER: "Diğer",
}

WQ_STATUS_ACIK = "acik"        # kapatılmamış açık yanlış
WQ_STATUS_KAPANDI = "kapandi"  # aralıklı tekrar ile kapatıldı
WQ_STATUSES = (WQ_STATUS_ACIK, WQ_STATUS_KAPANDI)

WQ_IMAGE_QUESTION = "question"
WQ_IMAGE_SOLUTION = "solution"
WQ_IMAGE_KINDS = (WQ_IMAGE_QUESTION, WQ_IMAGE_SOLUTION)

# Kapanış kuralı: aralıklı (≥ WQ_STREAK_MIN_GAP_HOURS) en az WQ_CLOSE_STREAK
# başarılı (rating ≥ GOOD) yeniden çözüm → kapandı.
WQ_CLOSE_STREAK = 2
WQ_STREAK_MIN_GAP_HOURS = 20


class WrongQuestion(Base):
    """Bir öğrencinin arşivlediği tek bir yanlış/boş soru.

    Kaynak bağları (task/book_section/exam_result) opsiyoneldir; hepsi SET NULL
    ile geçmişe dayanıklıdır (görev silinse de arşiv kaydı yaşar). subject/topic
    bağı öneri motoru + koç analitiği + müfredat entegrasyonunun anahtarıdır.
    """

    __tablename__ = "wrong_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )  # koç seansta da ekleyebilir

    # Etiketler / bağlam
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )
    book_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    exam_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_results.id", ondelete="SET NULL"), nullable=True
    )
    source_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WQ_SOURCE_DIGER
    )
    error_type: Mapped[str | None] = mapped_column(String(24), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)          # öğrenci notu
    coach_note: Mapped[str | None] = mapped_column(Text, nullable=True)    # koç açıklaması

    # AI etiketleme çıktıları (Faz 3 — Gemini vision; öğrenci onaylı)
    ai_question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_hint: Mapped[str | None] = mapped_column(Text, nullable=True)  # Sokratik ipucu (tam çözüm DEĞİL)
    ai_tagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    difficulty_guess: Mapped[str | None] = mapped_column(String(8), nullable=True)  # kolay|orta|zor

    # Yaşam döngüsü / kapanış
    status: Mapped[str] = mapped_column(
        String(12), nullable=False, default=WQ_STATUS_ACIK, index=True
    )
    correct_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempts_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # FSRS durumu (app/services/fsrs.py compute_next ile güncellenir)
    fsrs_state: Mapped[str] = mapped_column(String(12), nullable=False, default="new")
    fsrs_stability: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    fsrs_difficulty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])  # noqa: F821
    topic = relationship("Topic", foreign_keys=[topic_id])
    subject = relationship("Subject", foreign_keys=[subject_id])
    book = relationship("Book", foreign_keys=[book_id])
    section = relationship("BookSection", foreign_keys=[book_section_id])
    images: Mapped[list["WrongQuestionImage"]] = relationship(
        "WrongQuestionImage", back_populates="wrong_question",
        cascade="all, delete-orphan", order_by="WrongQuestionImage.id",
    )

    __table_args__ = (
        Index("ix_wrong_q_student_status", "student_id", "status"),
        Index("ix_wrong_q_student_due", "student_id", "due_at"),
        Index("ix_wrong_q_student_topic", "student_id", "topic_id"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WrongQuestion id={self.id} student={self.student_id} status={self.status}>"


class WrongQuestionImage(Base):
    """Yanlış sorunun fotoğrafı (soru ve/veya çözüm).

    Veri DB'de LargeBinary deferred saklanır — liste/özet sorguları yüklemez,
    yalnız görüntüleme ucu okur (support_attachments ile aynı desen; S3/volume
    bağımlılığı yok, SQLite dev + Postgres prod taşınabilir).
    """

    __tablename__ = "wrong_question_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wrong_question_id: Mapped[int] = mapped_column(
        ForeignKey("wrong_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(12), nullable=False, default=WQ_IMAGE_QUESTION)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    wrong_question: Mapped[WrongQuestion] = relationship(
        "WrongQuestion", back_populates="images"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<WrongQuestionImage id={self.id} wq={self.wrong_question_id} kind={self.kind}>"
