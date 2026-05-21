"""owner_tags: kurum/bağımsız öğretmen etiket sistemi (VIP, Pilot, B2B vb.)

Revision ID: k2l4o7n8o66i
Revises: j1k3n6m7n55h
Create Date: 2026-05-18 10:00:00.000000

Tek bir owner çoklu etiket alabilir. XOR check: kurum veya bağımsız öğretmen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k2l4o7n8o66i"
down_revision: Union[str, None] = "j1k3n6m7n55h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "owner_tags",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("owner_type", sa.String(length=20), nullable=False,
                  server_default=sa.text("'institution'")),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "vip", "pilot", "b2b_reference", "strategic",
                "demo", "enterprise", "early_adopter", "at_risk_manual",
                name="ownertagkind",
            ),
            nullable=False,
        ),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE",
            name="fk_owner_tags_institution_id_institutions",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_owner_tags_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL",
            name="fk_owner_tags_created_by_users",
        ),
        sa.UniqueConstraint(
            "institution_id", "kind", name="uq_owner_tag_inst_kind",
        ),
        sa.UniqueConstraint(
            "user_id", "kind", name="uq_owner_tag_user_kind",
        ),
        sa.CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_owner_tags_owner_xor",
        ),
    )
    op.create_index("ix_owner_tags_institution", "owner_tags",
                     ["institution_id"], unique=False)
    op.create_index("ix_owner_tags_user", "owner_tags",
                     ["user_id"], unique=False)
    op.create_index("ix_owner_tags_kind", "owner_tags", ["kind"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_owner_tags_kind", table_name="owner_tags")
    op.drop_index("ix_owner_tags_user", table_name="owner_tags")
    op.drop_index("ix_owner_tags_institution", table_name="owner_tags")
    op.drop_table("owner_tags")
    sa.Enum(name="ownertagkind").drop(op.get_bind(), checkfirst=True)
