"""Kurum yöneticisi haftalık özeti Salı 12:00 TR'ye (2026-11-12).

Ölçüm (prod, 9 hafta): Pazartesi 12:00'de bir haftanın tamamlamalarının ort. %5'i
(en çok %12) henüz işaretlenmemiş; Salı 12:00'de ~%2. Raporlanan hafta değişmez
(geçen Pazartesi–Pazar); yalnız gönderim bir gün sonraya alınır.

Revision ID: c3e6j9k0j55f
Revises: b2d5i8j9i44e
"""
from alembic import op
import sqlalchemy as sa

revision = "c3e6j9k0j55f"
down_revision = "b2d5i8j9i44e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE cron_schedules SET day_of_week = 1, hour = 9, minute = 0, "
        "description = :d WHERE job_key = 'admin_weekly_digest'"
    ), {"d": "Her Salı 09:00 UTC (TR 12:00) — kurum yöneticilerine geçen haftanın (Pzt–Paz) özeti"})


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE cron_schedules SET day_of_week = 0, hour = 9, minute = 0, "
        "description = :d WHERE job_key = 'admin_weekly_digest'"
    ), {"d": "Her Pazartesi 09:00 UTC (TR 12:00) — kurum yöneticilerine haftalık özet e-posta"})
