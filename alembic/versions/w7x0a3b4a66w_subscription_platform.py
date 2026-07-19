"""users.subscription_platform — aboneliğin satın alındığı kanal

Apple App Store IAP entegrasyonu (3.1.1 çözümü): solo koç aboneliği artık
3 kanaldan aktive olabilir — iyzico (web kart), app_store (RevenueCat/IAP),
manual (süper admin). Yenileme cron'u ve UI "aboneliği nereden yönet"
kararını bu alandan verir (app_store → dönem sonu Apple/RevenueCat'ten
senkronlanır, past_due üretilmez).

Additive — yalnız yeni nullable kolon; mevcut veriyi ETKİLEMEZ. Downgrade'li.

Revision ID: w7x0a3b4a66w
Revises: v6w9z2a3z55v
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa

revision = "w7x0a3b4a66w"
down_revision = "v6w9z2a3z55v"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("subscription_platform", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "subscription_platform")
