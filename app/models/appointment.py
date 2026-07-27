"""Online görüşme / randevu sistemi modelleri (koç ↔ öğrenci).

Şehir dışına ONLINE koçluk veren koçun görüşmelerini sistem içinde yönetmesi:
- `CoachingAppointment`   → İLERİYE dönük randevu (CoachingSession'ın gelecek
  hali; görüşme yapılınca koç KS1 seans kaydına dönüştürür — sonraki paket).
- `CoachingAppointmentSeries` → haftalık tekrarlayan randevu kuralı
  ("Elif her Çarşamba 17:00"); occurrences cron'la ileriye doğru üretilir.
- `CoachAvailabilityWindow` → self-servis slot seçimi için koçun uygunluk
  pencereleri (Pzt 16:00-20:00 gibi).
- `CoachGoogleAccount` → koçun KENDİ Google hesabı OAuth bağlantısı (refresh
  token Fernet ŞİFRELİ saklanır) — Meet linki otomatik üretimi için.

Saat modeli: tarih (Date) + "HH:MM" duvar saati (Türkiye; TR sabit UTC+3,
yaz saati yok). UTC dönüşümü YOK — koç/öğrenci ne görüyorsa DB'de o yazar;
hatırlatma cron'u UTC now + 3 saat ile karşılaştırır (appointment_service).

Durum/kaynak alanları bilinçli düz VARCHAR (Postgres native enum ALTER TYPE
migration yükünden kaçınma — comm_log deseni).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text as sa_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


# ---------------------------------------------------------------------------
# Sabitler (düz string — enum migration'sız)
# ---------------------------------------------------------------------------

APPT_STATUS_PENDING = "pending"        # öğrenci/veli isteği — koç onayı bekler
APPT_STATUS_SCHEDULED = "scheduled"    # planlandı (koç atadı veya onayladı)
APPT_STATUS_CANCELLED = "cancelled"    # iptal edildi
APPT_STATUS_REJECTED = "rejected"      # istek reddedildi
APPT_STATUS_DONE = "done"              # yapıldı (koç işaretler)
APPT_STATUS_NO_SHOW = "no_show"        # öğrenci gelmedi

APPT_STATUSES = (
    APPT_STATUS_PENDING, APPT_STATUS_SCHEDULED, APPT_STATUS_CANCELLED,
    APPT_STATUS_REJECTED, APPT_STATUS_DONE, APPT_STATUS_NO_SHOW,
)

APPT_STATUS_LABELS_TR: dict[str, str] = {
    APPT_STATUS_PENDING: "Onay bekliyor",
    APPT_STATUS_SCHEDULED: "Planlandı",
    APPT_STATUS_CANCELLED: "İptal",
    APPT_STATUS_REJECTED: "Reddedildi",
    APPT_STATUS_DONE: "Yapıldı",
    APPT_STATUS_NO_SHOW: "Gelmedi",
}

# Aktif takvimi işgal eden durumlar (çakışma/slot hesabında sayılır)
APPT_ACTIVE_STATUSES = (APPT_STATUS_PENDING, APPT_STATUS_SCHEDULED)

APPT_SOURCE_COACH = "coach"      # koç doğrudan atadı
APPT_SOURCE_STUDENT = "student"  # öğrenci self-servis istedi
APPT_SOURCE_PARENT = "parent"    # veli self-servis istedi

APPT_SOURCE_LABELS_TR: dict[str, str] = {
    APPT_SOURCE_COACH: "Koç planladı",
    APPT_SOURCE_STUDENT: "Öğrenci istedi",
    APPT_SOURCE_PARENT: "Veli istedi",
}

APPT_LINK_MANUAL = "manual"   # koç kendi linkini yapıştırdı (Meet/Zoom fark etmez)
APPT_LINK_GOOGLE = "google"   # sistem, koçun Google hesabından Meet linki üretti


class CoachingAppointmentSeries(Base):
    """Haftalık tekrarlayan randevu kuralı — occurrences bundan üretilir.

    Koç "her Çarşamba 17:00" der → cron (appointment_maintenance) ileriye dönük
    ~28 günlük occurrence satırlarını üretir. Tek occurrence iptali seriyi
    öldürmez; seri pasifleşince GELECEK scheduled occurrence'lar iptal edilir.
    Google bağlı koçta seri = TEK tekrarlayan Calendar etkinliği (tek Meet
    linki her hafta yeniden kullanılır).
    """

    __tablename__ = "coaching_appointment_series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Pzt..6=Paz
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    duration_min: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="40"
    )

    meeting_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
    google_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("true")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    coach: Mapped["User"] = relationship("User", foreign_keys=[coach_id])

    def __repr__(self) -> str:
        return (
            f"<ApptSeries c={self.coach_id} s={self.student_id} "
            f"dow={self.weekday} {self.start_time} active={self.active}>"
        )


class CoachingAppointment(Base):
    """Tek bir görüşme randevusu (ileriye dönük plan).

    Koç atar (scheduled) veya öğrenci/veli ister (pending → koç onaylar).
    `meeting_link` doluysa öğrenci/veli "Görüşmeye katıl" butonu görür.
    Hatırlatma damgaları (D-1 / 1 saat) cron mükerrer göndermesin diye satırda.
    """

    __tablename__ = "coaching_appointments"
    __table_args__ = (
        Index("ix_appt_coach_date", "coach_id", "date"),
        Index("ix_appt_student_date", "student_id", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("coaching_appointment_series.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    duration_min: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="40"
    )

    status: Mapped[str] = mapped_column(
        String(12), nullable=False, server_default=APPT_STATUS_SCHEDULED
    )
    source: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default=APPT_SOURCE_COACH
    )
    requested_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    meeting_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_source: Mapped[str | None] = mapped_column(String(8), nullable=True)
    google_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    note: Mapped[str | None] = mapped_column(Text, nullable=True)          # koç notu
    request_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # istek notu
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    reminder_d1_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reminder_h1_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    student: Mapped["User"] = relationship("User", foreign_keys=[student_id])
    coach: Mapped["User | None"] = relationship("User", foreign_keys=[coach_id])
    series: Mapped["CoachingAppointmentSeries | None"] = relationship(
        "CoachingAppointmentSeries", foreign_keys=[series_id]
    )

    def __repr__(self) -> str:
        return (
            f"<Appt c={self.coach_id} s={self.student_id} "
            f"{self.date} {self.start_time} {self.status}>"
        )


class CoachAvailabilityWindow(Base):
    """Koçun self-servis randevu için uygunluk penceresi.

    Haftanın günü + saat aralığı; slotlar `slot_minutes` adımlarla üretilir.
    Pencere yoksa öğrenci/veli slot GÖREMEZ (self-servis fiilen kapalı) —
    koç doğrudan atamaya devam edebilir.
    """

    __tablename__ = "coach_availability_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Pzt..6=Paz
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    slot_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="40"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=sa_text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<AvailWindow c={self.coach_id} dow={self.weekday} "
            f"{self.start_time}-{self.end_time}>"
        )


class CoachGoogleAccount(Base):
    """Koçun Google hesabı OAuth bağlantısı (Meet linki otomatik üretimi).

    Refresh token Fernet ŞİFRELİ (system_secrets deseni — anahtar
    session_secret'tan türetilir). Koç başına TEK satır. Bağlantı koparsa
    (token revoke/expire) `last_error` dolar; link üretimi manuel alana düşer
    (best-effort — randevu akışı ASLA bloklanmaz).
    """

    __tablename__ = "coach_google_accounts"
    __table_args__ = (UniqueConstraint("coach_id", name="uq_coach_google"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    coach_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    google_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refresh_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<CoachGoogleAccount c={self.coach_id} {self.google_email}>"
