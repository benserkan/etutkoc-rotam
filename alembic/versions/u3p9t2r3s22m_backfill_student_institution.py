"""student.institution_id backfill — öğretmen üzerinden tenant kurma

Revision ID: u3p9t2r3s22m
Revises: t2o8s1q2r11l
Create Date: 2026-05-09 18:30:00.000000

Stage 3 öncesi yakalanan veri tutarsızlığı:
- /teacher/students POST öğrenci oluştururken institution_id set etmiyordu
- Bu yüzden kurum öğretmeninin eklediği bazı öğrencilerin institution_id NULL
- Cohort analizi User.institution_id ile filtreliyor → kaçıyor

Backfill: NULL olan öğrenci kayıtlarını teacher.institution_id ile doldur.
Idempotent: zaten dolu olanlar etkilenmez. Teacher'ı NULL olan veya teacher'ı
da institution_id NULL olan öğrenciler etkilenmez.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "u3p9t2r3s22m"
down_revision: Union[str, None] = "t2o8s1q2r11l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # SQLite'da UPDATE ... FROM çalışmaz, subquery formu kullan
    bind.execute(sa.text("""
        UPDATE users
        SET institution_id = (
            SELECT t.institution_id
            FROM users t
            WHERE t.id = users.teacher_id
        )
        WHERE users.role = 'STUDENT'
          AND users.institution_id IS NULL
          AND users.teacher_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM users t
              WHERE t.id = users.teacher_id
                AND t.institution_id IS NOT NULL
          )
    """))


def downgrade() -> None:
    # Backfill geri alınamaz (hangi student'ların önceden NULL olduğunu bilmiyoruz)
    pass
