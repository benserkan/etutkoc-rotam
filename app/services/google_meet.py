"""Google OAuth + Meet linki üretimi (randevu sistemi).

Koç KENDİ Google hesabını "Google ile bağlan" ile bağlar → sistem, koç adına
Google Calendar API'yle etkinlik oluşturup Meet linki üretir (link koçun kendi
hesabından çıkar; etkinlik koçun kişisel takvimine de düşer). Ücretsiz Gmail
1:1 Meet'te 24 saate kadar yeter — Google One/Workspace GEREKMEZ.

- Refresh token Fernet ŞİFRELİ `coach_google_accounts` satırında
  (system_secrets._encrypt/_decrypt reuse — anahtar session_secret türevi).
- `is_configured()` False iken (env'de client id/secret yok) tüm yüzeyler
  gizli; link alanı (elle yapıştırma) her durumda çalışır.
- TÜM çağrılar best-effort sarmalanacak şekilde hata TİPİ fırlatır
  (GoogleMeetError) — randevu akışı asla bloklanmaz, hata koça bilgi olarak
  yansır (`last_error`).
- Ağ çağrıları mock-able helper'larda (`_post_form`, `_api_request`) — smoke
  testleri gerçek Google'a çıkmadan monkeypatch'ler.

Doğrulama notu: calendar.events "hassas kapsam" — Google uygulama doğrulaması
tamamlanana dek OAuth ekranı uyarılı + 100 test kullanıcısıyla sınırlı çalışır
(kurulum rehberi: deploy/GOOGLE_OAUTH_SETUP.md).
"""

from __future__ import annotations

import logging
import threading
import time as time_mod
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CoachGoogleAccount, User
from app.services.system_secrets import _decrypt, _encrypt

logger = logging.getLogger(__name__)

OAUTH_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
OAUTH_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPES = "openid email https://www.googleapis.com/auth/calendar.events"

_TIMEOUT = 20.0
_STATE_TTL_MIN = 20

# Koç başına access token cache (refresh grant pahalı değil ama gereksiz tekrar
# olmasın). {coach_id: (access_token, expires_epoch)}
_token_lock = threading.Lock()
_token_cache: dict[int, tuple[str, float]] = {}


class GoogleMeetError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def is_configured() -> bool:
    return bool(
        (settings.google_oauth_client_id or "").strip()
        and (settings.google_oauth_client_secret or "").strip()
    )


def redirect_uri() -> str:
    return f"{settings.app_base_url.rstrip('/')}/api/v2/google/oauth/callback"


# ---------------------------------------------------------------------------
# OAuth akışı
# ---------------------------------------------------------------------------


def build_state(user_id: int) -> str:
    """CSRF korumalı, süreli, imzalı state (PyJWT + session_secret)."""
    payload = {
        "type": "google_oauth",
        "uid": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=_STATE_TTL_MIN),
    }
    return jwt.encode(payload, settings.session_secret, algorithm="HS256")


def decode_state(state: str) -> int | None:
    try:
        payload = jwt.decode(state, settings.session_secret, algorithms=["HS256"])
        if payload.get("type") != "google_oauth":
            return None
        return int(payload.get("uid"))
    except Exception:  # noqa: BLE001
        return None


def build_auth_url(user: User) -> str:
    if not is_configured():
        raise GoogleMeetError("not_configured", "Google bağlantısı yapılandırılmamış.")
    params = {
        "client_id": settings.google_oauth_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # refresh token her bağlantıda gelsin
        "state": build_state(user.id),
    }
    return f"{OAUTH_AUTH_URL}?{urlencode(params)}"


def _post_form(url: str, data: dict) -> dict:
    """OAuth token/revoke uçlarına form POST. Mock-able (smoke)."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(url, data=data)
    if resp.status_code >= 400:
        raise GoogleMeetError(
            "oauth_http_error", f"Google OAuth hatası ({resp.status_code}): {resp.text[:200]}"
        )
    try:
        return resp.json()
    except ValueError:
        return {}


def _api_request(method: str, url: str, *, token: str, json_body: dict | None = None) -> dict:
    """Calendar/userinfo API çağrısı. Mock-able (smoke)."""
    headers = {"Authorization": f"Bearer {token}"}
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.request(method, url, headers=headers, json=json_body)
    if resp.status_code == 204:
        return {}
    if resp.status_code >= 400:
        raise GoogleMeetError(
            "google_api_error",
            f"Google API hatası ({resp.status_code}): {resp.text[:200]}",
        )
    try:
        return resp.json()
    except ValueError:
        return {}


def exchange_code(db: Session, coach: User, code: str) -> CoachGoogleAccount:
    """OAuth callback: code → refresh token; hesabı kaydet/güncelle."""
    if not is_configured():
        raise GoogleMeetError("not_configured", "Google bağlantısı yapılandırılmamış.")
    data = _post_form(OAUTH_TOKEN_URL, {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri(),
    })
    refresh = (data.get("refresh_token") or "").strip()
    access = (data.get("access_token") or "").strip()
    if not refresh:
        raise GoogleMeetError(
            "no_refresh_token",
            "Google refresh token vermedi — hesap izin ekranında tüm izinler onaylanmalı.",
        )

    email: str | None = None
    if access:
        try:
            info = _api_request("GET", USERINFO_URL, token=access)
            email = info.get("email")
        except GoogleMeetError:
            email = None

    account = (
        db.query(CoachGoogleAccount)
        .filter(CoachGoogleAccount.coach_id == coach.id)
        .first()
    )
    if account is None:
        account = CoachGoogleAccount(coach_id=coach.id)
        db.add(account)
    account.refresh_token_encrypted = _encrypt(refresh)
    account.google_email = email
    account.last_error = None
    db.flush()
    with _token_lock:
        _token_cache.pop(coach.id, None)
    return account


def disconnect(db: Session, coach: User) -> bool:
    account = (
        db.query(CoachGoogleAccount)
        .filter(CoachGoogleAccount.coach_id == coach.id)
        .first()
    )
    if account is None:
        return False
    refresh = _decrypt(account.refresh_token_encrypted)
    if refresh:
        try:  # best-effort revoke — başarısızlık silmeyi engellemez
            _post_form(OAUTH_REVOKE_URL, {"token": refresh})
        except GoogleMeetError as e:
            logger.info("google revoke failed (non-fatal): %s", e)
    db.delete(account)
    db.flush()
    with _token_lock:
        _token_cache.pop(coach.id, None)
    return True


def _access_token(db: Session, account: CoachGoogleAccount) -> str:
    with _token_lock:
        hit = _token_cache.get(account.coach_id)
        if hit is not None and hit[1] > time_mod.time() + 60:
            return hit[0]
    refresh = _decrypt(account.refresh_token_encrypted)
    if not refresh:
        raise GoogleMeetError(
            "decrypt_failed", "Kayıtlı Google bağlantısı çözülemedi — yeniden bağlan."
        )
    data = _post_form(OAUTH_TOKEN_URL, {
        "client_id": settings.google_oauth_client_id,
        "client_secret": settings.google_oauth_client_secret,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    })
    token = (data.get("access_token") or "").strip()
    if not token:
        raise GoogleMeetError(
            "refresh_failed", "Google erişim yenilenemedi — hesabı yeniden bağla."
        )
    expires = time_mod.time() + float(data.get("expires_in") or 3600)
    with _token_lock:
        _token_cache[account.coach_id] = (token, expires)
    return token


# ---------------------------------------------------------------------------
# Meet linki üretimi (Calendar API)
# ---------------------------------------------------------------------------


def _event_times(d, start_time: str, duration_min: int) -> tuple[str, str]:
    from app.services.appointment_service import parse_hhmm

    start = datetime.combine(d, parse_hhmm(start_time))
    end = start + timedelta(minutes=duration_min or 40)
    return start.isoformat(), end.isoformat()


def _event_body(
    *, summary: str, d, start_time: str, duration_min: int,
    recurrence_weekly: bool = False,
) -> dict:
    start_iso, end_iso = _event_times(d, start_time, duration_min)
    body: dict = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": "Europe/Istanbul"},
        "end": {"dateTime": end_iso, "timeZone": "Europe/Istanbul"},
        "conferenceData": {
            "createRequest": {
                "requestId": uuid.uuid4().hex,
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }
    if recurrence_weekly:
        body["recurrence"] = ["RRULE:FREQ=WEEKLY"]
    return body


def _extract_meet_link(event: dict) -> str | None:
    link = event.get("hangoutLink")
    if link:
        return link
    conf = event.get("conferenceData") or {}
    for ep in conf.get("entryPoints") or []:
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            return ep["uri"]
    return None


def get_account(db: Session, coach_id: int) -> CoachGoogleAccount | None:
    return (
        db.query(CoachGoogleAccount)
        .filter(CoachGoogleAccount.coach_id == coach_id)
        .first()
    )


def create_meet_event(
    db: Session,
    *,
    coach_id: int,
    student_name: str,
    d,
    start_time: str,
    duration_min: int,
    recurrence_weekly: bool = False,
) -> tuple[str, str]:
    """Koçun takviminde Meet konferanslı etkinlik oluştur.

    Döner: (event_id, meet_link). Hata → GoogleMeetError (çağıran best-effort
    sarar; last_error'a yazar).
    """
    account = get_account(db, coach_id)
    if account is None:
        raise GoogleMeetError("not_connected", "Google hesabı bağlı değil.")
    token = _access_token(db, account)
    body = _event_body(
        summary=f"Koçluk görüşmesi — {student_name}",
        d=d, start_time=start_time, duration_min=duration_min,
        recurrence_weekly=recurrence_weekly,
    )
    event = _api_request(
        "POST", f"{CALENDAR_EVENTS_URL}?conferenceDataVersion=1",
        token=token, json_body=body,
    )
    event_id = event.get("id") or ""
    link = _extract_meet_link(event)
    if not event_id or not link:
        raise GoogleMeetError(
            "no_meet_link", "Google etkinliği oluştu ama Meet linki dönmedi."
        )
    account.last_error = None
    return event_id, link


def update_event_time(
    db: Session,
    *,
    coach_id: int,
    event_id: str,
    d,
    start_time: str,
    duration_min: int,
) -> None:
    account = get_account(db, coach_id)
    if account is None:
        raise GoogleMeetError("not_connected", "Google hesabı bağlı değil.")
    token = _access_token(db, account)
    start_iso, end_iso = _event_times(d, start_time, duration_min)
    _api_request(
        "PATCH", f"{CALENDAR_EVENTS_URL}/{event_id}",
        token=token,
        json_body={
            "start": {"dateTime": start_iso, "timeZone": "Europe/Istanbul"},
            "end": {"dateTime": end_iso, "timeZone": "Europe/Istanbul"},
        },
    )


def delete_event(db: Session, *, coach_id: int, event_id: str) -> None:
    account = get_account(db, coach_id)
    if account is None:
        return
    token = _access_token(db, account)
    _api_request("DELETE", f"{CALENDAR_EVENTS_URL}/{event_id}", token=token)


# ---------------------------------------------------------------------------
# Randevu entegrasyonu (best-effort sarmalayıcılar)
# ---------------------------------------------------------------------------


def try_attach_meet_link(db: Session, appt, *, series=None) -> bool:
    """Randevuya (veya seriye) otomatik Meet linki üretmeyi DENE.

    Koşullar: yapılandırılmış + koç bağlı + elle link YOK. Seri verilirse tek
    tekrarlayan etkinlik açılır (tek link her hafta kullanılır) ve hem seriye
    hem mevcut occurrence'lara yazılır. Başarısızlık randevuyu BOZMAZ; hata
    hesaba not edilir (koç panelde görür).
    """
    from app.models import (
        APPT_LINK_GOOGLE, APPT_STATUS_SCHEDULED, CoachingAppointment,
    )

    if not is_configured():
        return False
    if appt.meeting_link:
        return False
    if appt.coach_id is None:
        return False
    account = get_account(db, appt.coach_id)
    if account is None:
        return False
    student_name = appt.student.full_name if appt.student else "Öğrenci"
    try:
        event_id, link = create_meet_event(
            db,
            coach_id=appt.coach_id,
            student_name=student_name,
            d=appt.date,
            start_time=appt.start_time,
            duration_min=appt.duration_min or 40,
            recurrence_weekly=series is not None,
        )
    except GoogleMeetError as e:
        logger.warning("meet link create failed coach=%s: %s", appt.coach_id, e.message)
        account.last_error = e.message
        db.flush()
        return False

    if series is not None:
        series.meeting_link = link
        series.link_source = APPT_LINK_GOOGLE
        series.google_event_id = event_id
        # Mevcut occurrence'lara da yaz (link'i olmayanlara)
        for occ in (
            db.query(CoachingAppointment)
            .filter(
                CoachingAppointment.series_id == series.id,
                CoachingAppointment.status == APPT_STATUS_SCHEDULED,
                CoachingAppointment.meeting_link.is_(None),
            )
            .all()
        ):
            occ.meeting_link = link
            occ.link_source = APPT_LINK_GOOGLE
            occ.google_event_id = event_id
    appt.meeting_link = link
    appt.link_source = APPT_LINK_GOOGLE
    appt.google_event_id = event_id
    db.flush()
    return True


def try_sync_time_change(db: Session, appt) -> None:
    """Randevu saati değişince Google etkinliğini best-effort taşı.

    Seriye bağlı (tekrarlayan) etkinlik tek occurrence taşımada GÜNCELLENMEZ
    (tüm seriyi kaydırırdı) — yalnız tekil etkinlikler taşınır.
    """
    from app.models import APPT_LINK_GOOGLE

    if appt.link_source != APPT_LINK_GOOGLE or not appt.google_event_id:
        return
    if appt.series_id is not None:
        return
    try:
        update_event_time(
            db, coach_id=appt.coach_id, event_id=appt.google_event_id,
            d=appt.date, start_time=appt.start_time,
            duration_min=appt.duration_min or 40,
        )
    except GoogleMeetError as e:
        logger.warning("meet event move failed (non-fatal): %s", e.message)


def try_sync_cancel(db: Session, appt) -> None:
    """İptalde tekil Google etkinliğini best-effort sil (seri etkinliği kalır)."""
    from app.models import APPT_LINK_GOOGLE

    if appt.link_source != APPT_LINK_GOOGLE or not appt.google_event_id:
        return
    if appt.series_id is not None:
        return
    try:
        delete_event(db, coach_id=appt.coach_id, event_id=appt.google_event_id)
    except GoogleMeetError as e:
        logger.warning("meet event delete failed (non-fatal): %s", e.message)
