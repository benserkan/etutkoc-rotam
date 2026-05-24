"""support_requests.target_user_id: yönetici → koç (aşağı yönlü) talep hedefi

Revision ID: h5i8l0m1l99f
Revises: g4h7k9l0k88e
Create Date: 2026-05-24 14:00:00.000000

Additive — yeni nullable kolon. Mevcut veriyi ETKİLEMEZ. Downgrade'li.
Kurum yöneticisinin riskli öğrenci için ilgili koça açtığı talepte (audience=
"teacher") muhatap koç bu kolonla belirlenir. Yukarı-yönlü taleplerde NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h5i8l0m1l99f"
down_revision: Union[str, None] = "g4h7k9l0k88e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("support_requests", schema=None) as batch_op:
        batch_op.add_column(sa.Column("target_user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_support_requests_target_user_id", ["target_user_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_support_requests_target_user_id_users", "users",
            ["target_user_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    op.execute("DELETE FROM support_requests WHERE audience = 'teacher'")
    with op.batch_alter_table("support_requests", schema=None) as batch_op:
        batch_op.drop_constraint("fk_support_requests_target_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_support_requests_target_user_id")
        batch_op.drop_column("target_user_id")
