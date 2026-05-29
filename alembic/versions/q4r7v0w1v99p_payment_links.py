"""payment_links — süper admin tarafından oluşturulan ödeme linkleri (Paket Ö2a)

Revision ID: q4r7v0w1v99p
Revises: p3q6u9v0u88o
Create Date: 2026-05-28

Kurum ödemesi self-serve değil — fiyat 'özel teklif' olabilir (Enterprise).
Süper admin "şu kuruma şu tutarda bu paketi" link oluşturur → kurum yöneticisi
link üzerinden öder → Iyzico → callback → plan aktive.

Owner-agnostic: target_owner_type='institution'|'user' (bağımsız koç için de
ileride kullanılabilir — özel indirim, manuel teklif vs.).

Tek kullanım (status=consumed) + opsiyonel süre (expires_at).
"""
from alembic import op
import sqlalchemy as sa


revision = "q4r7v0w1v99p"
down_revision = "p3q6u9v0u88o"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True, index=True),
        sa.Column("target_owner_type", sa.String(20), nullable=False),  # institution | user
        sa.Column("target_owner_id", sa.Integer(), nullable=False, index=True),
        sa.Column("plan_code", sa.String(50), nullable=False),
        sa.Column("cycle", sa.String(20), nullable=False),  # monthly | annual
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="TRY"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active", index=True),
        # active | consumed | expired | cancelled
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "consumed_by_user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "consumed_transaction_id", sa.Integer(),
            sa.ForeignKey("payment_transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by_admin_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Composite index: bir kurumun aktif linklerini hızlı bul
    op.create_index(
        "ix_payment_links_target_status",
        "payment_links",
        ["target_owner_type", "target_owner_id", "status"],
    )

    # PaymentTransaction'a payment_link_id ekle (hangi link tüketildi)
    op.add_column(
        "payment_transactions",
        sa.Column(
            "payment_link_id", sa.Integer(),
            sa.ForeignKey("payment_links.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("payment_transactions", "payment_link_id")
    op.drop_index("ix_payment_links_target_status", table_name="payment_links")
    op.drop_table("payment_links")
