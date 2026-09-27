"""Şube (sınıf grubu) + veli davetinde ad/telefon (2026-09-27)

Kurum toplu kaydı (CSV) için:
- users + class_group (VARCHAR(60), nullable, index): öğrencinin şubesi / grubu
  ("10-A", "Mezun Sayısal"). Koç öğrenci listesini buna göre süzer, toplu
  işlemleri (kitap seti, iskelet kopyası) şubeye uygular.
- parent_invitations + invited_name (VARCHAR(120)) + invited_phone (VARCHAR(20)):
  CSV'de verilen veli adı/telefonu; veli aktivasyon formu önceden dolu gelir.
Additive, mevcut satırlar etkilenmez, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "h9i2l5m6l00h"
down_revision = "g8h1k4l5k99g"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("class_group", sa.String(length=60), nullable=True))
        b.create_index("ix_users_class_group", ["class_group"])
    with op.batch_alter_table("parent_invitations") as b:
        b.add_column(sa.Column("invited_name", sa.String(length=120), nullable=True))
        b.add_column(sa.Column("invited_phone", sa.String(length=20), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("parent_invitations") as b:
        b.drop_column("invited_phone")
        b.drop_column("invited_name")
    with op.batch_alter_table("users") as b:
        b.drop_index("ix_users_class_group")
        b.drop_column("class_group")
