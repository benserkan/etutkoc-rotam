"""review_cards + review_logs (Stage 12 — FSRS-light spaced repetition)

Revision ID: i7d3g6e7f66a
Revises: h6c2f5d6e55z
Create Date: 2026-05-11 09:00:00.000000

Stage 12 — Spaced Repetition:
- review_cards: öğrenci × topic için FSRS state (stability, difficulty, state, due_at)
- review_logs: her tekrar olayının audit log'u (before/after değerler)

Kart key'i (student_id, topic_id) unique. due_at indeksi vade-bazlı sorgular için.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i7d3g6e7f66a"
down_revision: Union[str, None] = "h6c2f5d6e55z"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "review_cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column(
            "stability", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column(
            "difficulty", sa.Float(), nullable=False, server_default=sa.text("5.0")
        ),
        sa.Column(
            "state", sa.String(length=16), nullable=False, server_default="new"
        ),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_rating", sa.Integer(), nullable=True),
        sa.Column(
            "review_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "lapse_count", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id", "topic_id", name="uq_review_card_student_topic"
        ),
    )
    op.create_index(
        "ix_review_cards_student_id", "review_cards", ["student_id"]
    )
    op.create_index("ix_review_cards_topic_id", "review_cards", ["topic_id"])
    op.create_index("ix_review_cards_state", "review_cards", ["state"])
    op.create_index("ix_review_cards_due_at", "review_cards", ["due_at"])
    op.create_index(
        "ix_review_card_due", "review_cards", ["student_id", "due_at"]
    )

    op.create_table(
        "review_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("topic_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column(
            "elapsed_days", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column(
            "scheduled_days", sa.Float(), nullable=False, server_default=sa.text("0.0")
        ),
        sa.Column(
            "stability_before",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
        sa.Column(
            "stability_after",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0.0"),
        ),
        sa.Column(
            "difficulty_before",
            sa.Float(),
            nullable=False,
            server_default=sa.text("5.0"),
        ),
        sa.Column(
            "difficulty_after",
            sa.Float(),
            nullable=False,
            server_default=sa.text("5.0"),
        ),
        sa.Column(
            "state_before", sa.String(length=16), nullable=False, server_default="new"
        ),
        sa.Column(
            "state_after", sa.String(length=16), nullable=False, server_default="new"
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["card_id"], ["review_cards.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_review_logs_card_id", "review_logs", ["card_id"])
    op.create_index("ix_review_logs_student_id", "review_logs", ["student_id"])
    op.create_index("ix_review_logs_topic_id", "review_logs", ["topic_id"])
    op.create_index("ix_review_logs_reviewed_at", "review_logs", ["reviewed_at"])


def downgrade() -> None:
    op.drop_index("ix_review_logs_reviewed_at", table_name="review_logs")
    op.drop_index("ix_review_logs_topic_id", table_name="review_logs")
    op.drop_index("ix_review_logs_student_id", table_name="review_logs")
    op.drop_index("ix_review_logs_card_id", table_name="review_logs")
    op.drop_table("review_logs")

    op.drop_index("ix_review_card_due", table_name="review_cards")
    op.drop_index("ix_review_cards_due_at", table_name="review_cards")
    op.drop_index("ix_review_cards_state", table_name="review_cards")
    op.drop_index("ix_review_cards_topic_id", table_name="review_cards")
    op.drop_index("ix_review_cards_student_id", table_name="review_cards")
    op.drop_table("review_cards")
