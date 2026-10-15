"""Havuz dönemi — veliye gönderilen seans özeti izi (K53, 2026-10-12, Adım 5).

Seans kapanışında özet otomatik HAZIRLANIR, rehber önizler/düzenler, isterse
gönderir; otomatik gitmez. Gönderilen hâl dönemde saklanır (yeniden açma + PDF
aynı içerik — deneme duyurusu deseni). Additive, downgrade'li.

Revision ID: n8p1u4v5u99q
Revises: n7o0t3u4t88p
Create Date: 2026-10-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n8p1u4v5u99q"
down_revision: Union[str, None] = "n7o0t3u4t88p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("study_periods", schema=None) as batch_op:
        batch_op.add_column(sa.Column("parent_summary_sent_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("parent_summary_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("study_periods", schema=None) as batch_op:
        batch_op.drop_column("parent_summary_json")
        batch_op.drop_column("parent_summary_sent_at")
