"""tasks.block_detached — bloğu silinmiş görev (DENEME değil, Diğer)

Serbest Blok görevleri kitapsız (book_id=None) kalem olarak saklanır; "blok"
olduklarını yalnız work_block_id belirler. Blok SİLİNİNCE work_block_id NULL'a
düşer → kitapsız kalem yanlışlıkla 'tam_deneme' (DENEME) sınıflanırdı. Bu bayrak
True iken görev DENEME değil 'etkinlik/Diğer' sayılır. Program verisi değişmez;
yalnız blok bağı silinmiş görevler işaretlenir (carry ile taşınanlar dahil).
Additive, downgrade'li.

Revision ID: o8p1s4t5s77n
Revises: n7o0r3s4r66m
Create Date: 2026-06-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "o8p1s4t5s77n"
down_revision: Union[str, None] = "n7o0r3s4r66m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("block_detached", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("tasks", "block_detached")
