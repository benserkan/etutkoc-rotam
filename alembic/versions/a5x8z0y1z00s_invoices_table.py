"""Invoice tablosu — ödeme takvimi & dunning için temel kayıt (Sprint A.2).

Revision ID: a5x8z0y1z00s
Revises: z4v1y3x4w22r
Create Date: 2026-05-16 13:00:00.000000

  - Yeni tablo: invoices
  - Indexler: institution_id+status, due_at, status+due_at
  - Enum: InvoiceStatus (pending/paid/overdue/failed/refunded/cancelled),
    PaymentMethod (card/bank_transfer/manual)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a5x8z0y1z00s"
down_revision: Union[str, None] = "z4v1y3x4w22r"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "institution_id", sa.Integer(),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("plan", sa.String(length=32), nullable=False),
        sa.Column("amount_try", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "paid", "overdue", "failed", "refunded", "cancelled",
                name="invoicestatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "payment_method",
            sa.Enum(
                "card", "bank_transfer", "manual",
                name="paymentmethod",
            ),
            nullable=True,
        ),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reminder_kind", sa.String(length=16), nullable=True),
        sa.Column("last_reminder_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )
    op.create_index(
        "ix_invoices_institution_id", "invoices", ["institution_id"],
    )
    op.create_index(
        "ix_invoices_institution_status", "invoices",
        ["institution_id", "status"],
    )
    op.create_index(
        "ix_invoices_due_at", "invoices", ["due_at"],
    )
    op.create_index(
        "ix_invoices_status_due", "invoices", ["status", "due_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_invoices_status_due", table_name="invoices")
    op.drop_index("ix_invoices_due_at", table_name="invoices")
    op.drop_index("ix_invoices_institution_status", table_name="invoices")
    op.drop_index("ix_invoices_institution_id", table_name="invoices")
    op.drop_table("invoices")
    # SQLite Enum cleanup — bind dialect kontrol
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        sa.Enum(name="invoicestatus").drop(bind, checkfirst=True)
        sa.Enum(name="paymentmethod").drop(bind, checkfirst=True)
