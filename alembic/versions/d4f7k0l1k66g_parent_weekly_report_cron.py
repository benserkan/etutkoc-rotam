"""Veli haftalık raporu: Pazartesi 19:00 TR, Pazartesi–Pazar haftası (2026-11-12).

- YENİ cron `parent_weekly_report` (Pazartesi 16:00 UTC)
- `weekly_backstop` (her gece "son 7 gün") KAPATILIR — iş fonksiyonu da no-op.

Revision ID: d4f7k0l1k66g
Revises: c3e6j9k0j55f
"""
from alembic import op
import sqlalchemy as sa

revision = "d4f7k0l1k66g"
down_revision = "c3e6j9k0j55f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    exists = bind.execute(sa.text(
        "SELECT 1 FROM cron_schedules WHERE job_key = 'parent_weekly_report'")).first()
    if not exists:
        bind.execute(sa.text(
            "INSERT INTO cron_schedules (job_key, description, hour, minute, day_of_week, enabled, "
            "created_at, updated_at) VALUES ('parent_weekly_report', :d, 16, 0, 0, :e, "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"),
            {"d": "Her Pazartesi 16:00 UTC (TR 19:00) — velilere geçen Pzt–Paz haftasının raporu",
             "e": True})
    bind.execute(sa.text(
        "UPDATE cron_schedules SET enabled = :e WHERE job_key = 'weekly_backstop'"), {"e": False})


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM cron_schedules WHERE job_key = 'parent_weekly_report'"))
    bind.execute(sa.text(
        "UPDATE cron_schedules SET enabled = :e WHERE job_key = 'weekly_backstop'"), {"e": True})
