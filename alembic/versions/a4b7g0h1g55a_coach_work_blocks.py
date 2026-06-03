"""coach_work_blocks — serbest iş bloğu (Katman 3) + tasks.work_block_id

Koç birbirine bağlı bir iş bloğu tanımlar (ör. "Özel Ders Mat — 10 test" veya
"Matematik öğretmeni ödevi"). Blok genelde SİSTEM-DIŞI kaynaktır (özel ders
sorusu, başka öğretmenin ödevi) — sistemde kitabı yoktur, bu yüzden Kaynak
Durumu izleyemez. Blok bir TOPLAM hedef tutar; koç günlere görev dağıttıkça
sistem "dağıtılan / kalan"ı hesaplar (görev.work_block_id ile bağlanan
görevlerin planlanan toplamı). Böylece "Pazartesi 3 koydum, 7 kaldı"yı
elle saymaya gerek kalmaz.

İki değişiklik, ikisi de ADDITIVE (mevcut veriyi ETKİLEMEZ), downgrade'li:
  1) yeni tablo  coach_work_blocks
  2) yeni nullable FK kolon  tasks.work_block_id  (SET NULL — blok silinince
     görev kalır, sadece bağ kopar)

Revision ID: a4b7g0h1g55a
Revises: z3a6f9g0f44z
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "a4b7g0h1g55a"
down_revision = "z3a6f9g0f44z"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "coach_work_blocks",
        sa.Column("id", sa.Integer(), primary_key=True),
        # Bloğu oluşturan koç — silinirse blok kalsın (SET NULL).
        sa.Column("coach_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        # Bloğun ait olduğu öğrenci — öğrenci silinirse blok da silinsin.
        sa.Column("student_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        # Opsiyonel ders (renk/gruplama için) — ders silinirse bağ kopsun.
        sa.Column("subject_id", sa.Integer(),
                  sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("total_count", sa.Integer(), nullable=False),
        # Birim: test / soru / deneme (gösterim amaçlı).
        sa.Column("unit", sa.String(length=16), nullable=False, server_default="test"),
        sa.Column("note", sa.Text(), nullable=True),
        # Durum: active / done / archived (yumuşak arşiv için archived_at ayrıca var).
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_coach_work_blocks_student_id", "coach_work_blocks", ["student_id"])
    op.create_index("ix_coach_work_blocks_coach_id", "coach_work_blocks", ["coach_id"])

    # tasks.work_block_id — görevi bir bloğa bağlar (opsiyonel).
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("work_block_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_tasks_work_block_id", ["work_block_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_tasks_work_block_id_coach_work_blocks", "coach_work_blocks",
            ["work_block_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_constraint("fk_tasks_work_block_id_coach_work_blocks", type_="foreignkey")
        batch_op.drop_index("ix_tasks_work_block_id")
        batch_op.drop_column("work_block_id")

    op.drop_index("ix_coach_work_blocks_coach_id", table_name="coach_work_blocks")
    op.drop_index("ix_coach_work_blocks_student_id", table_name="coach_work_blocks")
    op.drop_table("coach_work_blocks")
