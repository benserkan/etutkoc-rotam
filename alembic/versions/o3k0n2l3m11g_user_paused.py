"""user.is_paused — manuel + otonom uyarı susturma

Revision ID: o3k0n2l3m11g
Revises: n2j9m1k2l00f
Create Date: 2026-05-14 14:00:00.000000

User'a 5 yeni alan:
- is_paused (bool, default False) — alert susturma durumu
- paused_at (datetime nullable) — ne zaman pasifleşti
- paused_by_id (FK users.id SET NULL) — kim tarafından (sistem ise NULL)
- pause_reason (str nullable) — "manual" / "auto_inactivity"
- last_manual_resume_at (datetime nullable) — sticky override için 7 günlük cooldown

Cron seed:
- auto_pause_inactive_users — her gece 03:00 UTC. Öğrenci 21+ gün, öğretmen
  30+ gün sessizlikse pasif eder (panik koruyucu %5 günlük limit).

NOT: is_active alanına dokunulmadı (auth login bağımlılığı var).
Pasif kullanıcı GİRİŞ YAPABİLİR; sadece alert/notification akışlarından
çıkarılır. Geçişler audit log'a düşer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o3k0n2l3m11g"
down_revision: Union[str, None] = "n2j9m1k2l00f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("is_paused", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        batch.add_column(
            sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        )
        batch.add_column(
            sa.Column("paused_by_id", sa.Integer(), nullable=True),
        )
        batch.add_column(
            sa.Column("pause_reason", sa.String(length=40), nullable=True),
        )
        batch.add_column(
            sa.Column("last_manual_resume_at", sa.DateTime(timezone=True), nullable=True),
        )
        batch.create_foreign_key(
            "fk_user_paused_by", "users",
            ["paused_by_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_index("ix_user_is_paused", ["is_paused"])

    # Cron seed — auto_pause_inactive_users, her gece 03:00 UTC
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO cron_schedules (job_key, description, hour, minute, "
            "day_of_week, enabled) VALUES (:k, :d, :h, :m, :w, 1)"
        ),
        {
            "k": "auto_pause_inactive_users",
            "d": "Her gece 03:00 — sessizleşen öğrenci/öğretmenleri otomatik pasif eder",
            "h": 3, "m": 0, "w": None,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = 'auto_pause_inactive_users'")
    )
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_user_is_paused")
        batch.drop_constraint("fk_user_paused_by", type_="foreignkey")
        batch.drop_column("last_manual_resume_at")
        batch.drop_column("pause_reason")
        batch.drop_column("paused_by_id")
        batch.drop_column("paused_at")
        batch.drop_column("is_paused")
