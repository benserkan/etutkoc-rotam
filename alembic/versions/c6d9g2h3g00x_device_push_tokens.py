"""device_push_tokens — mobil push bildirim cihaz token'ları (Expo)

Mobil uygulama (öğrenci/veli/koç/kurum yöneticisi) açılış + login sonrası
Expo push token'ını kaydeder. Backend, e-posta/bildirim üretildiğinde aynı
kullanıcının cihaz(lar)ına push gönderir (e-posta → uygulama bildirimi).

Additive — yalnız yeni tablo; mevcut veriyi ETKİLEMEZ. Downgrade'li.

Revision ID: c6d9g2h3g00x
Revises: b5c8f1g2f99w
Create Date: 2026-06-05
"""
from alembic import op
import sqlalchemy as sa

revision = "c6d9g2h3g00x"
down_revision = "b5c8f1g2f99w"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_push_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # Expo push token (ExponentPushToken[...]) — benzersiz.
        sa.Column("token", sa.String(length=255), nullable=False, unique=True),
        # "ios" | "android" | "web"
        sa.Column("platform", sa.String(length=16), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_device_push_tokens_token", "device_push_tokens", ["token"], unique=True)
    op.create_index("ix_device_push_tokens_user_id", "device_push_tokens", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_device_push_tokens_user_id", table_name="device_push_tokens")
    op.drop_index("ix_device_push_tokens_token", table_name="device_push_tokens")
    op.drop_table("device_push_tokens")
