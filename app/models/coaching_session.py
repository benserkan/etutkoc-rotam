"""CoachingSession — bağımsız koçun öğrenci görüşme/seans kaydı (KS1).

Koç, haftalık koçluk görüşmesini düşük efor + yapılandırılmış şekilde kaydeder.
Senin "Haftalık Program Değerlendirme Formu"nun dijital karşılığı: alanlar 3
kovaya bölünür —
  - Kova 1 (otomatik): verimli günler/tempo/net/zayıf ders → `auto_snapshot`
    (study_dna + analytics + exam_result'tan seans anında hesaplanıp SAKLANIR;
    sonradan veri değişse de o günkü form korunur).
  - Kova 2 (anlatı): `coach_note` (ses/foto→AI ileride, KS3).
  - Kova 3 (koç kararı): `agenda` (zorunlu) + `next_change`.

`status` tahsilatın (KS2) temeli: yalnız DONE seanslar ücrete sayılır.

Gizlilik (KVKK): kişisel/gelişimsel veri → yalnız seansı giren koç erişir
(sahiplik 404). Veli/öğrenci görmez.
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
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false as sa_false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class CoachingSessionStatus(str, enum.Enum):
    DONE = "done"            # yapıldı — tahsilata sayılır
    POSTPONED = "postponed"  # ertelendi
    CANCELLED = "cancelled"  # iptal
    NO_SHOW = "no_show"      # öğrenci gelmedi


COACHING_STATUS_LABELS: dict[CoachingSessionStatus, str] = {
    CoachingSessionStatus.DONE: "Yapıldı",
    CoachingSessionStatus.POSTPONED: "Ertelendi",
    CoachingSessionStatus.CANCELLED: "İptal",
    CoachingSessionStatus.NO_SHOW: "Gelmedi",
}


class CoachingChannel(str, enum.Enum):
    IN_PERSON = "in_person"
    ONLINE = "online"
    PHONE = "phone"


COACHING_CHANNEL_LABELS: dict[CoachingChannel, str] = {
    CoachingChannel.IN_PERSON: "Yüz yüze",
    CoachingChannel.ONLINE: "Online",
    CoachingChannel.PHONE: "Telefon",
}


class SessionCaptureSource(str, enum.Enum):
    MANUAL = "manual"   # elle form
    VOICE = "voice"     # ses → metin (KS3)
    PHOTO = "photo"     # kâğıt form fotoğrafı → metin (KS3)


class CoachingSession(Base):
    __tablename__ = "coaching_sessions"
    __table_args__ = (
        Index("ix_coaching_session_student_date", "student_id", "session_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[CoachingSessionStatus] = mapped_column(
        Enum(CoachingSessionStatus), nullable=False,
        server_default=CoachingSessionStatus.DONE.name,
    )
    duration_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channel: Mapped[CoachingChannel | None] = mapped_column(
        Enum(CoachingChannel), nullable=True
    )

    # Kova 3 — koç kararı
    agenda: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    next_change: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Kova 2 — anlatı (genel görüşme notu)
    coach_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Yapılandırılmış sinyaller (AI içgörü + trend için)
    mood: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1-5
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)     # JSON list

    # Kova 1 — seans anındaki otomatik veri (JSON, geçmiş korunur)
    auto_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)

    capture_source: Mapped[SessionCaptureSource] = mapped_column(
        Enum(SessionCaptureSource), nullable=False,
        server_default=SessionCaptureSource.MANUAL.name,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])

    def __repr__(self) -> str:
        return f"<CoachingSession s={self.student_id} {self.session_date} {self.status.value}>"


class CoachingInsight(Base):
    """AI koçluk içgörüsü cache (KS4) — öğrenci başına TEK güncel kayıt.

    KREDİ GÜVENLİĞİ: İçgörü pahalı Claude çağrısıyla bir kez üretilir + burada
    saklanır. Sonraki görüntülemeler DB'den okunur (ücretsiz). Yalnız koç "Yenile"
    derse yeniden üretilir (kredi düşer). Yeni/değişen seans → `is_stale=True`
    (AI çağrısı YOK; sadece bayraklanır, koç isterse yeniler).

    Gizlilik (KVKK): yalnız ilgili koç erişir; veli/öğrenci görmez. Öneri/taslaktır.
    """
    __tablename__ = "coaching_insights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    generated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    summary: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    agenda_suggestions: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON list
    psychological_tips: Mapped[str | None] = mapped_column(Text, nullable=True)   # JSON list
    watch_outs: Mapped[str | None] = mapped_column(Text, nullable=True)           # JSON list
    based_on_sessions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    is_stale: Mapped[bool] = mapped_column(
        # Yeni seans/güncelleme sonrası True — koça "yenile" önerilir
        Boolean, nullable=False, server_default=sa_false()
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<CoachingInsight s={self.student_id} stale={self.is_stale}>"
