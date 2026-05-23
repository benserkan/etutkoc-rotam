"""support_requests: escalated_by_id + escalated_at (yönlendirme izleme)

Revision ID: c0d3g5h6g44a
Revises: b9c2f4g5f33z
Create Date: 2026-05-23 14:00:00.000000

Additive — yalnız 2 nullable kolon ekler; mevcut veriyi ETKİLEMEZ. Downgrade'li.
Kurum yöneticisi bir talebi süper yöneticiye yönlendirince talep ondan KOPMAZ:
escalated_by_id ile yönlendiren kurum yöneticisi talebi görmeye + süper adminin
cevabını izlemeye devam eder (3 taraflı thread).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c0d3g5h6g44a"
down_revision: Union[str, None] = "b9c2f4g5f33z"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("support_requests", sa.Column("escalated_by_id", sa.Integer(), nullable=True))
    op.add_column("support_requests", sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_support_requests_escalated_by_id", "support_requests", ["escalated_by_id"], unique=False
    )
    with op.batch_alter_table("support_requests") as batch:
        batch.create_foreign_key(
            "fk_support_requests_escalated_by_id_users",
            "users", ["escalated_by_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("support_requests") as batch:
        batch.drop_constraint("fk_support_requests_escalated_by_id_users", type_="foreignkey")
    op.drop_index("ix_support_requests_escalated_by_id", table_name="support_requests")
    op.drop_column("support_requests", "escalated_at")
    op.drop_column("support_requests", "escalated_by_id")
