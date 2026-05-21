"""crm_action_templates: önceden yazılı aksiyon taslakları (Faz B4)

Revision ID: m4n6q9r0q88k
Revises: l3m5p8q9p77j
Create Date: 2026-05-18 11:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m4n6q9r0q88k"
down_revision: Union[str, None] = "l3m5p8q9p77j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crm_action_templates",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "call", "email", "whatsapp", "meeting",
                "offer_sent", "onboarding", "other",
                name="crmactionkind",
                create_type=False,  # enum zaten crm tablolarından mevcut
            ),
            nullable=False,
        ),
        sa.Column("subject", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False,
                  server_default=sa.text("1")),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL",
            name="fk_crm_action_templates_created_by_users",
        ),
    )
    op.create_index(
        "ix_crm_action_templates_kind", "crm_action_templates",
        ["kind"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_crm_action_templates_kind",
                   table_name="crm_action_templates")
    op.drop_table("crm_action_templates")
