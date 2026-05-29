"""payment_transactions — Iyzico ödeme akışı (Ödeme Paket Ö1)

Revision ID: p3q6u9v0u88o
Revises: o2p5t7u8t77n
Create Date: 2026-05-28

Self-serve ödeme akışı için ödeme deneme/sonuç kayıtları. Provider-agnostic —
iyzico/shopier/manual hepsi aynı tabloda. Idempotency için provider_reference
unique değil (aynı conversation_id'ye birden çok callback gelebilir, son satır
güncellenir).

Akış:
  pending → 3ds_pending → succeeded/failed/expired (callback'te belirlenir)
                       → refunded (sonra, admin elle)

raw_request/raw_response JSON olarak saklanır (sandbox debug + uyuşmazlık takibi).
"""
from alembic import op
import sqlalchemy as sa


revision = "p3q6u9v0u88o"
down_revision = "o2p5t7u8t77n"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_reference", sa.String(200), nullable=True, index=True),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="TRY"),
        sa.Column("plan_code", sa.String(50), nullable=False),
        sa.Column("cycle", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending", index=True),
        sa.Column("status_reason", sa.String(500), nullable=True),
        sa.Column("raw_request", sa.JSON(), nullable=True),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("payment_transactions")
