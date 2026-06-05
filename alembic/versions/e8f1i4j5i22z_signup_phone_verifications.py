"""signup_phone_verifications — hesap-öncesi telefon doğrulama (#5 telefon kapısı)

Revision ID: e8f1i4j5i22z
Revises: d7e0h3i4h11y
Create Date: 2026-06-06

Koç signup'ında SMS telefon doğrulama kapısı için hesap-OLUŞMADAN ÖNCE OTP saklayan
tablo (mevcut phone_verifications user_id'ye bağlı → pre-account için kullanılamaz).
Kapı yalnız SMS_ENABLED=true (SMS OTP paketi satın alınınca) iken devreye girer;
o zamana kadar tablo boş kalır (DORMANT). Additive, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "e8f1i4j5i22z"
down_revision = "d7e0h3i4h11y"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "signup_phone_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(length=20), nullable=False, index=True),
        sa.Column("code", sa.String(length=6), nullable=False),
        sa.Column("channel", sa.String(length=10), nullable=False, server_default="sms"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_signup_phone_verif_phone_created",
        "signup_phone_verifications", ["phone", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_signup_phone_verif_phone_created", table_name="signup_phone_verifications")
    op.drop_table("signup_phone_verifications")
