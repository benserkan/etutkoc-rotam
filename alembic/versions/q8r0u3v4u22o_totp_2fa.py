"""2FA/TOTP: users.totp_secret + totp_enabled_at + totp_backup_codes (Dalga 7 P4)

Revision ID: q8r0u3v4u22o
Revises: p7q9t2u3t11n
Create Date: 2026-05-20 14:00:00.000000

Additive — yalnız 2 nullable kolon + yeni tablo; mevcut veriyi ETKİLEMEZ
(totp_secret NULL = 2FA kapalı). Yalnız Süper Admin + Kurum Yöneticisi
etkinleştirebilir (uygulama katmanında kısıt). Downgrade'li.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q8r0u3v4u22o"
down_revision: Union[str, None] = "p7q9t2u3t11n"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("totp_secret", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "totp_backup_codes",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_totp_backup_codes_user_id_users",
        ),
    )
    op.create_index(
        "ix_totp_backup_codes_user_id", "totp_backup_codes", ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_totp_backup_codes_user_id", table_name="totp_backup_codes")
    op.drop_table("totp_backup_codes")
    op.drop_column("users", "totp_enabled_at")
    op.drop_column("users", "totp_secret")
