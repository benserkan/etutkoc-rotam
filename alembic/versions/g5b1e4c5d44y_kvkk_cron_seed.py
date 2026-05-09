"""kvkk_apply_expired_deletions cron seed (günlük 02:00 UTC)

Revision ID: g5b1e4c5d44y
Revises: f4a0d3b4c33x
Create Date: 2026-05-09 14:30:00.000000

Stage 10 — RTBF cron seed:
- 30 günlük grace period'u dolmuş silme taleplerini günlük 02:00 UTC'de uygular
- apply_deletion çağrısı kullanıcıyı anonimleştirir (full_name + email + password
  + telefon temizlenir; AuditLog/Tasks/NotificationLog adli iz amaçlı korunur)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g5b1e4c5d44y"
down_revision: Union[str, None] = "f4a0d3b4c33x"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "kvkk_apply_expired_deletions"},
    ).first()
    if existing is not None:
        return
    bind.execute(
        sa.text(
            "INSERT INTO cron_schedules "
            "(job_key, description, hour, minute, day_of_week, enabled) "
            "VALUES (:k, :d, :h, :m, NULL, 1)"
        ),
        {
            "k": "kvkk_apply_expired_deletions",
            "d": "KVKK madde 11 silme taleplerini 30g grace sonrası uygular (anonimleştirme)",
            "h": 2,
            "m": 0,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "kvkk_apply_expired_deletions"},
    )
