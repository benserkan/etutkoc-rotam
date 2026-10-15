"""Haftalık görev havuzu modu — şube · dönem · havuz kalemi (2026-10-12).

Tasarım (K1–K61, CLAUDE.md "HAFTALIK GÖREV HAVUZU"): dershane öğrencisi için
gün-gün programa ALTERNATİF model. Rehber seansta havuzu yazar, öğrenci her gün
havuzdan "kabını" kurar (kap = o güne yazılan mevcut Task), yapılmayan kalem
gün sonunda havuza döner.

Değişmez kurallar:
  · Havuz kalemi REZERV TUTMAZ (K-havuz). Kaba konunca açılan görev kalemi
    `reservation_released_at` ile doğar → mevcut tamamlama kodu rezerv sayacına
    dokunmaz, çözülen test yine kitap sayacına yazılır.
  · Kalem çekirdeği = ders + miktar + birim. Konu / kaynak / gün etiketi isteğe
    bağlı; kaynaksızlık hiçbir adımı durdurmaz (K13/K14).
  · Dönem = iki gerçekleşen seans arası; takvim haftasına hizalı değil (K6/K8).
  · Öğrenci başına tek mod (users.program_mode); mod değişimi yalnız açık dönem
    yokken (Basamak 9).
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User

# ---- program modu (users.program_mode)
PROGRAM_MODE_GUN_GUN = "gun_gun"   # mevcut davranış (varsayılan)
PROGRAM_MODE_HAVUZ = "havuz"       # haftalık görev havuzu
PROGRAM_MODES = (PROGRAM_MODE_GUN_GUN, PROGRAM_MODE_HAVUZ)
PROGRAM_MODE_LABELS: dict[str, str] = {
    PROGRAM_MODE_GUN_GUN: "Gün gün program",
    PROGRAM_MODE_HAVUZ: "Haftalık görev havuzu",
}

# ---- dönem durumu
PERIOD_OPEN = "acik"
PERIOD_CLOSED = "kapandi"
PERIOD_BREAK = "ara"               # tatil / ara (K61)
PERIOD_CLOSED_NO_SESSION = "gorusmesiz"  # 14+ gün seans yok, rehber görüşmesiz kapattı (K57)
PERIOD_STATUSES = (PERIOD_OPEN, PERIOD_CLOSED, PERIOD_BREAK, PERIOD_CLOSED_NO_SESSION)
PERIOD_STATUS_LABELS: dict[str, str] = {
    PERIOD_OPEN: "Açık",
    PERIOD_CLOSED: "Kapandı",
    PERIOD_BREAK: "Ara",
    PERIOD_CLOSED_NO_SESSION: "Görüşmesiz kapandı",
}
PERIOD_MAX_DAYS = 14               # K6: dönem en çok 14 gün beklenir
PERIOD_NO_SESSION_RED_DAYS = 14    # K57: 14 gün seans yok → kırmızı

# ---- kalem birimi (K16/K27)
UNIT_TEST = "test"
UNIT_SORU = "soru"
UNIT_SAYFA = "sayfa"
UNIT_DENEME = "deneme"
UNIT_ETKINLIK = "etkinlik"         # miktarsız olabilen tek birim (1 birim sayılır)
POOL_UNITS = (UNIT_TEST, UNIT_SORU, UNIT_SAYFA, UNIT_DENEME, UNIT_ETKINLIK)
POOL_UNIT_LABELS: dict[str, str] = {
    UNIT_TEST: "test",
    UNIT_SORU: "soru",
    UNIT_SAYFA: "sayfa",
    UNIT_DENEME: "deneme",
    UNIT_ETKINLIK: "etkinlik",
}

# ---- kalem kaynağı (kim/ne ekledi)
SOURCE_COACH = "rehber"
SOURCE_STUDENT = "ogrenci"         # K38: onay bekler
SOURCE_EXAM = "deneme"             # K29: deneme şeridinden tek dokunuş
SOURCE_CARRY = "devir"             # K22/K58
SOURCE_TEMPLATE = "sablon"         # K26: şube/iskelet önerisi kabul edildi
POOL_SOURCES = (SOURCE_COACH, SOURCE_STUDENT, SOURCE_EXAM, SOURCE_CARRY, SOURCE_TEMPLATE)
# KONU ZORUNLULUĞU (koç, 2026-10-14): TEST/SORU birimli kalem kitapsızsa bir KONUYA bağlı olmalı —
# konusuz test kalemi konu performansına ve müfredat haritasına hiç giremez (D/Y/B girilse de boşa
# gider) ve görev istatistiğinde "deneme" sanılır. Öğrencinin kendi kalemi (onaya düşer) ve devir
# (eski kalemin kopyası) muaf.
TOPIC_REQUIRED_UNITS = ("test", "soru")
TOPIC_REQUIRED_EXEMPT_SOURCES = (SOURCE_STUDENT, SOURCE_CARRY)

# ---- onay (yalnız öğrencinin eklediği kalemde anlamlı — K38)
APPROVAL_NA = "yok"
APPROVAL_PENDING = "bekliyor"
APPROVAL_APPROVED = "onaylandi"
APPROVAL_REJECTED = "reddedildi"
APPROVALS = (APPROVAL_NA, APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED)

CARRY_AVOID_THRESHOLD = 3          # K58: 3. devir → K44 kaçınılan sinyali
LATE_ENTRY_DAYS = 2                # K59: kapanıştan sonra 2 gün öğrenci geç kayıt; sonrası yalnız rehber
CUP_AVOID_THRESHOLD = 3            # K44: 3 kez kaba girip döndü


def _loads(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        v = json.loads(raw)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


class ClassGroup(Base):
    """Şube kaydı. `users.class_group` metni ad olarak bağ kurar (mevcut süzgeç/
    toplu işlem bozulmaz). scope_key = 'inst:{id}' (kurum) | 'coach:{id}' (bağımsız koç)."""

    __tablename__ = "class_groups"
    __table_args__ = (
        UniqueConstraint("scope_key", "name", name="uq_class_groups_scope_name"),
        Index("ix_class_groups_scope_key", "scope_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scope_key: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    # K9: ders başına "şu an işlenen konu" → JSON {subject_id: {"topic_id", "updated_on", "by"}}
    topic_positions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # K37: haftanın günü → o gün dershanede işlenen dersler → JSON {"0": [subject_id, ...]} (0 = Pazartesi)
    lesson_days: Mapped[str | None] = mapped_column(Text, nullable=True)
    # K12: kurum yayını seti (toplu atama kaynağı)
    book_set_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_sets.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def positions(self) -> dict:
        return _loads(self.topic_positions)

    @property
    def lessons(self) -> dict:
        return _loads(self.lesson_days)

    def __repr__(self) -> str:
        return f"<ClassGroup {self.scope_key} {self.name}>"


class StudyPeriod(Base):
    """Dönem: seans gününde açılır, bir sonraki gerçekleşen seansta kapanır (K6/K8/K23)."""

    __tablename__ = "study_periods"
    __table_args__ = (
        Index("ix_study_periods_student_opened", "student_id", "opened_on"),
        Index("ix_study_periods_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)
    opened_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("coaching_sessions.id", ondelete="SET NULL"), nullable=True
    )
    # K8: beklenen ama çakılı olmayan sonraki seans günü (tempo buna göre)
    expected_next_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    closed_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("coaching_sessions.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=PERIOD_OPEN,
                                        server_default=PERIOD_OPEN)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # K53: veliye gönderilen seans özeti (rehber önizleyip gönderdi; otomatik gitmez)
    parent_summary_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    items: Mapped[list["PoolItem"]] = relationship(
        "PoolItem", back_populates="period", cascade="all, delete-orphan",
        order_by="PoolItem.id",
    )

    @property
    def is_open(self) -> bool:
        return self.status == PERIOD_OPEN

    def __repr__(self) -> str:
        return f"<StudyPeriod s={self.student_id} {self.opened_on} {self.status}>"


class PoolItem(Base):
    """Havuz kalemi — ders + miktar + birim çekirdeği; rezerv tutmaz."""

    __tablename__ = "pool_items"
    __table_args__ = (
        Index("ix_pool_items_period_id", "period_id"),
        Index("ix_pool_items_student_id", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = mapped_column(
        ForeignKey("study_periods.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )
    book_section_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True
    )
    # Serbest metin / kaynak adı (K28 ayrıştırma sonucu ya da etkinlik etiketi)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    # Kaplardaki görevlerden türetilen tamamlanan birim (sync_item_progress yazar) —
    # ÖĞRENCİNİN kaydı; erken uyarı yalnız buna bakar (K18).
    completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # Rehberin seansta geriye dönük işaretlediği birim (K18 ikinci kaynak; kaynak kanıtıyla).
    session_marked: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    session_marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    day_hint: Mapped[date | None] = mapped_column(Date, nullable=True)  # K30
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=SOURCE_COACH,
                                        server_default=SOURCE_COACH)
    teacher_homework: Mapped[bool] = mapped_column(  # K11: yalnız değerlendirme işareti
        Boolean, nullable=False, default=False, server_default="0"
    )
    approval: Mapped[str] = mapped_column(String(16), nullable=False, default=APPROVAL_NA,
                                          server_default=APPROVAL_NA)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    carry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cup_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    parent_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("pool_items.id", ondelete="SET NULL"), nullable=True
    )
    exam_result_id: Mapped[int | None] = mapped_column(
        ForeignKey("exam_results.id", ondelete="SET NULL"), nullable=True
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Rehber sildi (iz kalır, listede görünmez)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    period: Mapped["StudyPeriod"] = relationship("StudyPeriod", back_populates="items")
    subject = relationship("Subject")
    topic = relationship("Topic")
    book = relationship("Book")
    section = relationship("BookSection")

    @property
    def done_units(self) -> int:
        """Öğrenci kaydı + rehberin seans işareti (yüzdeye ikisi birden girer)."""
        return min(int(self.quantity or 0), int(self.completed or 0) + int(self.session_marked or 0))

    @property
    def remaining(self) -> int:
        return max(0, (self.quantity or 0) - self.done_units)

    @property
    def is_done(self) -> bool:
        return self.remaining == 0

    @property
    def counts_toward_pool(self) -> bool:
        """Havuz yüzdesine / tempoya girer mi (K38: onaysız öğrenci kalemi girmez)."""
        if self.removed_at is not None:
            return False
        if self.source == SOURCE_STUDENT:
            return self.approval == APPROVAL_APPROVED
        return True

    def __repr__(self) -> str:
        return f"<PoolItem p={self.period_id} {self.quantity} {self.unit} {self.label or self.topic_id}>"


class ProgramModeChange(Base):
    """Program modu geçişi (gün gün ↔ havuz) — geçmiş kaydı (2026-10-15).

    `effective_on` gününden itibaren öğrenci `to_mode`'dadır; o günden önceki tarihler
    `from_mode`'a aittir. `trigger`: manual | session_finish. `summary_json`: geçişte yapılan
    temizlik (silinen görev, serbest bırakılan rezerv, havuzdan çıkan kalem sayıları)."""

    __tablename__ = "program_mode_changes"
    __table_args__ = (Index("ix_program_mode_changes_student", "student_id", "effective_on"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    from_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    to_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_on: Mapped[date] = mapped_column(Date, nullable=False)
    trigger: Mapped[str] = mapped_column(String(24), nullable=False, default="manual", server_default="manual")
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    period_id: Mapped[int | None] = mapped_column(ForeignKey("study_periods.id", ondelete="SET NULL"), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    @property
    def summary(self) -> dict:
        try:
            return json.loads(self.summary_json) if self.summary_json else {}
        except (ValueError, TypeError):
            return {}
