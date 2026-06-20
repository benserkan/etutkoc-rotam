"""Mobil push bildirim servisi (Expo Push API).

E-posta/bildirim üretildiğinde aynı kullanıcının kayıtlı cihazlarına push
gönderir. Expo Push API kimlik gerektirmez (Expo, FCM/APNs'i kendi yönetir);
yalnız `ExponentPushToken[...]` yeterli.

Tüm gönderim **best-effort**: hata fırlatmaz, yalnız loglar. Token geçersizse
(`DeviceNotRegistered`) DB'den silinir.
"""
from __future__ import annotations

import json
import logging
import time
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
    from app.services import comm_log  # best-effort gözlem log'u

    kind = (data or {}).get("kind") if isinstance(data, dict) else None
    rows = db.query(DevicePushToken).filter(DevicePushToken.user_id == user_id).all()
    if not rows:
        # Hedef kullanıcının kayıtlı cihazı yok → push ulaşamaz (gözlem için kaydet).
        comm_log.log_push(
            status="suppressed", to_user_id=user_id, subject=title,
            category=kind, error="no_device",
        )
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
        comm_log.log_push(
            status="failed", to_user_id=user_id, subject=title, category=kind,
            to_address=comm_log.mask_token(rows[0].token), error=str(e),
            meta_json=json.dumps({"devices": len(rows)}),
        )
        return 0

    # Geçersiz token'ları temizle (receipt sırası mesaj sırasıyla aynı).
    invalid: list[str] = []
    ok_count = 0
    for r, rec in zip(rows, receipts):
        if not isinstance(rec, dict):
            continue
        if rec.get("status") == "error":
            err = (rec.get("details") or {}).get("error")
            if err == "DeviceNotRegistered":
                invalid.append(r.token)
        elif rec.get("status") == "ok":
            ok_count += 1
    if invalid:
        try:
            db.query(DevicePushToken).filter(DevicePushToken.token.in_(invalid)).delete(
                synchronize_session=False
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("invalid push token cleanup failed: %s", e)

    comm_log.log_push(
        status="sent" if ok_count > 0 else "failed",
        to_user_id=user_id, subject=title, category=kind,
        to_address=comm_log.mask_token(rows[0].token),
        error=None if ok_count > 0 else "all_devices_failed",
        meta_json=json.dumps(
            {"devices": len(rows), "ok": ok_count, "invalid": len(invalid)}
        ),
    )
    return len(messages)


def safe_push(
    db: Session,
    *,
    user_id: int | None,
    title: str,
    body: str,
    data: dict | None = None,
) -> None:
    """E-posta bildirimini mobil push olarak da yansıt (best-effort).

    Tüm rollerde (koç/kurum yöneticisi/öğrenci/veli) e-posta üretilen yerlerde
    çağrılır. ASLA raise etmez — push hiçbir e-posta/iş akışını bozmamalı.
    `user_id` None ise (sistem/satış e-postası) no-op.
    """
    if not user_id:
        return
    try:
        send_push_to_user(db, user_id=user_id, title=title, body=(body or "")[:200], data=data)
    except Exception as e:  # noqa: BLE001
        logger.warning("safe_push failed (non-fatal): %s", e)


# Öğrenci ilerleme → koç push'u için bellek-içi throttle (görev başına spam önleme).
# {student_id: son_push_epoch}. Tek web process'inde tutulur; çok-worker'da nadiren
# birkaç mükerrer push olabilir (best-effort, kabul edilebilir). Migration gerektirmez.
_coach_progress_last: dict[int, float] = {}
COACH_PROGRESS_THROTTLE_SECONDS = 3 * 60 * 60  # öğrenci başına 3 saatte 1 push


def notify_coach_student_progress(
    db: Session,
    *,
    student_id: int,
    student_name: str,
    coach_id: int | None,
    detail: str | None = None,
) -> None:
    """Öğrenci programda işaretleme yapınca koça MOBİL-ONLY push (e-posta YOK).

    Koçun "öğrencim çalışıyor" sinyali. Throttle: öğrenci başına 3 saatte 1 push
    (öğrenci gün içinde çok kalem işaretlese de koç bombardımana uğramaz).
    Best-effort — asla raise etmez.
    """
    if not coach_id:
        return
    try:
        now = time.time()
        last = _coach_progress_last.get(student_id)
        if last is not None and (now - last) < COACH_PROGRESS_THROTTLE_SECONDS:
            return
        _coach_progress_last[student_id] = now
        send_push_to_user(
            db,
            user_id=coach_id,
            title="Öğrenci ilerlemesi",
            body=detail or f"{student_name} programında ilerleme kaydetti.",
            data={"type": "coach_student", "student_id": student_id},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("coach progress push failed (non-fatal): %s", e)
