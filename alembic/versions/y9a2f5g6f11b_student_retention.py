"""users.deactivated_at + retention_warned_at + KVKK saklama süresi cron'u

Revision ID: y9a2f5g6f11b
Revises: x8z1e4f5e00a
Create Date: 2026-11-01

Koçluğu sonlandırılan (pasif) öğrencinin verisi süresiz kalıyordu ve pasife
alma tarihi hiç tutulmuyordu. Kural (kullanıcı kararı): koçluk sonlandırıldıktan
3 ay sonra öğrenci KVKK kapsamında otomatik anonimleştirilir; 14 gün önce koça
hatırlatma gider.

- users.deactivated_at: is_active False olduğu an (model olayı otomatik yazar).
- users.retention_warned_at: koça hatırlatma gönderildi işareti (dedup).
- Geriye dönük: hâlihazırda pasif ve anonimleştirilmemiş öğrencilerde sayaç
  migration anından başlar (gerçek tarih bilinmiyor; erken silmemek için).
- Cron seed: kvkk_retention_inactive — her gün 02:30 UTC.
Additive; downgrade sütunları ve cron satırını kaldırır.
"""
import sqlalchemy as sa
from alembic import op

revision = "y9a2f5g6f11b"
down_revision = "x8z1e4f5e00a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True))
        b.add_column(sa.Column("retention_warned_at", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE users SET deactivated_at = CURRENT_TIMESTAMP "
            "WHERE is_active = :f AND role = 'STUDENT' "
            "AND email NOT LIKE 'anonymized-%' AND deactivated_at IS NULL"
        ),
        {"f": False},
    )

    existing = bind.execute(
        sa.text("SELECT 1 FROM cron_schedules WHERE job_key = :k"),
        {"k": "kvkk_retention_inactive"},
    ).first()
    if existing is None:
        bind.execute(
            sa.text(
                "INSERT INTO cron_schedules "
                "(job_key, description, hour, minute, day_of_week, enabled) "
                "VALUES (:k, :d, :h, :m, :w, :e)"
            ),
            {
                "k": "kvkk_retention_inactive",
                "d": "KVKK saklama süresi: koçluğu 3 ay önce sonlandırılan öğrenciyi anonimleştir; 14 gün önce koça hatırlat",
                "h": 2,
                "m": 30,
                "w": None,
                "e": True,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM cron_schedules WHERE job_key = :k"),
        {"k": "kvkk_retention_inactive"},
    )
    with op.batch_alter_table("users") as b:
        b.drop_column("retention_warned_at")
        b.drop_column("deactivated_at")
