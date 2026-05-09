"""addons_monthly_renewal cron schedule — günlük 00:30 UTC

Revision ID: d2y8b1a2b11v
Revises: c1x7a0z1a00u
Create Date: 2026-05-09 09:00:00.000000

Stage 9 (Faz 2.2) — add-on aylık yenileme cron seed:
- job_key='addons_monthly_renewal'
- Günlük 00:30 UTC tick — job ayın 1'inde efektif iş yapar (içeride filtre);
  auto_renew=True olan ve dönemi biten add-on'ları yeni aya yeniler.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d2y8b1a2b11v"
down_revision: Union[str, None] = "c1x7a0z1a00u"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "addons_monthly_renewal"},
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
            "k": "addons_monthly_renewal",
            "d": "Aylık ek paket yenileme — auto_renew aktif add-on'ları her ayın 1'inde yeniler",
            "h": 0,
            "m": 30,
            "w": None,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "addons_monthly_renewal"},
    )
