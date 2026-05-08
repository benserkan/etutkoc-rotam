"""Veli (PARENT) rotaları — davet kabul + read-only paneller.

Sprint 2 + 3 kapsamı:
- /parent/invitation/{token} (GET/POST) — davet kabul akışı
- /parent — dashboard (her çocuk için özet kart)
- /parent/students/{id} — öğrenci detay (metrikler, ders, trend, öğretmen notları)
- /parent/students/{id}/week — read-only haftalık program
- /legal/kvkk-veli — KVKK aydınlatma metni

GİZLİLİK: Tüm /parent/students/{id} rotaları parent_view.assert_parent_can_view()
ile öğrenci-veli bağını doğrular. Bağ yoksa 404 döner (yetki sızdırmamak için
"yok" mesajı; "var ama erişimin yok" yerine).

MOBİL HAZIR: Veri toplayıcı parent_view service'i saf dict üretir; ileride
/api/parent/... rotaları aynı dict'i JSON döner.
"""

from __future__ import annotations

import logging
import secrets
from datetime import date, datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
from starlette import status

from app.deps import get_db, require_parent
from app.models import (
    PARENT_RELATION_LABELS,
    NotificationChannel,
    NotificationKind,
    NotificationLog,
    NotificationStatus,
    ParentNotificationPref,
    ParentPhoneVerification,
    ParentSessionLog,
    ParentStudentLink,
    User,
    UserRole,
)
from app.services.email_service import notify_parent_invitation
from app.services.parent_invitation import (
    InvitationError,
    can_register_parent_email,
    consume_invitation,
    find_user_by_email,
    lookup_token,
)
from app.services.parent_view import (
    ParentAccessDenied,
    list_parent_students,
    list_recent_notifications,
    student_overview,
    student_week,
)
from app.services.security import hash_password
from app.services.whatsapp import normalize_phone, send_otp
from app.templating import templates

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------- KVKK metni ----------------------------


@router.get("/legal/kvkk-veli")
def kvkk_text(request: Request):
    return templates.TemplateResponse(
        "legal/kvkk_parent.html",
        {"request": request, "user": None},
    )


# ---------------------------- Davet kabul akışı ----------------------------


def _render_invalid(request: Request, reason: str):
    return templates.TemplateResponse(
        "parent/invitation_invalid.html",
        {"request": request, "reason": reason, "user": None},
        status_code=400,
    )


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:255] if request.headers else None
    return ip, ua


@router.get("/parent/invitation/{token}")
def invitation_form(token: str, request: Request, db: Session = Depends(get_db)):
    lookup = lookup_token(db, token)
    if lookup.error:
        return _render_invalid(request, lookup.error.value)

    inv = lookup.invitation
    relation_label = PARENT_RELATION_LABELS.get(inv.relation, "—")
    return templates.TemplateResponse(
        "parent/invitation_accept.html",
        {
            "request": request,
            "user": None,
            "inv": inv,
            "relation_label": relation_label,
            "form": {"full_name": ""},
            "error": None,
        },
    )


def _form_error(request: Request, inv, message: str, prefilled: dict):
    return templates.TemplateResponse(
        "parent/invitation_accept.html",
        {
            "request": request,
            "user": None,
            "inv": inv,
            "relation_label": PARENT_RELATION_LABELS.get(inv.relation, "—"),
            "form": prefilled,
            "error": message,
        },
        status_code=400,
    )


@router.post("/parent/invitation/{token}/accept")
def invitation_accept(
    token: str,
    request: Request,
    db: Session = Depends(get_db),
    full_name: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    kvkk_accept: str = Form(""),
):
    lookup = lookup_token(db, token)
    if lookup.error:
        return _render_invalid(request, lookup.error.value)
    inv = lookup.invitation

    name = full_name.strip()
    prefilled = {"full_name": name}

    # Form doğrulamaları
    if not name or len(name) < 3:
        return _form_error(request, inv, "Ad-soyad en az 3 karakter olmalıdır.", prefilled)
    if len(password) < 8:
        return _form_error(request, inv, "Şifre en az 8 karakter olmalıdır.", prefilled)
    if password != password_confirm:
        return _form_error(request, inv, "Şifreler eşleşmiyor.", prefilled)
    if kvkk_accept != "yes":
        return _form_error(
            request, inv,
            "Hesap oluşturmak için aydınlatma metnini onaylamanız gereklidir.",
            prefilled,
        )

    # Email rol çakışması (KARAR a — yasak)
    can_register, conflict_role = can_register_parent_email(db, inv.invited_email)
    if not can_register:
        role_label = "öğretmen" if conflict_role == UserRole.TEACHER else "öğrenci"
        return _form_error(
            request, inv,
            f"Bu e-posta adresi sistemde {role_label} olarak kullanılıyor. "
            "Lütfen sizi davet eden koçunuza farklı bir e-posta ile davet talep edin.",
            prefilled,
        )

    # Mevcut PARENT hesabı varsa: ona link ekle. Yoksa: yeni User + Pref.
    parent_user = find_user_by_email(db, inv.invited_email)
    is_new_account = parent_user is None

    if is_new_account:
        parent_user = User(
            email=inv.invited_email.strip().lower(),
            password_hash=hash_password(password),
            full_name=name,
            role=UserRole.PARENT,
            is_active=True,
        )
        db.add(parent_user)
        db.flush()

        pref = ParentNotificationPref(
            parent_id=parent_user.id,
            unsubscribe_token=secrets.token_urlsafe(48),
        )
        db.add(pref)
    else:
        # Mevcut PARENT hesabı — şifre/ad değiştirme YOK (güvenlik: davet sahipleniciliği
        # zaten email üzerinden ispatlanmış olur, ama mevcut hesabın bilgilerini
        # değiştirmek için ayrı bir akış gerekir).
        pass

    # parent_student_link — UNIQUE(parent_id, student_id) kontrolü
    existing_link = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.parent_id == parent_user.id,
            ParentStudentLink.student_id == inv.student_id,
        )
        .first()
    )
    if not existing_link:
        link = ParentStudentLink(
            parent_id=parent_user.id,
            student_id=inv.student_id,
            relation=inv.relation,
            is_primary=inv.is_primary,
            created_by_id=inv.invited_by_id,
        )
        db.add(link)

    consume_invitation(db, inv)

    # Telemetri: oturum kaydı + login session
    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=parent_user.id,
        action="invitation_accepted" if is_new_account else "invitation_added_link",
        ip=ip, user_agent=ua,
    ))
    db.add(ParentSessionLog(
        parent_id=parent_user.id,
        action="login", ip=ip, user_agent=ua,
    ))

    db.commit()

    request.session["user_id"] = parent_user.id
    return RedirectResponse(url="/parent", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------- Veli dashboard ----------------------------


@router.get("/parent")
def parent_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
):
    students = list_parent_students(db, user)
    return templates.TemplateResponse(
        "parent/dashboard.html",
        {
            "request": request,
            "user": user,
            "students": students,
        },
    )


# ---------------------------- Öğrenci detay (read-only) ----------------------------


def _handle_access(exc: ParentAccessDenied):
    """Yetki yoksa 404 dön — 'var ama yetkin yok' bilgisini sızdırma."""
    raise HTTPException(status_code=404, detail="Öğrenci bulunamadı")


@router.get("/parent/students/{student_id}")
def parent_student_detail(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
):
    try:
        data = student_overview(db, user, student_id)
    except ParentAccessDenied:
        _handle_access(None)

    return templates.TemplateResponse(
        "parent/student_detail.html",
        {"request": request, "user": user, "data": data},
    )


@router.get("/parent/students/{student_id}/week")
def parent_student_week(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
    start: str | None = Query(None),
):
    """Belirli bir hafta başlangıç tarihi yoksa bugünden başlar."""
    try:
        if start:
            try:
                start_date = date.fromisoformat(start)
            except ValueError:
                start_date = date.today()
        else:
            start_date = date.today()
        data = student_week(db, user, student_id, start_date)
    except ParentAccessDenied:
        _handle_access(None)

    return templates.TemplateResponse(
        "parent/student_week.html",
        {"request": request, "user": user, "data": data},
    )


# ---------------------------- Bildirim geçmişi (Sprint 3 küçük ek) ----------------------------


@router.get("/parent/notifications")
def parent_notifications(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
):
    items = list_recent_notifications(db, user, limit=100)
    return templates.TemplateResponse(
        "parent/notifications.html",
        {"request": request, "user": user, "items": items},
    )


# ---------------------------- Tek tıkla bildirim kapat ----------------------------


@router.get("/parent/unsubscribe/{token}")
def parent_unsubscribe(token: str, request: Request, db: Session = Depends(get_db)):
    """Tek tıkla bildirim kapatma — email/WA mesajlarındaki linkten erişilir.

    Login GEREKMİYOR (token zaten secret). Tıklama anında kapatır; INVITATION/OTP
    gibi sistem mesajları yine gönderilebilir.
    """
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.unsubscribe_token == token)
        .first()
    )
    if not pref:
        return templates.TemplateResponse(
            "parent/unsubscribed.html",
            {"request": request, "user": None, "status": "invalid"},
            status_code=400,
        )

    if pref.unsubscribed_at:
        return templates.TemplateResponse(
            "parent/unsubscribed.html",
            {"request": request, "user": None, "status": "already"},
        )

    pref.unsubscribed_at = datetime.now(timezone.utc)
    # Tüm bildirim türlerini kapat (kullanıcı isterse panele girip tekil açar)
    pref.daily_summary_enabled = False
    pref.weekly_report_enabled = False
    pref.empty_day_alert_enabled = False
    pref.drop_alert_enabled = False
    pref.new_program_alert_enabled = False
    pref.teacher_note_enabled = False
    pref.exam_approaching_enabled = False
    pref.whatsapp_enabled = False

    # Telemetri
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent", "")[:255] if request.headers else None
    db.add(ParentSessionLog(
        parent_id=pref.parent_id, action="unsubscribed", ip=ip, user_agent=ua,
    ))
    db.commit()

    return templates.TemplateResponse(
        "parent/unsubscribed.html",
        {"request": request, "user": None, "status": "unsubscribed"},
    )


# ---------------------------- Settings iskelet (Sprint 10'da dolacak) ----------------------------


@router.get("/parent/settings")
def parent_settings(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
):
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    # Açık bir doğrulama oturumu var mı? (kod gönderildi, henüz consume edilmedi,
    # süresi dolmadı). Varsa template "kodu gir" formunu göstersin.
    pending_verify = (
        db.query(ParentPhoneVerification)
        .filter(
            ParentPhoneVerification.parent_id == user.id,
            ParentPhoneVerification.consumed_at.is_(None),
            ParentPhoneVerification.expires_at > datetime.now(timezone.utc),
        )
        .order_by(ParentPhoneVerification.id.desc())
        .first()
    )
    # Bu velinin bağlı çocukları (mute toggle için)
    child_links = (
        db.query(ParentStudentLink)
        .options(joinedload(ParentStudentLink.student))
        .filter(ParentStudentLink.parent_id == user.id)
        .all()
    )
    from app.config import settings as app_settings
    return templates.TemplateResponse(
        "parent/settings_skeleton.html",
        {
            "request": request,
            "user": user,
            "pref": pref,
            "pending_verify": pending_verify,
            "child_links": child_links,
            "PARENT_RELATION_LABELS": PARENT_RELATION_LABELS,
            "settings": app_settings,
            "flash_ok": request.query_params.get("ok"),
            "flash_err": request.query_params.get("err"),
        },
    )


# ---------------------------- Tercih güncelleme ----------------------------


def _parse_time_str(s: str | None) -> tuple[int, int] | None:
    """'HH:MM' → (hour, minute) ya da None."""
    if not s:
        return None
    s = s.strip()
    parts = s.split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h <= 23 and 0 <= m <= 59):
        return None
    return h, m


@router.post("/parent/settings/preferences")
def update_preferences(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
    daily_summary: str = Form(""),
    weekly_report: str = Form(""),
    empty_day: str = Form(""),
    new_program: str = Form(""),
    drop_alert: str = Form(""),
    teacher_note: str = Form(""),
    exam_approaching: str = Form(""),
    quiet_start: str = Form("22:00"),
    quiet_end: str = Form("07:00"),
):
    """Bildirim tür toggle'ları + sessiz saatler. Checkbox değerleri 'yes' veya boş.

    Veli "unsubscribed_at"i set ettiyse genel kapatma override eder; bu form
    unsubscribed_at'i temizler (yani kullanıcı buradan tekrar ayar yaparak
    bildirimleri açmış olur).
    """
    from datetime import time as dt_time

    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    if pref is None:
        pref = ParentNotificationPref(
            parent_id=user.id,
            unsubscribe_token=secrets.token_urlsafe(48),
        )
        db.add(pref)
        db.flush()

    def _on(v: str) -> bool:
        return v in ("yes", "1", "on", "true")

    pref.daily_summary_enabled = _on(daily_summary)
    pref.weekly_report_enabled = _on(weekly_report)
    pref.empty_day_alert_enabled = _on(empty_day)
    pref.new_program_alert_enabled = _on(new_program)
    pref.drop_alert_enabled = _on(drop_alert)
    pref.teacher_note_enabled = _on(teacher_note)
    pref.exam_approaching_enabled = _on(exam_approaching)

    qs = _parse_time_str(quiet_start)
    qe = _parse_time_str(quiet_end)
    if qs is None or qe is None:
        msg = "Sessiz saat formatı geçersiz (HH:MM bekleniyor)."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )
    pref.quiet_hours_start = dt_time(qs[0], qs[1])
    pref.quiet_hours_end = dt_time(qe[0], qe[1])

    # Veli bu sayfadan tekrar ayar yapıyorsa unsubscribed durumu otomatik kalksın
    if pref.unsubscribed_at is not None:
        pref.unsubscribed_at = None

    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=user.id, action="preferences_updated", ip=ip, user_agent=ua,
    ))
    db.commit()

    msg = "Bildirim tercihleriniz kaydedildi."
    return RedirectResponse(
        url=f"/parent/settings?ok={quote(msg)}", status_code=303
    )


@router.post("/parent/settings/students/{student_id}/mute")
def toggle_child_mute(
    student_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
    muted: str = Form(""),
):
    """Bu velinin {student_id} çocuğu için bildirim akışını aç/kapat."""
    link = (
        db.query(ParentStudentLink)
        .filter(
            ParentStudentLink.parent_id == user.id,
            ParentStudentLink.student_id == student_id,
        )
        .first()
    )
    if not link:
        msg = "Çocuk bağlantısı bulunamadı."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    new_state = muted in ("yes", "1", "on", "true")
    link.muted = new_state

    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=user.id,
        action=f"child_{'muted' if new_state else 'unmuted'}",
        ip=ip, user_agent=ua,
    ))
    db.commit()

    name = link.student.full_name if link.student else f"#{student_id}"
    msg = (
        f"{name} için bildirimler kapatıldı."
        if new_state else f"{name} için bildirimler tekrar açıldı."
    )
    return RedirectResponse(
        url=f"/parent/settings?ok={quote(msg)}", status_code=303
    )


# ---------------------------- WhatsApp telefon doğrulama ----------------------------

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 60


def _generate_otp_code() -> str:
    """6 haneli, kriptografik güvenli OTP kodu."""
    return f"{secrets.randbelow(1_000_000):06d}"


@router.post("/parent/settings/whatsapp/start")
def whatsapp_start(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
    phone: str = Form(...),
):
    """Telefon doğrulama akışını başlat: kodu üret + WA üzerinden gönder."""
    normalized = normalize_phone(phone)
    if not normalized:
        msg = "Telefon numarası geçersiz. Türkiye numarası için 0532... veya +90532... yazabilirsiniz."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    # Cooldown — son 60sn'de zaten gönderilmiş bir aktif kod var mı?
    now = datetime.now(timezone.utc)
    recent = (
        db.query(ParentPhoneVerification)
        .filter(
            ParentPhoneVerification.parent_id == user.id,
            ParentPhoneVerification.created_at
            > now - timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS),
        )
        .order_by(ParentPhoneVerification.id.desc())
        .first()
    )
    if recent and not recent.consumed_at:
        msg = "Az önce kod gönderildi. Lütfen 1 dakika bekleyip tekrar deneyin."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    code = _generate_otp_code()
    ppv = ParentPhoneVerification(
        parent_id=user.id,
        phone=normalized,
        code=code,
        expires_at=now + timedelta(minutes=OTP_TTL_MINUTES),
    )
    db.add(ppv)
    db.flush()

    # OTP gönderim — başarısız olursa kayıt rollback edilir.
    result = send_otp(to_phone=normalized, code=code)
    if not result.success:
        db.rollback()
        logger.warning(
            "WA OTP gönderimi başarısız: parent=%s phone=%s err=%s",
            user.id, normalized, result.error,
        )
        msg = (
            "WhatsApp kodu gönderilemedi. Numaranızı kontrol edin veya "
            "biraz sonra tekrar deneyin."
        )
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    # NotificationLog'a OTP girişi (audit + counter dışında — OTP daily cap'e dahil değil)
    nl = NotificationLog(
        parent_id=user.id,
        student_id=None,
        kind=NotificationKind.OTP,
        channel=NotificationChannel.WHATSAPP,
        status=NotificationStatus.SENT,
        external_id=result.external_id,
        sent_at=now,
        subject=f"OTP → {normalized}",
    )
    db.add(nl)
    db.commit()

    msg = f"Doğrulama kodu {normalized} numarasına gönderildi. WhatsApp'tan kontrol edin."
    return RedirectResponse(
        url=f"/parent/settings?ok={quote(msg)}", status_code=303
    )


@router.post("/parent/settings/whatsapp/verify")
def whatsapp_verify(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
    code: str = Form(...),
):
    """Veli'nin girdiği OTP kodunu doğrula → pref güncelle."""
    code = (code or "").strip()
    if not code or not code.isdigit() or len(code) != 6:
        msg = "Kod 6 hane olmalıdır."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    now = datetime.now(timezone.utc)
    ppv = (
        db.query(ParentPhoneVerification)
        .filter(
            ParentPhoneVerification.parent_id == user.id,
            ParentPhoneVerification.consumed_at.is_(None),
            ParentPhoneVerification.expires_at > now,
        )
        .order_by(ParentPhoneVerification.id.desc())
        .first()
    )
    if not ppv:
        msg = "Aktif bir doğrulama oturumu bulunamadı. Lütfen tekrar telefonunuzu girin."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    # Brute force koruması
    if ppv.attempts >= OTP_MAX_ATTEMPTS:
        # Süresi henüz dolmadıysa bile kilitle
        ppv.expires_at = now
        db.commit()
        msg = "Çok fazla yanlış deneme. Yeni bir kod isteyin."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    ppv.attempts += 1

    if not secrets.compare_digest(ppv.code, code):
        db.commit()
        remaining = OTP_MAX_ATTEMPTS - ppv.attempts
        msg = f"Kod yanlış. Kalan deneme hakkı: {max(remaining, 0)}."
        return RedirectResponse(
            url=f"/parent/settings?err={quote(msg)}", status_code=303
        )

    # Başarılı — pref güncelle
    ppv.consumed_at = now
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    if pref is None:
        pref = ParentNotificationPref(
            parent_id=user.id,
            unsubscribe_token=secrets.token_urlsafe(48),
        )
        db.add(pref)

    pref.whatsapp_phone = ppv.phone
    pref.whatsapp_phone_verified_at = now
    pref.whatsapp_enabled = True

    ip, ua = _client_meta(request)
    db.add(ParentSessionLog(
        parent_id=user.id, action="whatsapp_verified", ip=ip, user_agent=ua,
    ))
    db.commit()

    msg = f"WhatsApp doğrulandı: {ppv.phone}. Bildirimleri WhatsApp'tan da alacaksınız."
    return RedirectResponse(
        url=f"/parent/settings?ok={quote(msg)}", status_code=303
    )


@router.post("/parent/settings/whatsapp/disable")
def whatsapp_disable(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_parent),
):
    """Veli WhatsApp kanalını kapatır (telefon kaydı silinir, doğrulama düşer)."""
    pref = (
        db.query(ParentNotificationPref)
        .filter(ParentNotificationPref.parent_id == user.id)
        .first()
    )
    if pref:
        pref.whatsapp_enabled = False
        pref.whatsapp_phone = None
        pref.whatsapp_phone_verified_at = None

        ip, ua = _client_meta(request)
        db.add(ParentSessionLog(
            parent_id=user.id, action="whatsapp_disabled", ip=ip, user_agent=ua,
        ))
        db.commit()

    msg = "WhatsApp kanalı kapatıldı."
    return RedirectResponse(
        url=f"/parent/settings?ok={quote(msg)}", status_code=303
    )
