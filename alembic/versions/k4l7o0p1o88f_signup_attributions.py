"""signup_attributions — landing donusum (conversion) iliskilendirme

Anonim landing oturumu (fc_telemetry_sid) ile uyelik kaydini iliskilendirir →
ziyaretci → etkilesim → demo → uye → ucretli hunisi + A/B varyant donusumu
olculebilir hale gelir. Additive, downgrade'li.

Revision ID: k4l7o0p1o88f
Revises: j3k6n9o0n77e
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "k4l7o0p1o88f"
down_revision: Union[str, None] = "j3k6n9o0n77e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "signup_attributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("session_id", sa.String(length=40), nullable=True),
        sa.Column("variant_slug", sa.String(length=40), nullable=True),
        sa.Column("signup_role", sa.String(length=20), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="direct"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_signup_attributions_session", "signup_attributions", ["session_id"])
    op.create_index("ix_signup_attributions_created", "signup_attributions", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_signup_attributions_created", table_name="signup_attributions")
    op.drop_index("ix_signup_attributions_session", table_name="signup_attributions")
    op.drop_table("signup_attributions")
