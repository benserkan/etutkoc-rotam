"""Haftalık İskelet — kalıptan program (F1, 2026-09-25).

Koç bir kez "hangi gün hangi ders" iskeletini kurar; yeni haftada Hafta
Izgarası'nda HAYALET hücreler çıkar. Hayalet görev DEĞİLDİR, rezerv tutmaz,
tabloda saklanmaz — iskelet + o haftanın görevlerinden hesaplanır. Koç çipe
tıklayınca normal görev oluşur.

İskelet TARİHE değil HAFTA GÜNÜNE bağlıdır (0=Pazartesi … 6=Pazar) — program
haftası Pazartesi'ye hizalı olmasa da (Emir: Perşembe–Çarşamba) aynı iskelet
çalışır.

`skeleton_ghost_actions` iki iş görür: (1) "bu hafta bu hayaleti kaldır"
hafızası (kaldırılan hayalet o gün bir daha çıkmaz), (2) KABUL ORANI ölçümü
(kaçıncı çip seçildi, ne kadar "başka konu" dendi) — F1'in başarı ölçüsü.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

SKELETON_SOURCES = ("from_week", "manual")
# Hayalet üzerindeki koç eylemi.
GHOST_ACTIONS = ("accepted", "other", "dismissed")
# Kabul edilen çipin türü: iplik devamı / kitapta sıradaki / yeni konu / zayıf konu tekrarı.
CHIP_KINDS = ("thread", "next", "new", "weak", "routine", "activity")
# Kitaba bağlı rutinin ilerleme biçimi:
#   sirali — günlük adet kitapta sırayla alınır, bölüm biterse sıradakine taşar
#   karma  — her gün FARKLI bölümlerden birer test, bölümler arasında döner
ROUTINE_MODES = ("sirali", "karma")


class WeeklySkeleton(Base):
    __tablename__ = "weekly_skeletons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Öğrenci başına TEK etkin iskelet.
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, default="Haftalık iskelet")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    slots: Mapped[list["WeeklySkeletonSlot"]] = relationship(
        "WeeklySkeletonSlot",
        back_populates="skeleton",
        cascade="all, delete-orphan",
        order_by="(WeeklySkeletonSlot.weekday, WeeklySkeletonSlot.position)",
    )


class WeeklySkeletonSlot(Base):
    """İskelette bir satır: gün + (periyot) + ders. Aynı gün aynı derse iki
    satır olabilir (TYT Mat'ta konu ipliği + problem ipliği) → iki hayalet."""

    __tablename__ = "weekly_skeleton_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    skeleton_id: Mapped[int] = mapped_column(
        ForeignKey("weekly_skeletons.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Pzt … 6=Paz
    period: Mapped[str | None] = mapped_column(String(16), nullable=True)  # morning|noon|evening
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Rutin: her gün aynı iş (paragraf/problem) — konu seçimi önemsiz, toplu onaylanabilir.
    is_routine: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # F2-1: satırın KAYNAĞI. Rutinde rutinin kitabı; konu satırında çiplerde önce
    # bu kitabın ipliği. Kitapsız (serbest metinli) görevden gelen satırda
    # label = görev başlığı → aynı derste birden çok satırın hangisi olduğu okunur.
    book_id: Mapped[int | None] = mapped_column(
        ForeignKey("books.id", ondelete="SET NULL"), nullable=True
    )
    label: Mapped[str | None] = mapped_column(String(160), nullable=True)
    # Kitaba bağlı rutinde ilerleme biçimi: 'sirali' | 'karma' (bkz. ROUTINE_MODES)
    routine_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)

    skeleton: Mapped["WeeklySkeleton"] = relationship("WeeklySkeleton", back_populates="slots")


class SkeletonGhostAction(Base):
    __tablename__ = "skeleton_ghost_actions"
    __table_args__ = (Index("ix_skeleton_ghost_actions_student_date", "student_id", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # İskelet satırı sonradan silinse de ölçüm izi kalır.
    slot_id: Mapped[int | None] = mapped_column(
        ForeignKey("weekly_skeleton_slots.id", ondelete="SET NULL"), nullable=True
    )
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    chip_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1 = ilk çip
    chip_kind: Mapped[str | None] = mapped_column(String(16), nullable=True)
    chip_count: Mapped[int | None] = mapped_column(Integer, nullable=True)  # kaç çip gösterildi
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("book_sections.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
