"""Ücretsiz pakette tek seferlik deneme PDF analizi hakkı (2026-10-28).

Kullanıcı kararı: ücretsiz pakete düşen koç (ya da ücretsiz kurum) deneme
analizinin nasıl çalıştığını görebilsin — hesap başına TOPLAM `FREE_EXAM_IMPORT_QUOTA`
PDF analizi, aylık yenilenmez. Hak bitince yükseltme mesajı.

- Ücretli paket / aktif deneme → bu modül devreye girmez (normal kredi akışı).
- Ücretsiz hak KREDİ DÜŞMEZ (ücretsiz paketin 50 kredisi 8 analize yetmezdi);
  0 kredilik `AI_EXAM_IMPORT_FREE` ölçüm satırı yazılır, sayım ondan yapılır.
  Deneme süresinde yapılan analizler (AI_EXAM_IMPORT) bu hakka SAYILMAZ.
- Sahip = kredi sahibi (bağımsız koç → kendisi, kurum öğretmeni → kurum).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import UsageEvent, UsageKind, User

FREE_EXAM_IMPORT_QUOTA = 10


@dataclass
class FreeExamQuota:
    applies: bool       # ücretsiz hak modu mu (ücretli pakette False)
    quota: int
    used: int

    @property
    def left(self) -> int:
        return max(0, self.quota - self.used)


def _owner(coach: User):
    from app.services.credits import CreditOwner
    return CreditOwner.for_user(coach)


def used_count(db: Session, coach: User) -> int:
    owner = _owner(coach)
    return int(
        db.query(func.count(UsageEvent.id))
        .filter(
            UsageEvent.owner_type == owner.type,
            UsageEvent.owner_id == owner.id,
            UsageEvent.kind == UsageKind.AI_EXAM_IMPORT_FREE,
        )
        .scalar()
        or 0
    )


def status_for(db: Session, coach: User) -> FreeExamQuota:
    from app.services.plans import ai_premium_allowed
    if ai_premium_allowed(db, coach):
        return FreeExamQuota(applies=False, quota=FREE_EXAM_IMPORT_QUOTA, used=0)
    return FreeExamQuota(applies=True, quota=FREE_EXAM_IMPORT_QUOTA,
                         used=used_count(db, coach))


def record_free_use(db: Session, coach: User, *, actor_id: int, metadata: dict) -> None:
    """0 kredilik ölçüm kaydı (commit etmez). record_usage KULLANILMAZ —
    krediyi 1'e clamp'leyip hesaptan düşerdi (ai_book_structure deseni)."""
    from app.services.credits import current_period
    owner = _owner(coach)
    db.add(UsageEvent(
        owner_type=owner.type,
        owner_id=owner.id,
        kind=UsageKind.AI_EXAM_IMPORT_FREE,
        credits=0,
        period_year_month=current_period(datetime.now(timezone.utc)),
        actor_user_id=actor_id,
        metadata_json=json.dumps(metadata, ensure_ascii=False),
    ))
