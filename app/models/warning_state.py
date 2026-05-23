"""WarningState — uyarı akışı tazelik + 'gördüm/ertele' durumu.

Uyarılar canlı veriden HESAPLANIR (kalıcı değil). Bu tablo her uyarının
(actor görünümünde) ne zaman İLK göründüğünü (first_seen — 'kaç gündür sürüyor')
ve koç/yöneticinin onu 'gördüm/ertele' ile ne zamana dek sustuduğunu (snooze_until)
tutar. Anahtar = (actor_id, student_id, code).

Reconcile mantığı (feed her yüklendiğinde):
  - Yeni uyarı (state yok) → first_seen=now ekle.
  - Mevcutsa first_seen korunur (yaş büyür).
  - Canlı uyarılarda ARTIK YOKSA (koşul düzeldi) → state SİLİNİR → tekrar
    ederse 'taze' sayılır (first_seen sıfırlanır, eski erteleme geçersiz).
  - snooze_until > now → uyarı aktif akıştan gizlenir ('Ertelenenler'e iner);
    süre dolunca koşul hâlâ sürüyorsa otomatik geri döner.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class WarningState(Base):
    __tablename__ = "warning_states"
    __table_args__ = (
        UniqueConstraint("actor_id", "student_id", "code", name="uq_warning_state_actor_student_code"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Uyarıyı gören kişi (koç / kurum yöneticisi / süper admin) — erteleme onun görünümüne özel
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    actor: Mapped["User"] = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<WarningState a={self.actor_id} s={self.student_id} {self.code}>"
