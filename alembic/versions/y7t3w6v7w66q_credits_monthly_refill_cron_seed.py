"""credits_monthly_refill cron schedule — günlük 00:30 UTC tick

Revision ID: y7t3w6v7w66q
Revises: x6s2v5u6v55p
Create Date: 2026-05-09 22:30:00.000000

Stage 6 — kredi aylık refill cron seed:
- job_key='credits_monthly_refill'
- Günlük 00:30 UTC tick — ayın 1. günü değilse iş içinde skip
- enabled=True default
- Idempotent: zaten varsa atlar
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y7t3w6v7w66q"
down_revision: Union[str, None] = "x6s2v5u6v55p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "credits_monthly_refill"},
    ).first()
    if existing is not None:
        return
    bind.execute(
        sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, enabled) "
            "VALUES (:k, :d, :h, :m, :w, 1)"
        ),
        {
            "k": "credits_monthly_refill",
            "d": "Günlük 00:30 UTC — sadece ayın 1. günü etkili (kredi havuzu yenileme)",
            "h": 0,
            "m": 30,
            "w": None,  # her gün
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "credits_monthly_refill"},
    )
