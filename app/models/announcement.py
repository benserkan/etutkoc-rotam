"""Stage 7 — Sistem geneli duyuru bandı.

Süper admin tüm kullanıcılara üst banner ile mesaj iletebilsin: bakım
penceresi, yeni özellik, kritik uyarı, vs.

Tasarım:
- starts_at/ends_at — zamanlanmış aktif pencere
- severity → renk (info=mavi, warn=sarı, critical=kırmızı)
- audience → kim görsün (all/super_admin/institution_admin/teacher/student/parent)
- dismissible: kullanıcı kapatabilirse localStorage'da tutulur (her duyuru
  ayrı id ile, kapanan tekrar açılmaz)
- Ardışık birden fazla aktif duyuru olabilir; en yüksek severity'li en üstte
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnnouncementSeverity(str, enum.Enum):
    INFO = "info"        # mavi — bilgi (yeni özellik, eğitim materyali)
    WARN = "warn"        # sarı — dikkat (planlı bakım yaklaşıyor)
    CRITICAL = "critical"  # kırmızı — acil (devam eden kesinti)


class AnnouncementAudience(str, enum.Enum):
    ALL = "all"
    SUPER_ADMIN = "super_admin"
    INSTITUTION_ADMIN = "institution_admin"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


SEVERITY_LABELS_TR: dict[AnnouncementSeverity, str] = {
    AnnouncementSeverity.INFO: "Bilgi",
    AnnouncementSeverity.WARN: "Uyarı",
    AnnouncementSeverity.CRITICAL: "Kritik",
}

AUDIENCE_LABELS_TR: dict[AnnouncementAudience, str] = {
    AnnouncementAudience.ALL: "Tüm kullanıcılar",
    AnnouncementAudience.SUPER_ADMIN: "Süper admin",
    AnnouncementAudience.INSTITUTION_ADMIN: "Kurum yöneticileri",
    AnnouncementAudience.TEACHER: "Öğretmenler",
    AnnouncementAudience.STUDENT: "Öğrenciler",
    AnnouncementAudience.PARENT: "Veliler",
}


class SystemAnnouncement(Base):
    __tablename__ = "system_announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    severity: Mapped[AnnouncementSeverity] = mapped_column(
        Enum(AnnouncementSeverity), nullable=False,
        default=AnnouncementSeverity.INFO,
    )
    audience: Mapped[AnnouncementAudience] = mapped_column(
        Enum(AnnouncementAudience), nullable=False,
        default=AnnouncementAudience.ALL,
    )

    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    dismissible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true"),
    )

    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )

    def is_active(self, now: datetime | None = None) -> bool:
        if now is None:
            from datetime import timezone
            now = datetime.now(timezone.utc)
        starts = self.starts_at
        if starts and starts.tzinfo is None:
            from datetime import timezone
            starts = starts.replace(tzinfo=timezone.utc)
        if starts > now:
            return False
        if self.ends_at:
            ends = self.ends_at
            if ends.tzinfo is None:
                from datetime import timezone
                ends = ends.replace(tzinfo=timezone.utc)
            if ends <= now:
                return False
        return True

    def __repr__(self) -> str:
        return f"<SystemAnnouncement #{self.id} {self.severity.value}>"
