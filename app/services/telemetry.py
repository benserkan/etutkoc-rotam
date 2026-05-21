"""Katman 6 — Ziyaretçi davranış telemetri servisi.

Anasayfa kartlarıyla etkileşim olaylarını kaydeder. Katman 7'nin
contextual bandit'ine girdi sağlar.

KVKK güvencesi:
  - Düz IP/UA değerleri ASLA DB'ye yazılmaz; yalnız SHA256 hash (server salt'ı:
    settings.session_secret — deployment'a özel, log'larda görünmez)
  - Anon ziyaretçi session_id: 40-char (urlsafe token), cookie 90 gün TTL
  - Login varsa viewer_id de tutulur ama session_id korunur (cross-device
    ilişkilendirme YAPMAZ — sadece içerik dağılımı)
  - Throttle: aynı (session_id, slug, event_type) son 10sn'de varsa atla

Public API:
    record_event(db, slug, event_type, session_id, *, ip, ua, viewer)
        → FeatureCardEvent | None  (throttle düşürürse None)
    get_card_stats(db, card_id) → {"impression": N, "view": M, ...}
    get_bulk_stats(db, card_ids) → {card_id: {event_type: count}}
    ensure_session_id(request, response) → str  (cookie alır veya üretir)
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping

from fastapi import Request, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    FeatureCard,
    FeatureCardEvent,
    FeatureEventType,
    User,
)


logger = logging.getLogger(__name__)


SESSION_COOKIE_NAME = "fc_telemetry_sid"
SESSION_COOKIE_MAX_AGE_DAYS = 90
THROTTLE_WINDOW_SECONDS = 10
VALID_EVENT_TYPES: set[str] = {e.value for e in FeatureEventType}


# ---------------------------- Hash + session ----------------------------


def _hash_value(value: str | None) -> str | None:
    """SHA256(salt + value) → 64-char hex. None için None."""
    if not value:
        return None
    salt = settings.session_secret.encode("utf-8")
    h = hashlib.sha256()
    h.update(salt)
    h.update(b"::")
    h.update(value.encode("utf-8", errors="replace")[:512])  # max 512B
    return h.hexdigest()


def _new_session_id() -> str:
    """URL-safe rasgele 40 karakter — anon ziyaretçi cookie değeri."""
    return secrets.token_urlsafe(30)[:40]


def ensure_session_id(request: Request, response: Response) -> str:
    """Cookie varsa al, yoksa üret + Set-Cookie. 90 gün TTL, HttpOnly, SameSite=Lax."""
    sid = request.cookies.get(SESSION_COOKIE_NAME) or ""
    # 40 char tipinde, alfa-numerik/dash/underscore karakter kümesi bekliyoruz
    if not _is_valid_sid(sid):
        sid = _new_session_id()
    # Her zaman set-cookie — TTL'i yenile (sliding session)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        sid,
        max_age=SESSION_COOKIE_MAX_AGE_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=False,  # dev'de HTTP; production'da reverse proxy HTTPS olur
    )
    return sid


def _is_valid_sid(sid: str) -> bool:
    if not sid or not (10 <= len(sid) <= 40):
        return False
    # URL-safe token: harf, rakam, -, _
    return all(c.isalnum() or c in "-_" for c in sid)


# ---------------------------- IP/UA çıkartma ----------------------------


def _client_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    if request.client is not None:
        return (request.client.host or "")[:64]
    return None


def _client_ua(request: Request) -> str | None:
    return (request.headers.get("user-agent") or "")[:512] or None


# ---------------------------- Public API ----------------------------


def record_event(
    db: Session,
    *,
    slug: str,
    event_type: str,
    session_id: str,
    request: Request | None = None,
    viewer: User | None = None,
    now: datetime | None = None,
    variant_slug: str | None = None,
) -> FeatureCardEvent | None:
    """Olay kaydını oluştur — throttle filtresinden geçerse.

    variant_slug: Katman 9 A/B test variant'ı; None ise deney aktif değil.

    None döner:
      - slug DB'de yok
      - event_type geçersiz
      - throttle penceresinde aynı olay zaten var
    """
    if event_type not in VALID_EVENT_TYPES:
        return None
    if not _is_valid_sid(session_id):
        return None

    card = (
        db.query(FeatureCard)
        .filter(FeatureCard.slug == slug)
        .first()
    )
    if card is None:
        return None

    if now is None:
        now = datetime.now(timezone.utc)

    # Throttle: aynı (session, slug, event) son 10sn içinde var mı
    window_start = now - timedelta(seconds=THROTTLE_WINDOW_SECONDS)
    recent = (
        db.query(FeatureCardEvent.id)
        .filter(
            FeatureCardEvent.session_id == session_id,
            FeatureCardEvent.card_id == card.id,
            FeatureCardEvent.event_type == event_type,
            FeatureCardEvent.created_at >= window_start,
        )
        .first()
    )
    if recent is not None:
        return None  # throttled

    # KVKK: düz IP/UA tutma — sadece hash
    ip_h: str | None = None
    ua_h: str | None = None
    if request is not None:
        ip_h = _hash_value(_client_ip(request))
        ua_h = _hash_value(_client_ua(request))

    entry = FeatureCardEvent(
        card_id=card.id,
        card_slug=card.slug,
        event_type=event_type,
        session_id=session_id,
        viewer_role=(viewer.role.value if viewer is not None else None),
        viewer_id=(viewer.id if viewer is not None else None),
        created_at=now,
        ip_hash=ip_h,
        ua_hash=ua_h,
        variant_slug=variant_slug,
    )
    try:
        db.add(entry)
        db.commit()
        db.refresh(entry)
    except Exception as e:  # noqa: BLE001
        logger.warning("telemetry record_event hata: %s", e)
        try:
            db.rollback()
        except Exception:
            pass
        return None

    # Katman 7 — bandit online güncelleme. Reward varsa state update.
    # Hata olursa event kaybedilmez; bandit güncellemesi best-effort.
    try:
        from app.services import bandit
        bandit.record_event_hook(db, entry, viewer=viewer)
    except Exception as e:  # noqa: BLE001
        logger.warning("bandit record_event_hook hata: %s", e)

    return entry


def get_card_stats(db: Session, card_id: int) -> dict[str, int]:
    """Tek kartın tüm event tiplerinde toplam sayısı."""
    out: dict[str, int] = {e.value: 0 for e in FeatureEventType}
    rows = (
        db.query(FeatureCardEvent.event_type, func.count(FeatureCardEvent.id))
        .filter(FeatureCardEvent.card_id == card_id)
        .group_by(FeatureCardEvent.event_type)
        .all()
    )
    for et, n in rows:
        if et in out:
            out[et] = int(n)
    return out


def get_bulk_stats(
    db: Session, card_ids: Iterable[int]
) -> dict[int, dict[str, int]]:
    """Birden çok kart için event sayımlarını topluca al — admin listesi için tek sorgu."""
    ids = list(card_ids)
    if not ids:
        return {}
    out: dict[int, dict[str, int]] = defaultdict(
        lambda: {e.value: 0 for e in FeatureEventType}
    )
    rows = (
        db.query(
            FeatureCardEvent.card_id,
            FeatureCardEvent.event_type,
            func.count(FeatureCardEvent.id),
        )
        .filter(FeatureCardEvent.card_id.in_(ids))
        .group_by(FeatureCardEvent.card_id, FeatureCardEvent.event_type)
        .all()
    )
    for cid, et, n in rows:
        if et in out[cid]:
            out[cid][et] = int(n)
    return dict(out)


def purge_older_than(db: Session, *, days: int = 90) -> int:
    """KVKK saklama: ham veriyi N gün sonra sil. Cron için (Katman 6.5)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    n = (
        db.query(FeatureCardEvent)
        .filter(FeatureCardEvent.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(n or 0)
