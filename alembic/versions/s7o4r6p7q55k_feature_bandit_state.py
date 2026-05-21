"""feature_bandit_state — LinUCB contextual bandit durum tablosu (Katman 7)

Revision ID: s7o4r6p7q55k
Revises: r6n3q5o6p44j
Create Date: 2026-05-15 12:00:00.000000

Her FeatureCard için bir bandit-arm durumu:
  - A (context_dim × context_dim ridge precision matrix), JSON serialize
  - b (context_dim reward-context vektörü), JSON serialize
  - alpha (keşif parametresi), reward_count (kaç gözlem öğrenildi)

LinUCB güncellemesi:
  A_new = A + xxᵀ
  b_new = b + r·x   (r = view 0.3, demo_click 1.0, cta_click 0.8)
  θ = A⁻¹·b
  UCB = θᵀx + α·√(xᵀA⁻¹x)

context_dim ŞU AN 10: bias + 5 rol one-hot + 4 saat bin. Genişletilirse
yeni dim eski state ile uyumsuz olur → reset mantığı bandit.py'de.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s7o4r6p7q55k"
down_revision: Union[str, None] = "r6n3q5o6p44j"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_bandit_state",
        sa.Column(
            "card_id",
            sa.Integer(),
            sa.ForeignKey("feature_cards.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("context_dim", sa.Integer(), nullable=False),
        sa.Column("a_matrix_json", sa.Text(), nullable=False),
        sa.Column("b_vector_json", sa.Text(), nullable=False),
        sa.Column("alpha", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("reward_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("feature_bandit_state")
