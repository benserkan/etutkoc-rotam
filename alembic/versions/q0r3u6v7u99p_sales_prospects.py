"""sales_prospects (Hedef Havuzu) + membership_offers.target_prospect_id

Sisteme üye olmayan potansiyel kurum/koç (satış adayı) kayıtları. Üyelik teklifi
bir prospect'i hedef alabilsin diye membership_offers'a target_prospect_id eklenir.
Additive, downgrade'li.

Revision ID: q0r3u6v7u99p
Revises: p9q2t5u6t88o
Create Date: 2026-06-21
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "q0r3u6v7u99p"
down_revision: Union[str, None] = "p9q2t5u6t88o"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_prospects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="coach"),
        sa.Column("org_name", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=True),
        sa.Column("city", sa.String(length=80), nullable=True),
        sa.Column("source", sa.String(length=24), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=True),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_admin_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_prospect_phone", "sales_prospects", ["phone"])
    op.create_index("ix_prospect_status", "sales_prospects", ["status"])
    op.create_index("ix_prospect_kind", "sales_prospects", ["kind"])

    with op.batch_alter_table("membership_offers") as batch:
        batch.add_column(sa.Column("target_prospect_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_membership_offer_prospect", "sales_prospects",
            ["target_prospect_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("membership_offers") as batch:
        batch.drop_constraint("fk_membership_offer_prospect", type_="foreignkey")
        batch.drop_column("target_prospect_id")
    op.drop_index("ix_prospect_kind", table_name="sales_prospects")
    op.drop_index("ix_prospect_status", table_name="sales_prospects")
    op.drop_index("ix_prospect_phone", table_name="sales_prospects")
    op.drop_table("sales_prospects")
