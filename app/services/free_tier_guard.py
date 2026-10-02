"""Ücretsiz paket tekilliği — "ücretsiz paket ve deneme kişi başına bir kez".

Sorun (2026-10-02): Keşif (ücretsiz) paketi 3 öğrenciyle sınırlı; aynı kişi
farklı e-postalarla birden çok koç hesabı açıp her birinde 3'er öğrenci tutarak
(ya da her 14 günde yeni hesapla sınırsız deneme alarak) paket almadan
çalışabilir. Bu modül aynı KİŞİYE ait olabilecek bağımsız koç hesaplarını
("ilişkili hesaplar") üç kanıtla bulur:

  - device : aynı cihaz (web kalıcı `etk_dev` çerezi / mobil X-Device-Id)
  - phone  : aynı cep telefonu (E.164)
  - email  : aynı kanonik e-posta (Gmail'de nokta ve +etiket yok sayılır;
             diğer sağlayıcılarda +etiket)

Kurallar:
  1. Kayıtta ilişkili hesap varsa 14 günlük deneme VERİLMEZ; hesap doğrudan
     Keşif ile açılır (users.trial_denied_reason). Seçtiği paket ödeme
     ekranında hazır bekler.
  2. Ücretli olmayan (deneme / Keşif) hesapta yeni öğrenci eklenirken (ya da
     pasif öğrenci aktif edilirken) ilişkili bir hesapta aktif öğrenci varsa
     → 403 free_tier_duplicate_account. Öğrenciler tek hesapta toplanır ya da
     paket alınır. Ücretli pakette bu kural yoktur (paket kişi başına değil
     hesap başına satın alınır).

IP adresi bilinçli olarak kanıt DEĞİLDİR: mobil operatörler binlerce kişiyi
aynı IP'den çıkarır (yanlış pozitif). IP hızı ayrıca signup_guard'da sınırlı.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User, UserRole
from app.models.coach_device import CoachDeviceLink

DEVICE_COOKIE = "etk_dev"
DEVICE_HEADER = "x-device-id"
DEVICE_COOKIE_MAX_AGE = 2 * 365 * 24 * 3600
_DEVICE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")

REASON_LABELS_TR = {
    "device": "aynı cihaz",
    "phone": "aynı telefon numarası",
    "email": "aynı e-posta adresi",
}

_GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}


# ---------------------------------------------------------------------------
# Kimlik parçaları
# ---------------------------------------------------------------------------


def canonical_email(email: str | None) -> str | None:
    """Aynı posta kutusuna giden yazımları tek biçime indirir."""
    if not email or "@" not in email:
        return None
    local, _, domain = email.strip().lower().rpartition("@")
    local = local.split("+", 1)[0]
    if domain in _GMAIL_DOMAINS:
        local = local.replace(".", "")
        domain = "gmail.com"
    if not local:
        return None
    return f"{local}@{domain}"


def _hash(device_id: str) -> str:
    return hashlib.sha256(device_id.encode("utf-8")).hexdigest()


def device_id_from_request(request) -> str | None:
    """Web çerezi ya da mobil başlıktan cihaz kimliği (geçersizse None)."""
    if request is None:
        return None
    raw = request.headers.get(DEVICE_HEADER) or request.cookies.get(DEVICE_COOKIE)
    if raw and _DEVICE_RE.match(raw):
        return raw
    return None


def ensure_device_id(request, response) -> str | None:
    """Cihaz kimliğini döndür; web'de yoksa kalıcı çerez üret (mobil başlık
    varsa çerez basılmaz). response None ise yalnız okur."""
    existing = device_id_from_request(request)
    if existing or response is None:
        return existing
    new_id = secrets.token_urlsafe(24)
    response.set_cookie(
        key=DEVICE_COOKIE,
        value=new_id,
        max_age=DEVICE_COOKIE_MAX_AGE,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return new_id


def _is_independent_coach(user: User | None) -> bool:
    return bool(
        user is not None
        and user.role == UserRole.TEACHER
        and user.institution_id is None
    )


def record_device(db: Session, user: User, device_id: str | None) -> None:
    """Bağımsız koç ↔ cihaz bağını yaz (idempotent; çağıran commit eder).
    Kimliğe bürünme oturumlarında ÇAĞRILMAZ (yöneticinin cihazı koça bağlanmasın)."""
    if not device_id or not _is_independent_coach(user):
        return
    h = _hash(device_id)
    now = datetime.now(timezone.utc)
    link = (
        db.query(CoachDeviceLink)
        .filter(CoachDeviceLink.user_id == user.id, CoachDeviceLink.device_hash == h)
        .first()
    )
    if link is None:
        db.add(CoachDeviceLink(user_id=user.id, device_hash=h,
                               first_seen_at=now, last_seen_at=now))
    else:
        link.last_seen_at = now
    db.flush()


# ---------------------------------------------------------------------------
# İlişkili hesaplar
# ---------------------------------------------------------------------------


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _valid_link(seen: datetime | None, owner: User) -> bool:
    """Bağ, sahibinin hesabı açıldıktan sonra görülmüş olmalı (1 dk tolerans)."""
    s, c = _aware(seen), _aware(getattr(owner, "created_at", None))
    if s is None or c is None:
        return True
    return (s - c).total_seconds() >= -60


def _coach_query(db: Session, exclude_id: int):
    return db.query(User).filter(
        User.role == UserRole.TEACHER,
        User.institution_id.is_(None),
        User.id != exclude_id,
        ~User.email.like("%@kvkk.local"),
    )


def find_related_accounts(
    db: Session, user: User, *, device_id: str | None = None,
) -> list[tuple[User, str]]:
    """Aynı kişiye ait olabilecek DİĞER bağımsız koç hesapları + kanıt.

    device_id: henüz bağı yazılmamış istek cihazı (kayıt anı) — ek kanıt.
    Her hesap bir kez döner (ilk bulunan kanıtla: device > phone > email).
    """
    found: dict[int, tuple[User, str]] = {}

    # Hesap açılmadan ÖNCE kaydedilmiş bağ geçersizdir (yalnız FK zorlaması
    # olmayan SQLite'ta silinen kullanıcının id'si yeniden kullanılınca oluşur).
    hashes = {
        h for (h, seen) in db.query(CoachDeviceLink.device_hash, CoachDeviceLink.last_seen_at)
        .filter(CoachDeviceLink.user_id == user.id).all()
        if _valid_link(seen, user)
    }
    if device_id:
        hashes.add(_hash(device_id))
    if hashes:
        seen_by_uid: dict[int, datetime] = {}
        for uid, seen in (
            db.query(CoachDeviceLink.user_id, CoachDeviceLink.last_seen_at)
            .filter(CoachDeviceLink.device_hash.in_(hashes),
                    CoachDeviceLink.user_id != user.id).all()
        ):
            prev = seen_by_uid.get(uid)
            if prev is None or (_aware(seen) or prev) > (_aware(prev) or prev):
                seen_by_uid[uid] = seen
        if seen_by_uid:
            for u in _coach_query(db, user.id).filter(User.id.in_(list(seen_by_uid))).all():
                if _valid_link(seen_by_uid[u.id], u):
                    found.setdefault(u.id, (u, "device"))

    if user.phone:
        for u in _coach_query(db, user.id).filter(User.phone == user.phone).all():
            found.setdefault(u.id, (u, "phone"))

    canon = canonical_email(user.email)
    if canon:
        domain = canon.rpartition("@")[2]
        domains = list(_GMAIL_DOMAINS) if domain == "gmail.com" else [domain]
        q = _coach_query(db, user.id).filter(
            or_(*[func.lower(User.email).like(f"%@{d}") for d in domains])
        )
        for u in q.all():
            if canonical_email(u.email) == canon:
                found.setdefault(u.id, (u, "email"))

    return list(found.values())


def _active_student_count(db: Session, coach_id: int) -> int:
    return (
        db.query(func.count(User.id))
        .filter(
            User.role == UserRole.STUDENT,
            User.teacher_id == coach_id,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .scalar() or 0
    )


def trial_denial_reason(db: Session, user: User, *, device_id: str | None) -> str | None:
    """Kayıt anı: ilişkili hesap varsa deneme verilmez → kanıt kodu; yoksa None."""
    related = find_related_accounts(db, user, device_id=device_id)
    return related[0][1] if related else None


class FreeSeatTaken(Exception):
    def __init__(self, other: User, reason: str, students: int):
        self.other = other
        self.reason = reason
        self.students = students
        super().__init__(f"free seat taken by #{other.id} ({reason})")


def check_free_seat(db: Session, coach: User) -> None:
    """Ücretli olmayan bağımsız koç: ilişkili bir hesapta aktif öğrenci varsa
    FreeSeatTaken fırlatır. Ücretli pakette / kurumlu koçta kural yok."""
    from app.services.plans import is_paid_plan

    if not _is_independent_coach(coach) or is_paid_plan(coach.plan or ""):
        return
    for other, reason in find_related_accounts(db, coach):
        if not other.is_active:
            continue
        n = _active_student_count(db, other.id)
        if n > 0:
            raise FreeSeatTaken(other, reason, n)


def free_seat_error_detail(exc: FreeSeatTaken) -> dict:
    """403 gövdesi — mesaj ilişkili hesabın e-postasını maskeli söyler."""
    email = exc.other.email or ""
    local, _, domain = email.partition("@")
    masked = (local[:2] + "***@" + domain) if domain else "başka bir hesap"
    return {
        "error": "forbidden",
        "code": "free_tier_duplicate_account",
        "message": (
            f"Ücretsiz paket kişi başına bir hesaptır. {REASON_LABELS_TR.get(exc.reason, 'Aynı kişi')} "
            f"ile açılmış {masked} hesabında zaten {exc.students} aktif öğrencin var. "
            "Öğrencilerini tek hesapta topla ya da bu hesapta bir paket seç."
        ),
        "details": {
            "reason": exc.reason,
            "other_email_masked": masked,
            "other_students": exc.students,
            "upgrade_url": "/teacher/plan",
        },
    }
