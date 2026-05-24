"""institutions.logo — kurum logosu (DB'de saklanan, co-branding)

Revision ID: i6j9m1n2m00g
Revises: h5i8l0m1l99f
Create Date: 2026-05-24 16:00:00.000000

Additive — yeni nullable kolonlar. Mevcut veriyi ETKİLEMEZ. Downgrade'li.
Logo DB'de saklanır (support-attachment deseni; S3/volume gerekmez, dev SQLite +
prod Postgres taşınabilir). Kurum yöneticisi + bağlı öğretmen panellerinde
co-branding (platform + kurum logosu) için kullanılır. Süper admin yükler.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i6j9m1n2m00g"
down_revision: Union[str, None] = "h5i8l0m1l99f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("institutions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("logo_data", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("logo_content_type", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("logo_updated_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("institutions", schema=None) as batch_op:
        batch_op.drop_column("logo_updated_at")
        batch_op.drop_column("logo_content_type")
        batch_op.drop_column("logo_data")
