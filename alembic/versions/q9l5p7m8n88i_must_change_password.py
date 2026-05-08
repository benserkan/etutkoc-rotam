"""users.must_change_password — ilk girişte şifre değiştirme zorunluluğu

Revision ID: q9l5p7m8n88i
Revises: p8k4o6l7m77h
Create Date: 2026-05-09 14:00:00.000000

Sprint 4 sonrası iyileştirme — şifre yönetimi profesyonelleştirme.

Akış:
- Admin kullanıcı oluşturduğunda must_change_password=True
- Şifre admin tarafından sıfırlandığında must_change_password=True
- İlk girişte /password/change'a zorunlu yönlendirme
- Kullanıcı şifre değiştirince flag False olur

Default False — mevcut kullanıcılar etkilenmez.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q9l5p7m8n88i"
down_revision: Union[str, None] = "p8k4o6l7m77h"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "must_change_password", sa.Boolean(),
            nullable=False, server_default=sa.text("0"),
        ))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("must_change_password")
