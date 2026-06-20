"""E-posta bildirim servisi.

- `EMAIL_ENABLED=false` (veya SMTP_HOST tanımsız) ise gerçek mail gönderilmez,
  log'a yazılır (geliştirme/test modu).
- Şablonlar `app/templates/emails/<name>.html` altında. Her şablonun ilk satırı
  `Subject: ...` formatında; geri kalanı HTML gövdesi.
- BackgroundTasks ile asenkron çağrı destekli (request_service helper'ları
  tarafından çağrılır).
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings


logger = logging.getLogger(__name__)


_TPL_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_env = Environment(
    loader=FileSystemLoader(str(_TPL_DIR)),
    autoescape=select_autoescape(["html"]),
)


def render_template_safe(name: str, ctx: dict[str, Any]) -> tuple[str, str, str] | None:
    """`_render`'ın güvenli sarmalayıcısı: hata olursa None döner.

    Dispatcher şablon olmadan (template eksik / değişken eksik) gönderim girişimini
    "stub-sent" yazmasın diye kullanılır.
    """
    try:
        return _render(name, ctx)
    except Exception as e:
        logger.warning("Email render failed for %s: %s", name, e)
        return None


def _render(name: str, ctx: dict[str, Any]) -> tuple[str, str, str]:
    """Şablonu render et, (subject, html, plain_fallback) döndür.

    Şablonun ilk satırı `Subject: ...` olarak yorumlanır; geri kalanı HTML.
    Plain text fallback HTML'den çok kaba bir şekilde üretilir (uzun mesajlarda
    OK; özel layout istiyorsak sonra ayrı .txt dosyası ekleriz).
    """
    tpl = _env.get_template(f"{name}.html")
    rendered = tpl.render(**ctx, app_base_url=settings.app_base_url, app_name=settings.app_name)
    lines = rendered.split("\n", 1)
    subject = ""
    body = rendered
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body = lines[1] if len(lines) > 1 else ""
    # Çok basit plain text dönüşüm — HTML etiketlerini at
    import re
    plain = re.sub(r"<[^>]+>", "", body)
    plain = re.sub(r"\n\s*\n+", "\n\n", plain).strip()
    return subject, body.strip(), plain


def send_email(to: str, template: str, ctx: dict[str, Any]) -> bool:
    """Şablon adını ve bağlamı alır, gönderir veya log'lar.

    Returns: gönderildi mi (True) / atlandı (False).
    """
    if not to or "@" not in to:
        logger.warning(f"Email skipped — invalid recipient: {to!r}")
        return False
    try:
        subject, html, plain = _render(template, ctx)
    except Exception as e:
        logger.exception(f"Email template render failed for {template}: {e}")
        return False

    # İletişim gözlem log'u (best-effort; gönderimi asla bozmaz)
    from app.services import comm_log

    if not settings.email_enabled or not settings.smtp_host:
        # Log-only — geliştirme/test ortamı
        logger.info(
            "[EMAIL] (devre dışı) → %s | konu: %s",
            to,
            subject,
        )
        # Verbose görünüm istenirse debug log'da gövde
        logger.debug("[EMAIL BODY]\n%s", plain)
        comm_log.log_email(
            status=comm_log_status_suppressed(),
            to_address=to,
            category=template,
            subject=subject,
            error="email_disabled",
            provider=_email_provider(),
        )
        return False

    msgid = make_msgid(domain="etutkoc.com")
    msg = EmailMessage()
    msg["Subject"] = subject or settings.app_name
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Message-ID"] = msgid
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    try:
        if settings.smtp_use_ssl:
            server: smtplib.SMTP = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
            if settings.smtp_use_tls:
                server.starttls()
        try:
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        finally:
            server.quit()
        logger.info("Email sent: %s → %s", subject, to)
        comm_log.log_email(
            status="sent",
            to_address=to,
            category=template,
            subject=subject,
            provider=_email_provider(),
            provider_message_id=msgid,
        )
        return True
    except Exception as e:
        logger.exception("Email send failed: %s → %s — %s", subject, to, e)
        comm_log.log_email(
            status="failed",
            to_address=to,
            category=template,
            subject=subject,
            provider=_email_provider(),
            provider_message_id=msgid,
            error=str(e),
        )
        return False


def _email_provider() -> str:
    """SMTP host'tan kısa sağlayıcı adı türet (gözlem log'u için)."""
    host = (settings.smtp_host or "").lower()
    if "zepto" in host:
        return "zeptomail"
    if "zoho" in host:
        return "zoho"
    return host or "smtp"


def comm_log_status_suppressed() -> str:
    from app.models.communication_log import STATUS_SUPPRESSED
    return STATUS_SUPPRESSED


# ---------------------------- Yüksek seviye yardımcılar ----------------------------


def notify_teacher_new_request(req) -> None:
    """Yeni talep geldiğinde öğretmene mail."""
    if not req.teacher or not req.teacher.email:
        return
    type_labels = {
        "change": "Sayı değişiklik talebi",
        "replace": "Kaynak değiştirme talebi",
        "remove": "Görev çıkarma talebi",
        "add": "Yeni görev önerisi",
        "question": "Soru",
    }
    send_email(
        to=req.teacher.email,
        template="teacher_new_request",
        ctx={
            "teacher": req.teacher,
            "student": req.student,
            "request": req,
            "type_label": type_labels.get(req.type.value, req.type.value),
        },
    )


def notify_parent_invitation(invitation, *, teacher, student, relation_label: str) -> bool:
    """Veli davet maili gönder. parent_invitations satırı zaten oluşturulmuş olmalı.

    Returns: gerçekten gönderildi (True) / log-only (False).
    """
    if not invitation.invited_email:
        return False
    return send_email(
        to=invitation.invited_email,
        template="parent_invitation",
        ctx={
            "invitation": invitation,
            "teacher": teacher,
            "student": student,
            "relation_label": relation_label,
        },
    )


def notify_new_signup_admin(user) -> int:
    """Yeni koç self-signup olduğunda satış/admin adresine bilgilendirme maili.

    Alıcı: pricing katalogundaki `contact.sales_email` (yoksa SMTP_FROM fallback'i).
    Returns: gönderilen mail sayısı (1 ya da 0).
    """
    from datetime import datetime, timezone
    from app.services import pricing
    catalog = pricing.get_pricing_catalog()
    sales = (catalog.get("contact") or {}).get("sales_email")
    to = sales or settings.smtp_from or ""
    # Display-name içeriyorsa ("ETUTKOC Rotam <x@y>") sadece adresi çıkar
    if "<" in to and ">" in to:
        to = to.split("<", 1)[1].rstrip(">").strip()
    if not to:
        logger.info("notify_new_signup_admin: alıcı tanımlı değil — atlandı")
        return 0
    ok = send_email(
        to=to,
        template="new_signup_admin",
        ctx={
            "user_full_name": user.full_name or user.email,
            "user_email": user.email,
            "user_role": "Bağımsız Koç",
            "user_plan": user.plan or "solo_trial",
            "signed_up_at_label": datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC"),
            "admin_url": f"/admin/users/{user.id}",
        },
    )
    return 1 if ok else 0


def notify_student_request_resolved(req, action: str) -> None:
    """Talep işlendiğinde öğrenciye mail.
    action: 'approved' / 'rejected' / 'answered'
    """
    if not req.student or not req.student.email:
        return
    template = {
        "approved": "student_request_approved",
        "rejected": "student_request_rejected",
        "answered": "student_question_answered",
    }.get(action)
    if not template:
        return
    send_email(
        to=req.student.email,
        template=template,
        ctx={
            "student": req.student,
            "teacher": req.teacher,
            "request": req,
        },
    )
