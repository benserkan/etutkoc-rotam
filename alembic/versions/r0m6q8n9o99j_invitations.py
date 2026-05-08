"""invitations tablosu — kurumsal davetiye akışı

Revision ID: r0m6q8n9o99j
Revises: q9l5p7m8n88i
Create Date: 2026-05-09 16:00:00.000000

Sprint 5 — multi-tenant signup. Bir kurum yöneticisi (veya süper admin) bir
öğretmen için davetiye linki üretir. Token tek seferlik, default 7 gün
geçerli.

Status (computed):
- PENDING: consumed_at NULL, revoked_at NULL, expires_at > now
- CONSUMED: consumed_at dolu (kullanıldı)
- EXPIRED: süresi geçti
- REVOKED: admin tarafından iptal edildi
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r0m6q8n9o99j"
down_revision: Union[str, None] = "q9l5p7m8n88i"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invitations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "TEACHER", "STUDENT", "PARENT",
                "INSTITUTION_ADMIN", "SUPER_ADMIN",
                name="userrole",
            ),
            nullable=False,
        ),
        sa.Column("institution_id", sa.Integer(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("token", name="uq_invitation_token"),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["consumed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revoked_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_invitations_token", "invitations", ["token"])
    op.create_index("ix_invitations_institution_id", "invitations", ["institution_id"])


def downgrade() -> None:
    op.drop_index("ix_invitations_institution_id", table_name="invitations")
    op.drop_index("ix_invitations_token", table_name="invitations")
    op.drop_table("invitations")
