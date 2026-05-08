"""Auth güvenlik politikaları — login lockout, session hardening, şifre üretme/doğrulama.

Kullanıcı tipine göre farklı eşikler:
- SUPER_ADMIN: en sıkı (3 başarısız → 30 dk kilit)
- INSTITUTION_ADMIN: orta (5 → 15 dk)
- TEACHER/STUDENT/PARENT: gevşek (5 → 10 dk)

Genel mantık:
- Başarısız giriş → failed_login_count++
- Eşik aşılırsa locked_until = now + duration
- locked_until > now iken login isteği reddedilir (parola doğru olsa bile)
- Başarılı giriş → counter sıfır, locked_until None, last_login_* güncellenir
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.models import User, UserRole


# Kullanıcı rolüne göre lockout politikası
# (failed_threshold, lock_duration_minutes)
LOCKOUT_POLICY: dict[UserRole, tuple[int, int]] = {
    UserRole.SUPER_ADMIN: (3, 30),
    UserRole.INSTITUTION_ADMIN: (5, 15),
    UserRole.TEACHER: (5, 10),
    UserRole.STUDENT: (5, 10),
    UserRole.PARENT: (5, 10),
}

# Genel default (rol tespit edilemediyse)
DEFAULT_LOCKOUT = (5, 10)

# Session max-age (saniye) — rol bazlı.
# Admin oturumları daha kısa (yetkili kullanıcı sık logout düşünmeli).
SESSION_MAX_AGE_SECONDS: dict[UserRole, int] = {
    UserRole.SUPER_ADMIN: 4 * 60 * 60,         # 4 saat
    UserRole.INSTITUTION_ADMIN: 8 * 60 * 60,    # 8 saat
    UserRole.TEACHER: 24 * 60 * 60,             # 24 saat
    UserRole.STUDENT: 24 * 60 * 60,
    UserRole.PARENT: 24 * 60 * 60,
}
DEFAULT_SESSION_MAX_AGE = 24 * 60 * 60  # 1 gün

# Cookie default — middleware-level olarak da set edilir (main.py)
SESSION_COOKIE_MAX_AGE = 24 * 60 * 60


def is_locked(user: User, now: datetime | None = None) -> bool:
    """Kullanıcı şu an lockout altında mı?"""
    if user.locked_until is None:
        return False
    now = now or datetime.now(timezone.utc)
    # locked_until naive olabilir (SQLite TIMESTAMP) — UTC varsay
    lu = user.locked_until
    if lu.tzinfo is None:
        lu = lu.replace(tzinfo=timezone.utc)
    return lu > now


def lockout_seconds_remaining(user: User, now: datetime | None = None) -> int:
    """Kalan kilit süresi (saniye). Kilit yoksa 0."""
    if user.locked_until is None:
        return 0
    now = now or datetime.now(timezone.utc)
    lu = user.locked_until
    if lu.tzinfo is None:
        lu = lu.replace(tzinfo=timezone.utc)
    delta = (lu - now).total_seconds()
    return max(0, int(delta))


def register_failed_login(user: User, now: datetime | None = None) -> bool:
    """Başarısız giriş kaydet. Eşik aşılırsa kilitle. Kilit aktif edildiyse True döner."""
    now = now or datetime.now(timezone.utc)
    user.failed_login_count = (user.failed_login_count or 0) + 1
    threshold, duration_min = LOCKOUT_POLICY.get(user.role, DEFAULT_LOCKOUT)
    if user.failed_login_count >= threshold:
        user.locked_until = now + timedelta(minutes=duration_min)
        return True
    return False


def register_successful_login(
    user: User, *, ip: str | None, now: datetime | None = None
) -> None:
    """Başarılı giriş — sayaçları sıfırla, last_* alanları güncelle."""
    now = now or datetime.now(timezone.utc)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    user.last_login_ip = (ip or "")[:64] or None


def session_max_age_for(user: User) -> int:
    return SESSION_MAX_AGE_SECONDS.get(user.role, DEFAULT_SESSION_MAX_AGE)


# ---------------------------- Şifre üretme ve politikası ----------------------------

import secrets
import string

# Rol bazlı minimum şifre uzunluğu
PASSWORD_MIN_LENGTH: dict[UserRole, int] = {
    UserRole.SUPER_ADMIN: 14,
    UserRole.INSTITUTION_ADMIN: 12,
    UserRole.TEACHER: 10,
    UserRole.STUDENT: 8,
    UserRole.PARENT: 8,
}
DEFAULT_PASSWORD_MIN = 8

# Karışıklığa neden olan karakterler hariç (0/O, 1/l/I, vb.)
_AMBIGUOUS = set("0O1lI")
_LOWER = "".join(c for c in string.ascii_lowercase if c not in _AMBIGUOUS)
_UPPER = "".join(c for c in string.ascii_uppercase if c not in _AMBIGUOUS)
_DIGITS = "".join(c for c in string.digits if c not in _AMBIGUOUS)
_SPECIAL = "@#$%&*+-="


def generate_strong_password(role: UserRole | None = None) -> str:
    """Role uygun, güçlü, kullanıcı dostu şifre üret.

    Yapı:
    - Min uzunluk role bazlı (14/12/10/8)
    - En az 1 büyük, 1 küçük, 1 rakam, 1 özel karakter (admin/teacher için)
    - Karışık karakterler (0/O, 1/l/I) çıkarılmış — okurken yanılma yok

    Bu şifre TEK SEFERLİK — kullanıcı ilk girişte must_change_password ile
    zorunlu yeniden belirler.
    """
    if role is None:
        length = DEFAULT_PASSWORD_MIN + 4  # default 12
    else:
        length = PASSWORD_MIN_LENGTH.get(role, DEFAULT_PASSWORD_MIN) + 2
    # Çekirdek: en az 1 her gruptan
    parts = [
        secrets.choice(_UPPER),
        secrets.choice(_LOWER),
        secrets.choice(_DIGITS),
    ]
    if role in (UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.TEACHER):
        parts.append(secrets.choice(_SPECIAL))
    pool = _LOWER + _UPPER + _DIGITS + (_SPECIAL if len(parts) == 4 else "")
    while len(parts) < length:
        parts.append(secrets.choice(pool))
    secrets.SystemRandom().shuffle(parts)
    return "".join(parts)


def validate_password_strength(
    password: str, role: UserRole | None = None
) -> str | None:
    """Şifreyi politikaya göre doğrula.

    Returns:
        None: şifre yeterince güçlü
        str: hata mesajı (kullanıcıya gösterilir)
    """
    if not password:
        return "Şifre boş olamaz."
    min_len = PASSWORD_MIN_LENGTH.get(role, DEFAULT_PASSWORD_MIN) if role else DEFAULT_PASSWORD_MIN
    if len(password) < min_len:
        return f"Şifre en az {min_len} karakter olmalı."
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    if not (has_lower and has_upper and has_digit):
        return "Şifre en az 1 büyük harf, 1 küçük harf ve 1 rakam içermeli."
    # Admin/teacher rolleri için özel karakter zorunlu
    if role in (UserRole.SUPER_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.TEACHER):
        if not any(not c.isalnum() for c in password):
            return "Bu rol için şifrede en az 1 özel karakter (örn @#$%) bulunmalı."
    # Çok yaygın paternleri eleyelim (basit blacklist)
    lowered = password.lower()
    if lowered in {"password", "12345678", "qwerty12", "ogretmen123", "admin1234"}:
        return "Bu şifre çok yaygın — daha rastgele bir tane seçin."
    return None
