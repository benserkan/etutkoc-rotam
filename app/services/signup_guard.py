"""Signup-anı kötüye kullanım kapısı — aynı IP'den çoklu koç hesabı (#5).

Bağlam: bağımsız koç solo_free 3-öğrenci limitini, birden çok ücretsiz hesap
açıp her birinde 3 öğrenci yöneterek aşabilir. Mobil signup Turnstile'ı atladığı
için (captcha yok) signup-anı IP hız kapısı asıl korumadır.

İki katman:
  - HARD BLOCK: aynı IP'den 24s içinde >= BLOCK_THRESHOLD self-signup varsa
    yenisi 429 ile engellenir (mass farming durur).
  - SIGNAL: abuse_detection.detect_signup_velocity (saatlik tarama) >= FLAG_THRESHOLD
    olan IP'leri süper admin güvenlik kamerasında işaretler.

Kesin önlem (bir kişi = bir hesap) SMS telefon doğrulama kapısıdır (SMS canlıya
alınınca). Bu IP kapısı kaba ama mobil signup'ta tek koruma olduğu için kritik.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AuditAction, AuditLog

SIGNUP_IP_WINDOW_HOURS = 24
# Aynı IP'den 24s içinde bu kadar self-signup VARSA bir sonraki engellenir.
# 3 → ofis/kafe gibi paylaşımlı IP'de birkaç meşru kayıt geçer, 4.+ (mass farming) durur.
SIGNUP_IP_BLOCK_THRESHOLD = 3
# Süper admin sinyali için (yakalansın ama engellenmesin) eşiği.
SIGNUP_IP_FLAG_THRESHOLD = 3


def recent_self_signup_count(
    db: Session, *, ip: str | None, window_hours: int = SIGNUP_IP_WINDOW_HOURS
) -> int:
    """Bu IP'den window_hours içindeki self-signup (USER_CREATE) sayısı."""
    if not ip:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    return (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.action == AuditAction.USER_CREATE,
            AuditLog.ip_address == ip,
            AuditLog.created_at >= cutoff,
            AuditLog.details_json.like('%"self_signup": true%'),
        )
        .scalar()
        or 0
    )


def signup_ip_blocked(db: Session, *, ip: str | None) -> bool:
    """Bu IP'den çok sayıda self-signup yapıldı mı (hard block)?"""
    return recent_self_signup_count(db, ip=ip) >= SIGNUP_IP_BLOCK_THRESHOLD
