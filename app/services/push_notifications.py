"""Mobil push bildirim servisi (Expo Push API).

E-posta/bildirim üretildiğinde aynı kullanıcının kayıtlı cihazlarına push
gönderir. Expo Push API kimlik gerektirmez (Expo, FCM/APNs'i kendi yönetir);
yalnız `ExponentPushToken[...]` yeterli.

Tüm gönderim **best-effort**: hata fırlatmaz, yalnız loglar. Token geçersizse
(`DeviceNotRegistered`) DB'den silinir.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import DevicePushToken

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
_TIMEOUT = 10.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def register_token(db: Session, *, user_id: int, token: str, platform: str | None = None) -> DevicePushToken:
    """Token'ı kaydet/güncelle (upsert). Token başka kullanıcıdaysa bu kullanıcıya taşı."""
    token = token.strip()
    row = db.query(DevicePushToken).filter(DevicePushToken.token == token).one_or_none()
    if row is None:
        row = DevicePushToken(user_id=user_id, token=token, platform=platform)
        db.add(row)
    else:
        row.user_id = user_id
        if platform:
            row.platform = platform
        row.last_seen_at = _now()
    return row


def unregister_token(db: Session, *, token: str, user_id: int | None = None) -> int:
    """Token'ı sil (çıkışta). user_id verilirse yalnız o kullanıcıya aitse siler."""
    q = db.query(DevicePushToken).filter(DevicePushToken.token == token.strip())
    if user_id is not None:
        q = q.filter(DevicePushToken.user_id == user_id)
    n = q.delete(synchronize_session=False)
    return n


def _expo_send(messages: list[dict]) -> list[dict]:
    """Expo Push API'ye gönder, receipt listesi döner. Mock-able (smoke için)."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            EXPO_PUSH_URL,
            json=messages,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
    out = data.get("data")
    if isinstance(out, list):
        return out
    if isinstance(out, dict):
        return [out]
    return []


def send_push_to_user(
    db: Session,
    *,
    user_id: int,
    title: str,
    body: str,
    data: dict | None = None,
) -> int:
    """Kullanıcının tüm cihazlarına push gönder. Gönderilen mesaj sayısını döner.

    Best-effort: ağ/Expo hatasında 0 döner ve loglar (asla raise etmez).
    Geçersiz token'lar (DeviceNotRegistered) silinir.
    """
    rows = db.query(DevicePushToken).filter(DevicePushToken.user_id == user_id).all()
    if not rows:
        return 0

    messages = [
        {
            "to": r.token,
            "title": title,
            "body": body,
            "sound": "default",
            "data": data or {},
        }
        for r in rows
    ]
    try:
        receipts = _expo_send(messages)
    except Exception as e:  # noqa: BLE001 — push asla akışı bozmamalı
        logger.warning("expo push send failed (non-fatal): %s", e)
        return 0

    # Geçersiz token'ları temizle (receipt sırası mesaj sırasıyla aynı).
    invalid: list[str] = []
    for r, rec in zip(rows, receipts):
        if not isinstance(rec, dict):
            continue
        if rec.get("status") == "error":
            err = (rec.get("details") or {}).get("error")
            if err == "DeviceNotRegistered":
                invalid.append(r.token)
    if invalid:
        try:
            db.query(DevicePushToken).filter(DevicePushToken.token.in_(invalid)).delete(
                synchronize_session=False
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("invalid push token cleanup failed: %s", e)

    return len(messages)
