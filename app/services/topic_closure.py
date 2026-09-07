"""Konu kapatma servisi — müfredat tamamlanmasının TEK MERKEZİ (2026-09-07).

Koç öğrenciyle görüşür, "bu konu bitti mi?" diye sorar ve kararını işaretler.
Kapatma iki yerden yapılabilir (müfredat paneli · program yaparken konu kartı)
ama TEK KAYIT üretir — iki yüzey aynı gerçeği gösterir.

İdempotent: aynı konuyu iki kez kapatmak hata değil, ikinci çağrı no-op'tur
(koç iki sekmede birden basmış olabilir).
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import TopicClosure, User


def closed_topic_ids(db: Session, student_id: int) -> set[int]:
    """Öğrencinin kapatılmış konu id'leri — müfredat durum hesabı için."""
    rows = (
        db.query(TopicClosure.topic_id)
        .filter(TopicClosure.student_id == student_id)
        .all()
    )
    return {r[0] for r in rows}


def closure_map(db: Session, student_id: int) -> dict[int, TopicClosure]:
    """topic_id → kapatma kaydı (tarih/kim gösterilecekse)."""
    rows = (
        db.query(TopicClosure)
        .filter(TopicClosure.student_id == student_id)
        .all()
    )
    return {r.topic_id: r for r in rows}


def close_topic(
    db: Session,
    *,
    student_id: int,
    topic_id: int,
    actor: User | None = None,
    note: str | None = None,
) -> TopicClosure:
    """Konuyu kapat. İdempotent — zaten kapalıysa mevcut kayıt döner."""
    existing = (
        db.query(TopicClosure)
        .filter(
            TopicClosure.student_id == student_id,
            TopicClosure.topic_id == topic_id,
        )
        .first()
    )
    if existing is not None:
        # Not sonradan yazıldıysa güncelle; kapatma anını KORU (ilk karar).
        if note and not existing.note:
            existing.note = note
        return existing
    row = TopicClosure(
        student_id=student_id,
        topic_id=topic_id,
        closed_at=datetime.now(timezone.utc),
        closed_by_id=actor.id if actor is not None else None,
        note=(note or None),
    )
    db.add(row)
    db.flush()
    return row


def reopen_topic(db: Session, *, student_id: int, topic_id: int) -> bool:
    """Konuyu yeniden aç (kapatma kaydını sil). Dönüş: kayıt var mıydı."""
    row = (
        db.query(TopicClosure)
        .filter(
            TopicClosure.student_id == student_id,
            TopicClosure.topic_id == topic_id,
        )
        .first()
    )
    if row is None:
        return False
    db.delete(row)
    db.flush()
    return True
