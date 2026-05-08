"""Veli (PARENT) sistemi modelleri.

Çoğa-çoğa parent_student_link, davet token'ı, bildirim tercihleri,
gönderim günlüğü, öğretmen-veli özel notu ve KVKK denetim izi.
"""

from __future__ import annotations

import enum
from datetime import datetime, time
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class ParentRelation(str, enum.Enum):
    ANNE = "anne"
    BABA = "baba"
    VASI = "vasi"
    DIGER = "diger"


class NotificationKind(str, enum.Enum):
    DAILY_SUMMARY = "daily_summary"
    EMPTY_DAY = "empty_day"
    WEEKLY_REPORT = "weekly_report"
    NEW_PROGRAM = "new_program"
    DROP_ALERT = "drop_alert"
    TEACHER_NOTE = "teacher_note"
    INVITATION = "invitation"
    OTP = "otp"
    # Faz 8: sınav yaklaşıyor — eşik bazlı (D-30, D-7, D-1).
    # exam_target öğrenci profilinden türetilir (User.effective_exam_target),
    # böylece aynı veliye 8. sınıf çocuğu için "LGS yaklaşıyor", 12. sınıf için
    # "YKS yaklaşıyor" yazılır. Tetikleyici cron + idempotent (her eşik bir kez).
    EXAM_APPROACHING = "exam_approaching"


class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"  # şu an sadece OTP için


class NotificationStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class ParentStudentLink(Base):
    """Çoğa-çoğa veli ↔ öğrenci ilişkisi.

    Bir veli birden fazla çocuğa, bir öğrenci birden fazla veliye bağlanabilir.
    is_primary: rapor imzalarında ve varsayılan iletişimde belirleyici.
    """

    __tablename__ = "parent_student_links"
    __table_args__ = (
        UniqueConstraint("parent_id", "student_id", name="uq_parent_student"),
        Index("ix_parent_student_parent", "parent_id"),
        Index("ix_parent_student_student", "student_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[ParentRelation] = mapped_column(
        Enum(ParentRelation), nullable=False, default=ParentRelation.DIGER
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Veli, bu çocuk için tüm bildirimleri sustursa True. INVITATION/OTP gibi
    # sistem mesajları yine geçer; cron/event üreticileri muted olanı atlar.
    muted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    parent: Mapped["User"] = relationship("User", foreign_keys=[parent_id])
    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    created_by: Mapped["User | None"] = relationship("User", foreign_keys=[created_by_id])


class ParentInvitation(Base):
    """Öğretmenin veli davetinin token'ı. 7 gün geçerli."""

    __tablename__ = "parent_invitations"
    __table_args__ = (
        Index("ix_parent_inv_email", "invited_email"),
        Index("ix_parent_inv_student", "student_id"),
        Index("ix_parent_inv_expires", "expires_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invited_email: Mapped[str] = mapped_column(String(255), nullable=False)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    invited_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[ParentRelation] = mapped_column(
        Enum(ParentRelation), nullable=False, default=ParentRelation.DIGER
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    invited_by: Mapped["User"] = relationship("User", foreign_keys=[invited_by_id])


class ParentNotificationPref(Base):
    """Veli başına bildirim açma/kapama + WhatsApp telefonu + sessiz saatler.

    Tek satır per parent (UNIQUE(parent_id)). Veli kayıt olunca varsayılanlarla oluşturulur.
    """

    __tablename__ = "parent_notification_prefs"
    __table_args__ = (UniqueConstraint("parent_id", name="uq_parent_pref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    daily_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weekly_report_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    empty_day_alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    drop_alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    new_program_alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    teacher_note_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Faz 8: sınav yaklaşıyor tetikleyicisi (D-30, D-7, D-1) — varsayılan açık.
    exam_approaching_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default=sa_text("1")
    )

    # WhatsApp — telefon doğrulanmadan gönderim yapılmaz
    whatsapp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    whatsapp_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)  # E.164
    whatsapp_phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    quiet_hours_start: Mapped[time] = mapped_column(Time, default=time(22, 0), nullable=False)
    quiet_hours_end: Mapped[time] = mapped_column(Time, default=time(7, 0), nullable=False)

    # Tek-tıkla bildirim kapatma için stabil token. Davet kabulünde üretilir,
    # her email/WA mesajında aynı kalır; veli "kapat"a basınca tüm bildirimler off.
    unsubscribe_token: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True
    )
    unsubscribed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    parent: Mapped["User"] = relationship("User", foreign_keys=[parent_id])


class NotificationLog(Base):
    """Tüm bildirim gönderim girişimlerinin tek-yazıldığı (append-only) log.

    Üç fayda: (1) "veliye gerçekten ulaştı mı" görünürlük, (2) günlük tavan kontrolü
    (örn. saatte 3'ten fazla mail atma), (3) WhatsApp gibi paralı kanalda fatura uyumu.
    """

    __tablename__ = "notification_logs"
    __table_args__ = (
        Index("ix_notif_parent_sent", "parent_id", "sent_at"),
        Index("ix_notif_student_kind_sent", "student_id", "kind", "sent_at"),
        Index("ix_notif_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[NotificationKind] = mapped_column(Enum(NotificationKind), nullable=False)
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel), nullable=False
    )
    status: Mapped[NotificationStatus] = mapped_column(
        Enum(NotificationStatus), nullable=False, default=NotificationStatus.QUEUED
    )

    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Sessiz saatler / gelecekte gönderilecek bildirimler için tetik zamanı.
    # NULL ise hemen elenebilir.
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Retry mekanizması: kaç defa denendi + bir sonraki deneme ne zaman.
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    parent: Mapped["User"] = relationship("User", foreign_keys=[parent_id])
    student: Mapped["User | None"] = relationship("User", foreign_keys=[student_id])


class TeacherNoteToParent(Base):
    """Öğretmenin veli(ler)e ilettiği özel not.

    GİZLİLİK: Öğrenci asla bu kaydı görmemeli. Öğrenci API/template'lerinde sorgu
    yapılırsa bug. Test fixture'ı ile pinlenecek (Sprint 7+).
    """

    __tablename__ = "teacher_notes_to_parent"
    __table_args__ = (
        Index("ix_tnp_student", "student_id"),
        Index("ix_tnp_teacher", "teacher_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    teacher: Mapped["User"] = relationship("User", foreign_keys=[teacher_id])


class ParentPhoneVerification(Base):
    """Veli telefon doğrulama OTP'si — WhatsApp üzerinden gönderilir.

    Yaşam döngüsü: parent settings'te "WA aç + telefon" → kod üret + WA gönder
    → veli kodu girer → consumed_at set, ParentNotificationPref.whatsapp_phone +
    whatsapp_phone_verified_at güncellenir. expires_at + max attempts ile brute
    force kapatılır.
    """

    __tablename__ = "parent_phone_verifications"
    __table_args__ = (
        Index("ix_ppv_parent_created", "parent_id", "created_at"),
        Index("ix_ppv_phone", "phone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False)  # E.164 normalize
    code: Mapped[str] = mapped_column(String(10), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    parent: Mapped["User"] = relationship("User", foreign_keys=[parent_id])


class ParentSessionLog(Base):
    """KVKK denetim izi — veli login/logout/önemli aksiyonları."""

    __tablename__ = "parent_session_logs"
    __table_args__ = (Index("ix_psl_parent_created", "parent_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    parent: Mapped["User"] = relationship("User", foreign_keys=[parent_id])


PARENT_RELATION_LABELS: dict[ParentRelation, str] = {
    ParentRelation.ANNE: "Anne",
    ParentRelation.BABA: "Baba",
    ParentRelation.VASI: "Vasi",
    ParentRelation.DIGER: "Diğer",
}

NOTIFICATION_KIND_LABELS: dict[NotificationKind, str] = {
    NotificationKind.DAILY_SUMMARY: "Günlük özet",
    NotificationKind.EMPTY_DAY: "Boş gün uyarısı",
    NotificationKind.WEEKLY_REPORT: "Haftalık rapor",
    NotificationKind.NEW_PROGRAM: "Yeni program",
    NotificationKind.DROP_ALERT: "Düşüş alarmı",
    NotificationKind.TEACHER_NOTE: "Öğretmen notu",
    NotificationKind.INVITATION: "Davet",
    NotificationKind.OTP: "Doğrulama kodu",
    NotificationKind.EXAM_APPROACHING: "Sınav yaklaşıyor",
}
