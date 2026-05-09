"""Stage 11 — Öğrenci hedef ağacı (Goal Tree).

Hiyerarşik hedef yapısı: ana sınav hedefi → ders altları → konu altları
→ haftalık/günlük operatif hedefler. Her hedef bir parent'a bağlanabilir;
yaprak hedeflerin tamamlanma oranı yukarı doğru aggregate edilir.

Hedef türleri (GoalKind):
- EXAM_TARGET : Sınav hedefi (LGS başarı sırası, YKS net sayısı vb.)
- SUBJECT     : Ders bazlı hedef (Matematik 36/40 net, Türkçe 38/40)
- TOPIC       : Konu bazlı hedef (Cebir 90% bitir, Geometri 80%)
- WEEKLY      : Haftalık operatif (Bu hafta 25 test çöz)
- DAILY       : Günlük operatif (Bugün 4 saat çalış)
- CUSTOM      : Serbest hedef (öğretmen veya öğrenci özel ekledi)

Durum (GoalStatus):
- ACTIVE     : Üzerinde çalışılıyor
- ACHIEVED   : Hedef tamamlandı (target_value'ya ulaşıldı veya manuel)
- ABANDONED  : Yarıda bırakıldı (öğrenci/öğretmen kararı)

İlerleme: leaf (alt hedefi olmayan) hedeflerin current_value/target_value
oranlarının ağırlıklı ortalaması üst hedefin progress'ini verir. Servis
katmanında hesaplanır (tabloda denormalized cache yok — küçük tree'ler
için on-demand hesap yeterli; öğrenci başına ortalama 20-50 düğüm).
"""

from __future__ import annotations

import enum
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
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class GoalKind(str, enum.Enum):
    EXAM_TARGET = "exam_target"
    SUBJECT = "subject"
    TOPIC = "topic"
    WEEKLY = "weekly"
    DAILY = "daily"
    CUSTOM = "custom"


class GoalStatus(str, enum.Enum):
    ACTIVE = "active"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"


GOAL_KIND_LABELS_TR: dict[GoalKind, str] = {
    GoalKind.EXAM_TARGET: "Sınav Hedefi",
    GoalKind.SUBJECT: "Ders Hedefi",
    GoalKind.TOPIC: "Konu Hedefi",
    GoalKind.WEEKLY: "Haftalık Hedef",
    GoalKind.DAILY: "Günlük Hedef",
    GoalKind.CUSTOM: "Özel Hedef",
}

GOAL_STATUS_LABELS_TR: dict[GoalStatus, str] = {
    GoalStatus.ACTIVE: "Aktif",
    GoalStatus.ACHIEVED: "Tamamlandı",
    GoalStatus.ABANDONED: "Bırakıldı",
}

GOAL_KIND_EMOJIS: dict[GoalKind, str] = {
    GoalKind.EXAM_TARGET: "🎯",
    GoalKind.SUBJECT: "📘",
    GoalKind.TOPIC: "📖",
    GoalKind.WEEKLY: "📅",
    GoalKind.DAILY: "⏱️",
    GoalKind.CUSTOM: "⭐",
}


class StudentGoal(Base):
    """Bir öğrencinin hiyerarşik hedef düğümü.

    parent_id self-referenced — null ise kök hedef. Bir öğrencinin birden
    çok kök hedefi olabilir (ör. LGS hedefi + 9. sınıf okul ortalaması).

    target_value/current_value sayısal alanlar (puan, net, yüzde, saat).
    unit string — UI'da fontlandırma için ('net', '%', 'saat', 'sıra').
    """
    __tablename__ = "student_goals"
    __table_args__ = (
        Index("ix_student_goals_student_status", "student_id", "status"),
        Index("ix_student_goals_parent", "parent_id"),
        Index("ix_student_goals_kind", "kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Hedefin sahibi öğrenci
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Hiyerarşi — null = kök hedef
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("student_goals.id", ondelete="CASCADE"),
        nullable=True,
    )

    kind: Mapped[GoalKind] = mapped_column(Enum(GoalKind), nullable=False)
    status: Mapped[GoalStatus] = mapped_column(
        Enum(GoalStatus), nullable=False, default=GoalStatus.ACTIVE,
    )

    # Başlık ve açıklama
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Sayısal hedef + güncel değer + birim
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Hedeflenen tamamlanma tarihi (sınav günü, hafta sonu vb.)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Otomatik mi yoksa manuel mi oluşturuldu (sistem türetti vs öğretmen ekledi)
    is_auto_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False,
    )

    # Tamamlandığı an (status=ACHIEVED iken set)
    achieved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    abandoned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Hedefi kim oluşturdu (öğretmen/öğrenci/sistem). NULL = sistem cron.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        nullable=False, index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    # İlişkiler
    student: Mapped["User"] = relationship(
        "User", foreign_keys=[student_id],
    )
    parent: Mapped["StudentGoal | None"] = relationship(
        "StudentGoal", remote_side="StudentGoal.id",
        back_populates="children",
    )
    children: Mapped[list["StudentGoal"]] = relationship(
        "StudentGoal", back_populates="parent",
        cascade="all, delete-orphan",
    )
    created_by: Mapped["User | None"] = relationship(
        "User", foreign_keys=[created_by_user_id], viewonly=True,
    )

    @property
    def is_leaf(self) -> bool:
        """Alt hedef yoksa yaprak."""
        return not self.children

    @property
    def progress_pct(self) -> int | None:
        """Yaprak hedefin yüzde ilerlemesi (sayısal hedef varsa).

        Üst düğümler için bu değer servis katmanında ağaç yürünerek
        hesaplanır (children agregesi); model-level property tek düğüme
        bakar.
        """
        if self.target_value is None or self.target_value <= 0:
            return None
        cv = self.current_value or 0
        pct = round(100 * cv / self.target_value)
        # 0..100 clamp; aşımı 100'de göster (achieved')
        return max(0, min(100, pct))

    def __repr__(self) -> str:
        return (
            f"<StudentGoal #{self.id} student={self.student_id} "
            f"{self.kind.value} '{self.title}'>"
        )
