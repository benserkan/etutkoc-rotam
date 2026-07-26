"""Rota Veli Asistanı P1 — parent_commentaries (yorum önbelleği + ses)

Veli için AI yorumlayıcı: çocuk başına tür başına (program|deneme) TEK satır.
Ekran metni (rakamlı, bölümlü) + seslendirme metni (sayılar yazıyla) tek Gemini
çağrısında üretilir; MP3/WAV ilk dinlemede üretilip bu tabloda saklanır —
tekrar dinleme kredisiz. Additive; mevcut veriye dokunmaz. parent_insights
tablosu (P2b) olduğu gibi kalır (eski mobil sürümler kırılmasın).

Revision ID: b2c5f8g9g11b
Revises: a1b4e7f8e00a
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "b2c5f8g9g11b"
down_revision = "a1b4e7f8e00a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parent_commentaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("sections_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("speech_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("based_on_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("audio", sa.LargeBinary(), nullable=True),
        sa.Column("audio_content_type", sa.String(length=64), nullable=True),
        sa.Column("audio_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "generated_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("student_id", "kind", name="uq_parent_commentary"),
    )
    op.create_index(
        "ix_parent_commentaries_student_id", "parent_commentaries", ["student_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_parent_commentaries_student_id", table_name="parent_commentaries")
    op.drop_table("parent_commentaries")
