"""feature_cards — Katman 1 Özellik Kataloğu

Revision ID: n2j9m1k2l00f
Revises: m1h7k0i1j00e
Create Date: 2026-05-14 10:00:00.000000

Tanıtıma değer her özelliğin tek satırda toplandığı katalog. Anasayfa
kartları, demo bağlantıları, hedef rol/alan sınıflandırması, yayın durumu
hep buradan beslenir.

Seed bu migration'da YOK — `python -m scripts.seed_feature_catalog` ile
8-9 başlangıç kartı ayrı çalıştırılır (içeriği bol Türkçe, SQL'e basmak
yerine Python script daha okunur).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n2j9m1k2l00f"
down_revision: Union[str, None] = "m1h7k0i1j00e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_cards",
        sa.Column("id", sa.Integer(), nullable=False),

        # Kimlik
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("tagline", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("description_md", sa.Text(), nullable=False, server_default=""),

        # Görsel
        sa.Column("icon", sa.String(length=64), nullable=False, server_default="sparkles"),
        sa.Column("accent_color", sa.String(length=32), nullable=False, server_default="#3b82f6"),

        # JSON-as-Text listeler
        sa.Column("target_roles_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("benefits_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("pain_points_json", sa.Text(), nullable=False, server_default="[]"),

        # Demo bağlantısı (mevcut /demos?play=<slug> sayfasına referans)
        sa.Column("demo_slug", sa.String(length=80), nullable=True),

        # Sınıflandırma
        sa.Column("domain", sa.String(length=20), nullable=False, server_default="genel"),
        sa.Column("tier", sa.String(length=20), nullable=False, server_default="enhancement"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),

        # Tarih/kaynak
        sa.Column(
            "introduced_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column("introduced_in_commit", sa.String(length=40), nullable=True),
        sa.Column("pr_url", sa.String(length=255), nullable=True),

        # Kürasyon
        sa.Column("strategic_priority", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("manual_pin", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("pin_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manual_hide", sa.Boolean(), nullable=False, server_default=sa.text("0")),

        # CTA
        sa.Column("cta_label", sa.String(length=80), nullable=False, server_default="Detayları gör"),
        sa.Column("cta_url", sa.String(length=255), nullable=True),

        # Audit
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("updated_by", sa.Integer(), nullable=True),

        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], ondelete="SET NULL",
            name="fk_feature_card_created_by",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], ondelete="SET NULL",
            name="fk_feature_card_updated_by",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_feature_card_slug"),
    )

    # Sık sorgulanan filtreler için ikincil indeksler
    with op.batch_alter_table("feature_cards") as batch:
        batch.create_index("ix_feature_card_status", ["status"])
        batch.create_index("ix_feature_card_domain", ["domain"])
        batch.create_index("ix_feature_card_tier", ["tier"])


def downgrade() -> None:
    with op.batch_alter_table("feature_cards") as batch:
        batch.drop_index("ix_feature_card_tier")
        batch.drop_index("ix_feature_card_domain")
        batch.drop_index("ix_feature_card_status")
    op.drop_table("feature_cards")
