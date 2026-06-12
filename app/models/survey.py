"""Öğrenci Tanıma Anket/Envanter Sistemi — modeller (Faz 1, 2026-06-11).

Koç, katalogdaki anketi öğrencisine atar → öğrenci doldurur (web+mobil) →
sistem boyut-bazlı skorlar → sonuç anında koça düşer.

KONUMLANDIRMA (kullanıcı kararı): bu araçlar "psikolojik test" DEĞİL,
"koçluk amaçlı tanıma anketi"dir — tanı koymaz, görüşme + program tasarımı
girdisi üretir. Rapor ekranlarında sabit ibare gösterilir.

TELİF: madde metinleri ETÜTKOÇ'a özgüdür (çerçeveler — çoklu zeka alanları,
RIASEC tipleri, yaşam çarkı — telifsizdir); RIASEC anketi O*NET Interest
Profiler'dan (CC BY 4.0) esinlenen özgün uyarlamadır, atıf alanında belirtilir.

Şablonlar DB'de yaşar (whatsapp_templates deseni): idempotent seed +
süper admin düzenleyebilir; seed mevcut `code`'u EZMEZ.
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# --- Kategori sabitleri (çekirdek 4 grup — kullanıcı kararı 2026-06-11) ---
SURVEY_CATEGORY_TANIMA = "tanima"
SURVEY_CATEGORY_SINAV = "sinav"
SURVEY_CATEGORY_KARIYER = "kariyer"
SURVEY_CATEGORY_MOTIVASYON = "motivasyon"

SURVEY_CATEGORIES = (
    SURVEY_CATEGORY_TANIMA,
    SURVEY_CATEGORY_SINAV,
    SURVEY_CATEGORY_KARIYER,
    SURVEY_CATEGORY_MOTIVASYON,
)

SURVEY_CATEGORY_LABELS_TR: dict[str, str] = {
    SURVEY_CATEGORY_TANIMA: "Tanıma",
    SURVEY_CATEGORY_SINAV: "Sınav & Çalışma",
    SURVEY_CATEGORY_KARIYER: "Kariyer Keşif",
    SURVEY_CATEGORY_MOTIVASYON: "Hedef & Motivasyon",
}

# --- Skorlama tipleri ---
SCORING_DIMENSIONS = "dimensions"  # boyut bazlı Likert ortalaması → % profil (radar)
SCORING_WHEEL = "wheel"            # yaşam çarkı — her dilim 1-10 kaydırıcı
SCORING_QUALITATIVE = "qualitative"  # açık uçlu (SWOT) — skor yok, kadran metni

SURVEY_SCORING_TYPES = (SCORING_DIMENSIONS, SCORING_WHEEL, SCORING_QUALITATIVE)

# --- Soru tipleri ---
QTYPE_LIKERT5 = "likert5"    # 1-5 katılım (Hiç uygun değil → Tamamen uygun)
QTYPE_SLIDER10 = "slider10"  # 1-10 kaydırıcı (yaşam çarkı dilimi)
QTYPE_CHOICE = "choice"      # çoktan seçmeli (options_json) — skorlamaya girmez
QTYPE_OPEN = "open"          # açık uç — skorlamaya girmez, raporda metin

SURVEY_QTYPES = (QTYPE_LIKERT5, QTYPE_SLIDER10, QTYPE_CHOICE, QTYPE_OPEN)

# --- Atama durumları ---
ASSIGNMENT_PENDING = "pending"
ASSIGNMENT_IN_PROGRESS = "in_progress"
ASSIGNMENT_COMPLETED = "completed"
ASSIGNMENT_CANCELLED = "cancelled"

SURVEY_ASSIGNMENT_STATUSES = (
    ASSIGNMENT_PENDING,
    ASSIGNMENT_IN_PROGRESS,
    ASSIGNMENT_COMPLETED,
    ASSIGNMENT_CANCELLED,
)

SURVEY_ASSIGNMENT_STATUS_LABELS_TR: dict[str, str] = {
    ASSIGNMENT_PENDING: "Bekliyor",
    ASSIGNMENT_IN_PROGRESS: "Dolduruluyor",
    ASSIGNMENT_COMPLETED: "Tamamlandı",
    ASSIGNMENT_CANCELLED: "İptal edildi",
}

# Rapor ekranlarında sabit ibare (konumlandırma — kullanıcı kararı)
SURVEY_DISCLAIMER_TR = (
    "Bu bir psikolojik test değildir; koçluk amaçlı tanıma anketidir. "
    "Sonuçlar tanı koymaz — koçluk görüşmesi ve program tasarımı için ipucu sağlar."
)


class SurveyTemplate(Base):
    """Anket şablonu — sorular + boyutlar + skorlama tanımı DB'de yaşar."""

    __tablename__ = "survey_templates"
    __table_args__ = (
        Index("ix_survey_templates_category_sort", "category", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # Koça yönelik "ne işe yarar" açıklaması
    description: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=sa_text("''"),
    )
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    scoring_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SCORING_DIMENSIONS,
        server_default=sa_text("'dimensions'"),
    )
    # JSON list[{key,label,description,high_text,low_text,high_is_good}]
    dimensions_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default=sa_text("'[]'"),
    )
    # Rapor altına eklenen serbest not (yorum çerçevesi)
    report_note: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=sa_text("''"),
    )
    # Telif/uyarlama atfı (örn. O*NET CC BY 4.0)
    source_attribution: Mapped[str] = mapped_column(
        String(300), nullable=False, default="", server_default=sa_text("''"),
    )
    estimated_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=10, server_default=sa_text("10"),
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=100, server_default=sa_text("100"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=sa_text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
    updated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    questions: Mapped[list["SurveyQuestion"]] = relationship(
        "SurveyQuestion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="SurveyQuestion.order_no",
    )


class SurveyQuestion(Base):
    """Anket sorusu — boyut anahtarıyla skorlamaya bağlanır."""

    __tablename__ = "survey_questions"
    __table_args__ = (
        Index("ix_survey_questions_template_order", "template_id", "order_no"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("survey_templates.id", ondelete="CASCADE"), nullable=False,
    )
    order_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    qtype: Mapped[str] = mapped_column(
        String(20), nullable=False, default=QTYPE_LIKERT5,
        server_default=sa_text("'likert5'"),
    )
    # Skorlamada hangi boyuta sayılır (open/choice için null olabilir)
    dimension_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # choice için JSON list[{value,label}]
    options_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Ters madde — likert5'te 6-değer olarak skorlanır
    reverse: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa_text("false"),
    )

    template: Mapped[SurveyTemplate] = relationship(
        "SurveyTemplate", back_populates="questions"
    )


class CareerInsight(Base):
    """AI Kariyer Sentezi cache — öğrenci başına TEK güncel kayıt.

    Anket sonuçları (RIASEC ilgi + Beceri Seti zorunlu; Akademik Benlik +
    Çoklu Zeka varsa dahil) + GERÇEK akademik veri (deneme netleri, tamamlama)
    Gemini'ye verilir → 3-5 meslek/bölüm önerisi + YKS alan uyumu + koç için
    hedef-belirleme seans gündemi.

    KREDİ GÜVENLİĞİ (KS4 deseni): GET cache'den ücretsiz okur; yalnız POST
    (üret/yenile) kredi düşürür. İlgili bir anket yeniden tamamlanınca
    `is_stale=True` (AI çağrısı YOK — koça "yenile" önerilir).

    Gizlilik: yalnız ilgili koç erişir; öneri/taslaktır, yönlendirme kararı
    koç + öğrenci + velinindir.
    """

    __tablename__ = "career_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    generated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # JSON list[{title, field, why, example_departments[]}]
    career_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)
    strengths: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON list
    agenda: Mapped[str | None] = mapped_column(Text, nullable=True)      # JSON list
    watch_outs: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list
    # JSON {surveys: [code,...], exam_count: int} — neye dayandı
    based_on: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("false"),
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


# Kariyer Sentezi'nin beslendiği anketler — biri yeniden tamamlanınca cache bayatlar
CAREER_SURVEY_CODES = ("mesleki-ilgi", "beceri-seti", "akademik-benlik", "coklu-zeka")
# Sentez üretimi için zorunlu çekirdek (ilgi + beceri denkleminin iki yarısı)
CAREER_REQUIRED_CODES = ("mesleki-ilgi", "beceri-seti")


class SurveyAssignment(Base):
    """Koç → öğrenci anket ataması + cevaplar + hesaplanan skorlar.

    Cevaplar `answers_json` (question_id → değer) olarak tek satırda tutulur;
    tamamlanınca `scores_json` doldurulur (survey_service.compute_scores).
    """

    __tablename__ = "survey_assignments"
    __table_args__ = (
        Index("ix_survey_assignments_student_status", "student_id", "status"),
        Index("ix_survey_assignments_teacher", "teacher_id", "assigned_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("survey_templates.id", ondelete="CASCADE"), nullable=False,
    )
    # Koç silinirse atama/sonuç kaybolmasın (öğrenci bağımsız kalabilir)
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=ASSIGNMENT_PENDING,
        server_default=sa_text("'pending'"),
    )
    # Koçun öğrenciye görünen notu ("İlk görüşmemiz öncesi doldurur musun?")
    note: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=sa_text("''"),
    )
    # question_id(str) → cevap (int likert/slider, str open/choice)
    answers_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default=sa_text("'{}'"),
    )
    # Hesaplanan sonuç (boyut skorları / nitel bloklar) — completed'da dolu
    scores_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    template: Mapped[SurveyTemplate] = relationship("SurveyTemplate")
    teacher: Mapped["User | None"] = relationship("User", foreign_keys=[teacher_id])
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
