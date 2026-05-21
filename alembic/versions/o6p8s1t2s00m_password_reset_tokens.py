"""password_reset_tokens: self-service şifre sıfırlama (Dalga 7 P2)

Revision ID: o6p8s1t2s00m
Revises: n5o7r0s1r99l
Create Date: 2026-05-20 12:00:00.000000

Additive — yalnız yeni tablo ekler; mevcut tabloları/veriyi ETKİLEMEZ.
Tek-kullanımlık, 60 dk ömürlü şifre sıfırlama tokenları.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o6p8s1t2s00m"
down_revision: Union[str, None] = "n5o7r0s1r99l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_password_reset_tokens_user_id_users",
        ),
        sa.UniqueConstraint("token", name="uq_password_reset_token"),
    )
    op.create_index(
        "ix_password_reset_tokens_token", "password_reset_tokens",
        ["token"], unique=False,
    )
    op.create_index(
        "ix_password_reset_tokens_user_id", "password_reset_tokens",
        ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
