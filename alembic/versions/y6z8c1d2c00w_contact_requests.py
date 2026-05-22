"""contact_requests: kurumsal/genel iletişim talepleri

Revision ID: y6z8c1d2c00w
Revises: x5y7b0c1b99v
Create Date: 2026-05-22 12:00:00.000000

Additive — yalnız yeni tablo ekler; mevcut tabloları/veriyi ETKİLEMEZ. Downgrade'li.
Kurumlar için fiyat gösterilmez; /pricing kurumsal bölümünden form doldurulur,
talep e-posta ile satışa gider + süper admin panelde listelenir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "y6z8c1d2c00w"
down_revision: Union[str, None] = "x5y7b0c1b99v"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("coach_count", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="pricing_institution"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="new"),
        sa.Column("handled_by_id", sa.Integer(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["handled_by_id"], ["users.id"], ondelete="SET NULL",
            name="fk_contact_requests_handled_by_id_users",
        ),
    )
    op.create_index(
        "ix_contact_requests_created_at", "contact_requests", ["created_at"], unique=False,
    )
    op.create_index(
        "ix_contact_requests_status", "contact_requests", ["status"], unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_contact_requests_status", table_name="contact_requests")
    op.drop_index("ix_contact_requests_created_at", table_name="contact_requests")
    op.drop_table("contact_requests")
