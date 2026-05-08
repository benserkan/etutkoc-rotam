"""AuditLog — güvenlik açısından kritik aksiyonların kalıcı kaydı.

Bir hesap kompromise edildiğinde "ne oldu, ne zaman, kim tarafından" sorularına
cevap vermek için. Sprint 2 (multi-tenant) sonrası özellikle SUPER_ADMIN
aksiyonları, başarılı/başarısız login denemeleri ve permission-deny olayları
buraya yazılır.

Tasarım kararları (2026-05-09):
- Geriye doğru immutable: hiç UPDATE yok, sadece INSERT (acidik açıdan basit).
- actor_id NULL olabilir: başarısız login denemelerinde aktör kullanıcı tespit
  edilmemiş olabilir (yanlış e-posta vb.) → email_attempted alanı ile bilgi.
- target_type + target_id: opaque referans (User, Institution, Book, ...).
  ORM relationship YOK — log'un kendisi bağımsız kalsın diye.
- details_json: JSON olarak ek bağlam (IP, UA, request path, before/after diff).
- Bu tablo yedeklenmeli, retention politikası ileride netleşir (örn. 1 yıl).
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditAction(str, enum.Enum):
    """Loglanacak güvenlik olayları.

    Yeni olay eklerken: enum'a değer ekle, log_action() çağrısı koy. UI'da
    super-admin filtreleyebilir.
    """
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGIN_LOCKED = "login_locked"          # lockout devreye girdi
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    PASSWORD_RESET = "password_reset"      # admin tarafından
    PERMISSION_DENIED = "permission_denied"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_DEACTIVATE = "user_deactivate"
    INSTITUTION_CREATE = "institution_create"
    INSTITUTION_UPDATE = "institution_update"
    INSTITUTION_DELETE = "institution_delete"
    IMPERSONATE_START = "impersonate_start"  # super admin sahte oturum aç
    IMPERSONATE_END = "impersonate_end"
    ROLE_CHANGE = "role_change"            # rol değişimi (super admin only)


AUDIT_ACTION_LABELS: dict[AuditAction, str] = {
    AuditAction.LOGIN_SUCCESS: "Giriş başarılı",
    AuditAction.LOGIN_FAILED: "Giriş başarısız",
    AuditAction.LOGIN_LOCKED: "Hesap kilitlendi",
    AuditAction.LOGOUT: "Çıkış",
    AuditAction.PASSWORD_CHANGE: "Şifre değişimi",
    AuditAction.PASSWORD_RESET: "Şifre sıfırlandı (admin)",
    AuditAction.PERMISSION_DENIED: "Yetkisiz erişim denemesi",
    AuditAction.USER_CREATE: "Kullanıcı oluşturuldu",
    AuditAction.USER_UPDATE: "Kullanıcı güncellendi",
    AuditAction.USER_DELETE: "Kullanıcı silindi",
    AuditAction.USER_DEACTIVATE: "Kullanıcı pasifleştirildi",
    AuditAction.INSTITUTION_CREATE: "Kurum oluşturuldu",
    AuditAction.INSTITUTION_UPDATE: "Kurum güncellendi",
    AuditAction.INSTITUTION_DELETE: "Kurum silindi",
    AuditAction.IMPERSONATE_START: "Sahte oturum başlatıldı",
    AuditAction.IMPERSONATE_END: "Sahte oturum bitti",
    AuditAction.ROLE_CHANGE: "Rol değiştirildi",
}


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_actor_created", "actor_id", "created_at"),
        Index("ix_audit_action_created", "action", "created_at"),
        Index("ix_audit_target", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Aksiyonu yapan kullanıcı. Başarısız login'de NULL olabilir (kullanıcı
    # tespit edilmemiş — yanlış e-posta vb.).
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Yanlış girilen e-posta (login_failed senaryosunda actor_id NULL olur,
    # bu alan dolu kalır → "kim hangi e-posta ile denedi" görmek için).
    email_attempted: Mapped[str | None] = mapped_column(String(255), nullable=True)

    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)

    # Hedef nesne — varsa (örn. user_create için yaratılan user'ın ID'si).
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # İz: kim/nerden geldi
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Ek bağlam — JSON olarak (örn. before/after diff, sebep, vb.)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action.value} actor={self.actor_id} t={self.created_at}>"
