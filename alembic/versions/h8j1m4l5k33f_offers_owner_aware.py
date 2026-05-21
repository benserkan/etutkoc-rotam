"""offers: owner-aware (Institution + bağımsız öğretmen User)

Revision ID: h8j1m4l5k33f
Revises: g7i0l3k4j22e
Create Date: 2026-05-17 20:00:00.000000

CRM/Invoice/HealthScoreSnapshot ile aynı owner pattern: `owner_type` +
nullable XOR FK'ler. Mevcut tüm teklifler institution'a aitti —
server_default='institution' alır.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h8j1m4l5k33f"
down_revision: Union[str, None] = "g7i0l3k4j22e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("offers") as batch:
        batch.add_column(
            sa.Column("owner_type", sa.String(length=20), nullable=False,
                      server_default=sa.text("'institution'")),
        )
        batch.add_column(
            sa.Column("user_id", sa.Integer(), nullable=True),
        )
    with op.batch_alter_table("offers") as batch:
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=True)
        batch.create_foreign_key(
            "fk_offers_user_id_users",
            "users", ["user_id"], ["id"], ondelete="CASCADE",
        )
        batch.create_check_constraint(
            "ck_offers_owner_xor",
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
        )
    op.create_index(
        "ix_offers_user_status", "offers",
        ["user_id", "status"], unique=False,
    )
    op.create_index(
        "ix_offers_user_id", "offers", ["user_id"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_offers_user_id", table_name="offers")
    op.drop_index("ix_offers_user_status", table_name="offers")
    with op.batch_alter_table("offers") as batch:
        batch.drop_constraint("ck_offers_owner_xor", type_="check")
        batch.drop_constraint("fk_offers_user_id_users", type_="foreignkey")
        batch.alter_column("institution_id", existing_type=sa.Integer(),
                           nullable=False)
        batch.drop_column("user_id")
        batch.drop_column("owner_type")
