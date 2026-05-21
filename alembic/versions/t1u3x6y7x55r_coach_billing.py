"""coach_student_rates + coach_payments: bağımsız koç tahsilatı (KS2)

Revision ID: t1u3x6y7x55r
Revises: s0t2w5x6w44q
Create Date: 2026-05-21 12:00:00.000000

Additive — yalnız 2 yeni tablo. Mevcut veriyi ETKİLEMEZ. Koç↔öğrenci tahsilatı
(platform↔koç Invoice'tan ayrı). Aylık hesap hesaplanır; tabloda tutulmaz.
Downgrade'li.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t1u3x6y7x55r"
down_revision: Union[str, None] = "s0t2w5x6w44q"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coach_student_rates",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("coach_id", sa.Integer(), nullable=True),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("session_fee", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["coach_id"], ["users.id"], ondelete="SET NULL",
                                name="fk_coach_student_rates_coach_id_users"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_coach_student_rates_student_id_users"),
        sa.UniqueConstraint("student_id", name="uq_coach_student_rate_student"),
    )
    op.create_index("ix_coach_student_rates_student_id", "coach_student_rates", ["student_id"], unique=False)

    op.create_table(
        "coach_payments",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("coach_id", sa.Integer(), nullable=True),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("paid_at", sa.Date(), nullable=False),
        sa.Column("method", sa.Enum("CASH", "TRANSFER", "OTHER", name="coachpaymentmethod"),
                  nullable=False, server_default="CASH"),
        sa.Column("period_month", sa.String(length=7), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["coach_id"], ["users.id"], ondelete="SET NULL",
                                name="fk_coach_payments_coach_id_users"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_coach_payments_student_id_users"),
    )
    op.create_index("ix_coach_payments_coach_id", "coach_payments", ["coach_id"], unique=False)
    op.create_index("ix_coach_payments_student_id", "coach_payments", ["student_id"], unique=False)
    op.create_index("ix_coach_payment_student_period", "coach_payments", ["student_id", "period_month"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_coach_payment_student_period", table_name="coach_payments")
    op.drop_index("ix_coach_payments_student_id", table_name="coach_payments")
    op.drop_index("ix_coach_payments_coach_id", table_name="coach_payments")
    op.drop_table("coach_payments")
    op.drop_index("ix_coach_student_rates_student_id", table_name="coach_student_rates")
    op.drop_table("coach_student_rates")
