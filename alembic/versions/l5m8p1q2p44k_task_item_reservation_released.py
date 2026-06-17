"""task_book_items.reservation_released_at — olu rezerv serbest birakma izi

Haftasi/programi gecmis + tamamlanmamis bir gorevin yapilmamis rezerv kismi
serbest birakildiginda (reconcile_past_reservations) bu kalem isaretlenir →
ayni kalem iki kez serbest birakilmaz (sonradan gorev silinirse cift-iade
onlenir). NULL = henuz serbest birakilmadi (canli rezerv). Additive, downgrade'li.

Revision ID: l5m8p1q2p44k
Revises: k4l7o0p1o88f
Create Date: 2026-06-17
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "l5m8p1q2p44k"
down_revision: Union[str, None] = "k4l7o0p1o88f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_book_items",
        sa.Column("reservation_released_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("task_book_items", "reservation_released_at")
