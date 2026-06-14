"""testimonials — sosyal kanit (kullanici yorumu / kurum referansi / basari hikayesi)

Anasayfada yayinlanacak sosyal kanit. Uygulama-ici gonderim (ogrenci/veli/koc/
kurum yoneticisi -> pending) + super admin elle giris + moderasyon (publish/hide)
+ public yayinlanmis liste. Additive, downgrade'li.

Revision ID: j3k6n9o0n77e
Revises: i2j5m8n9m66d
Create Date: 2026-06-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "j3k6n9o0n77e"
down_revision: Union[str, None] = "i2j5m8n9m66d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "testimonials",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default="review"),
        sa.Column("author_name", sa.String(length=160), nullable=False),
        sa.Column("author_role", sa.String(length=30), nullable=True),
        sa.Column("author_title", sa.String(length=200), nullable=True),
        sa.Column("institution_name", sa.String(length=200), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column(
            "submitted_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("consent_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_testimonials_status", "testimonials", ["status"])
    op.create_index("ix_testimonials_kind", "testimonials", ["kind"])
    op.create_index("ix_testimonials_submitted_by", "testimonials", ["submitted_by_id"])


def downgrade() -> None:
    op.drop_index("ix_testimonials_submitted_by", table_name="testimonials")
    op.drop_index("ix_testimonials_kind", table_name="testimonials")
    op.drop_index("ix_testimonials_status", table_name="testimonials")
    op.drop_table("testimonials")
