"""active_sessions.imp_by — impersonation oturum işareti (abuse false-positive fix)

Revision ID: d7e0h3i4h11y
Revises: c6d9g2h3g00x
Create Date: 2026-06-06

Süper admin impersonate edince hedef için ActiveSession senin tarayıcı IP+UA'ndan
açılıyor → multi_account_same_device dedektörü bunları "çoklu hesap abuse" sanıp
sürekli yanlış-pozitif sinyal üretiyordu. `imp_by` (impersonator admin id) ile
impersonation oturumları işaretlenir; dedektör bunları + süper admin'i sayımdan
dışlar. Additive, nullable — mevcut satırlar etkilenmez.
"""
from alembic import op
import sqlalchemy as sa

revision = "d7e0h3i4h11y"
down_revision = "c6d9g2h3g00x"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "active_sessions",
        sa.Column("imp_by", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("active_sessions", "imp_by")
