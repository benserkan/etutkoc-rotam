"""SupportRequest — rol-bazlı talep/iletişim sistemi (internal ticket).

TaskRequest (koç↔öğrenci, programa özel) ve ContactRequest (public iletişim
formu) DIŞINDA, sistem-içi roller arası talep akışı:

  - Bağımsız koç (TEACHER + institution_id NULL) → Süper Admin
  - Kurum yöneticisi (INSTITUTION_ADMIN)        → Süper Admin
  - Kuruma bağlı öğretmen (TEACHER + institution) → kendi Kurum yöneticisi

Yaşam döngüsü: Açık → Değerlendiriliyor → Cevaplandı → Çözümlendi (+ Geri çekildi).
Thread: ilk mesaj talep gövdesi, sonrası karşılıklı yazışma (SupportRequestMessage).

KVKK: mesaj içeriği yalnız talep eden + muhatap (rol-bazlı + tenant izolasyonlu)
görür. Kişisel veri saklama amacı talebin işlenmesiyle sınırlı.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.institution import Institution
    from app.models.user import User


# ----------------------------- Muhatap (audience) -----------------------------
SUPPORT_AUDIENCE_SUPER_ADMIN = "super_admin"
SUPPORT_AUDIENCE_INSTITUTION_ADMIN = "institution_admin"
# Aşağı yönlü: kurum yöneticisi → belirli bir koça (target_user_id). Riskli
# öğrenci için "Koça ilet" akışında kullanılır.
SUPPORT_AUDIENCE_TEACHER = "teacher"

SUPPORT_AUDIENCE_LABELS_TR: dict[str, str] = {
    SUPPORT_AUDIENCE_SUPER_ADMIN: "Süper Yönetici",
    SUPPORT_AUDIENCE_INSTITUTION_ADMIN: "Kurum Yöneticisi",
    SUPPORT_AUDIENCE_TEACHER: "Koç",
}

# ----------------------------- Durum (status) -----------------------------
SUPPORT_STATUS_OPEN = "open"
SUPPORT_STATUS_UNDER_REVIEW = "under_review"
SUPPORT_STATUS_ANSWERED = "answered"
SUPPORT_STATUS_RESOLVED = "resolved"
SUPPORT_STATUS_WITHDRAWN = "withdrawn"

SUPPORT_STATUS_LABELS_TR: dict[str, str] = {
    SUPPORT_STATUS_OPEN: "Açık",
    SUPPORT_STATUS_UNDER_REVIEW: "Değerlendiriliyor",
    SUPPORT_STATUS_ANSWERED: "Cevaplandı",
    SUPPORT_STATUS_RESOLVED: "Çözümlendi",
    SUPPORT_STATUS_WITHDRAWN: "Geri çekildi",
}

# Aktif (kapanmamış) durumlar — sayım/filtre için
SUPPORT_OPEN_STATUSES = (
    SUPPORT_STATUS_OPEN,
    SUPPORT_STATUS_UNDER_REVIEW,
    SUPPORT_STATUS_ANSWERED,
)
SUPPORT_TERMINAL_STATUSES = (SUPPORT_STATUS_RESOLVED, SUPPORT_STATUS_WITHDRAWN)

# Muhatabın yanıt bekleyen (kuyrukta) saydığı durumlar
SUPPORT_RECIPIENT_PENDING_STATUSES = (SUPPORT_STATUS_OPEN, SUPPORT_STATUS_UNDER_REVIEW)

# ----------------------------- Kategori -----------------------------
SUPPORT_CATEGORY_LABELS_TR: dict[str, str] = {
    "technical": "Teknik sorun",
    "account": "Hesap / erişim",
    "billing": "Üyelik / ödeme",
    "feature": "Öneri / istek",
    "student_risk": "Riskli öğrenci",
    # Veli → koç kategorileri (P3)
    "exam_comment": "Deneme yorumu",
    "progress_question": "Gidişat sorusu",
    "other": "Diğer",
}

# ----------------------------- Ek (dosya) -----------------------------
SUPPORT_ATTACH_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
SUPPORT_ATTACH_MAX_PER_REQUEST = 10
# Ekran görüntüsü (jpg/png/webp/gif) + fatura/belge (pdf)
SUPPORT_ATTACH_ALLOWED_TYPES: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "application/pdf": "pdf",
}


class SupportRequest(Base):
    __tablename__ = "support_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # En son hareket (mesaj/durum) — gelen kutusunu sıralamak için
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    requester_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Görüntüleme için anlık rol (teacher / institution_admin)
    requester_role: Mapped[str] = mapped_column(String(20), nullable=False)

    # Muhatap: super_admin | institution_admin
    audience: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # institution_admin muhatabı için kurum (teacher→admin) + super_admin
    # muhatabı için bağlam (kurum yöneticisinin kurumu). Bağımsız koçta NULL.
    institution_id: Mapped[int | None] = mapped_column(
        ForeignKey("institutions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Aşağı yönlü (audience=teacher) talepte muhatap koç. Yukarı yönlüde NULL.
    target_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    category: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SUPPORT_STATUS_OPEN, index=True
    )

    # Muhatap tarafında talebi üstlenen yönetici
    handled_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Yönlendirme: kurum yöneticisi talebi süper yöneticiye iletince dolar.
    # Talep ondan KOPMAZ — escalated_by ile görmeye + cevabı izlemeye devam eder.
    escalated_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    requester: Mapped["User"] = relationship("User", foreign_keys=[requester_id])
    handled_by: Mapped["User | None"] = relationship("User", foreign_keys=[handled_by_id])
    target_user: Mapped["User | None"] = relationship("User", foreign_keys=[target_user_id])
    escalated_by: Mapped["User | None"] = relationship("User", foreign_keys=[escalated_by_id])
    institution: Mapped["Institution | None"] = relationship(
        "Institution", foreign_keys=[institution_id]
    )
    messages: Mapped[list["SupportRequestMessage"]] = relationship(
        "SupportRequestMessage",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="SupportRequestMessage.created_at",
    )
    attachments: Mapped[list["SupportAttachment"]] = relationship(
        "SupportAttachment",
        back_populates="request",
        cascade="all, delete-orphan",
        order_by="SupportAttachment.created_at",
    )

    def __repr__(self) -> str:
        return f"<SupportRequest #{self.id} {self.audience} {self.status}>"


class SupportRequestMessage(Base):
    __tablename__ = "support_request_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("support_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    request: Mapped["SupportRequest"] = relationship("SupportRequest", back_populates="messages")
    sender: Mapped["User | None"] = relationship("User", foreign_keys=[sender_id])

    def __repr__(self) -> str:
        return f"<SupportRequestMessage #{self.id} req={self.request_id}>"


class SupportAttachment(Base):
    """Talebe eklenen dosya (ekran görüntüsü jpg/png, fatura pdf vb.).

    Veri DB'de saklanır (LargeBinary, deferred — listeleme/detay sorgusunda
    yüklenmez; yalnız indirme ucu okur). KVKK: yalnız talebin tarafları
    (talep eden / aktif muhatap / yönlendiren) erişebilir; saklama talebin
    yaşam döngüsüyle sınırlı (talep silinince CASCADE ile silinir).
    """

    __tablename__ = "support_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(
        ForeignKey("support_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    request: Mapped["SupportRequest"] = relationship("SupportRequest", back_populates="attachments")
    uploaded_by: Mapped["User | None"] = relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self) -> str:
        return f"<SupportAttachment #{self.id} req={self.request_id} {self.filename}>"
