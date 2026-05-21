"""owner_contacts: genişletilmiş iletişim metadata (yetkili kişi/cep/LinkedIn vb.)

Revision ID: l3m5p8q9p77j
Revises: k2l4o7n8o66i
Create Date: 2026-05-18 10:30:00.000000

Owner başına 1 satır. XOR institution_id/user_id. UI'da collapsible form.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l3m5p8q9p77j"
down_revision: Union[str, None] = "k2l4o7n8o66i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "owner_contacts",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("owner_type", sa.String(length=20), nullable=False,
                  server_default=sa.text("'institution'")),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("responsible_person_name", sa.String(length=255), nullable=True),
        sa.Column("responsible_person_title", sa.String(length=120), nullable=True),
        sa.Column("billing_email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("whatsapp", sa.String(length=50), nullable=True),
        sa.Column("linkedin_url", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=255), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE",
            name="fk_owner_contacts_institution_id_institutions",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE",
            name="fk_owner_contacts_user_id_users",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"], ondelete="SET NULL",
            name="fk_owner_contacts_updated_by_users",
        ),
        sa.UniqueConstraint("institution_id", name="uq_owner_contact_institution"),
        sa.UniqueConstraint("user_id", name="uq_owner_contact_user"),
        sa.CheckConstraint(
            "(owner_type = 'institution' AND institution_id IS NOT NULL AND user_id IS NULL) "
            "OR (owner_type = 'user' AND user_id IS NOT NULL AND institution_id IS NULL)",
            name="ck_owner_contacts_owner_xor",
        ),
    )
    op.create_index("ix_owner_contacts_institution", "owner_contacts",
                     ["institution_id"], unique=False)
    op.create_index("ix_owner_contacts_user", "owner_contacts",
                     ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_owner_contacts_user", table_name="owner_contacts")
    op.drop_index("ix_owner_contacts_institution", table_name="owner_contacts")
    op.drop_table("owner_contacts")
