"""coaching_sessions: bağımsız koç seans/değerlendirme kaydı (KS1)

Revision ID: s0t2w5x6w44q
Revises: r9s1v4w5v33p
Create Date: 2026-05-21 10:00:00.000000

Additive — yalnız yeni tablo (coaching_sessions). Mevcut veriyi ETKİLEMEZ.
Koç haftalık görüşmeyi düşük efor + yapılandırılmış kaydeder; status DONE
seanslar tahsilatın (KS2) temelidir. Downgrade'li.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s0t2w5x6w44q"
down_revision: Union[str, None] = "r9s1v4w5v33p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "coaching_sessions",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True),
        sa.Column("coach_id", sa.Integer(), nullable=True),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("session_date", sa.Date(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DONE", "POSTPONED", "CANCELLED", "NO_SHOW", name="coachingsessionstatus"),
            nullable=False, server_default="DONE",
        ),
        sa.Column("duration_min", sa.Integer(), nullable=True),
        sa.Column(
            "channel",
            sa.Enum("IN_PERSON", "ONLINE", "PHONE", name="coachingchannel"),
            nullable=True,
        ),
        sa.Column("agenda", sa.Text(), nullable=False, server_default=""),
        sa.Column("next_change", sa.Text(), nullable=True),
        sa.Column("coach_note", sa.Text(), nullable=True),
        sa.Column("mood", sa.Integer(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("auto_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "capture_source",
            sa.Enum("MANUAL", "VOICE", "PHOTO", name="sessioncapturesource"),
            nullable=False, server_default="MANUAL",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["coach_id"], ["users.id"], ondelete="SET NULL",
                                name="fk_coaching_sessions_coach_id_users"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE",
                                name="fk_coaching_sessions_student_id_users"),
    )
    op.create_index("ix_coaching_sessions_coach_id", "coaching_sessions", ["coach_id"], unique=False)
    op.create_index("ix_coaching_sessions_student_id", "coaching_sessions", ["student_id"], unique=False)
    op.create_index("ix_coaching_session_student_date", "coaching_sessions",
                    ["student_id", "session_date"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_coaching_session_student_date", table_name="coaching_sessions")
    op.drop_index("ix_coaching_sessions_student_id", table_name="coaching_sessions")
    op.drop_index("ix_coaching_sessions_coach_id", table_name="coaching_sessions")
    op.drop_table("coaching_sessions")
