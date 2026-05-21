"""Sprint C (Roadmap Faz F-2) — Dunning (ödeme hatırlatma) zinciri.

Bir fatura için kademe kademe hatırlatma gönderir:

  - D-7: nazik hatırlatma (ödeme bir hafta sonra)
  - D-3: ikinci hatırlatma (3 gün kaldı)
  - D-1: son uyarı (yarın dolacak)
  - D+1: ödeme gecikti uyarısı
  - D+3: hesap kısıtlama uyarısı
  - D+7: son şans / oto-downgrade uyarısı

Her aşama bir kez gönderilir (`last_reminder_kind` ile dedup). Cron günde
bir çalışır; eksik aşamayı tetikler.

Manuel tetikleme: admin "Hatırlatma gönder" butonuna basabilir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import (
    Institution,
    Invoice,
    InvoiceStatus,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# Sıralı dunning aşamaları — soldan sağa
REMINDER_STAGES = ["d_minus_7", "d_minus_3", "d_minus_1",
                   "d_plus_1", "d_plus_3", "d_plus_7"]


REMINDER_STAGE_LABELS_TR: dict[str, str] = {
    "d_minus_7": "Vadeden 7 gün önce — nazik hatırlatma",
    "d_minus_3": "Vadeden 3 gün önce — ikinci hatırlatma",
    "d_minus_1": "Vadeden 1 gün önce — son uyarı",
    "d_plus_1": "Vade geçti, 1 gün — ödeme gecikti",
    "d_plus_3": "Vade geçti, 3 gün — hesap kısıtlama uyarısı",
    "d_plus_7": "Vade geçti, 7 gün — son şans / oto-pasif",
    "manual": "Manuel hatırlatma (admin tetikledi)",
}


def _stage_for_invoice(inv: Invoice, *, now: datetime) -> str | None:
    """Bir faturanın şu an hangi aşamaya layık olduğunu belirle.

    Henüz gönderilmemiş veya o aşamanın tetiklenme penceresi gelmiş aşamayı döner.
    Hepsi gönderildiyse veya aşama dışındaysa None.
    """
    if inv.status not in (InvoiceStatus.PENDING, InvoiceStatus.OVERDUE):
        return None
    due = _aware(inv.due_at)
    if due is None:
        return None
    delta = (due - now).total_seconds() / 86400  # gün cinsinden, ileri = pozitif
    # delta = 7 → 7 gün sonra dolacak
    # delta = -3 → 3 gün önce dolmuş

    already = inv.last_reminder_kind or ""
    # Penceredeki aşama
    # d_minus_7: 6 < delta <= 8 (7 gün civarı, hafta öncesi)
    # d_minus_3: 2 < delta <= 4
    # d_minus_1: 0 < delta <= 2
    # d_plus_1: -2 <= delta < 0
    # d_plus_3: -4 <= delta < -2
    # d_plus_7: delta < -4 (7+ gün gecikme)
    sent_index = REMINDER_STAGES.index(already) if already in REMINDER_STAGES else -1

    candidate_stages: list[tuple[str, bool]] = []
    if 6 < delta <= 8:
        candidate_stages.append(("d_minus_7", True))
    if 2 < delta <= 4:
        candidate_stages.append(("d_minus_3", True))
    if 0 < delta <= 2:
        candidate_stages.append(("d_minus_1", True))
    if -2 <= delta < 0:
        candidate_stages.append(("d_plus_1", True))
    if -4 <= delta < -2:
        candidate_stages.append(("d_plus_3", True))
    if delta < -4:
        candidate_stages.append(("d_plus_7", True))

    for stage, _ in candidate_stages:
        idx = REMINDER_STAGES.index(stage)
        if idx > sent_index:
            return stage
    return None


def _institution_admin_email(db: Session, *, institution_id: int) -> tuple[str | None, str | None]:
    """Kurumun yetkili admin'inin e-postası (varsa). Yoksa contact_email."""
    admin = (
        db.query(User)
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.INSTITUTION_ADMIN,
            User.is_active.is_(True),
        )
        .first()
    )
    if admin is not None and admin.email:
        return (admin.email, admin.full_name)
    inst = db.get(Institution, institution_id)
    if inst and inst.contact_email:
        return (inst.contact_email, inst.name)
    return (None, None)


def _invoice_recipient(
    db: Session, inv: Invoice,
) -> tuple[str | None, str | None, str]:
    """Invoice owner'a göre (email, recipient_name, owner_display_name).

    - owner_type='institution' → mevcut akış (institution_admin veya contact_email)
    - owner_type='user' → bağımsız öğretmenin kendi email'i + full_name
    """
    if inv.owner_type == "user" and inv.user_id is not None:
        u = db.get(User, inv.user_id)
        if u and u.email:
            display = u.full_name or u.email
            return (u.email, u.full_name or u.email, display)
        return (None, None, "Hesabınız")
    # institution
    email, name = _institution_admin_email(db, institution_id=inv.institution_id)
    inst = db.get(Institution, inv.institution_id) if inv.institution_id else None
    display = inst.name if inst else "Kurumunuz"
    return (email, name, display)


def _email_subject_and_body(
    *, stage: str, invoice: Invoice, recipient_name: str | None,
    institution_name: str | None = None,
    owner_name: str | None = None,
) -> tuple[str, str]:
    """Aşamaya göre e-posta. owner_name = "kurum adı" veya "öğretmenin adı".
    Backward compat: institution_name parametresi hâlâ kabul edilir (alias).
    """
    if owner_name is None:
        owner_name = institution_name or "Hesabınız"
    institution_name = owner_name  # iç gövde aynen kullanıyor
    """Aşamaya göre e-posta konu + gövde (sade, hatırlatma odaklı)."""
    due_str = invoice.due_at.strftime("%d.%m.%Y") if invoice.due_at else "—"
    amount_str = f"{invoice.amount_try:,}".replace(",", ".") + " ₺"
    name = recipient_name or "Sayın Yetkili"

    if stage == "d_minus_7":
        return (
            f"Yaklaşan ödeme — {amount_str} (vade {due_str})",
            f"{name},\n\n"
            f"{institution_name} hesabınızın aylık ödemesi 7 gün sonra ({due_str}) "
            f"dolacak. Tutar: {amount_str}.\n\n"
            f"Otomatik tahsilat aktif değilse, lütfen ödemeyi planlayın.\n\n"
            f"İyi günler dileriz."
        )
    if stage == "d_minus_3":
        return (
            f"Hatırlatma — ödeme 3 gün sonra ({amount_str})",
            f"{name},\n\n"
            f"Hatırlatma: {institution_name} ödemesi 3 gün içinde dolacak ({due_str}). "
            f"Tutar: {amount_str}.\n\n"
            f"Sorununuz varsa lütfen bize ulaşın.\n"
        )
    if stage == "d_minus_1":
        return (
            f"⚠ Yarın vade — {amount_str}",
            f"{name},\n\n"
            f"{institution_name} ödemesi yarın ({due_str}) dolacak. "
            f"Tutar: {amount_str}.\n\n"
            f"Lütfen bugün gerekli adımı atın — hesabınızın kesintisiz kalması için."
        )
    if stage == "d_plus_1":
        return (
            f"Ödeme gecikti — {amount_str}",
            f"{name},\n\n"
            f"Önemli: {institution_name} ödemesi dün ({due_str}) doldu, hâlâ tahsil edilemedi.\n"
            f"Tutar: {amount_str}.\n\n"
            f"3 gün ek süre tanıyoruz. Lütfen mümkün olan en kısa sürede ödeyin "
            f"veya bize ulaşın."
        )
    if stage == "d_plus_3":
        return (
            f"⚠ Hesap kısıtlama uyarısı — {amount_str}",
            f"{name},\n\n"
            f"{institution_name} ödemesi 3 gündür gecikti ({due_str} vadeli).\n"
            f"Tutar: {amount_str}.\n\n"
            f"Önümüzdeki 4 gün içinde ödeme yapılmazsa hesap özellikleri kısıtlanabilir. "
            f"Lütfen acilen bizimle iletişime geçin."
        )
    if stage == "d_plus_7":
        return (
            f"🚨 Son uyarı — hesap pasifleşecek",
            f"{name},\n\n"
            f"{institution_name} ödemesi 7 gündür gecikti ({due_str} vadeli, {amount_str}).\n\n"
            f"Bu son hatırlatmamızdır. Önümüzdeki 24 saat içinde ödeme alınmazsa "
            f"hesabınız otomatik pasif moda alınacak.\n\n"
            f"Lütfen hemen bize ulaşın."
        )
    # manual veya unknown
    return (
        f"Ödeme hatırlatma — {amount_str}",
        f"{name},\n\n"
        f"{institution_name} için açık ödeme: {amount_str} (vade {due_str}).\n\n"
        f"Yardımcı olabileceğimiz bir şey varsa bize yazın."
    )


@dataclass
class SendResult:
    ok: bool
    error: str | None = None
    stage: str | None = None
    institution_id: int | None = None
    recipient: str | None = None


def send_reminder(
    db: Session,
    *,
    invoice_id: int,
    kind: str = "manual",
    triggered_by_user_id: int | None = None,
    manual: bool = False,
    autocommit: bool = True,
) -> dict:
    """Bir fatura için ödeme hatırlatması gönder.

    manual=True → admin'in tetiklediği, dedup yok (her zaman gönder).
    manual=False → cron'un tetiklediği, dedup var (`last_reminder_kind` ile).
    """
    inv = db.get(Invoice, invoice_id)
    if inv is None:
        return {"ok": False, "error": "invoice_not_found"}
    if inv.status not in (InvoiceStatus.PENDING, InvoiceStatus.OVERDUE):
        return {"ok": False, "error": "invoice_not_eligible",
                "status": inv.status.value}

    if not manual:
        # Cron tarafı: aşama belirle ve dedup kontrol et
        stage = _stage_for_invoice(inv, now=_now())
        if stage is None:
            return {"ok": False, "error": "no_stage_due"}
        if inv.last_reminder_kind == stage:
            return {"ok": False, "error": "already_sent", "stage": stage}
        kind = stage
    else:
        # Manuel: kind parametresi geçerliyse al, değilse "manual"
        if kind not in REMINDER_STAGES and kind != "manual":
            kind = "manual"

    # Alıcı e-posta (owner-aware: institution vs bağımsız öğretmen)
    email, recipient_name, owner_display = _invoice_recipient(db, inv)
    if not email:
        return {"ok": False, "error": "no_recipient",
                "owner_type": inv.owner_type,
                "institution_id": inv.institution_id,
                "user_id": inv.user_id}

    subject, body = _email_subject_and_body(
        stage=kind, invoice=inv, recipient_name=recipient_name,
        owner_name=owner_display,
    )

    # Email gönder (stub modda log basar, gerçek modda SMTP)
    sent = False
    try:
        from app.services.email_service import send_email
        sent = send_email(
            to=email,
            template="dunning_reminder",
            ctx={
                "subject": subject,
                "body": body,
                "invoice_id": inv.id,
                "amount_try": inv.amount_try,
                "due_at": inv.due_at.isoformat() if inv.due_at else None,
                "stage": kind,
            },
        )
    except Exception:
        logger.exception("dunning email send fail invoice=%s", invoice_id)
        sent = False

    # Tahmini gönderildi sayalım (stub mod False döner ama log var)
    inv.last_reminder_kind = kind
    inv.last_reminder_at = _now()
    # Notes'a yaz
    summary = f"Dunning [{kind}] gönderildi → {email}"
    inv.notes = ((inv.notes or "") + f"\n[{_now().isoformat()}] {summary}")[:8000]
    if autocommit:
        db.commit()

    return {
        "ok": True,
        "stage": kind,
        "owner_type": inv.owner_type,
        "user_id": inv.user_id,
        "institution_id": inv.institution_id,
        "recipient": email,
        "sent_via_email": sent,
        "subject": subject,
    }


def run_dunning_for_all(db: Session, *, autocommit: bool = True) -> dict:
    """Cron: tüm uygun faturalar için aşama tetikle.

    Returns: özetlerin sayımı.
    """
    now = _now()
    rows = (
        db.query(Invoice)
        .filter(
            Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
            Invoice.due_at <= now + timedelta(days=8),  # D-7 penceresine kadar
        )
        .all()
    )
    summary = {
        "total_eligible": len(rows),
        "sent": 0,
        "skipped_already_sent": 0,
        "skipped_no_stage": 0,
        "skipped_no_recipient": 0,
        "by_stage": {},
        "errors": 0,
    }
    for inv in rows:
        result = send_reminder(
            db, invoice_id=inv.id, manual=False,
            autocommit=False,  # toplu commit
        )
        if not result.get("ok"):
            err = result.get("error", "unknown")
            if err == "already_sent":
                summary["skipped_already_sent"] += 1
            elif err == "no_stage_due":
                summary["skipped_no_stage"] += 1
            elif err == "no_recipient":
                summary["skipped_no_recipient"] += 1
            else:
                summary["errors"] += 1
            continue
        summary["sent"] += 1
        stage = result.get("stage", "?")
        summary["by_stage"][stage] = summary["by_stage"].get(stage, 0) + 1
    if autocommit:
        db.commit()
    return summary


__all__ = [
    "REMINDER_STAGES",
    "REMINDER_STAGE_LABELS_TR",
    "run_dunning_for_all",
    "send_reminder",
]
