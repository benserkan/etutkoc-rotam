"""membership_offers — WhatsApp üyelik teklifi (yeni üyelik + yenileme)

Süper admin bir üyelik teklifi oluşturur (hedef koç/kurum + plan + döngü +
opsiyonel özel fiyat + mesaj) → benzersiz token + public link üretilir →
WhatsApp ile gönderilir → kullanıcı markalı sayfada "Üye ol/Yenile" talebi
bırakır veya havale/EFT ile öder → süper admin manuel aktive eder.

Additive — yalnız yeni tablo; mevcut veriyi ETKİLEMEZ. Downgrade'li.

Revision ID: b5c8f1g2f99w
Revises: a4b7g0h1g55a
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = "b5c8f1g2f99w"
down_revision = "a4b7g0h1g55a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "membership_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_by_admin_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # Hedef koç/kurum kullanıcısı (kişiselleştirme); NULL = genel link.
        sa.Column("target_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # "new" (yeni üyelik) | "renewal" (yenileme)
        sa.Column("offer_type", sa.String(length=16), nullable=False, server_default="new"),
        sa.Column("plan_code", sa.String(length=40), nullable=False),
        # "monthly" | "annual"
        sa.Column("cycle", sa.String(length=16), nullable=False, server_default="monthly"),
        # Özel fiyat (kuruş değil TL, tam sayı); NULL = plan varsayılanı / "size özel".
        sa.Column("amount", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        # active | accepted | cancelled | expired
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        # NULL | requested (talep) | havale_claimed (ödedim dedi) | activated
        sa.Column("completion", sa.String(length=20), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("contact_request_id", sa.Integer(),
                  sa.ForeignKey("contact_requests.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_membership_offers_token", "membership_offers", ["token"], unique=True)
    op.create_index("ix_membership_offers_target_user_id", "membership_offers", ["target_user_id"])


def downgrade() -> None:
    op.drop_index("ix_membership_offers_target_user_id", table_name="membership_offers")
    op.drop_index("ix_membership_offers_token", table_name="membership_offers")
    op.drop_table("membership_offers")
