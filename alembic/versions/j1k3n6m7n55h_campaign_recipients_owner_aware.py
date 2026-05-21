"""campaign_recipients: owner-aware (Institution + bağımsız öğretmen User)

Revision ID: j1k3n6m7n55h
Revises: h8j1m4l5k33f
Create Date: 2026-05-18 09:30:00.000000

Mevcut tüm recipient'lar kuruma aitti → server_default='institution'.
institution_id nullable yapılır, user_id eklenir, XOR check + index'ler.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j1k3n6m7n55h"
down_revision: Union[str, None] = "h8j1m4l5k33f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("campaign_recipients") as batch:
        batch.add_column(
            sa.Column("owner_type", sa.String(length=20), nullable=False,
                      server_default=sa.text("'institution'")),
        )
        batch.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True),
        )
    with op.batch_alter_table("campaign_recipients") as batch:
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=True)
        batch.create_foreign_key(
            "fk_campaign_recipients_user_id_users",
            "users", ["user_id"], ["id"], ondelete="CASCADE",
        )
        batch.create_check_constraint(
            "ck_campaign_recipients_owner_xor",
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
        )
    op.create_index(
        "ix_campaign_recipients_user", "campaign_recipients",
        ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_campaign_recipients_user", table_name="campaign_recipients")
    with op.batch_alter_table("campaign_recipients") as batch:
        batch.drop_constraint("ck_campaign_recipients_owner_xor", type_="check")
        batch.drop_constraint("fk_campaign_recipients_user_id_users",
                               type_="foreignkey")
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=False)
        batch.drop_column("user_id")
        batch.drop_column("owner_type")
