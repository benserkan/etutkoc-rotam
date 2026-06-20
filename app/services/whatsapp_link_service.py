"""P3 — Click-to-WhatsApp URL üretici + yetki + maske yardımcıları.

Tek girdi noktası: `build_wa_dispatch(db, sender, template, target_user_id,
variables, freeform_note)` → `WaDispatchResult`. Endpoint bu fonksiyonu çağırır
ve sonucu Pydantic'e döker.

Yetki matrisi (`can_send_wa_to`):
  - SUPER_ADMIN → herkese
  - INSTITUTION_ADMIN → aynı kurumun tüm aktif kullanıcılarına
  - TEACHER → kendi öğrencilerine + onların velilerine
  - Diğer roller (PARENT/STUDENT) → şimdilik mesaj gönderemez (P3 kapsamı)
  - Kendine her zaman serbest (test gönderimi)

Yetki yoksa: 404 hissi veren `target_not_found` PhoneSendError (sızıntı önleme).

URL biçimi: `https://wa.me/{phone_no_plus}?text={percent_encoded_message}`.
RFC 3986 percent encoding (`urllib.parse.quote`); UTF-8 Türkçe karakter güvenli.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.models import (
    ParentStudentLink,
    User,
    UserRole,
    WhatsAppDispatchLog,
    WhatsAppTemplate,
)
from app.services.whatsapp_template_service import (
    parse_variables_json,
    render_preview,
)


# Uzunluk uyarı eşiği — wa.me URL'inde 4096 hard, 2000+ render güvenli sınır
LONG_TEXT_THRESHOLD = 2000

WA_BASE_URL = "https://wa.me"


@dataclass
class WaDispatchResult:
    wa_url: str
    rendered_text: str
    target_name: str
    target_phone_masked: str
    character_count: int
    long_text: bool
    warnings: list[str] = field(default_factory=list)
    log_id: int | None = None


class WaDispatchError(Exception):
    """Endpoint'te 400/404'e çevrilir. `code` kullanıcı/UI hata kodudur."""

    def __init__(self, code: str, message: str, status: int = 400):
        self.code = code
        self.message = message
        self.status = status
        super().__init__(message)


# ----------------------------------------------------------------------
# Telefon uygunluğu (soft mod)
# ----------------------------------------------------------------------


def can_message_phone(target: User) -> bool:
    """Hedefe WhatsApp/Click-to-WA gönderilebilir mi?

    Numara ŞART. Doğrulama YALNIZCA SMS doğrulama canlıyken (is_sms_enabled)
    zorunlu — soft modda (SMS henüz açılmamış) kimse doğrulayamadığı için numara
    mevcutsa yeterli. SMS açıldığında doğrulama tekrar şart olur.
    """
    from app.services.sms_provider import is_sms_enabled
    if not target.phone:
        return False
    if target.phone_verified_at is not None:
        return True
    return not is_sms_enabled()


# ----------------------------------------------------------------------
# Yetki
# ----------------------------------------------------------------------


def can_send_wa_to(
    db: Session, *, sender: User, target: User,
) -> bool:
    """Sender, target'a WhatsApp mesajı gönderebilir mi?

    Süper admin her zaman OK. Kuruma bağlı kullanıcılar aynı kurum içinde.
    TEACHER kendi öğrencisine + velisine. Kendine her zaman OK.
    """
    if sender.id == target.id:
        return True

    if sender.role == UserRole.SUPER_ADMIN:
        return True

    if sender.role == UserRole.INSTITUTION_ADMIN:
        # Kurum yöneticisi yalnız kendi kurumundaki aktif kullanıcılara
        if not sender.institution_id:
            return False
        return target.institution_id == sender.institution_id

    if sender.role == UserRole.TEACHER:
        # Koç → kendi öğrencisi VEYA öğrencisinin velisi
        if target.role == UserRole.STUDENT:
            return target.teacher_id == sender.id
        if target.role == UserRole.PARENT:
            # Velinin bağlı olduğu öğrencilerden biri sender'a bağlı mı?
            count = (
                db.query(ParentStudentLink)
                .join(User, ParentStudentLink.student_id == User.id)
                .filter(
                    ParentStudentLink.parent_id == target.id,
                    User.teacher_id == sender.id,
                )
                .count()
            )
            return count > 0

    # Diğer roller (PARENT/STUDENT) → gönderim yok (P3 kapsamı)
    return False


# ----------------------------------------------------------------------
# Telefon maskeleme + URL üretimi
# ----------------------------------------------------------------------


def mask_phone_e164(phone: str | None) -> str:
    """E.164 telefon numarasını okunur şekilde maskele.

    Örnek: 905321234567 → "+90 532 *** ** 67"
    """
    if not phone:
        return "—"
    p = phone.strip().replace("+", "")
    if len(p) != 12 or not p.startswith("90"):
        return phone  # beklenmedik format — olduğu gibi göster
    return f"+90 {p[2:5]} *** ** {p[10:12]}"


def build_wa_url(phone_e164: str, text: str) -> str:
    """wa.me URL'i üret. phone_e164 — `+` olmadan ("905...")."""
    encoded = quote(text or "", safe="")
    return f"{WA_BASE_URL}/{phone_e164}?text={encoded}"


# ----------------------------------------------------------------------
# Ana dispatcher (servis fonksiyonu)
# ----------------------------------------------------------------------


def build_wa_dispatch(
    db: Session,
    *,
    sender: User,
    template_id: int,
    target_user_id: int,
    variables: dict[str, str] | None = None,
    freeform_note: str | None = None,
    write_log: bool = True,
) -> WaDispatchResult:
    """URL'i üret + log yaz.

    Raises: WaDispatchError (status_code'lu)
    """
    variables = variables or {}

    # 1) Şablonu al
    tmpl = (
        db.query(WhatsAppTemplate)
        .filter(WhatsAppTemplate.id == template_id, WhatsAppTemplate.is_active == True)  # noqa: E712
        .first()
    )
    if not tmpl:
        raise WaDispatchError(
            "template_not_found",
            "Şablon bulunamadı veya pasif.",
            status=404,
        )

    # 2) Hedef kullanıcıyı al + yetki kontrolü
    target = db.query(User).filter(User.id == target_user_id).first()
    if not target or not target.is_active:
        # Sızıntı önleme: yetki ya da varlık yoksa aynı kod
        raise WaDispatchError(
            "target_not_found",
            "Hedef kullanıcı bulunamadı.",
            status=404,
        )

    if not can_send_wa_to(db, sender=sender, target=target):
        # Yetki yoksa 404 — varlık ifşası yok
        raise WaDispatchError(
            "target_not_found",
            "Hedef kullanıcı bulunamadı.",
            status=404,
        )

    # 3) Telefon kontrolü (soft mod: numara yeterli; SMS canlıysa doğrulama şart)
    if not can_message_phone(target):
        raise WaDispatchError(
            "target_phone_not_verified",
            "Hedef kullanıcının telefonu doğrulanmamış veya kayıtlı numarası yok. "
            "WhatsApp gönderimi yapılamaz.",
            status=400,
        )

    # 4) Render — variables_json'dan defaults al
    var_defs = parse_variables_json(tmpl.variables_json)
    preview = render_preview(
        template=tmpl.content_template,
        values=variables,
        variable_defs=var_defs,
    )
    rendered = preview.rendered

    # 5) Freeform note (yalnız şablon izin veriyorsa)
    note_clean = (freeform_note or "").strip()
    if note_clean:
        if not tmpl.allow_freeform_note:
            raise WaDispatchError(
                "freeform_not_allowed",
                "Bu şablona serbest not eklenemez.",
                status=400,
            )
        # Sonuna iki satır boşluk + not
        rendered = f"{rendered}\n\n{note_clean}"

    # 6) Karakter uzunluk
    char_count = len(rendered)
    warnings = list(preview.warnings)
    long_text = char_count >= LONG_TEXT_THRESHOLD
    if long_text:
        warnings.append(
            f"Metin {char_count} karakter — bazı uygulamalar 2000+'i kırpabilir."
        )

    # 7) URL üret
    wa_url = build_wa_url(target.phone, rendered)

    # 8) Audit log
    log_id: int | None = None
    if write_log:
        log = WhatsAppDispatchLog(
            sender_user_id=sender.id,
            target_user_id=target.id,
            template_key=tmpl.key,
            template_id=tmpl.id,
            params_json=json.dumps(
                {"variables": variables, "freeform_note": note_clean or None},
                ensure_ascii=False, default=str,
            ),
            character_count=char_count,
        )
        db.add(log)
        db.flush()
        log_id = log.id

        # Birleşik iletişim gözlem log'u (spam-guard log'undan ayrı, best-effort)
        from app.services import comm_log
        comm_log.log_whatsapp(
            db=db, status="sent", to_user_id=target.id,
            to_address=mask_phone_e164(target.phone),
            category=tmpl.key, subject=rendered[:120],
            meta_json=json.dumps({"chars": char_count, "sender_id": sender.id}),
        )

    return WaDispatchResult(
        wa_url=wa_url,
        rendered_text=rendered,
        target_name=target.full_name,
        target_phone_masked=mask_phone_e164(target.phone),
        character_count=char_count,
        long_text=long_text,
        warnings=warnings,
        log_id=log_id,
    )
