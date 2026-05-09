"""subscription_resume + subscription_guarantee_eval cron seed

Revision ID: e3z9c2a3b22w
Revises: d2y8b1a2b11v
Create Date: 2026-05-09 12:00:00.000000

Stage 9 (Faz 2.5):
- subscription_resume: günlük 01:00 UTC — pause süresi geçen kurumları resume
- subscription_guarantee_eval: günlük 06:00 UTC (içeride pazartesi filtresi) —
  60g performans garantisi değerlendir
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e3z9c2a3b22w"
down_revision: Union[str, None] = "d2y8b1a2b11v"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    seeds = [
        {
            "k": "subscription_resume",
            "d": "Yaz pause süresi biten kurumları akademik yıla resume eder",
            "h": 1, "m": 0,
        },
        {
            "k": "subscription_guarantee_eval",
            "d": "60g performans garantisi haftalık değerlendirme (Pzt 06:00 UTC)",
            "h": 6, "m": 0,
        },
    ]
    for seed in seeds:
        existing = bind.execute(
            sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
            {"k": seed["k"]},
        ).first()
        if existing is not None:
            continue
        bind.execute(
            sa.text(
                "INSERT INTO cron_schedules "
                "(job_key, description, hour, minute, day_of_week, enabled) "
                "VALUES (:k, :d, :h, :m, NULL, 1)"
            ),
            seed,
        )


def downgrade() -> None:
    bind = op.get_bind()
    for k in ("subscription_resume", "subscription_guarantee_eval"):
        bind.execute(
            sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
            {"k": k},
        )
