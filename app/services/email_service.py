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

    if not settings.email_enabled or not settings.smtp_host:
        # Log-only — geliştirme/test ortamı
        logger.info(
            "[EMAIL] (devre dışı) → %s | konu: %s",
            to,
            subject,
        )
        # Verbose görünüm istenirse debug log'da gövde
        logger.debug("[EMAIL BODY]\n%s", plain)
        return False

    msg = EmailMessage()
    msg["Subject"] = subject or settings.app_name
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
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
        return True
    except Exception as e:
        logger.exception("Email send failed: %s → %s — %s", subject, to, e)
        return False


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
