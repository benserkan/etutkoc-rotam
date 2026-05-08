"""Audit log servisi — güvenlik olaylarını DB'ye yazma yardımcısı.

Tek public fonksiyon: `log_action()`. Çağıran taraflar (auth, deps,
super_admin route'ları) bu fonksiyonu kullanır. Hatalar yutulur ve loglanır
— audit yazımı kullanıcı akışını ASLA bloklamaz.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.models import AuditAction, AuditLog


logger = logging.getLogger(__name__)


def _extract_request_meta(request: Request | None) -> tuple[str | None, str | None]:
    """Request'ten IP ve User-Agent çıkar. Reverse proxy arkasında ise
    X-Forwarded-For başlığının ilk değerini tercih et.
    """
    if request is None:
        return (None, None)
    ua = (request.headers.get("user-agent") or "")[:255] or None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        ip = fwd.split(",")[0].strip()[:64]
    else:
        ip = (request.client.host if request.client else None)
        if ip:
            ip = ip[:64]
    return (ip, ua)


def log_action(
    db: Session,
    *,
    action: AuditAction,
    actor_id: int | None = None,
    email_attempted: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
    autocommit: bool = True,
) -> AuditLog | None:
    """Audit kaydı oluştur. Hata durumunda None döner ve uyarır — kullanıcı
    akışını bloklamaz.

    autocommit=False çağıran tarafın bir transaction içinde topluca commit
    etmesine olanak verir (örn. login akışında user.last_login_at update +
    audit insert tek transaction).
    """
    try:
        ip, ua = _extract_request_meta(request)
        details_json: str | None = None
        if details:
            try:
                details_json = json.dumps(details, ensure_ascii=False, default=str)
            except (TypeError, ValueError) as e:
                logger.warning("audit details serialize hatası: %s", e)
        entry = AuditLog(
            actor_id=actor_id,
            email_attempted=(email_attempted or "").strip().lower()[:255] or None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip,
            user_agent=ua,
            details_json=details_json,
        )
        db.add(entry)
        if autocommit:
            db.commit()
        else:
            db.flush()
        return entry
    except Exception as e:
        logger.warning("audit log yazımı başarısız (sessizce yutuluyor): %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return None
