"""Koç başına öğrenilen öneri ağırlıkları (2026-11-08).

Gece işi (`rec_weights_train`) her koçun öğrencilerinde son haftaları yeniden
oynatır; koçun GERÇEKTE verdiği bölümleri en iyi öne çıkaran özellik
ağırlıklarını öğrenir. Öğrenilen ağırlık o koçun ayrılmış son günlerinde
varsayılandan belirgin iyiyse `weights_json` dolar, değilse NULL kalır
(varsayılan kullanılır). Ölçümler her durumda yazılır — koç/yönetici
"öneriler ne kadar isabetli" sorusunu buradan görür.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

REC_STATUS_LEARNED = "learned"          # öğrenilen ağırlık kullanılıyor
REC_STATUS_DEFAULT = "default"          # öğrenme varsayılanı geçemedi
REC_STATUS_INSUFFICIENT = "insufficient"  # öğrenecek kadar veri yok


class CoachRecWeights(Base):
    __tablename__ = "coach_rec_weights"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=REC_STATUS_INSUFFICIENT)
    weights_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    n_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    n_students: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # ayrılmış (eğitimde kullanılmayan) günlerde koçun verdiği bölümün ekrandaki
    # önerilerde bulunma oranı (0..1)
    shown_default: Mapped[float | None] = mapped_column(Float, nullable=True)
    shown_learned: Mapped[float | None] = mapped_column(Float, nullable=True)
    top3_default: Mapped[float | None] = mapped_column(Float, nullable=True)
    top3_learned: Mapped[float | None] = mapped_column(Float, nullable=True)
    trained_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
