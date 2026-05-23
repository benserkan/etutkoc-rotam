"""support_requests + support_request_messages: rol-bazlı talep sistemi

Revision ID: b9c2f4g5f33z
Revises: a8b1e3f4e22y
Create Date: 2026-05-23 12:00:00.000000

Additive — yalnız 2 yeni tablo ekler; mevcut tabloları/veriyi ETKİLEMEZ.
Downgrade'li. Roller arası talep akışı (koç/kurum yöneticisi → süper admin,
kuruma bağlı öğretmen → kurum yöneticisi). TaskRequest (programa özel) ve
ContactRequest (public form) DOKUNULMAZ.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b9c2f4g5f33z"
down_revision: Union[str, None] = "a8b1e3f4e22y"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "support_requests",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("requester_id", sa.Integer(), nullable=False),
        sa.Column("requester_role", sa.String(length=20), nullable=False),
        sa.Column("audience", sa.String(length=20), nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False, server_default="other"),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("handled_by_id", sa.Integer(), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["requester_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_support_requests_requester_id_users"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="SET NULL",
                                name="fk_support_requests_institution_id_institutions"),
        sa.ForeignKeyConstraint(["handled_by_id"], ["users.id"], ondelete="SET NULL",
                                name="fk_support_requests_handled_by_id_users"),
    )
    op.create_index("ix_support_requests_created_at", "support_requests", ["created_at"], unique=False)
    op.create_index("ix_support_requests_last_activity_at", "support_requests", ["last_activity_at"], unique=False)
    op.create_index("ix_support_requests_requester_id", "support_requests", ["requester_id"], unique=False)
    op.create_index("ix_support_requests_audience", "support_requests", ["audience"], unique=False)
    op.create_index("ix_support_requests_institution_id", "support_requests", ["institution_id"], unique=False)
    op.create_index("ix_support_requests_status", "support_requests", ["status"], unique=False)

    op.create_table(
        "support_request_messages",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["support_requests.id"], ondelete="CASCADE",
                                name="fk_support_request_messages_request_id"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL",
                                name="fk_support_request_messages_sender_id_users"),
    )
    op.create_index("ix_support_request_messages_request_id", "support_request_messages", ["request_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_support_request_messages_request_id", table_name="support_request_messages")
    op.drop_table("support_request_messages")
    op.drop_index("ix_support_requests_status", table_name="support_requests")
    op.drop_index("ix_support_requests_institution_id", table_name="support_requests")
    op.drop_index("ix_support_requests_audience", table_name="support_requests")
    op.drop_index("ix_support_requests_requester_id", table_name="support_requests")
    op.drop_index("ix_support_requests_last_activity_at", table_name="support_requests")
    op.drop_index("ix_support_requests_created_at", table_name="support_requests")
    op.drop_table("support_requests")
