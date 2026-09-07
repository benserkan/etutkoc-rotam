"""Konu kapatma — müfredat tamamlanmasının TEK kaynağı (2026-09-07).

KULLANICI KARARI: "koç öğrenciyle görüşmesinde konu bitti mi sorsun; bittiğinde
müfredat panelinden işaretleyerek konunun bittiği belirlensin. Müfredatın
tamamlanması böylece doğru olarak izlenir."

Neden kitabın sayacından okumuyoruz: bir konunun bitip bitmediği kitapta kaç
test kaldığından çıkmaz — öğrenci sistem dışı çalışmış, kitap sayımı şaşmış ya
da koç konuyu başka kaynakla kapatmış olabilir. Karar koçundur; sistem yalnız
kararı kaydeder ve gerekçe olacak sinyalleri (çözülen test, doğruluk, denemede
durum, açık yanlış) önüne koyar.

Kayıt VARSA konu kapalıdır; "yeniden aç" kaydı siler. Kim/ne zaman kapattığı
denetim için saklanır.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TopicClosure(Base):
    __tablename__ = "topic_closures"
    __table_args__ = (
        UniqueConstraint("student_id", "topic_id", name="uq_topic_closure"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(
        ForeignKey("topics.id", ondelete="CASCADE"), nullable=False
    )
    closed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    closed_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    topic: Mapped["Topic"] = relationship("Topic")  # noqa: F821

    def __repr__(self) -> str:
        return f"<TopicClosure student={self.student_id} topic={self.topic_id}>"
