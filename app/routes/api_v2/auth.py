"""API v2 — Auth: login / refresh / logout / me (BFF cookie ile).

Next.js BFF (Backend-for-Frontend) için tasarlandı: JWT token'lar HttpOnly
cookie'lerde tutulur, JS'e gelmez (XSS sıfırlama). Response body sadece user
özeti içerir; token gövdede değildir.

Cookie yapısı:
  - access cookie    (`settings.auth_cookie_access_name`)
    HttpOnly, SameSite=Lax, Path=/
    Production'da Secure + __Host- prefix (env override).
  - refresh cookie   (`settings.auth_cookie_refresh_name`)
    HttpOnly, SameSite=Strict, Path=/api/v2/auth/refresh
    Path-scoped: yalnız refresh endpoint'ine gönderilir.

KIRMIZI ÇİZGİ KORUMASI:
  - API v1 (mobile Bearer) DOKUNULMAZ → bu modül ayrı bir router,
    ayrı endpoint path'leri, ayrı sözleşme.
  - Jinja /login DOKUNULMAZ → SessionMiddleware kendi cookie'sini kurar,
    bu modül onunla çakışmaz (farklı cookie adları).
  - Aynı `issue_token_pair`, `verify_password`, `register_*_login`,
    `enforce_login_rate_limit`, `log_action` çağrıları kullanılır.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.deps import get_db
from app.models import AuditAction, User
from app.routes.api_v2.dependencies import (
    _auth_error,
    get_current_refresh_user_v2,
    get_current_user_v2,
)
from app.routes.api_v2.schemas.me import UserPublic
from app.services import security_monitor as secmon
from app.services.audit import log_action
from app.services.auth_security import (
    is_locked,
    lockout_seconds_remaining,
    register_failed_login,
    register_successful_login,
)
from app.services.jwt_auth import (
    TokenError,
    TokenPair,
    decode_token,
    issue_access_token,
    issue_token_pair,
    verify_against_user,
)
from app.services.rate_limit import enforce_login_rate_limit
from app.services.security import verify_password
from app.services import turnstile


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["v2-auth"])


# ============================================================================
# Schemas
# ============================================================================


class LoginIn(BaseModel):
    email: str
    password: str
    # Cloudflare Turnstile token — yalnız CAPTCHA aktifse doğrulanır.
    turnstile_token: str = ""
    # mobile=True (RN app): cookie KURULMAZ, token'lar response body'sinde döner
    # (RN cookie kullanamaz → expo-secure-store'a yazar). Web (False): cookie.
    mobile: bool = False


class TurnstileConfigOut(BaseModel):
    """GET /api/v2/auth/turnstile — frontend widget'ı için."""
    enabled: bool
    site_key: str | None = None


class ImpersonationStatusOut(BaseModel):
    """GET /api/v2/auth/impersonation-status — panel banner'ı için."""
    active: bool = False
    impersonator_name: str | None = None
    target_name: str | None = None


class ForgotPasswordIn(BaseModel):
    email: str
    turnstile_token: str = ""


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str
    confirm_password: str


class GenericOkOut(BaseModel):
    ok: bool = True
    message: str


class SignupTeacherIn(BaseModel):
    full_name: str
    email: str
    password: str
    password_confirm: str
    accept_terms: bool = False
    turnstile_token: str = ""
    # P1 (2026-05-30): cep telefonu — yeni istemcide zorunlu; eski istemci
    # opsiyonel (geriye uyum). Verilirse User.phone'a normalize edilip yazılır,
    # verified_at=None — kullanıcı panelden OTP ile doğrulayacak.
    phone: str | None = None
    # /pricing'den "14 gün ücretsiz dene" ile gelen koç bir tier seçmiş olur
    # (solo_pro/solo_elite/solo_unlimited). Trial bitince bu plan'a geçmek için
    # ödeme talep edilir; başka tier verilirse veya boşsa varsayılan solo_free.
    intended_plan: str | None = None
    # mobile=True (RN app): Turnstile atlanır (mobilde captcha yok — IP hız kapısı
    # korur) + cookie KURULMAZ, token'lar response body'sinde döner (Bearer).
    mobile: bool = False
    # #5 telefon kapısı (SMS açıkken zorunlu): signup/phone/verify'dan alınan imzalı
    # token. SMS kapalıyken (paket alınmadan) yok sayılır.
    phone_token: str = ""


class SignupPhoneStartIn(BaseModel):
    phone: str


class SignupPhoneStartOut(BaseModel):
    sent: bool
    # Dev stub (DEBUG + SMS kapalı) — gerçek SMS gitmediğinde paneline kod
    dev_code: str | None = None


class SignupPhoneVerifyIn(BaseModel):
    phone: str
    code: str


class SignupPhoneVerifyOut(BaseModel):
    phone_token: str


class SignupPhoneRequiredOut(BaseModel):
    required: bool


class SignupInviteIn(BaseModel):
    full_name: str
    email: str
    password: str
    password_confirm: str
    accept_terms: bool = False
    # P1 — cep telefonu (opsiyonel: eski istemci uyumluluğu)
    phone: str | None = None


class InvitationInfoOut(BaseModel):
    """GET /api/v2/auth/signup/invite/{token} — davet bilgisi (public)."""
    valid: bool
    status: str               # pending | consumed | expired | revoked | not_found
    email: str | None = None
    full_name: str | None = None
    role: str | None = None
    institution_name: str | None = None


class SignupOut(BaseModel):
    """Kayıt başarılı — web'de BFF cookie kuruldu; mobilde token'lar gövdede."""
    user: UserPublic
    email_verification_sent: bool
    # mobile=True ise dolu (RN cookie kullanamaz → secure-store'a yazar)
    access_token: str | None = None
    refresh_token: str | None = None
    access_expires_in: int | None = None
    refresh_expires_in: int | None = None


class LoginOut(BaseModel):
    """Login response — token gövdede yok, cookie'de.

    `must_change_password=True` ise frontend kullanıcıyı /password/change'e
    yönlendirmeli; `get_current_user_v2` aksi halde 403 atar (R-001 azaltması).

    `two_factor_required=True` ise cookie KURULMADI; frontend `challenge` ile
    `/auth/2fa/verify`'a TOTP kodu gönderir (2. adım).
    """
    user: UserPublic | None = None
    must_change_password: bool = False
    two_factor_required: bool = False
    challenge: str | None = None
    # mobile=True login/2fa/refresh → token'lar burada döner (web'de None; cookie kullanır)
    access_token: str | None = None
    refresh_token: str | None = None
    access_expires_in: int | None = None
    refresh_expires_in: int | None = None


class TwoFactorVerifyIn(BaseModel):
    challenge: str
    code: str
    mobile: bool = False


class MobileRefreshIn(BaseModel):
    """Mobil (RN) refresh — refresh token gövdede gelir (cookie değil)."""
    refresh_token: str


def _login_out(user: User, pair: TokenPair | None = None) -> "LoginOut":
    """LoginOut üret; mobil ise pair token'larını gövdeye ekle."""
    out = LoginOut(
        user=UserPublic.from_user(user),
        must_change_password=user.must_change_password,
    )
    if pair is not None:
        out.access_token = pair.access_token
        out.refresh_token = pair.refresh_token
        out.access_expires_in = pair.access_expires_in
        out.refresh_expires_in = pair.refresh_expires_in
    return out


# ============================================================================
# Helpers
# ============================================================================


def _request_ip(request: Request) -> str | None:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else None)


_TWO_FACTOR_CHALLENGE_TTL_SECONDS = 5 * 60


def _issue_2fa_challenge(user_id: int) -> str:
    """Kısa ömürlü (5 dk) 2FA bekleme token'ı — cookie DEĞİL, body'de döner.

    Login 1. adımı (şifre doğru, 2FA aktif) sonrası üretilir; 2. adımda
    /auth/2fa/verify'a kod ile birlikte gönderilir. jwt_auth.decode_token'ın
    access/refresh kontrolüne takılmamak için ayrı imzalı token (type='2fa')."""
    import jwt as _jwt
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "2fa",
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + _TWO_FACTOR_CHALLENGE_TTL_SECONDS,
    }
    return _jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode_2fa_challenge(token: str) -> int | None:
    """2FA challenge token'ı çöz → user_id (geçersiz/expired/yanlış tip → None)."""
    import jwt as _jwt
    try:
        data = _jwt.decode(token.strip(), settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if data.get("type") != "2fa":
            return None
        return int(data["sub"])
    except Exception:
        return None


def _set_access_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    response.set_cookie(
        key=settings.auth_cookie_access_name,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite_access,
        path="/",
    )


def _set_refresh_cookie(response: Response, token: str, max_age_seconds: int) -> None:
    response.set_cookie(
        key=settings.auth_cookie_refresh_name,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite_refresh,
        path="/api/v2/auth/refresh",
    )


def _clear_auth_cookies(response: Response) -> None:
    """Logout — her iki cookie'yi de invalidate et (Max-Age=0).

    Cookie path'leri ile birebir aynı olmak ZORUNDA — yoksa browser
    farklı path'teki cookie'yi silmez.
    """
    response.delete_cookie(
        key=settings.auth_cookie_access_name,
        path="/",
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite_access,
        httponly=True,
    )
    response.delete_cookie(
        key=settings.auth_cookie_refresh_name,
        path="/api/v2/auth/refresh",
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite_refresh,
        httponly=True,
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/login", response_model=LoginOut)
def v2_login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """E-posta + şifre → Set-Cookie ile JWT'ler kuruldu. Body'de sade user özeti.

    api_v1/auth.py:api_login ile aynı lockout + audit + generic error mesajı
    politikası — kullanıcı sızıntısı (e-posta enumeration) önlenir.
    """
    email_norm = payload.email.strip().lower()
    ip = _request_ip(request)
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.email == email_norm)
        .first()
    )

    GENERIC = "E-posta veya şifre hatalı."

    # 0a) IP brute-force blok — hesap tespit edilmeden önce reddet (Jinja parite)
    blocked, _row = secmon.is_ip_blocked(db, ip=ip)
    if blocked:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=user.id if user else None,
            email_attempted=email_norm,
            request=request,
            details={"reason": "ip_blocked", "channel": "api_v2"},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limited", "code": "ip_blocked",
                "message": "Bu IP geçici olarak engellendi. Lütfen daha sonra tekrar deneyin.",
            },
        )

    # 0b) Turnstile CAPTCHA — yalnız aktifse VE web isteğiyse. Mobil (RN) app web
    # widget'ı basamaz → Turnstile atlanır; IP blok + lockout + sliding-window
    # rate limit korumaya devam eder (native app için kabul edilebilir; ileride
    # Play Integrity / App Attest eklenebilir).
    if turnstile.is_enabled() and not payload.mobile:
        if not turnstile.verify_token(payload.turnstile_token, ip=ip):
            log_action(
                db,
                action=AuditAction.LOGIN_FAILED,
                actor_id=user.id if user else None,
                email_attempted=email_norm,
                request=request,
                details={"reason": "captcha_failed", "channel": "api_v2"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthenticated", "code": "captcha_failed",
                    "message": "Bot doğrulaması başarısız. Sayfayı yenile ve tekrar dene.",
                },
            )

    if not user:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=None,
            email_attempted=email_norm,
            request=request,
            details={"reason": "user_not_found", "channel": "api_v2"},
        )
        secmon.record_failed_login_ip(db, ip=ip, email_attempted=email_norm)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "code": "invalid_credentials",
                    "message": GENERIC},
        )

    if not user.is_active:
        log_action(
            db,
            action=AuditAction.LOGIN_FAILED,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={"reason": "inactive_account", "channel": "api_v2"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "code": "invalid_credentials",
                    "message": GENERIC},
        )

    if is_locked(user):
        seconds = lockout_seconds_remaining(user)
        log_action(
            db,
            action=AuditAction.LOGIN_LOCKED,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={
                "reason": "locked_active",
                "seconds_remaining": seconds,
                "channel": "api_v2",
            },
        )
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": "locked",
                "code": "locked",
                "message": "Hesap geçici olarak kilitli.",
                "details": {"retry_after_seconds": seconds},
            },
        )

    if not verify_password(payload.password, user.password_hash):
        triggered = register_failed_login(user)
        action = AuditAction.LOGIN_LOCKED if triggered else AuditAction.LOGIN_FAILED
        log_action(
            db,
            action=action,
            actor_id=user.id,
            email_attempted=email_norm,
            request=request,
            details={
                "reason": "wrong_password",
                "failed_count": user.failed_login_count,
                "triggered_lock": triggered,
                "channel": "api_v2",
            },
            autocommit=False,
        )
        secmon.record_failed_login_ip(
            db, ip=ip, email_attempted=email_norm, autocommit=False
        )
        db.commit()
        if triggered:
            seconds = lockout_seconds_remaining(user)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "error": "locked",
                    "code": "locked",
                    "message": "Çok fazla başarısız deneme — hesap kilitlendi.",
                    "details": {"retry_after_seconds": seconds},
                },
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "code": "invalid_credentials",
                    "message": GENERIC},
        )

    # 2FA aktifse: cookie kurma, challenge dön (2. adım /auth/2fa/verify).
    # Şifre doğruydu ama henüz tam yetki yok — failed_count'a dokunma (2. adımda
    # başarıda sıfırlanır; 2FA brute force'u register_failed_login ile korunur).
    if user.two_factor_enabled:
        return LoginOut(two_factor_required=True, challenge=_issue_2fa_challenge(user.id))

    pair = _complete_login(db, user, request, response, email_norm=email_norm,
                           set_cookies=not payload.mobile)
    return _login_out(user, pair if payload.mobile else None)


def _complete_login(
    db: Session, user: User, request: Request, response: Response, *, email_norm: str,
    set_cookies: bool = True,
) -> TokenPair:
    """Başarılı kimlik doğrulama (şifre + varsa 2FA) sonrası oturumu tamamla.

    register_successful_login + audit + auto-resume + ActiveSession (sid) +
    cookie + süper admin alarmı. Login (2FA'sız) ve /auth/2fa/verify ortak kullanır.

    set_cookies=False (mobil/RN): cookie KURULMAZ; çağıran dönen TokenPair'i
    gövdeye koyar. Web (True): HttpOnly cookie kurulur (eski davranış). Her
    durumda üretilen TokenPair döner.
    """
    ip = _request_ip(request)
    register_successful_login(user, ip=ip)
    log_action(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        actor_id=user.id,
        email_attempted=email_norm,
        request=request,
        details={"role": user.role.value, "channel": "api_v2"},
        autocommit=False,
    )
    try:
        from app.services.pause import maybe_auto_resume
        if maybe_auto_resume(db, user):
            log_action(
                db,
                action=AuditAction.USER_AUTO_RESUME,
                actor_id=None,
                target_type="user",
                target_id=user.id,
                request=request,
                details={"trigger": "login", "channel": "api_v2"},
                autocommit=False,
            )
    except Exception:
        logger.exception("auto-resume v2 login fail user=%s", user.id)

    session_token = secmon.generate_session_token()
    try:
        secmon.record_session_start(
            db,
            user=user,
            session_token=session_token,
            ip=ip,
            user_agent=request.headers.get("user-agent"),
            autocommit=False,
        )
    except Exception:
        logger.exception("active_session v2 record fail user=%s", user.id)
    db.commit()

    if user.role.value == "super_admin":
        try:
            from app.services.security_monitor_alerts import notify_super_admin_login
            notify_super_admin_login(db, user=user, ip=ip, request=request)
        except Exception:
            logger.exception("super_admin v2 login alarm fail user=%s", user.id)

    now = datetime.now(timezone.utc)
    pair = issue_token_pair(user, now=now, sid=session_token)
    if set_cookies:
        _set_access_cookie(response, pair.access_token, pair.access_expires_in)
        _set_refresh_cookie(response, pair.refresh_token, pair.refresh_expires_in)
    return pair


@router.post("/2fa/verify", response_model=LoginOut)
def v2_2fa_verify(
    payload: TwoFactorVerifyIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """Login 2. adımı — challenge + TOTP/yedek kod → cookie kur.

    Geçersiz kod register_failed_login ile sayılır (lockout = 2FA brute force
    koruması). Challenge süresi 5 dk."""
    from app.services.totp import verify_login as totp_verify_login

    user_id = _decode_2fa_challenge(payload.challenge)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "code": "challenge_invalid",
                    "message": "Doğrulama oturumu geçersiz veya süresi doldu. Yeniden giriş yapın."},
        )
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == user_id)
        .first()
    )
    if user is None or not user.is_active or not user.two_factor_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "code": "challenge_invalid",
                    "message": "Doğrulama oturumu geçersiz. Yeniden giriş yapın."},
        )
    if is_locked(user):
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={"error": "locked", "code": "locked",
                    "message": "Hesap geçici olarak kilitli.",
                    "details": {"retry_after_seconds": lockout_seconds_remaining(user)}},
        )

    if not totp_verify_login(db, user=user, code=payload.code):
        triggered = register_failed_login(user)
        log_action(
            db,
            action=AuditAction.LOGIN_LOCKED if triggered else AuditAction.LOGIN_FAILED,
            actor_id=user.id,
            email_attempted=user.email,
            request=request,
            details={"reason": "wrong_2fa_code", "triggered_lock": triggered,
                     "channel": "api_v2"},
        )
        if triggered:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={"error": "locked", "code": "locked",
                        "message": "Çok fazla başarısız deneme — hesap kilitlendi.",
                        "details": {"retry_after_seconds": lockout_seconds_remaining(user)}},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthenticated", "code": "invalid_2fa_code",
                    "message": "Doğrulama kodu hatalı."},
        )

    pair = _complete_login(db, user, request, response, email_norm=user.email,
                           set_cookies=not payload.mobile)
    return _login_out(user, pair if payload.mobile else None)


@router.post("/token/refresh", response_model=LoginOut)
def v2_mobile_refresh(
    payload: MobileRefreshIn,
    db: Session = Depends(get_db),
):
    """Mobil (RN) refresh — refresh token gövdede; yeni access döner.

    Web /auth/refresh cookie okur (RN cookie kullanamaz). Rotation YOK (web/v1
    ile aynı): refresh süresi dolana dek aynı refresh ile yeni access alınır;
    şifre değişince pwd_stamp mismatch → refresh de revoke. sid korunur
    (ActiveSession sürekliliği + heartbeat).
    """
    try:
        rp = decode_token(payload.refresh_token.strip())
    except TokenError as e:
        raise _auth_error(str(e), "invalid_token")
    if rp.type != "refresh":
        raise _auth_error("Bu endpoint refresh token bekler", "wrong_token_type")
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == rp.user_id)
        .first()
    )
    if user is None:
        raise _auth_error("Kullanıcı bulunamadı", "user_not_found")
    try:
        verify_against_user(rp, user)
    except TokenError as e:
        raise _auth_error(str(e), "token_revoked")
    if rp.session_id:
        try:
            secmon.heartbeat(db, session_token=rp.session_id)
        except Exception:
            logger.exception("v2 mobile refresh heartbeat fail")
    now = datetime.now(timezone.utc)
    out = _login_out(user)
    out.access_token = issue_access_token(user, now=now, sid=rp.session_id)
    out.access_expires_in = settings.jwt_access_minutes * 60
    return out


@router.post("/refresh", response_model=UserPublic)
def v2_refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_refresh_user_v2),
):
    """Refresh cookie → yeni access cookie.

    Refresh token rotation YOK (stateless, v1 ile aynı). Refresh süresi
    dolana kadar aynı refresh ile yeni access alınır. Şifre değişirse
    pwd_stamp mismatch ile refresh de revoke olur.

    Cevap body'sinde güncel user — frontend "still logged in" doğrulayabilir.
    """
    now = datetime.now(timezone.utc)
    # Refresh token'daki sid'i koru → ActiveSession sürekliliği + heartbeat.
    # imp_by varsa (sahte oturum) onu da taşı → impersonation refresh'te kopmaz.
    sid: str | None = None
    imp_by: int | None = None
    refresh_token = request.cookies.get(settings.auth_cookie_refresh_name)
    if refresh_token:
        try:
            _rp = decode_token(refresh_token.strip())
            sid = _rp.session_id
            imp_by = _rp.impersonator_id
        except Exception:
            sid = None
    if sid:
        try:
            secmon.heartbeat(db, session_token=sid)
        except Exception:
            logger.exception("v2 refresh heartbeat fail")
    new_access = issue_access_token(user, now=now, sid=sid, imp_by=imp_by)
    max_age = settings.jwt_access_minutes * 60
    _set_access_cookie(response, new_access, max_age)
    return UserPublic.from_user(user)


@router.post("/logout")
def v2_logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Cookie'leri sil + audit yaz.

    Auth ZORUNLU DEĞİL — geçersiz cookie ile de istek 200 döner (kullanıcı
    deneyimi: "logout" her zaman çalışır, hata göstermez). Audit yalnız
    cookie'den user çözebilirse yazılır.
    """
    access_token = request.cookies.get(settings.auth_cookie_access_name)
    user = None
    sid: str | None = None
    if access_token:
        from app.routes.api_v2.dependencies import _resolve_from_cookie
        try:
            user = _resolve_from_cookie(request, db)
        except HTTPException:
            user = None
        try:
            sid = decode_token(access_token.strip()).session_id
        except Exception:
            sid = None

    if user is not None:
        log_action(
            db,
            action=AuditAction.LOGOUT,
            actor_id=user.id,
            request=request,
            details={"channel": "api_v2"},
        )
    # ActiveSession'ı kapat → canlı oturum panelinden düşer
    if sid:
        try:
            secmon.terminate_session(db, session_token=sid, reason="logout")
        except Exception:
            logger.exception("v2 logout terminate_session fail")

    # KRİTİK GÜVENLİK: Jinja SessionMiddleware oturumunu da temizle. BFF
    # dependency'si (dependencies._resolve_user_v2) 3. kanal olarak `session`
    # cookie'sini kabul ediyor (geçiş dönemi fallback'i). Impersonation bitince
    # (/admin/impersonate/end) admin'in user_id'si bu session'a yazılıyor; yalnız
    # BFF cookie'sini silmek YETMEZ — kalan session cookie ile dependency
    # authenticate etmeye devam eder ve çıkıştan sonra /admin açık kalır
    # (login de oturum görüp roleHome'a sıçratır). Session'ı boşaltınca
    # SessionMiddleware `session` cookie'sini de Max-Age=0 ile siler.
    try:
        request.session.clear()
    except Exception:
        pass

    _clear_auth_cookies(response)
    return {"ok": True}


def _establish_bff_session(
    db: Session, user: User, request: Request, response: Response,
    *, mobile: bool = False,
):
    """Başarılı kimlik doğrulama sonrası oturum kur (login + signup ortak).

    ActiveSession kaydı (sid) + token pair. Web → access/refresh cookie. Mobil
    (mobile=True) → cookie KURMA; pair'i döndür (caller body'ye koyar, RN Bearer).
    G2a/G3 canlı oturum panelini besler. Döndürdüğü pair'i web ihmal edebilir.
    """
    ip = _request_ip(request)
    session_token = secmon.generate_session_token()
    try:
        secmon.record_session_start(
            db, user=user, session_token=session_token, ip=ip,
            user_agent=request.headers.get("user-agent"),
        )
    except Exception:
        logger.exception("active_session signup record fail user=%s", user.id)
    now = datetime.now(timezone.utc)
    pair = issue_token_pair(user, now=now, sid=session_token)
    if not mobile:
        _set_access_cookie(response, pair.access_token, pair.access_expires_in)
        _set_refresh_cookie(response, pair.refresh_token, pair.refresh_expires_in)
    return pair


def _validate_signup_common(payload, role) -> str | None:
    """Ortak signup doğrulaması — ad/email/şartlar/şifre eşleşme + politika.
    Hata mesajı (str) veya None döner."""
    from app.services.auth_security import validate_password_strength

    full_name = (payload.full_name or "").strip()
    email = (payload.email or "").strip().lower()
    if not full_name or not email:
        return "Ad ve e-posta zorunlu."
    if "@" not in email or "." not in email:
        return "Geçerli bir e-posta girin."
    if not payload.accept_terms:
        return "Kullanım şartlarını kabul etmelisin."
    if payload.password != payload.password_confirm:
        return "Şifreler birbiriyle eşleşmiyor."
    policy_err = validate_password_strength(payload.password, role)
    if policy_err:
        return policy_err
    return None


@router.get("/signup/phone/required", response_model=SignupPhoneRequiredOut)
def v2_signup_phone_required():
    """Signup'ta telefon doğrulama zorunlu mu? (SMS açıkken True). Public."""
    from app.services.signup_phone_service import signup_phone_required
    return SignupPhoneRequiredOut(required=signup_phone_required())


@router.post("/signup/phone/start", response_model=SignupPhoneStartOut)
def v2_signup_phone_start(
    payload: SignupPhoneStartIn,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """Signup için telefon OTP'si gönder (hesap-öncesi). Public. SMS açıkken anlamlı."""
    from app.services.signup_phone_service import start_signup_phone
    from app.services.phone_service import PhoneError
    ip = _request_ip(request)
    try:
        _phone, dev_code = start_signup_phone(db, phone=payload.phone, ip=ip)
    except PhoneError as e:
        code_status = {
            "cooldown_active": status.HTTP_429_TOO_MANY_REQUESTS,
            "ip_rate_limited": status.HTTP_429_TOO_MANY_REQUESTS,
            "phone_in_use": status.HTTP_409_CONFLICT,
            "sms_send_failed": status.HTTP_502_BAD_GATEWAY,
        }.get(e.code, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=code_status,
                            detail={"error": "invalid", "code": e.code, "message": e.message})
    return SignupPhoneStartOut(sent=True, dev_code=dev_code)


@router.post("/signup/phone/verify", response_model=SignupPhoneVerifyOut)
def v2_signup_phone_verify(
    payload: SignupPhoneVerifyIn,
    db: Session = Depends(get_db),
):
    """Signup telefon OTP'sini doğrula → imzalı phone_token. Public."""
    from app.services.signup_phone_service import verify_signup_phone
    from app.services.phone_service import PhoneError
    try:
        token = verify_signup_phone(db, phone=payload.phone, code=payload.code)
    except PhoneError as e:
        st = status.HTTP_429_TOO_MANY_REQUESTS if e.code == "too_many_attempts" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=st,
                            detail={"error": "invalid", "code": e.code, "message": e.message})
    return SignupPhoneVerifyOut(phone_token=token)


@router.post("/signup/teacher", response_model=SignupOut)
def v2_signup_teacher(
    payload: SignupTeacherIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """Bağımsız öğretmen self-signup — 14g trial + BFF auto-login + doğrulama maili.
    Jinja parite: app/routes/signup.py:64. P3 eklemesi: CAPTCHA + email doğrulama."""
    from app.models import UserRole
    from app.services.security import hash_password
    from app.services.plans import start_solo_trial
    from app.services.email_verification import issue_and_send

    ip = _request_ip(request)
    # Mobilde Turnstile yok (RN widget'ı zor) — IP hız kapısı (aşağıda) korur.
    if turnstile.is_enabled() and not payload.mobile:
        if not turnstile.verify_token(payload.turnstile_token, ip=ip):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthenticated", "code": "captcha_failed",
                        "message": "Bot doğrulaması başarısız. Sayfayı yenile ve tekrar dene."},
            )

    # #5 — Signup-anı IP hız kapısı: aynı ağdan kısa sürede çok hesap → engelle
    # (özellikle mobilde captcha olmadığı için çoklu-hesap çiftliğine karşı koruma).
    from app.services.signup_guard import signup_ip_blocked
    if signup_ip_blocked(db, ip=ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limited", "code": "signup_ip_rate_limited",
                    "message": "Bu ağdan kısa sürede çok fazla hesap oluşturuldu. "
                               "Lütfen daha sonra tekrar deneyin veya destekle iletişime geçin."},
        )

    err = _validate_signup_common(payload, UserRole.TEACHER)
    if err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "signup_invalid", "message": err},
        )
    email_clean = payload.email.strip().lower()
    if db.query(User).filter(User.email == email_clean).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "conflict", "code": "email_taken",
                    "message": "Bu e-posta zaten kayıtlı. Giriş yapmayı deneyin."},
        )

    # #5 telefon kapısı (DORMANT — yalnız SMS açıkken/paket alınınca devreye girer):
    # signup_phone_required() True ise telefon SMS-DOĞRULANMIŞ olmalı (phone_token).
    # Kapalıyken (şu an) telefon opsiyonel + doğrulamasız (P1 eski davranış).
    from app.services.signup_phone_service import (
        decode_phone_token, phone_in_use, signup_phone_required,
    )
    phone_normalized: str | None = None
    phone_verified_at_value = None
    if signup_phone_required():
        verified_phone = decode_phone_token(payload.phone_token) if payload.phone_token else None
        if not verified_phone:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error": "invalid", "code": "phone_verification_required",
                        "message": "Devam etmek için cep telefonunu SMS ile doğrulaman gerekiyor."},
            )
        if phone_in_use(db, verified_phone):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "conflict", "code": "phone_in_use",
                        "message": "Bu telefon numarası zaten bir hesapla ilişkili."},
            )
        phone_normalized = verified_phone
        phone_verified_at_value = datetime.now(timezone.utc)
    elif payload.phone:
        from app.services.phone_service import normalize_e164_tr
        phone_normalized = normalize_e164_tr(payload.phone)
        if not phone_normalized:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid", "code": "invalid_phone",
                        "message": "Geçersiz telefon numarası. Türkiye cep telefonu formatı gerekir."},
            )

    new_user = User(
        email=email_clean,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=UserRole.TEACHER,
        institution_id=None,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=False,
        phone=phone_normalized,
        phone_verified_at=phone_verified_at_value,
    )
    db.add(new_user)
    db.flush()
    try:
        start_solo_trial(
            db, user=new_user,
            intended_plan=(payload.intended_plan or None),
            autocommit=False,
        )
    except Exception:
        logger.exception("solo trial start fail user=%s", new_user.id)
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=new_user.id,
        target_type="user",
        target_id=new_user.id,
        request=request,
        details={"email": email_clean, "role": "teacher", "self_signup": True,
                 "channel": "api_v2", "trial_started": True},
        autocommit=False,
    )
    db.commit()

    sent = False
    try:
        issue_and_send(db, user=new_user)
        sent = True
    except Exception:
        logger.exception("email verify issue fail user=%s", new_user.id)

    # Yeni koç self-signup'ı süper admin/satış inbox'una bildir (onboarding takibi).
    try:
        from app.services.email_service import notify_new_signup_admin
        notify_new_signup_admin(new_user)
    except Exception:
        logger.exception("new signup admin notify fail user=%s", new_user.id)

    # Landing dönüşüm ilişkilendirme (best-effort; akışı bloklamaz).
    try:
        from app.services import conversion_service
        conversion_service.record_signup_attribution(
            db, user=new_user, request=request, signup_role="teacher"
        )
    except Exception:
        logger.exception("signup attribution fail user=%s", new_user.id)

    pair = _establish_bff_session(db, new_user, request, response, mobile=payload.mobile)
    out = SignupOut(user=UserPublic.from_user(new_user), email_verification_sent=sent)
    if payload.mobile:
        out.access_token = pair.access_token
        out.refresh_token = pair.refresh_token
        out.access_expires_in = pair.access_expires_in
        out.refresh_expires_in = pair.refresh_expires_in
    return out


def _load_invitation(db: Session, token: str):
    from app.models import Invitation
    from sqlalchemy.orm import joinedload
    return (
        db.query(Invitation)
        .options(joinedload(Invitation.institution))
        .filter(Invitation.token == token)
        .first()
    )


@router.get("/signup/invite/{token}", response_model=InvitationInfoOut)
def v2_signup_invite_info(token: str, db: Session = Depends(get_db)):
    """Davet bilgisi (public) — form pre-fill + geçerlilik durumu."""
    inv = _load_invitation(db, token)
    if inv is None:
        return InvitationInfoOut(valid=False, status="not_found")
    return InvitationInfoOut(
        valid=inv.is_usable,
        status=inv.status.value,
        email=inv.email,
        full_name=inv.full_name,
        role=inv.role.value,
        institution_name=inv.institution.name if inv.institution else None,
    )


@router.post("/signup/invite/{token}", response_model=SignupOut)
def v2_signup_invite(
    token: str,
    payload: SignupInviteIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """Davetiyeli kayıt — kuota + atomik consume + auto-login + doğrulama maili.
    Jinja parite: app/routes/signup.py:210."""
    from app.services.security import hash_password
    from app.services.email_verification import issue_and_send

    inv = _load_invitation(db, token)
    if inv is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "code": "invitation_not_found",
                    "message": "Davetiye bulunamadı."},
        )
    if not inv.is_usable:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": "gone", "code": "invitation_unusable",
                    "message": "Bu davetiye artık kullanılamaz (süresi dolmuş, iptal edilmiş veya kullanılmış)."},
        )

    err = _validate_signup_common(payload, inv.role)
    if err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "signup_invalid", "message": err},
        )
    email_clean = payload.email.strip().lower()
    if db.query(User).filter(User.email == email_clean).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "conflict", "code": "email_taken",
                    "message": "Bu e-posta zaten kayıtlı."},
        )

    # Kuota kontrolü (kurum davetlerinde)
    if inv.institution_id is not None:
        from app.models import Institution
        from app.services.quotas import check_quota_for_create, QuotaExceeded
        inst = db.get(Institution, inv.institution_id)
        if inst is not None:
            qkey = (
                "institution_admins" if inv.role.value == "institution_admin"
                else "teachers" if inv.role.value == "teacher"
                else "students" if inv.role.value == "student"
                else None
            )
            if qkey:
                try:
                    check_quota_for_create(db, institution=inst, quota_key=qkey)
                except QuotaExceeded as e:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error": "conflict", "code": "quota_exceeded",
                                "message": f"Kuota: {e.message}"},
                    )

    # P1 — cep telefonu (opsiyonel)
    phone_normalized: str | None = None
    if payload.phone:
        from app.services.phone_service import normalize_e164_tr
        phone_normalized = normalize_e164_tr(payload.phone)
        if not phone_normalized:
            raise HTTPException(
                status_code=400,
                detail={"error": "invalid", "code": "invalid_phone",
                        "message": "Geçersiz telefon numarası. Türkiye cep telefonu formatı gerekir."},
            )

    new_user = User(
        email=email_clean,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=inv.role,
        institution_id=inv.institution_id,
        is_active=True,
        password_changed_at=datetime.now(timezone.utc),
        must_change_password=False,
        phone=phone_normalized,
    )
    db.add(new_user)
    db.flush()
    inv.consumed_at = datetime.now(timezone.utc)
    inv.consumed_by_user_id = new_user.id
    log_action(
        db,
        action=AuditAction.USER_CREATE,
        actor_id=new_user.id,
        target_type="user",
        target_id=new_user.id,
        request=request,
        details={"email": email_clean, "role": inv.role.value,
                 "institution_id": inv.institution_id, "via_invitation_id": inv.id,
                 "channel": "api_v2"},
        autocommit=False,
    )
    db.commit()

    sent = False
    try:
        issue_and_send(db, user=new_user)
        sent = True
    except Exception:
        logger.exception("email verify issue fail user=%s", new_user.id)

    _establish_bff_session(db, new_user, request, response)
    return SignupOut(user=UserPublic.from_user(new_user), email_verification_sent=sent)


@router.post("/verify-email/{token}", response_model=GenericOkOut)
def v2_verify_email(token: str, db: Session = Depends(get_db)):
    """E-posta doğrulama token'ını işle (public — token kanıt yeterli)."""
    from app.services.email_verification import verify

    user = verify(db, token=token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid", "code": "invalid_token",
                    "message": "Doğrulama bağlantısı geçersiz veya süresi dolmuş."},
        )
    return GenericOkOut(message="E-posta adresiniz doğrulandı. Teşekkürler!")


@router.post("/resend-verification", response_model=GenericOkOut)
def v2_resend_verification(
    user: User = Depends(get_current_user_v2),
    db: Session = Depends(get_db),
):
    """Giriş yapmış kullanıcıya yeni doğrulama maili gönder."""
    from app.services.email_verification import issue_and_send

    if user.email_verified_at is not None:
        return GenericOkOut(message="E-postanız zaten doğrulanmış.")
    try:
        issue_and_send(db, user=user)
    except Exception:
        logger.exception("resend verification fail user=%s", user.id)
    return GenericOkOut(message="Doğrulama bağlantısı e-posta adresinize yeniden gönderildi.")


@router.post("/forgot-password", response_model=GenericOkOut)
def v2_forgot_password(
    payload: ForgotPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(enforce_login_rate_limit),
):
    """Şifre sıfırlama iste — e-postaya token'lı link gönderir.

    Enumeration koruması: hesap var/yok ayrımı yapmadan HER ZAMAN generic 200.
    Token yalnız gerçek + aktif hesap için üretilir/gönderilir. CAPTCHA aktifse
    doğrulanır (e-posta bombardımanı koruması)."""
    ip = _request_ip(request)
    if turnstile.is_enabled():
        if not turnstile.verify_token(payload.turnstile_token, ip=ip):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthenticated", "code": "captcha_failed",
                    "message": "Bot doğrulaması başarısız. Sayfayı yenile ve tekrar dene.",
                },
            )
    from app.services.password_reset import request_reset

    try:
        request_reset(db, email=payload.email, ip=ip)
    except Exception:
        logger.exception("forgot-password request fail")

    return GenericOkOut(
        message=(
            "Eğer bu e-posta sistemde kayıtlıysa, şifre sıfırlama bağlantısı "
            "gönderildi. Gelen kutunuzu (ve spam klasörünü) kontrol edin."
        ),
    )


@router.post("/reset-password", response_model=GenericOkOut)
def v2_reset_password(
    payload: ResetPasswordIn,
    request: Request,
    db: Session = Depends(get_db),
):
    """Token + yeni şifre → şifreyi sıfırla. Politika + breach + tek-kullanım."""
    from app.services.auth_security import validate_password_strength
    from app.services.password_breach import (
        breach_check_message,
        check_password_breach,
    )
    from app.services.password_reset import consume_reset, get_usable_token
    from app.services.security import verify_password

    row = get_usable_token(db, token=payload.token)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid", "code": "invalid_token",
                "message": "Bağlantı geçersiz veya süresi dolmuş. Yeniden sıfırlama isteyin.",
            },
        )
    user = row.user

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "password_mismatch",
                    "message": "Şifreler birbiriyle eşleşmiyor."},
        )
    policy_err = validate_password_strength(payload.new_password, user.role)
    if policy_err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "password_weak", "message": policy_err},
        )
    if verify_password(payload.new_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "password_same",
                    "message": "Yeni şifre eski şifreyle aynı olamaz."},
        )
    breach_count = check_password_breach(payload.new_password)
    if breach_count and breach_count > 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid", "code": "password_breached",
                    "message": breach_check_message(breach_count)},
        )

    consume_reset(db, token_row=row, new_password=payload.new_password)
    log_action(
        db,
        action=AuditAction.PASSWORD_CHANGE,
        actor_id=user.id,
        target_type="user",
        target_id=user.id,
        request=request,
        details={"via": "password_reset", "channel": "api_v2"},
    )
    return GenericOkOut(message="Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.")


@router.get("/turnstile", response_model=TurnstileConfigOut)
def v2_turnstile_config():
    """Cloudflare Turnstile widget yapılandırması (public).

    Frontend login formu CAPTCHA widget'ını yalnız `enabled=True` ise gösterir.
    site_key public'tir (HTML'e gömülür); secret asla dönmez.
    """
    return TurnstileConfigOut(
        enabled=turnstile.is_enabled(),
        site_key=turnstile.get_site_key(),
    )


@router.get("/impersonation-status", response_model=ImpersonationStatusOut)
def v2_impersonation_status(request: Request, db: Session = Depends(get_db)):
    """Aktif istek bir 'sahte oturum' mu? Access cookie'sindeki imp_by claim'inden
    çözülür (token hedefin, imp_by süper admin'i taşır). Banner bunu çağırır;
    active=True ise 'Admin'e dön' gösterilir. Auth dep YOK (her panelde çağrılır)."""
    access = request.cookies.get(settings.auth_cookie_access_name)
    if not access:
        return ImpersonationStatusOut(active=False)
    try:
        p = decode_token(access.strip())
    except Exception:
        return ImpersonationStatusOut(active=False)
    if not p.impersonator_id:
        return ImpersonationStatusOut(active=False)
    admin = db.query(User).filter(User.id == p.impersonator_id).first()
    target = db.query(User).filter(User.id == p.user_id).first()
    return ImpersonationStatusOut(
        active=True,
        impersonator_name=admin.full_name if admin else None,
        target_name=target.full_name if target else None,
    )


@router.get("/me", response_model=UserPublic)
def v2_auth_me(user: User = Depends(get_current_user_v2)):
    """Kolaylık endpoint'i — Next.js middleware kullanıcı çözmek için çağırır.

    `/api/v2/me` ile aynı user'ı döner ama Dalga 1'in MyAccountResponse şişmiş
    payload'ını taşımaz; sadece UserPublic. İstek başına maliyet minimum.
    """
    return UserPublic.from_user(user)
