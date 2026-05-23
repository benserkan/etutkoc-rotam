"""API v2 — 3 kanallı auth resolver.

Kanallar (sıralı):
  1. BFF cookie (`settings.auth_cookie_access_name`)  → Next.js
  2. Authorization: Bearer <jwt>                       → Postman/curl/dev/mobile
  3. SessionMiddleware "session" cookie                → Mevcut Jinja akışı (geçiş süresince)

Hata formatı: API_CONTRACTS_DRAFT §0.2 — `{"error", "code", "message"}`.

KIRMIZI ÇİZGİ KORUMASI (kullanıcı 2026-05-18):
  - API v1 (mobile, Bearer) sözleşmesi DOKUNULMAZ → bu modül v1'in
    `app/routes/api_v1/dependencies.py`'ı ile aynı `decode_token` +
    `verify_against_user` çağrılarını yapar.
  - Jinja Session akışı bozulmaz → `_resolve_from_session`
    `app/deps.py:29-112`'deki password_stamp rotasyon mantığıyla aynı.
  - BFF cookie (yeni) eskileri etkilemez → 3. kanal bağımsız, ilki bulduğu
    kanalı kullanır, diğerleri dokunulmaz.

NOT: SUPER_ADMIN dahil tüm authenticated kullanıcılar erişebilir. Rol kapısı
endpoint-bazlı `require_role_v2(...)` ile eklenir.

MIGRATION_RISKS R-001 azaltması:
  - must_change_password=True ise 403 + code: "password_change_required"
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.deps import get_db
from app.models import User, UserRole
from app.services.jwt_auth import TokenError, decode_token, verify_against_user


bearer_scheme = HTTPBearer(auto_error=False)


def _auth_error(
    message: str,
    code: str,
    http_status: int = status.HTTP_401_UNAUTHORIZED,
) -> HTTPException:
    """Tek noktadan hata zarfı üret."""
    error = "unauthenticated" if http_status == 401 else "forbidden"
    headers = {"WWW-Authenticate": "Bearer"} if http_status == 401 else None
    return HTTPException(
        status_code=http_status,
        detail={"error": error, "code": code, "message": message},
        headers=headers,
    )


def _decode_access_token(token: str, db: Session, *, source: str) -> User:
    """JWT access token'ı çöz + User yükle + verify et.

    Bearer ve BFF cookie kanalları aynı JWT formatını paylaşır; bu helper
    her ikisi tarafından kullanılır. `source` etiketi sadece hata ayıklama için.
    """
    try:
        payload = decode_token(token.strip())
    except TokenError as e:
        raise _auth_error(str(e), "invalid_token")
    if payload.type != "access":
        raise _auth_error(
            f"Bu endpoint access token bekler, gelen: {payload.type}",
            "wrong_token_type",
        )
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == payload.user_id)
        .first()
    )
    if user is None:
        raise _auth_error("Kullanıcı bulunamadı", "user_not_found")
    try:
        verify_against_user(payload, user)
    except TokenError as e:
        raise _auth_error(str(e), "token_revoked")
    return user


def _resolve_from_cookie(request: Request, db: Session) -> User | None:
    """BFF cookie'den user çöz (Next.js akışı).

    Cookie adı `settings.auth_cookie_access_name`. Yoksa None döner —
    sıradaki kanal denenir.

    Token'da `sid` (ActiveSession token) varsa heartbeat atılır — böylece
    G2a/G3 "Aktif Oturumlar" + "Canlı Akış" panelleri BFF kullanıcılarını
    canlı görür. Heartbeat False dönerse oturum uzaktan sonlandırılmış
    demektir → 401 (kullanıcı yeniden giriş yapar).
    """
    token = request.cookies.get(settings.auth_cookie_access_name)
    if not token:
        return None
    user = _decode_access_token(token, db, source="cookie")
    try:
        payload = decode_token(token.strip())
        if payload.session_id:
            from app.services.security_monitor import heartbeat
            if not heartbeat(db, session_token=payload.session_id):
                raise _auth_error("Oturum sonlandırıldı", "session_terminated")
    except TokenError:
        pass
    return user


def _resolve_from_bearer(
    creds: HTTPAuthorizationCredentials | None, db: Session
) -> User | None:
    """Authorization: Bearer header'dan user çöz (mobile + dev/curl)."""
    if creds is None or not creds.credentials:
        return None
    return _decode_access_token(creds.credentials, db, source="bearer")


def _resolve_from_session(request: Request, db: Session) -> User | None:
    """SessionMiddleware cookie'den user çöz (mevcut Jinja akışı)."""
    if not hasattr(request, "session"):
        return None
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == user_id)
        .first()
    )
    if user is None or not user.is_active:
        return None
    # password_stamp rotasyon (app/deps.py:29-112 ile aynı mantık)
    stamp = request.session.get("password_stamp")
    current_stamp = (
        user.password_changed_at.isoformat() if user.password_changed_at else None
    )
    if stamp != current_stamp:
        return None
    return user


def _resolve_user_v2(
    request: Request,
    creds: HTTPAuthorizationCredentials | None,
    db: Session,
) -> User:
    """3-kanal user resolver (must_change kontrolü YOK).

    Cookie BFF → Bearer JWT → Session cookie. İlk dolu kanal kullanılır.
    Hiçbiri yoksa 401.
    """
    user = _resolve_from_cookie(request, db)
    if user is None:
        user = _resolve_from_bearer(creds, db)
    if user is None:
        user = _resolve_from_session(request, db)
    if user is None:
        raise _auth_error("Giriş yapmanız gerekiyor", "missing_credentials")
    return user


def get_current_user_v2(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """3-kanal user resolver — must_change_password=True ise 403.

    Normal endpoint'ler için. Zorunlu şifre değişimini tamamlamamış kullanıcı
    panel verilerine erişemez (R-001).
    """
    user = _resolve_user_v2(request, creds, db)
    if user.must_change_password:
        raise _auth_error(
            "Şifrenizi değiştirmeniz gerekiyor",
            "password_change_required",
            http_status=status.HTTP_403_FORBIDDEN,
        )
    return user


def get_current_user_v2_allow_pwchange(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """get_current_user_v2 gibi ama must_change_password 403'ü ATMAZ.

    Yalnız /me/password-change içindir — zorunlu şifre değişimi akışında
    kullanıcı (must_change=True) bu endpoint'e erişip yeni şifresini
    belirleyebilmeli; aksi halde hesabı kullanılamaz hale gelir."""
    return _resolve_user_v2(request, creds, db)


def get_current_refresh_user_v2(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Sadece /api/v2/auth/refresh için — refresh cookie'den user çöz.

    Path-scoped cookie (`path=/api/v2/auth/refresh`) olduğu için bu endpoint
    dışında gönderilmez. Token tipi `refresh` olmak zorunda.
    """
    token = request.cookies.get(settings.auth_cookie_refresh_name)
    if not token:
        raise _auth_error("Yenileme tokenı bulunamadı", "missing_refresh_token")
    try:
        payload = decode_token(token.strip())
    except TokenError as e:
        raise _auth_error(str(e), "invalid_token")
    if payload.type != "refresh":
        raise _auth_error("Bu endpoint refresh token bekler", "wrong_token_type")
    user = (
        db.query(User)
        .options(joinedload(User.institution))
        .filter(User.id == payload.user_id)
        .first()
    )
    if user is None:
        raise _auth_error("Kullanıcı bulunamadı", "user_not_found")
    try:
        verify_against_user(payload, user)
    except TokenError as e:
        raise _auth_error(str(e), "token_revoked")
    return user


def require_role_v2(*allowed_roles: UserRole):
    """Belirli rolleri gerektiren dependency üretici."""
    def _checker(user: User = Depends(get_current_user_v2)) -> User:
        if user.role not in allowed_roles:
            raise _auth_error(
                "Bu işlemi yapmaya yetkiniz yok",
                "role_required",
                http_status=status.HTTP_403_FORBIDDEN,
            )
        return user
    return _checker


def assert_active_coaching(db: Session, user: User) -> None:
    """Yumuşak ödeme duvarı: bağımsız koç deneme bitip ücretsiz limit aşıldıysa
    aktif koçluk write'larını (program yayınla / görev oluştur) engelle → 403.

    Salt-okuma + öğrenci yönetimi (pasifleştirme) serbest kalır; koç ya yükseltir
    ya öğrenci sayısını limite indirir. Endpoint gövdesinden çağrılır (dependency
    değil — teacher.py ve weekly_plan.py kendi _require_teacher'larını kullanıyor).
    """
    from app.services.plans import solo_trial_status

    st = solo_trial_status(db, user=user)
    if st.get("paywall"):
        if st.get("past_due"):
            msg = ("Aboneliğinizin yenileme zamanı geldi. Koçluğa devam etmek için "
                   "ödeme yapıp aboneliğinizi yenileyin.")
        else:
            msg = (
                f"Deneme süreniz bitti ve {st['student_count']} öğrenciniz var; "
                f"ücretsiz sürüm {st['student_limit']} öğrenci destekler. Devam için "
                f"paketi yükseltin ya da {st['student_limit']} öğrenci tutup gerisini "
                f"pasif duruma geçirin. Paketi yükselttiğinizde pasif öğrencileriniz "
                f"otomatik olarak yeniden aktif olur."
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "paywall_active", "message": msg},
        )


def assert_ai_premium(db: Session, user: User) -> None:
    """AI premium kapısı: ücretli paket + aktif solo deneme (50 kredi tavanlı).
    Ücretsiz / deneme bitmiş → 403 plan_upgrade_required. Tüm AI yazma
    uçlarında (foto/ses yakalama, koçluk içgörüsü, kitap-AI ünite önerisi)
    AYNI kapı kullanılır — tutarlılık için tek kaynak. Kredi tükenince
    consume_credits ayrıca 402 ai_credit_exhausted verir.
    """
    from app.services.plans import ai_premium_allowed

    if not ai_premium_allowed(db, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "code": "plan_upgrade_required",
                    "message": "Bu yapay zekâ özelliği ücretli pakette kullanılabilir. "
                               "Lütfen paketinizi yükseltin."},
        )
