"""admin_weekly_digest cron schedule — Pazartesi 09:00 UTC

Revision ID: w5r1u4t5u44o
Revises: v4q0u3s4t33n
Create Date: 2026-05-09 20:30:00.000000

Stage 4 — admin haftalık özet cron seed:
- job_key='admin_weekly_digest'
- Pazartesi (day_of_week=0) 09:00 UTC = TR 12:00 öğle
- enabled=True default
- Idempotent: zaten varsa atlar
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "w5r1u4t5u44o"
down_revision: Union[str, None] = "v4q0u3s4t33n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "admin_weekly_digest"},
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
            "k": "admin_weekly_digest",
            "d": "Her Pazartesi 09:00 UTC (TR 12:00) — kurum yöneticilerine haftalık özet e-posta",
            "h": 9,
            "m": 0,
            "w": 0,   # 0 = Pazartesi
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "admin_weekly_digest"},
    )
