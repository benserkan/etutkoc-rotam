"""warning_states: uyarı akışı tazelik + gördüm/ertele durumu

Revision ID: e2f5i7j8i66c
Revises: d1e4h6i7h55b
Create Date: 2026-05-23 18:00:00.000000

Additive — yalnız 1 yeni tablo ekler; mevcut veriyi ETKİLEMEZ. Downgrade'li.
Uyarı akışı canlı hesaplanır; bu tablo first_seen (kaç gündür sürüyor) +
snooze_until (gördüm/ertele) tutar. Anahtar (actor_id, student_id, code).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f5i7j8i66c"
down_revision: Union[str, None] = "d1e4h6i7h55b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "warning_states",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("snooze_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_warning_states_actor_id_users"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_warning_states_student_id_users"),
        sa.UniqueConstraint("actor_id", "student_id", "code", name="uq_warning_state_actor_student_code"),
    )
    op.create_index("ix_warning_states_actor_id", "warning_states", ["actor_id"], unique=False)
    op.create_index("ix_warning_states_student_id", "warning_states", ["student_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_warning_states_student_id", table_name="warning_states")
    op.drop_index("ix_warning_states_actor_id", table_name="warning_states")
    op.drop_table("warning_states")
