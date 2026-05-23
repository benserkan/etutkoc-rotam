"""offers.viewed_at: teklif kullanıcı tarafından açıldı/görüntülendi izleme

Revision ID: a8b1e3f4e22y
Revises: z7a9d2e3d11x
Create Date: 2026-05-23 14:00:00.000000

Additive — offers'a tek nullable kolon; mevcut veriyi ETKİLEMEZ. Downgrade'li.
Kullanıcı public /offers/{token} linkini ilk açtığında doldurulur → admin
"açtı mı / ne zaman açtı" görebilir.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a8b1e3f4e22y"
down_revision: Union[str, None] = "z7a9d2e3d11x"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("offers", "viewed_at")
