"""Video Sepeti — öğrenci başına koçun hazırladığı video oynatma listesi.

Koç YouTube oynatma listesi/video linki yapıştırır → videolar konu gruplarına
ayrılır (video_segmentation) → haftalık programda sürüklenip günlere bırakılır.

Bir sepet kaydı programa konduğunda bağlandığı görevi `task_id` ile tutar:
  - Görevin videoları = ona bağlı sepet kayıtları (çok linkli görev, ayrı link
    tablosu yok). Aynı gün + aynı konu → tek görev, birden çok video.
  - Görev silinince FK SET NULL → video kendiliğinden sepete geri döner.
  - "İzlendi" = bağlı görevin durumu (COMPLETED).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Rol: anlatım / soru çözümü / tekrar-özet / diğer (tanıtım, canlı yayın vb.)
VIDEO_ROLES = ("anlatim", "soru", "tekrar", "diger")
VIDEO_ROLE_LABELS = {
    "anlatim": "Konu anlatımı",
    "soru": "Soru çözümü",
    "tekrar": "Tekrar / özet",
    "diger": "Diğer",
}


class VideoBasketItem(Base):
    __tablename__ = "video_basket_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    youtube_id: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    channel_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    playlist_title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Ders (grid'de ders gruplaması + konu eşleştirmesi için)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id", ondelete="SET NULL"), nullable=True
    )
    # Konu grubu: aynı group_key = aynı konu bloğu (sepet başlığı group_label)
    group_key: Mapped[str] = mapped_column(String(64), nullable=False)
    group_label: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="anlatim")
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Hangi kayıtlı listeden geldi (sepette listeler birbirine karışmaz)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("video_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Programa konduğu görev (NULL = sepette bekliyor)
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    task = relationship("Task", back_populates="basket_videos", foreign_keys=[task_id])

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.youtube_id}"

    @property
    def duration_min(self) -> int | None:
        return None if self.duration_sec is None else max(1, round(self.duration_sec / 60))


class VideoSource(Base):
    """Koçun daha önce getirdiği oynatma listesi / video linki (kayıtlı arama).

    Koç başına tekildir (source_key = "pl:<liste>" ya da "v:<video>"); hangi
    öğrenci için getirildiğinden bağımsız → listeyi tekrar YouTube'da aramadan
    başka gün ya da başka öğrenci için yeniden getirebilir. Koç adını, dersini
    düzenleyebilir; silince sepetteki videolar durur (source_id NULL).
    """

    __tablename__ = "video_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_key: Mapped[str] = mapped_column(String(80), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    playlist_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Koçun verdiği ad (boşsa YouTube başlığı gösterilir)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True
    )
    video_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    @property
    def display_name(self) -> str:
        return (self.label or self.title or self.url)[:200]
