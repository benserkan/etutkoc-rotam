"""Video Sepeti → Haftalık Havuz (2026-10-20).

`video_basket_items.pool_item_id`: havuz modundaki öğrencide video grubu gün yerine havuza
kalem (etkinlik) olarak eklenir; öğrenci kaba alınca videolar o güne açılan görevin
(`task_id`) altına bağlanır. Kalem silinince bağ boşalır (SET NULL) → video sepete döner.
Additive, downgrade'li.

Revision ID: t4v7a0b1a66w
Revises: s3u6z9a0z55v
Create Date: 2026-10-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "t4v7a0b1a66w"
down_revision: Union[str, None] = "s3u6z9a0z55v"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("video_basket_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pool_item_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_video_basket_items_pool_item_id", "pool_items",
            ["pool_item_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_video_basket_items_pool_item_id", ["pool_item_id"])


def downgrade() -> None:
    with op.batch_alter_table("video_basket_items", schema=None) as batch_op:
        batch_op.drop_index("ix_video_basket_items_pool_item_id")
        batch_op.drop_constraint("fk_video_basket_items_pool_item_id", type_="foreignkey")
        batch_op.drop_column("pool_item_id")
