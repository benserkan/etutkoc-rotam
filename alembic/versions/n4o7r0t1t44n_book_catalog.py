"""Ortak Kitap Kataloğu — book_templates genişletmesi.

Koçların en büyük kitap-tanımlama acısı: müfredattan eklemede sabit test
sayısı (her üniteye aynı sayı) tek tek elle düzeltiliyor. Çözüm: bir kitap
Türkiye'de BİR KEZ tanımlanır (içindekiler fotoğrafı/örnek PDF okuma veya
elle), ortak kataloğa girer; sonraki her koç yapıyı (ünite + birebir test
sayısı + müfredat eşleştirmesi) tek tıkla alır.

Katalog, ayrı tablo yerine mevcut BookTemplate iskeletinin genişletilmesidir
(modeldeki not: "İleride paylaşım açılırsa NULL teacher_id system-template
olarak yorumlanabilir"). Kitap oluşturma yolu (template_id → section kopyala)
değişmeden çalışır.

- teacher_id nullable          : NULL = global katalog kaydı
- catalog_status               : NULL=kişisel şablon · pending/verified/hidden
- source                       : admin_seed / coach_contribution / ai_read
- name/publisher_normalized    : eşleştirme-arama anahtarı (indexli)
- contributed_by/verified_by   : denetim izi (koça anonim gösterilir)
- usage_count                  : kaç koç kullandı (arama sıralama sinyali)
- sections.topic_id            : verified kayıt müfredat eşleştirmesini de taşır

Additive + downgrade'li. Downgrade katalog satırlarını (teacher_id NULL)
silip kolonları düşürür.

Revision ID: n4o7r0t1t44n
Revises: m3n6q9s0s33m
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "n4o7r0t1t44n"
down_revision: Union[str, None] = "m3n6q9s0s33m"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- book_templates: katalog kolonları ---------------------------------
    op.add_column(
        "book_templates",
        sa.Column("catalog_status", sa.String(length=16), nullable=True),
    )
    op.add_column(
        "book_templates",
        sa.Column("source", sa.String(length=24), nullable=True),
    )
    op.add_column(
        "book_templates",
        sa.Column("name_normalized", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "book_templates",
        sa.Column("publisher_normalized", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "book_templates",
        sa.Column("contributed_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "book_templates",
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "book_templates",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "book_templates",
        sa.Column(
            "usage_count", sa.Integer(), nullable=False, server_default="0",
        ),
    )
    op.create_index(
        "ix_book_templates_catalog_status", "book_templates", ["catalog_status"],
    )
    op.create_index(
        "ix_book_templates_name_normalized", "book_templates", ["name_normalized"],
    )
    op.create_index(
        "ix_book_templates_publisher_normalized",
        "book_templates",
        ["publisher_normalized"],
    )

    # teacher_id nullable + yeni FK'ler — SQLite batch gerekir; PG'de de çalışır.
    with op.batch_alter_table("book_templates") as batch:
        batch.alter_column(
            "teacher_id", existing_type=sa.Integer(), nullable=True,
        )
        batch.create_foreign_key(
            "fk_book_templates_contributed_by",
            "users",
            ["contributed_by_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_book_templates_verified_by",
            "users",
            ["verified_by_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # --- book_template_sections: müfredat eşleştirmesi taşınır -------------
    op.add_column(
        "book_template_sections",
        sa.Column("topic_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_book_template_sections_topic_id", "book_template_sections", ["topic_id"],
    )
    with op.batch_alter_table("book_template_sections") as batch:
        batch.create_foreign_key(
            "fk_book_template_sections_topic",
            "topics",
            ["topic_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # --- AuditAction: katalog moderasyon olayı -----------------------------
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE auditaction ADD VALUE IF NOT EXISTS 'BOOK_CATALOG_UPDATE'"
        )
    # SQLite: Enum VARCHAR olarak saklanır — işlem gerekmez.


def downgrade() -> None:
    # Katalog satırları (teacher_id NULL) NOT NULL'a dönmeden silinmeli.
    op.execute("DELETE FROM book_templates WHERE teacher_id IS NULL")

    with op.batch_alter_table("book_template_sections") as batch:
        batch.drop_constraint(
            "fk_book_template_sections_topic", type_="foreignkey",
        )
    op.drop_index(
        "ix_book_template_sections_topic_id", table_name="book_template_sections",
    )
    op.drop_column("book_template_sections", "topic_id")

    with op.batch_alter_table("book_templates") as batch:
        batch.drop_constraint("fk_book_templates_verified_by", type_="foreignkey")
        batch.drop_constraint(
            "fk_book_templates_contributed_by", type_="foreignkey",
        )
        batch.alter_column(
            "teacher_id", existing_type=sa.Integer(), nullable=False,
        )
    op.drop_index(
        "ix_book_templates_publisher_normalized", table_name="book_templates",
    )
    op.drop_index("ix_book_templates_name_normalized", table_name="book_templates")
    op.drop_index("ix_book_templates_catalog_status", table_name="book_templates")
    op.drop_column("book_templates", "usage_count")
    op.drop_column("book_templates", "verified_at")
    op.drop_column("book_templates", "verified_by_id")
    op.drop_column("book_templates", "contributed_by_id")
    op.drop_column("book_templates", "publisher_normalized")
    op.drop_column("book_templates", "name_normalized")
    op.drop_column("book_templates", "source")
    op.drop_column("book_templates", "catalog_status")
    # PG enum üyesi (BOOK_CATALOG_UPDATE) güvenle düşürülemez; üye kalır (zararsız).
