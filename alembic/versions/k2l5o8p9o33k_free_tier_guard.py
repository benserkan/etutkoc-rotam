"""Ücretsiz paket tekilliği + plan akışı düzeltmeleri — 2026-10-02.

- coach_device_links: bağımsız koç hesabının giriş yaptığı cihazlar (kalıcı
  cihaz çerezi / mobil kurulum kimliği, SHA-256 özeti). Aynı kişinin birden çok
  hesapla ücretsiz paketi / denemeyi çoğaltmasını yakalamak için.
- users.trial_denied_reason: kayıtta deneme verilmediyse nedeni
  (device | phone | email) — banner "deneme bu kişide daha önce kullanılmış" der.
- VERİ: kayıt geçmişindeki "free → solo_trial" satırları "— → solo_trial" olur
  (hesap hiç 'free' seçmedi; eski varsayılan koddu). Bağımsız koçlardaki eski
  'free' plan kodu 'solo_free' (Keşif) olur.

Additive, downgrade'li (veri düzeltmesi geri alınmaz — zararsız).
"""
from alembic import op
import sqlalchemy as sa

revision = "k2l5o8p9o33k"
down_revision = "j1k4n7o8n22j"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coach_device_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_hash", sa.String(64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "device_hash", name="uq_coach_device_user_hash"),
    )
    op.create_index("ix_coach_device_links_device_hash", "coach_device_links", ["device_hash"])
    op.create_index("ix_coach_device_links_user_id", "coach_device_links", ["user_id"])

    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("trial_denied_reason", sa.String(20), nullable=True))

    bind = op.get_bind()
    # Enum'lar her iki veritabanında da üye ADIYLA saklanır (SIGNUP, TEACHER).
    bind.execute(sa.text(
        "UPDATE plan_change_history SET from_plan = NULL "
        "WHERE from_plan = 'free' AND to_plan = 'solo_trial' AND reason = 'SIGNUP'"
    ))
    bind.execute(sa.text(
        "UPDATE users SET plan = 'solo_free' "
        "WHERE plan = 'free' AND role = 'TEACHER' AND institution_id IS NULL"
    ))


def downgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.drop_column("trial_denied_reason")
    op.drop_index("ix_coach_device_links_user_id", table_name="coach_device_links")
    op.drop_index("ix_coach_device_links_device_hash", table_name="coach_device_links")
    op.drop_table("coach_device_links")
