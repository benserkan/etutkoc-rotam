"""feature_cards.mockup_type — anasayfa sağ-yan görsel şablon referansı

Revision ID: q5m2p4n5o33i
Revises: p4l1o3m4n22h
Create Date: 2026-05-14 19:00:00.000000

Anasayfa kartının sağ tarafındaki görsel mockup'ı (rounded-xl alan) seçmek
için. `app/services/mockup_registry.py` içinde tanımlı 5 hazır şablondan
biri seçilir; boşsa görsel render edilmez (geniş tek-kolon kart).

Mevcut 5 şablon (slug eşleşmesi):
- daily_schedule  ↔  daily-plan
- fsrs_rating     ↔  aralikli-tekrar
- burnout_gauge   ↔  dna-risk
- books_progress  ↔  soru-bankasi
- whatsapp_chat   ↔  veli-kanali
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q5m2p4n5o33i"
down_revision: Union[str, None] = "p4l1o3m4n22h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("feature_cards") as batch:
        batch.add_column(
            sa.Column("mockup_type", sa.String(length=40), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table("feature_cards") as batch:
        batch.drop_column("mockup_type")
