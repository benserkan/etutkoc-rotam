"""stale_session_cleanup cron seed

Bayat oturum kayıtlarını ve kapanmamış kimliğe-bürünme oturumlarını kapatan
günlük iş (2026-07-31). Yalnız cron_schedules satırı ekler — şema değişmez.

Revision ID: g7h0k3m4m77g
Revises: f6g9j2l3l66f
Create Date: 2026-07-31
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g7h0k3m4m77g"
down_revision = "f6g9j2l3l66f"
branch_labels = None
depends_on = None

JOB_KEY = "stale_session_cleanup"


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": JOB_KEY},
    ).first()
    if existing is not None:
        return
    bind.execute(
        sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, enabled) "
            "VALUES (:k, :d, :h, :m, :w, :e)"
        ),
        {
            "k": JOB_KEY,
            "d": (
                "Günlük 04:20 UTC — 30 gündür hareketsiz oturum kayıtlarını ve "
                "süresi dolmuş kimliğe-bürünme oturumlarını kapat (kayıt silinmez)"
            ),
            "h": 4,
            "m": 20,
            "w": None,  # her gün
            "e": True,  # bind param — Postgres bool (literal 1 DatatypeMismatch verir)
        },
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": JOB_KEY},
    )
