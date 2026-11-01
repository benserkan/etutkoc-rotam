"""study_periods.closing_flags_json — dönem kapanırken üretilen bayrakların anlık görüntüsü

Revision ID: x8z1e4f5e00a
Revises: w7y0d3e4d99z
Create Date: 2026-11-01

Havuz bayrakları yalnız AÇIK dönemden hesaplanıyordu; yeni dönem açılınca önceki dönemin
"N gündür dokunmadı / toplu işaretleme / D/Y yok / kaçınma" sinyalleri iz bırakmadan
kayboluyordu (Taha #84 vakası). Kapanışta JSON olarak saklanır. Additive.
"""
import sqlalchemy as sa
from alembic import op

revision = "x8z1e4f5e00a"
down_revision = "w7y0d3e4d99z"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("study_periods") as b:
        b.add_column(sa.Column("closing_flags_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("study_periods") as b:
        b.drop_column("closing_flags_json")
