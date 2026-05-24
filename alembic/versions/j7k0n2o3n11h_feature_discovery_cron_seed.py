"""feature_discovery_scan cron schedule — haftalık (Pzt 05:00 UTC)

Revision ID: j7k0n2o3n11h
Revises: i6j9m1n2m00g
Create Date: 2026-05-24 17:00:00.000000

Vitrin Kartları otomatik keşfi cron seed:
- job_key='feature_discovery_scan'
- Haftalık Pazartesi 05:00 UTC — son migration + commit'leri tarayıp yeni
  özellikler için DRAFT keşif kartı açar (idempotent). Önceden hiç otomatik
  tetiklenmiyordu (yalnız elle CLI); bu seed "yeni özellik → kart" sözünü
  gerçekten otomatikleştirir. Idempotent INSERT.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j7k0n2o3n11h"
down_revision: Union[str, None] = "i6j9m1n2m00g"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "feature_discovery_scan"},
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
            "k": "feature_discovery_scan",
            "d": "Haftalık Pzt 05:00 UTC — yeni özellikler için Vitrin keşif kartı aç",
            "h": 5,
            "m": 0,
            "w": 0,  # 0 = Pazartesi
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "feature_discovery_scan"},
    )
