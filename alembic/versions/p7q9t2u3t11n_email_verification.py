"""email doğrulama: users.email_verified_at + email_verification_tokens (Dalga 7 P3)

Revision ID: p7q9t2u3t11n
Revises: o6p8s1t2s00m
Create Date: 2026-05-20 13:00:00.000000

Additive:
  - users tablosuna nullable email_verified_at kolonu (mevcut veriyi etkilemez)
  - DATA: mevcut TÜM kullanıcılar geriye dönük doğrulanmış işaretlenir
    (kimse soft-banner ile rahatsız olmasın; yalnız yeni kayıtlar doğrulama bekler)
  - yeni email_verification_tokens tablosu
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p7q9t2u3t11n"
down_revision: Union[str, None] = "o6p8s1t2s00m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Mevcut kullanıcıları geriye dönük doğrulanmış işaretle
    op.execute("UPDATE users SET email_verified_at = CURRENT_TIMESTAMP WHERE email_verified_at IS NULL")

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_email_verification_tokens_user_id_users",
        ),
        sa.UniqueConstraint("token", name="uq_email_verification_token"),
    )
    op.create_index(
        "ix_email_verification_tokens_token", "email_verification_tokens",
        ["token"], unique=False,
    )
    op.create_index(
        "ix_email_verification_tokens_user_id", "email_verification_tokens",
        ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_token", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified_at")
