"""solo subscription state: bağımsız koç abonelik durumu (status/period_end/cycle)

Revision ID: z7a9d2e3d11x
Revises: y6z8c1d2c00w
Create Date: 2026-05-23 10:00:00.000000

Additive — yalnız users'a 3 nullable kolon ekler; mevcut veriyi ETKİLEMEZ.
Downgrade'li. Solo koç aboneliği: status (active/past_due/canceled) + dönem sonu
(yenileme tarihi) + döngü (monthly/academic_year). Kurum aboneliği zaten
Institution modelinde; bu solo koç (institution_id NULL) içindir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "z7a9d2e3d11x"
down_revision: Union[str, None] = "y6z8c1d2c00w"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("subscription_status", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("subscription_period_end", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("subscription_cycle", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "subscription_cycle")
    op.drop_column("users", "subscription_period_end")
    op.drop_column("users", "subscription_status")
