"""tasks.carried_at — devret (carryover) izi

Bir görev devret listesinden yeni haftaya taşınınca işaretlenir → listeden
dinamik düşer + geçmiş program gezilirken "sonraki haftaya eklenmiş" sayılır.
NULL = henüz taşınmadı. Tüm görev tipleri (test/blok/itemless/deneme) görev
düzeyinde işaretlenir. Additive, downgrade'li.

Revision ID: m6n9q2r3q55l
Revises: l5m8p1q2p44k
Create Date: 2026-06-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m6n9q2r3q55l"
down_revision: Union[str, None] = "l5m8p1q2p44k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("carried_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tasks", "carried_at")
