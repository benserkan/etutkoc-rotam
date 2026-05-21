"""feature_experiments — A/B test çerçevesi (Katman 9)

Revision ID: t8p5s7r8q66l
Revises: s7o4r6p7q55k
Create Date: 2026-05-15 13:00:00.000000

Anasayfa sıralama stratejileri arasında istatistiksel karşılaştırma yapan
A/B test motoru. Tek seferde bir aktif deney; ziyaretçiler deterministik
hash ile variant'lara dağıtılır.

İki değişiklik:
  1) feature_experiments tablosu (deney config + status)
  2) feature_card_events.variant_slug kolonu (her event hangi variant'tan
     geldi — istatistik agregasyonu için)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "t8p5s7r8q66l"
down_revision: Union[str, None] = "s7o4r6p7q55k"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_experiments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False,
                  server_default="draft"),
        # variants_json: list of {slug, label, strategy, weight, is_control}
        sa.Column("variants_json", sa.Text(), nullable=False),
        sa.Column("hypothesis", sa.Text(), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_feature_experiments_status",
        "feature_experiments",
        ["status"],
    )

    # feature_card_events.variant_slug
    with op.batch_alter_table("feature_card_events") as batch:
        batch.add_column(
            sa.Column("variant_slug", sa.String(length=40), nullable=True),
        )
    op.create_index(
        "ix_feature_card_events_variant_event",
        "feature_card_events",
        ["variant_slug", "event_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_feature_card_events_variant_event",
        table_name="feature_card_events",
    )
    with op.batch_alter_table("feature_card_events") as batch:
        batch.drop_column("variant_slug")
    op.drop_index("ix_feature_experiments_status", table_name="feature_experiments")
    op.drop_table("feature_experiments")
