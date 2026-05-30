"""P2 — WhatsApp şablon registry (Click-to-WA Faz 1 manuel şablonları).

Yeni tablo: whatsapp_templates
  - key (unique) — şablonun kalıcı tanıtıcısı (kod/seed/audit)
  - category — veli | ogrenci | kurum_ogretmen | kurum_veli | kurum_ogrenci |
    admin_yonetici | admin_sistem
  - target_role — kim kullanır: teacher | institution_admin | super_admin | any
  - name_tr — kullanıcıya görünür ad
  - description — kısa açıklama
  - content_template — değişkenli metin ({{degisken_adi}} sözdizimi)
  - variables_json — [{key,label_tr,example}] listesi
  - requires_date — tarih seçicili şablon (toplantı vb.)
  - allow_bulk — toplu gönderim için uygun
  - allow_freeform_note — koç ekstra metin yazabilir
  - sort_order, is_active
  - updated_by_id (FK users SET NULL)

Soft delete: is_active=false ile pasifleştirilir; veri/audit ref'leri korunur.

Additive + downgrade'li.
"""
from alembic import op
import sqlalchemy as sa


revision = "t7u0y2z3y11s"
down_revision = "s6t9x1y2x00r"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(80), nullable=False, unique=True),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column(
            "target_role",
            sa.String(40),
            nullable=False,
            server_default=sa.text("'any'"),
        ),
        sa.Column("name_tr", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("content_template", sa.Text(), nullable=False),
        sa.Column("variables_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column(
            "requires_date",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "allow_bulk",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "allow_freeform_note",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_wat_category_sort",
        "whatsapp_templates",
        ["category", "sort_order"],
    )
    op.create_index(
        "ix_wat_target_role",
        "whatsapp_templates",
        ["target_role"],
    )


def downgrade() -> None:
    op.drop_index("ix_wat_target_role", table_name="whatsapp_templates")
    op.drop_index("ix_wat_category_sort", table_name="whatsapp_templates")
    op.drop_table("whatsapp_templates")
