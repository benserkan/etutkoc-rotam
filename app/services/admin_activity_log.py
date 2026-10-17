"""Süper admin "Denetim" — kim, ne zaman, ne yaptı (2026-10-17).

Eskiden sayfa yalnız `audit_logs` tablosunu ham kodlarla (login_success, user_update…)
gösteriyordu; o tablo da büyük ölçüde giriş/çıkış içeriyor. Asıl işler (deneme
karnesi yükleme, öğrenci ekleme, program yayınlama, görev işaretleme, veli daveti…)
kendi tablolarında duruyor ve hiç görünmüyordu.

Bu servis iki kaynağı TEK zaman akışında birleştirir:
  1) audit_logs  → Türkçe başlık + kategori + önem + okunur ayrıntı satırları
  2) alan olayları (salt-okuma türetme; yeni tablo yok):
     deneme sonucu · yeni öğrenci · program yayını (öğrenci+saat gruplu) · görev
     tamamlama (öğrenci+gün gruplu) · seans kaydı · kitap ekleme (koç+saat gruplu) ·
     destek talebi · görev talebi · veli daveti · yanlış soru (öğrenci+gün gruplu) ·
     ödeme denemesi.

Her olay: zaman · kategori · önem (critical|warn|info) · kim (rol) · ne yaptı ·
hedef (bağlantılı) · IP/cihaz · ayrıntılar [{label, value}].
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.models.audit_log import AuditAction, AuditLog

TR = timezone(timedelta(hours=3))
SOURCE_LIMIT = 3000  # her kaynaktan pencere başına en çok satır

CATEGORY_LABELS = {
    "security": "Güvenlik ve giriş",
    "admin": "Yönetim işlemleri",
    "coaching": "Koçluk",
    "student": "Öğrenci",
    "commercial": "Ticari",
    "system": "Sistem",
}
ROLE_LABELS = {
    "super_admin": "Süper admin", "institution_admin": "Kurum yöneticisi",
    "teacher": "Koç", "student": "Öğrenci", "parent": "Veli",
}


@dataclass
class Event:
    key: str
    at: datetime
    category: str
    severity: str  # critical | warn | info
    title: str
    actor_id: int | None = None
    actor_text: str | None = None      # kullanıcı yoksa (ör. başarısız giriş e-postası)
    target_text: str | None = None
    target_url: str | None = None
    target_user_id: int | None = None
    ip: str | None = None
    device: str | None = None
    via_admin_id: int | None = None
    details: list[tuple[str, str]] = field(default_factory=list)


# ── Yardımcılar ──────────────────────────────────────────────────────────────

def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def device_label(ua: str | None) -> str | None:
    """User-Agent → "Chrome · Windows" / "Mobil uygulama · Android"."""
    if not ua:
        return None
    u = ua.lower()
    if "okhttp" in u or "expo" in u or "cfnetwork" in u or "darwin" in u:
        app = "Mobil uygulama"
    elif "edg/" in u:
        app = "Edge"
    elif "opr/" in u or "opera" in u:
        app = "Opera"
    elif "firefox" in u:
        app = "Firefox"
    elif "chrome" in u:
        app = "Chrome"
    elif "safari" in u:
        app = "Safari"
    elif "python" in u or "curl" in u or "httpx" in u or "testclient" in u:
        app = "Betik/test"
    else:
        app = "Tarayıcı"
    if "android" in u or "okhttp" in u:
        os_ = "Android"
    elif "iphone" in u or "ipad" in u or "ios" in u or "cfnetwork" in u:
        os_ = "iOS"
    elif "windows" in u:
        os_ = "Windows"
    elif "mac os" in u or "macintosh" in u:
        os_ = "macOS"
    elif "linux" in u:
        os_ = "Linux"
    else:
        os_ = None
    return f"{app} · {os_}" if os_ else app


_KEY_LABELS = {
    "role": "Rol", "channel": "Kanal", "reason": "Sebep", "failed_count": "Başarısız deneme sayısı",
    "triggered_lock": "Kilit tetiklendi", "via": "Yol", "email": "E-posta", "self_signup": "Kendi kaydoldu",
    "trial_started": "Deneme başladı", "institution_id": "Kurum no", "status": "Durum", "note": "Not",
    "name": "Ad", "slug": "Kısa ad", "plan": "Paket", "affected_users": "Etkilenen kullanıcı",
    "target_email": "Hedef e-posta", "target_role": "Hedef rol", "admin_email": "Admin e-postası",
    "expires_at": "Bitiş", "from": "Önceki", "to": "Yeni", "amount": "Tutar (₺)", "cycle": "Dönem",
    "credits": "Kredi", "pack": "Paket", "kind": "Tür", "ip": "IP", "hours": "Süre (saat)",
    "action": "İşlem", "op": "İşlem", "converted": "Dönüştürülen", "student_ai_enabled": "Öğrenci yapay zekâsı",
    "parent_ai_enabled": "Veli yapay zekâsı", "false_positive": "Yanlış alarm", "section_id": "Bölüm no",
    "type": "Tür", "size_bytes": "Boyut (bayt)", "logo": "Logo", "temp_password_issued": "Geçici şifre verildi",
    "forced_by_admin": "Admin tarafından", "trigger": "Tetikleyen", "last_signal_at": "Son sinyal",
    "is_active": "Aktif", "before": "Önce", "after": "Sonra", "data_subject_request_id": "KVKK talep no",
    "request_reason": "Talep gerekçesi", "status_reason": "Durum açıklaması", "summary": "Özet",
    "manual_scan": "Elle tarama", "triggered": "Tetiklenen", "total_rules": "Toplam kural",
    "themes_created": "Oluşan tema", "candidates_grouped": "Gruplanan aday", "source": "Kaynak",
    "raw_subject": "Konu", "ai_mapped": "Yapay zekâ eşledi", "count": "Sayı", "students": "Öğrenci",
}
_VALUE_LABELS = {
    "wrong_password": "yanlış şifre", "unknown_email": "kayıtlı olmayan e-posta", "inactive": "pasif hesap",
    "api_v2": "web", "api_v1": "mobil uygulama", "jinja": "eski panel", "password_reset": "şifre sıfırlama bağlantısı",
    "auto_inactivity": "uzun süre hareketsizlik", "login": "giriş", "monthly": "aylık", "academic_year": "akademik yıl",
    "annual": "yıllık", "one_time": "tek sefer", "credit_pack": "ek kredi paketi", "kvkk_rtbf_anonymization": "KVKK silme (anonimleştirme)",
    "block": "engelle", "unblock": "engeli kaldır", "resolve": "çözüldü", "send": "gönder", "create": "oluştur",
    "uploaded": "yüklendi", "migration": "veritabanı değişikliği", "verified": "onaylı", "pending": "bekliyor",
    "teacher": "koç", "student": "öğrenci", "parent": "veli", "institution_admin": "kurum yöneticisi",
    "super_admin": "süper admin", "closed": "kapatıldı",
}
_HIDDEN_KEYS = {"_via_admin", "signature", "impersonation_id", "task_ids", "seed_id"}


def _fmt(v) -> str:
    if isinstance(v, bool):
        return "evet" if v else "hayır"
    if v is None:
        return "—"
    if isinstance(v, (list, tuple)):
        return f"{len(v)} kayıt" if len(v) > 5 else ", ".join(_fmt(x) for x in v)
    if isinstance(v, dict):
        parts = [f"{_KEY_LABELS.get(k, k)}: {_fmt(x)}" for k, x in v.items() if x not in (0, None, "", False)]
        return "; ".join(parts) or "—"
    s = str(v)
    if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", s):
        try:
            return datetime.fromisoformat(s).astimezone(TR).strftime("%d.%m.%Y %H:%M")
        except ValueError:
            pass
    return _VALUE_LABELS.get(s, s)


def _details(d: dict) -> list[tuple[str, str]]:
    out = []
    for k, v in d.items():
        if k in _HIDDEN_KEYS or v in (None, "", [], {}):
            continue
        out.append((_KEY_LABELS.get(k, k.replace("_", " ").capitalize()), _fmt(v)))
    return out


# ── 1) audit_logs ────────────────────────────────────────────────────────────

# action → (kategori, önem, başlık)
_ACTION_META: dict[AuditAction, tuple[str, str, str]] = {
    AuditAction.LOGIN_SUCCESS: ("security", "info", "Giriş yaptı"),
    AuditAction.LOGIN_FAILED: ("security", "warn", "Giriş denemesi başarısız"),
    AuditAction.LOGIN_LOCKED: ("security", "critical", "Hesap kilitlendi (çok sayıda yanlış şifre)"),
    AuditAction.LOGOUT: ("security", "info", "Çıkış yaptı"),
    AuditAction.PASSWORD_CHANGE: ("security", "info", "Şifresini değiştirdi"),
    AuditAction.PASSWORD_RESET: ("security", "warn", "Şifre sıfırladı"),
    AuditAction.PERMISSION_DENIED: ("security", "critical", "Yetkisi olmayan bir sayfaya/işleme erişmeye çalıştı"),
    AuditAction.USER_CREATE: ("admin", "info", "Kullanıcı oluşturdu"),
    AuditAction.USER_UPDATE: ("admin", "info", "Kayıt güncelledi"),
    AuditAction.USER_DELETE: ("admin", "critical", "Kullanıcı sildi"),
    AuditAction.USER_DEACTIVATE: ("admin", "warn", "Pasife aldı / iptal etti"),
    AuditAction.INSTITUTION_CREATE: ("admin", "info", "Kurum oluşturdu"),
    AuditAction.INSTITUTION_UPDATE: ("admin", "info", "Kurum bilgisini güncelledi"),
    AuditAction.INSTITUTION_DELETE: ("admin", "critical", "Kurum sildi"),
    AuditAction.IMPERSONATE_START: ("security", "warn", "Sahte oturum açtı (başka kullanıcının gözünden)"),
    AuditAction.IMPERSONATE_END: ("security", "info", "Sahte oturumu kapattı"),
    AuditAction.IMPERSONATE_EXPIRED: ("security", "info", "Sahte oturum süresi doldu"),
    AuditAction.IMPERSONATE_REVOKED: ("security", "warn", "Sahte oturum başka admin tarafından kapatıldı"),
    AuditAction.ABUSE_REMEDIATION: ("security", "warn", "Kötüye kullanım sinyaline toplu işlem uyguladı"),
    AuditAction.ROLE_CHANGE: ("admin", "warn", "Kullanıcının rolünü değiştirdi"),
    AuditAction.FEATURE_CARD_CREATE: ("system", "info", "Vitrin kartı oluşturdu"),
    AuditAction.FEATURE_CARD_UPDATE: ("system", "info", "Vitrin kartını güncelledi"),
    AuditAction.FEATURE_CARD_DELETE: ("system", "info", "Vitrin kartını sildi"),
    AuditAction.FEATURE_CARD_STATUS_CHANGE: ("system", "info", "Vitrin kartının durumunu değiştirdi"),
    AuditAction.FEATURE_CARD_PIN: ("system", "info", "Vitrin kartını sabitledi/serbest bıraktı"),
    AuditAction.FEATURE_CARD_AUTO_DISCOVERED: ("system", "info", "Yeni özellik için vitrin kartı taslağı oluştu"),
    AuditAction.FEATURE_CARD_DISCOVERY_REJECTED: ("system", "info", "Vitrin kartı adayını reddetti"),
    AuditAction.SYSTEM_SETTING_UPDATE: ("admin", "warn", "Sistem ayarını değiştirdi (API anahtarı vb.)"),
    AuditAction.USER_PAUSE_ALERTS: ("coaching", "info", "Öğrencinin uyarılarını susturdu"),
    AuditAction.USER_RESUME_ALERTS: ("coaching", "info", "Öğrencinin uyarılarını açtı"),
    AuditAction.USER_AUTO_PAUSE: ("system", "info", "Uzun süre hareketsiz kaldığı için otomatik beklemeye alındı"),
    AuditAction.USER_AUTO_RESUME: ("system", "info", "Hareket görüldüğü için otomatik yeniden aktifleşti"),
    AuditAction.PAYMENT_INITIATED: ("commercial", "info", "Ödeme başlattı"),
    AuditAction.PAYMENT_SUCCEEDED: ("commercial", "info", "Ödeme yaptı"),
    AuditAction.PAYMENT_FAILED: ("commercial", "warn", "Ödeme başarısız oldu"),
    AuditAction.PAYMENT_REFUNDED: ("commercial", "warn", "Ödeme iade edildi"),
    AuditAction.TESTIMONIAL_MODERATE: ("system", "info", "Yorum/referansın yayın durumunu değiştirdi"),
    AuditAction.SELF_STUDY_UPDATE: ("coaching", "info", "Kitapta çözülen test sayısını elle girdi (bağımsız çalışma)"),
    AuditAction.BOOK_CATALOG_UPDATE: ("system", "info", "Kitap kataloğunu güncelledi"),
}

# user_update / deactivate'in "op"/"target_type" bazlı daha net başlıkları
_UPDATE_TITLES = {
    "ai_toggles": ("coaching", "info", "Öğrencinin yapay zekâ ayarlarını değiştirdi"),
    "ai_toggle_teacher": ("admin", "info", "Koçun yapay zekâ erişimini değiştirdi"),
    "ai_consent_revoked": ("coaching", "info", "Yapay zekâ onayını geri aldı"),
    "set_active": ("admin", "warn", "Hesabın aktifliğini değiştirdi"),
    "archive_books": ("coaching", "info", "Öğrencinin kitaplarını arşivledi/arşivden çıkardı"),
    "pool_period_delete": ("coaching", "warn", "Havuz dönemini sildi"),
    "task_topic_link": ("coaching", "info", "Konusuz görevleri müfredat konusuna bağladı"),
    "grid_revert_completed": ("coaching", "info", "Kitap ızgarasından çözülmüş testi geri aldı"),
    "reconcile_section_counters": ("coaching", "info", "Kitap sayaçlarını düzeltti"),
    "absolute_set": ("coaching", "info", "Kitapta çözülen test sayısını elle değiştirdi"),
    "alarm_resolve": ("admin", "info", "Alarmı çözüldü işaretledi"),
    "alarm_scan": ("admin", "info", "Alarm taramasını elle çalıştırdı"),
    "abuse_scan": ("admin", "info", "Kötüye kullanım taramasını elle çalıştırdı"),
    "contact_request": ("commercial", "info", "İletişim talebini güncelledi"),
    "crm_action": ("commercial", "info", "Müşteri aksiyonu kaydetti"),
    "error_event": ("admin", "info", "Sistem hatasını çözüldü işaretledi"),
    "offer": ("commercial", "info", "Teklif gönderdi/güncelledi"),
    "suspicious_ip": ("security", "warn", "Şüpheli IP adresini engelledi/serbest bıraktı"),
    "invitation_revoked": ("admin", "warn", "Daveti iptal etti"),
    "invitation_created": ("admin", "info", "Öğretmen daveti oluşturdu"),
}


def _audit_events(db: Session, since: datetime, until: datetime, actor_ids: set[int] | None,
                  email_q: str | None) -> list[Event]:
    q = db.query(AuditLog).filter(AuditLog.created_at >= since, AuditLog.created_at < until)
    if actor_ids is not None:
        cond = AuditLog.actor_id.in_(actor_ids or {-1})
        if email_q:
            cond = cond | AuditLog.email_attempted.ilike(f"%{email_q}%")
        q = q.filter(cond)
    out: list[Event] = []
    for a in q.order_by(AuditLog.created_at.desc()).limit(SOURCE_LIMIT).all():
        try:
            d = json.loads(a.details_json) if a.details_json else {}
        except ValueError:
            d = {}
        if not isinstance(d, dict):
            d = {}
        cat, sev, title = _ACTION_META.get(a.action, ("system", "info", a.action.value))
        sub = d.get("op") or d.get("type") or a.target_type
        if a.action in (AuditAction.USER_UPDATE, AuditAction.USER_DEACTIVATE, AuditAction.USER_CREATE) and sub in _UPDATE_TITLES:
            cat, sev, title = _UPDATE_TITLES[sub]
        if a.action == AuditAction.USER_CREATE and d.get("self_signup"):
            cat, title = "admin", "Kendi hesabını açtı (ücretsiz deneme)"
        if a.action == AuditAction.LOGIN_FAILED and d.get("reason") == "unknown_email":
            title = "Kayıtlı olmayan e-postayla giriş denendi"
        if a.action == AuditAction.PASSWORD_CHANGE and d.get("via") == "password_reset":
            title = "Şifremi unuttum bağlantısıyla şifresini yeniledi"
        if a.action == AuditAction.LOGIN_SUCCESS and d.get("channel") == "api_v1":
            title = "Mobil uygulamadan giriş yaptı"
        target_url = None
        target_user_id = None
        if a.target_type == "user" and a.target_id:
            target_url, target_user_id = f"/admin/users/{a.target_id}", a.target_id
        elif a.target_type == "institution" and a.target_id:
            target_url = f"/admin/institutions/{a.target_id}"
        target_text = d.get("target_email") or d.get("name") or d.get("email") if a.action not in (
            AuditAction.LOGIN_SUCCESS, AuditAction.LOGOUT) else None
        out.append(Event(
            key=f"a:{a.id}", at=_aware(a.created_at), category=cat, severity=sev, title=title,
            actor_id=a.actor_id, actor_text=None if a.actor_id else (a.email_attempted or "Sistem"),
            target_text=target_text, target_url=target_url, target_user_id=target_user_id,
            ip=a.ip_address, device=device_label(a.user_agent),
            via_admin_id=d.get("_via_admin") if isinstance(d.get("_via_admin"), int) else None,
            details=_details({k: v for k, v in d.items()
                              if not (a.action in (AuditAction.LOGIN_SUCCESS, AuditAction.LOGOUT) and k == "role")}),
        ))
    return out


# ── 2) Alan olayları ─────────────────────────────────────────────────────────

def _domain_events(db: Session, since: datetime, until: datetime, actor_ids: set[int] | None) -> list[Event]:
    from app.models import Book, ExamResult
    from app.models.coaching_session import CoachingSession
    from app.models.parent import ParentInvitation
    from app.models.payment_transaction import PaymentTransaction
    from app.models.support_request import SupportRequest
    from app.models.task import Task
    from app.models.task_request import REQUEST_TYPE_LABELS, TaskRequest
    from app.models.wrong_question import WrongQuestion

    def by_actor(q, col):
        return q.filter(col.in_(actor_ids or {-1})) if actor_ids is not None else q

    names: dict[int, str] = {}
    out: list[Event] = []

    # Deneme sonucu
    q = db.query(ExamResult).filter(ExamResult.created_at >= since, ExamResult.created_at < until)
    for e in by_actor(q, ExamResult.created_by_id).limit(SOURCE_LIMIT).all():
        pdf = e.import_source == "pdf_import"
        names[e.student_id] = ""
        sec = e.section.value.upper() if getattr(e, "section", None) is not None else ""
        out.append(Event(
            key=f"exam:{e.id}", at=_aware(e.created_at), category="coaching", severity="info",
            title="Deneme karnesini PDF'ten yükledi" if pdf else "Deneme sonucunu elle girdi",
            actor_id=e.created_by_id, target_user_id=e.student_id, target_url=f"/admin/users/{e.student_id}",
            target_text=f"'{e.title}'",
            details=[("Deneme", e.title), ("Tür", sec or "—"), ("Deneme tarihi", e.exam_date.strftime("%d.%m.%Y")),
                     ("Net", f"{e.net:.2f}".replace(".", ",")),
                     ("Doğru / Yanlış / Boş", f"{e.total_correct} / {e.total_wrong} / {e.total_blank}"),
                     ("Yöntem", "PDF karne (yapay zekâ okudu)" if pdf else "elle giriş")],
        ))

    # Yeni öğrenci (koçun eklediği)
    q = db.query(User).filter(User.role == UserRole.STUDENT, User.created_at >= since, User.created_at < until)
    for s in by_actor(q, User.teacher_id).limit(SOURCE_LIMIT).all():
        out.append(Event(
            key=f"stu:{s.id}", at=_aware(s.created_at), category="coaching", severity="info",
            title="Öğrenci ekledi" if s.teacher_id else "Öğrenci hesabı açıldı",
            actor_id=s.teacher_id, target_user_id=s.id, target_url=f"/admin/users/{s.id}",
            details=[("E-posta", s.email), ("Sınıf", s.display_grade_label)],
        ))

    # Program yayını — öğrenci + saat gruplu (koç aynı anda haftayı yayınlar)
    rows = (
        db.query(Task.student_id, User.teacher_id, func.min(Task.published_at), func.count(Task.id),
                 func.min(Task.date), func.max(Task.date))
        .join(User, User.id == Task.student_id)
        .filter(Task.published_at >= since, Task.published_at < until)
        .group_by(Task.student_id, User.teacher_id, func.date_trunc("hour", Task.published_at)
                  if db.bind.dialect.name == "postgresql" else func.strftime("%Y-%m-%d %H", Task.published_at))
    )
    if actor_ids is not None:
        rows = rows.filter(User.teacher_id.in_(actor_ids or {-1}))
    for sid, tid, at, n, d1, d2 in rows.limit(SOURCE_LIMIT).all():
        rng = d1.strftime("%d.%m") if d1 == d2 else f"{d1:%d.%m}–{d2:%d.%m}"
        out.append(Event(
            key=f"pub:{sid}:{_aware(at).timestamp():.0f}", at=_aware(at), category="coaching", severity="info",
            title=f"Program yayınladı ({n} görev)", actor_id=tid, target_user_id=sid,
            target_url=f"/admin/users/{sid}", details=[("Görev sayısı", str(n)), ("Program günleri", rng)],
        ))

    # Görev tamamlama — öğrenci + gün gruplu
    day = (func.date(func.timezone("Europe/Istanbul", Task.completed_at))
           if db.bind.dialect.name == "postgresql" else func.date(Task.completed_at))
    rows = (
        db.query(Task.student_id, day, func.count(Task.id), func.max(Task.completed_at))
        .filter(Task.completed_at >= since, Task.completed_at < until)
        .group_by(Task.student_id, day)
    )
    if actor_ids is not None:
        rows = rows.filter(Task.student_id.in_(actor_ids or {-1}))
    for sid, _d, n, last in rows.limit(SOURCE_LIMIT).all():
        out.append(Event(
            key=f"done:{sid}:{_d}", at=_aware(last), category="student", severity="info",
            title=f"{n} görevi tamamlandı işaretledi", actor_id=sid,
            details=[("Görev sayısı", str(n)), ("Gün", str(_d))],
        ))

    # Seans kaydı
    q = db.query(CoachingSession).filter(CoachingSession.created_at >= since, CoachingSession.created_at < until)
    for s in by_actor(q, CoachingSession.coach_id).limit(SOURCE_LIMIT).all():
        out.append(Event(
            key=f"ses:{s.id}", at=_aware(s.created_at), category="coaching", severity="info",
            title="Seans kaydı girdi", actor_id=s.coach_id, target_user_id=s.student_id,
            target_url=f"/admin/users/{s.student_id}",
            details=[("Seans tarihi", s.session_date.strftime("%d.%m.%Y")),
                     ("Durum", getattr(s.status, "value", str(s.status)))],
        ))

    # Kitap ekleme — koç + saat gruplu (katalogdan toplu kopyalama tek satır olsun)
    q = db.query(Book).filter(Book.created_at >= since, Book.created_at < until, Book.teacher_id.isnot(None))
    groups: dict[tuple, list] = {}
    for b in by_actor(q, Book.teacher_id).limit(SOURCE_LIMIT).all():
        at = _aware(b.created_at)
        groups.setdefault((b.teacher_id, at.strftime("%Y%m%d%H")), []).append(b)
    for (tid, hk), books in groups.items():
        at = max(_aware(b.created_at) for b in books)
        title = f"Kitap ekledi: {books[0].name}" if len(books) == 1 else f"{len(books)} kitap ekledi"
        out.append(Event(
            key=f"book:{tid}:{hk}", at=at, category="coaching", severity="info", title=title, actor_id=tid,
            details=[("Kitaplar", ", ".join(b.name for b in books[:8]) + (" …" if len(books) > 8 else ""))],
        ))

    # Destek talebi
    q = db.query(SupportRequest).filter(SupportRequest.created_at >= since, SupportRequest.created_at < until)
    for r in by_actor(q, SupportRequest.requester_id).limit(SOURCE_LIMIT).all():
        out.append(Event(
            key=f"sup:{r.id}", at=_aware(r.created_at), category="admin", severity="info",
            title="Destek talebi açtı", actor_id=r.requester_id, target_text=f"'{r.subject}'",
            target_url="/admin/support", details=[("Konu", r.subject), ("Kategori", r.category)],
        ))

    # Görev talebi (öğrenci → koç)
    q = db.query(TaskRequest).filter(TaskRequest.created_at >= since, TaskRequest.created_at < until)
    for r in by_actor(q, TaskRequest.student_id).limit(SOURCE_LIMIT).all():
        out.append(Event(
            key=f"treq:{r.id}", at=_aware(r.created_at), category="student", severity="info",
            title=f"Koçuna talep gönderdi: {REQUEST_TYPE_LABELS.get(r.type, r.type.value)}", actor_id=r.student_id,
            target_user_id=r.teacher_id, target_url=f"/admin/users/{r.teacher_id}",
            details=[("Mesaj", r.message or "—"), ("Görev", r.task_title_snapshot or "—")],
        ))

    # Veli daveti
    q = db.query(ParentInvitation).filter(ParentInvitation.created_at >= since, ParentInvitation.created_at < until)
    for v in by_actor(q, ParentInvitation.invited_by_id).limit(SOURCE_LIMIT).all():
        out.append(Event(
            key=f"pinv:{v.id}", at=_aware(v.created_at), category="coaching", severity="info",
            title="Veli davet etti", actor_id=v.invited_by_id, target_user_id=v.student_id,
            target_url=f"/admin/users/{v.student_id}", details=[("Veli e-postası", v.invited_email)],
        ))

    # Yanlış soru arşivi — öğrenci + gün gruplu
    wday = (func.date(func.timezone("Europe/Istanbul", WrongQuestion.created_at))
            if db.bind.dialect.name == "postgresql" else func.date(WrongQuestion.created_at))
    rows = (
        db.query(WrongQuestion.student_id, wday, func.count(WrongQuestion.id), func.max(WrongQuestion.created_at))
        .filter(WrongQuestion.created_at >= since, WrongQuestion.created_at < until)
        .group_by(WrongQuestion.student_id, wday)
    )
    if actor_ids is not None:
        rows = rows.filter(WrongQuestion.student_id.in_(actor_ids or {-1}))
    for sid, _d, n, last in rows.limit(SOURCE_LIMIT).all():
        out.append(Event(
            key=f"wq:{sid}:{_d}", at=_aware(last), category="student", severity="info",
            title=f"Yanlış soru arşivine {n} soru ekledi", actor_id=sid,
        ))

    # Ödeme denemesi
    q = db.query(PaymentTransaction).filter(PaymentTransaction.created_at >= since, PaymentTransaction.created_at < until)
    for p in by_actor(q, PaymentTransaction.user_id).limit(SOURCE_LIMIT).all():
        ok = p.status == "succeeded"
        out.append(Event(
            key=f"pay:{p.id}", at=_aware(p.created_at), category="commercial",
            severity="info" if ok or p.status in ("pending", "3ds_pending") else "warn",
            title="Kartla ödeme yaptı" if ok else f"Kartla ödeme denedi ({p.status})", actor_id=p.user_id,
            details=[("Tutar (₺)", str(p.amount)), ("Paket", p.plan_code or "—"), ("Açıklama", p.status_reason or "—")],
        ))
    return out


# ── Birleştirme ──────────────────────────────────────────────────────────────

def build_feed(
    db: Session, *, days: int = 7, category: str = "all", severity: str = "all",
    actor_id: int | None = None, q: str | None = None, role: str | None = None,
    page: int = 1, page_size: int = 50, now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    until = now + timedelta(minutes=1)

    actor_ids: set[int] | None = None
    email_q = None
    if actor_id:
        actor_ids = {actor_id}
    elif q and q.strip():
        like = f"%{q.strip()}%"
        uq = db.query(User.id).filter((User.full_name.ilike(like)) | (User.email.ilike(like)))
        if role:
            uq = uq.filter(User.role == UserRole(role))
        actor_ids = {i for (i,) in uq.limit(500).all()}
        email_q = q.strip()
    elif role:
        actor_ids = {i for (i,) in db.query(User.id).filter(User.role == UserRole(role)).all()}

    events = _audit_events(db, since, until, actor_ids, email_q) + _domain_events(db, since, until, actor_ids)

    # kişiler (aktör + hedef)
    ids = {e.actor_id for e in events if e.actor_id} | {e.target_user_id for e in events if e.target_user_id} \
        | {e.via_admin_id for e in events if e.via_admin_id}
    people = {u.id: u for u in db.query(User).filter(User.id.in_(ids or {-1})).all()}

    counts_cat = {k: 0 for k in CATEGORY_LABELS}
    counts_sev = {"critical": 0, "warn": 0, "info": 0}
    for e in events:
        counts_cat[e.category] = counts_cat.get(e.category, 0) + 1
        counts_sev[e.severity] += 1
    failed_logins = sum(1 for e in events if e.key.startswith("a:") and e.title.startswith(("Giriş denemesi", "Kayıtlı olmayan", "Hesap kilitlendi")))
    actors_active = len({e.actor_id for e in events if e.actor_id})

    sel = [e for e in events
           if (category == "all" or e.category == category)
           and (severity == "all" or (severity == "critical" and e.severity == "critical")
                or (severity == "warn" and e.severity in ("critical", "warn")))]
    sel.sort(key=lambda e: e.at, reverse=True)
    total = len(sel)
    page_items = sel[(page - 1) * page_size: page * page_size]

    # en hareketli kişiler (seçili süzgeçle)
    top: dict[int, int] = {}
    for e in sel:
        if e.actor_id:
            top[e.actor_id] = top.get(e.actor_id, 0) + 1
    top_actors = sorted(top.items(), key=lambda x: x[1], reverse=True)[:8]

    def person(uid: int | None) -> dict | None:
        u = people.get(uid) if uid else None
        if u is None:
            return None
        return {"id": u.id, "name": u.full_name, "email": u.email,
                "role": u.role.value, "role_label": ROLE_LABELS.get(u.role.value, u.role.value)}

    def to_item(e: Event) -> dict:
        tgt = person(e.target_user_id)
        actor = person(e.actor_id)
        actor_text = e.actor_text
        if actor is None and e.actor_id:
            actor_text = f"Silinmiş kullanıcı (#{e.actor_id})"
        return {
            "key": e.key, "at": e.at, "category": e.category, "category_label": CATEGORY_LABELS[e.category],
            "severity": e.severity, "title": e.title,
            "actor": actor, "actor_text": actor_text,
            "via_admin": person(e.via_admin_id),
            "target_name": (tgt["name"] if tgt else None) or e.target_text,
            "target_role_label": tgt["role_label"] if tgt else None,
            "target_extra": e.target_text if tgt and e.target_text else None,
            "target_url": e.target_url, "ip": e.ip, "device": e.device,
            "details": [{"label": k, "value": v} for k, v in e.details],
        }

    items = [to_item(e) for e in page_items]
    # Kritik olaylar akıştan bağımsız en üstte (kategori süzgecinden etkilenmez)
    recent_critical = [to_item(e) for e in sorted(
        (e for e in events if e.severity == "critical"), key=lambda e: e.at, reverse=True)[:6]]

    focus = None
    if actor_id and actor_id in people:
        focus = person(actor_id) | {
            "last_active_at": people[actor_id].last_active_at,
            "pages": _top_pages(db, actor_id, since),
        }

    return {
        "days": days, "category": category, "severity": severity, "total": total,
        "page": page, "page_size": page_size, "items": items, "recent_critical": recent_critical,
        "counts": {"categories": counts_cat, "severity": counts_sev, "all": len(events),
                   "failed_logins": failed_logins, "actors_active": actors_active},
        "top_actors": [person(uid) | {"count": n} for uid, n in top_actors if person(uid)],
        "focus": focus,
        "category_labels": CATEGORY_LABELS,
    }


def _top_pages(db: Session, user_id: int, since: datetime) -> list[dict]:
    """Kişinin gezdiği panel sayfaları — "giriş yaptı ama ne yaptı" sorusunun cevabı."""
    from app.models.panel_behavior import PanelVisitEvent
    from app.services.panel_behavior import _CATALOG_BY_KEY

    rows = (
        db.query(PanelVisitEvent.route_key, func.count(PanelVisitEvent.id),
                 func.sum(PanelVisitEvent.dwell_ms), func.max(PanelVisitEvent.created_at))
        .filter(PanelVisitEvent.user_id == user_id, PanelVisitEvent.created_at >= since)
        .group_by(PanelVisitEvent.route_key)
        .order_by(func.count(PanelVisitEvent.id).desc())
        .limit(12).all()
    )
    out = []
    for key, n, dwell, last in rows:
        entry = _CATALOG_BY_KEY.get(key)
        out.append({"route_key": key, "label": entry.label if entry else key, "visits": int(n),
                    "minutes": round((dwell or 0) / 60000, 1), "last_at": _aware(last)})
    return out
