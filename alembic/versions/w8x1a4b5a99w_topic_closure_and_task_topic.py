"""Konu kapatma + kaynaksız (konuya bağlı) görev kalemi (2026-09-07)

KOÇ GERİ BİLDİRİMİ: kitabın test sayısına bağlı kalmak program hazırlarken
yoruyor; test sayısı tutarsızlaşınca koç sıkışıyor. Kullanıcı kararı: mevcut
kaynaklı akış AYNEN kalsın, sıkışan koça ALTERNATİF yol açılsın — müfredat
takibi kaybolmadan.

İki additive değişiklik:
  1. `topic_closures` — koç öğrenciyle görüştükten sonra "bu konu bitti" der
     ve müfredat panelinden işaretler. Müfredatın tamamlanması artık kitabın
     test sayacından DEĞİL, koçun kararından okunur. (student, topic) tekil;
     kayıt varsa kapalı, silinirse yeniden açık.
  2. `task_book_items.topic_id` — kitapsız AMA konuya bağlı kalem. Bugün
     `book_section_id` NULL olan her kalem müfredatın, konu performansının ve
     öneri motorunun tamamen dışında kalıyor (kaçış var ama karşılığı ağır).
     Bu kolon kaynaksız görevin müfredat omurgasına bağlanmasını sağlar;
     rezerv/kapasite yine atlanır (book_id NULL olduğu için).

Revision ID: w8x1a4b5a99w
Revises: v7w0z3a4z88v
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "w8x1a4b5a99w"
down_revision = "v7w0z3a4z88v"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "topic_closures",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "student_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "topic_id", sa.Integer(),
            sa.ForeignKey("topics.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "closed_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "closed_by_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.UniqueConstraint("student_id", "topic_id", name="uq_topic_closure"),
    )
    op.create_index(
        "ix_topic_closures_student", "topic_closures", ["student_id"],
    )

    op.add_column(
        "task_book_items",
        sa.Column("topic_id", sa.Integer(), nullable=True),
    )
    # FK'yi batch ile ekle: SQLite ALTER TABLE ADD CONSTRAINT desteklemez.
    with op.batch_alter_table("task_book_items") as batch:
        batch.create_foreign_key(
            "fk_task_book_items_topic", "topics", ["topic_id"], ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_task_book_items_topic", "task_book_items", ["topic_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_task_book_items_topic", table_name="task_book_items")
    with op.batch_alter_table("task_book_items") as batch:
        batch.drop_constraint("fk_task_book_items_topic", type_="foreignkey")
    op.drop_column("task_book_items", "topic_id")
    op.drop_index("ix_topic_closures_student", table_name="topic_closures")
    op.drop_table("topic_closures")
