"""invoices_mark_overdue cron seed (Sprint A.2).

Revision ID: b6y9a1z2a11t
Revises: a5x8z0y1z00s
Create Date: 2026-05-16 13:30:00.000000

Günlük 02:30 UTC'de vadesi geçmiş PENDING faturaları OVERDUE'ya geçirir.
Ödeme takvimi banner ve drill bucket'ları için doğru sınıflandırma şart.
"""
from typing import Sequence, Union
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision: str = "b6y9a1z2a11t"
down_revision: Union[str, None] = "a5x8z0y1z00s"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    now = datetime.now(timezone.utc).isoformat()
    op.execute(sa.text(
        "INSERT INTO cron_schedules "
        "(job_key, description, hour, minute, day_of_week, "
        " interval_minutes, enabled, created_at, updated_at) "
        "VALUES (:k, :d, :h, :m, :dow, :iv, 1, :ts, :ts)"
    ).bindparams(
        k="invoices_mark_overdue",
        d=("Vadesi geçmiş bekleyen faturaları OVERDUE'ya geçirir "
           "(ödeme takvimi banner için)."),
        h=2, m=30, dow=None, iv=None, ts=now,
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "DELETE FROM cron_schedules WHERE job_key = 'invoices_mark_overdue'"
    ))
