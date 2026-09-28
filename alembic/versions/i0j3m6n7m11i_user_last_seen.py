"""Kullanıcı son görülme zamanı (2026-09-28)

- users + last_seen_at (TIMESTAMPTZ, nullable): kimliği doğrulanmış herhangi bir
  isteğin (web çerezi, mobil Bearer, Jinja oturumu) zamanı; 10 dakikada bir
  güncellenir. `last_login_at` yalnız şifreyle girişte değişir — mobil uygulama
  30 günlük oturumla açık kaldığı için öğrenci her gün çalışsa da "5+ gündür
  giriş yok" görünüyordu (Emir #113 vakası).
- Geriye dönük: last_seen_at = en yeni ActiveSession.last_seen_at /
  last_login_at / görev tamamlama zamanı.
Additive, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "i0j3m6n7m11i"
down_revision = "h9i2l5m6l00h"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    # Sıralı güncellemeler — PG ve SQLite'ta aynı çalışır (GREATEST/LATERAL yok)
    op.execute("UPDATE users SET last_seen_at = last_login_at")
    for sub in (
        "SELECT MAX(s.last_seen_at) FROM active_sessions s WHERE s.user_id = users.id",
        "SELECT MAX(t.completed_at) FROM tasks t WHERE t.student_id = users.id",
    ):
        op.execute(
            f"UPDATE users SET last_seen_at = ({sub}) "
            f"WHERE ({sub}) IS NOT NULL AND (last_seen_at IS NULL OR ({sub}) > last_seen_at)"
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.drop_column("last_seen_at")
