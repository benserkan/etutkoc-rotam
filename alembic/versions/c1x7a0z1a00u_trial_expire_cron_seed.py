"""trial_expire cron schedule — günlük 00:15 UTC

Revision ID: c1x7a0z1a00u
Revises: b0w6z9y0z99t
Create Date: 2026-05-10 00:45:00.000000

Stage 9 (Faz 2) — trial expire cron seed:
- job_key='trial_expire'
- Günlük 00:15 UTC tick — ay 1'inde değil, her gün; süresi dolan trial'lar
  o gün eski plana düşürülür
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1x7a0z1a00u"
down_revision: Union[str, None] = "b0w6z9y0z99t"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "trial_expire"},
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
            "k": "trial_expire",
            "d": "Günlük 00:15 UTC — süresi dolmuş trial planlarını otomatik düşür",
            "h": 0,
            "m": 15,
            "w": None,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "trial_expire"},
    )
