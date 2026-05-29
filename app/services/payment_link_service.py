"""PaymentLink servisi — süper admin ödeme linki yönetimi (Paket Ö2a).

Akış:
  1. Süper admin /admin/payment-links'te form doldurur: hedef kurum/koç + plan +
     döngü + tutar (özel) + opsiyonel açıklama + son kullanma (vars. 14g).
  2. `create_link(...)` → DB satırı + token üretir + URL döner.
  3. Süper admin URL'i kuruma e-posta/WhatsApp ile gönderir.
  4. Kurum yöneticisi linke tıklar, login olur, "Şimdi Öde" butonuna basar.
  5. Iyzico Checkout başlatılır (link_id PaymentTransaction'a yazılır).
  6. Iyzico callback → verify_callback → plan aktive + linkten consumed.

Linkin sahibi yalnız hedef olabilir:
  - target_owner_type=institution, target_owner_id=42 → o kurumun ADMIN'i ödeyebilir
    (veya süper admin başkası adına ödeyebilir test için)
  - target_owner_type=user, target_owner_id=42 → o user kendisi ödeyebilir

`mark_consumed` callback'te `iyzico_service.verify_callback` tarafından çağrılır.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    AuditAction,
    LINK_OWNER_INSTITUTION,
    LINK_OWNER_USER,
    LINK_STATUS_ACTIVE,
    LINK_STATUS_CANCELLED,
    LINK_STATUS_CONSUMED,
    LINK_STATUS_EXPIRED,
    Institution,
    PaymentLink,
    PaymentTransaction,
    User,
)
from app.services import audit as audit_service


DEFAULT_EXPIRY_DAYS = 14


class PaymentLinkError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _generate_token() -> str:
    """32-char URL-safe hex (secrets.token_hex(16) = 32 char)."""
    return secrets.token_hex(16)


def create_link(
    db: Session, *,
    admin: User,
    target_owner_type: str,
    target_owner_id: int,
    plan_code: str,
    cycle: str,
    amount: Decimal | float | int | str,
    description: str | None = None,
    expires_in_days: int | None = DEFAULT_EXPIRY_DAYS,
) -> PaymentLink:
    """Süper admin link oluşturur.

    Validation: target gerçekten var mı, plan/cycle geçerli mi, amount > 0.
    """
    if target_owner_type not in (LINK_OWNER_INSTITUTION, LINK_OWNER_USER):
        raise PaymentLinkError("link_owner_invalid", "Hedef türü geçersiz")

    if cycle not in ("monthly", "annual"):
        raise PaymentLinkError("link_cycle_invalid", "Geçersiz dönem (monthly|annual)")

    # Hedefi doğrula
    if target_owner_type == LINK_OWNER_INSTITUTION:
        target = db.get(Institution, target_owner_id)
        if target is None:
            raise PaymentLinkError("link_target_not_found", "Kurum bulunamadı")
    else:
        target = db.get(User, target_owner_id)
        if target is None:
            raise PaymentLinkError("link_target_not_found", "Kullanıcı bulunamadı")

    amount_dec = Decimal(str(amount))
    if amount_dec <= 0:
        raise PaymentLinkError("link_amount_invalid", "Tutar 0'dan büyük olmalı")

    expires_at = None
    if expires_in_days and expires_in_days > 0:
        expires_at = datetime.utcnow() + timedelta(days=expires_in_days)

    # Token çakışma ihtimali çok düşük (16 byte) ama yine de tekrar dene
    for _ in range(5):
        token = _generate_token()
        existing = db.query(PaymentLink).filter(PaymentLink.token == token).first()
        if existing is None:
            break
    else:
        raise PaymentLinkError("link_token_collision", "Benzersiz token üretilemedi")

    link = PaymentLink(
        token=token,
        target_owner_type=target_owner_type,
        target_owner_id=target_owner_id,
        plan_code=plan_code,
        cycle=cycle,
        amount=amount_dec,
        currency="TRY",
        description=description,
        status=LINK_STATUS_ACTIVE,
        expires_at=expires_at,
        created_by_admin_id=admin.id,
    )
    db.add(link)
    db.flush()

    audit_service.log_action(
        db,
        action=AuditAction.PAYMENT_INITIATED,
        actor_id=admin.id,
        target_type="payment_link",
        target_id=link.id,
        details={
            "target": f"{target_owner_type}:{target_owner_id}",
            "plan": plan_code,
            "cycle": cycle,
            "amount": str(amount_dec),
        },
        autocommit=False,
    )
    db.commit()
    return link


def get_by_token(db: Session, token: str) -> PaymentLink | None:
    return db.query(PaymentLink).filter(PaymentLink.token == token).first()


def list_links(
    db: Session, *,
    status_filter: str | None = None,
    target_owner_type: str | None = None,
    target_owner_id: int | None = None,
    limit: int = 100,
) -> list[PaymentLink]:
    q = db.query(PaymentLink)
    if status_filter:
        q = q.filter(PaymentLink.status == status_filter)
    if target_owner_type:
        q = q.filter(PaymentLink.target_owner_type == target_owner_type)
    if target_owner_id:
        q = q.filter(PaymentLink.target_owner_id == target_owner_id)
    return q.order_by(PaymentLink.created_at.desc()).limit(limit).all()


def cancel_link(db: Session, *, admin: User, link_id: int) -> PaymentLink:
    link = db.get(PaymentLink, link_id)
    if link is None:
        raise PaymentLinkError("link_not_found", "Link bulunamadı")
    if link.status != LINK_STATUS_ACTIVE:
        raise PaymentLinkError(
            "link_not_active",
            f"Yalnız aktif linkler iptal edilebilir (mevcut: {link.status})",
        )
    link.status = LINK_STATUS_CANCELLED
    audit_service.log_action(
        db,
        action=AuditAction.PAYMENT_FAILED,
        actor_id=admin.id,
        target_type="payment_link",
        target_id=link.id,
        details={"reason": "cancelled_by_admin"},
        autocommit=False,
    )
    db.commit()
    return link


def mark_consumed(
    db: Session, *,
    link: PaymentLink,
    transaction: PaymentTransaction,
    consumer_user: User | None = None,
    autocommit: bool = True,
) -> PaymentLink:
    """iyzico_service.verify_callback başarılı ödemede çağırır.

    Idempotent: zaten consumed ise no-op.
    """
    if link.status == LINK_STATUS_CONSUMED:
        return link

    link.status = LINK_STATUS_CONSUMED
    link.consumed_at = datetime.utcnow()
    link.consumed_transaction_id = transaction.id
    if consumer_user is not None:
        link.consumed_by_user_id = consumer_user.id

    if autocommit:
        db.commit()
    else:
        db.flush()
    return link


def expire_overdue_links(db: Session) -> int:
    """Cron tarafından çağrılır — süresi geçmiş ACTIVE linkleri EXPIRED yapar."""
    now = datetime.utcnow()
    rows = (
        db.query(PaymentLink)
        .filter(
            PaymentLink.status == LINK_STATUS_ACTIVE,
            PaymentLink.expires_at.is_not(None),
            PaymentLink.expires_at < now,
        )
        .all()
    )
    for link in rows:
        link.status = LINK_STATUS_EXPIRED
    if rows:
        db.commit()
    return len(rows)


def can_user_pay_link(user: User, link: PaymentLink) -> bool:
    """Bu kullanıcı bu linki ödeyebilir mi?

    Kurallar:
      - Süper admin her zaman ödeyebilir (test/destek için)
      - Kurum linki: o kurumun INSTITUTION_ADMIN'i ödeyebilir
      - User linki: yalnız o user kendisi ödeyebilir
    """
    from app.models import UserRole

    if user.role == UserRole.SUPER_ADMIN:
        return True

    if link.target_owner_type == LINK_OWNER_INSTITUTION:
        if user.role != UserRole.INSTITUTION_ADMIN:
            return False
        return user.institution_id == link.target_owner_id

    if link.target_owner_type == LINK_OWNER_USER:
        return user.id == link.target_owner_id

    return False
