"""task.solved_count — itemless (etkinlik/diğer) görevde öğrencinin çözdüğü soru

Diğer/Video/Özet/Tekrar görevlerinde kitap kalemi yok → öğrenci çözdüğü soruyu
giremiyordu. solved_count (nullable) eklenir; itemless görevde çözülen soru
buraya yazılır ve "çözülen test" hacmine sayılır (görev kategorisi etkinlik kalır).

Additive — yalnız yeni nullable kolon; mevcut veriyi ETKİLEMEZ. Downgrade'li.

Revision ID: y2z5e8f9e33y
Revises: x1y4d7e8d22x
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "y2z5e8f9e33y"
down_revision = "x1y4d7e8d22x"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("solved_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "solved_count")
