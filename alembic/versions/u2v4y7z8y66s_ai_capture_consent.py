"""users.ai_capture_consent_at: bağımsız koç AI yakalama rızası (KS3a)

Revision ID: u2v4y7z8y66s
Revises: t1u3x6y7x55r
Create Date: 2026-05-21 14:00:00.000000

Additive — yalnız 1 nullable kolon. Mevcut veriyi ETKİLEMEZ (NULL = rıza yok).
AI yakalama (foto/ses→metin) öncesi koç açık rıza verince doldurulur.
Downgrade'li. (UsageKind.AI_SESSION_CAPTURE için migration GEREKMEZ —
usage_events.kind VARCHAR, CHECK constraint yok.)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u2v4y7z8y66s"
down_revision: Union[str, None] = "t1u3x6y7x55r"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("ai_capture_consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "ai_capture_consent_at")
