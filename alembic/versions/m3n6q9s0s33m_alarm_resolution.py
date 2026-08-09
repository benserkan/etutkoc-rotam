"""alarm_events: çözümleme durumu + yanlış alarm işareti

Alarm körlüğü tekrarlayan bir sorun (Haziran'da 2308 birikmiş alarm, abuse
yanlış-pozitifleri, 2026-08-09 moment_silent vakası). "Gördüm" tek başına
yetmiyor: alarmın GERÇEKTEN çözülüp çözülmediği ve YANLIŞ alarm olup olmadığı
kaydedilmediği için aynı kural aylarca gürültü üretebiliyor.

- resolved_at/by/note : "sorun giderildi, sebebi buydu" damgası
- false_positive      : "bu alarm yanlıştı" — kural başına sayılır, eşik/kural
                        gözden geçirme sinyali olur

Additive + downgrade'li.

Revision ID: m3n6q9s0s33m
Revises: l2m5p8r9r22l
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "m3n6q9s0s33m"
down_revision: Union[str, None] = "l2m5p8r9r22l"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alarm_events",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alarm_events",
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "alarm_events",
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "alarm_events",
        sa.Column(
            "false_positive",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # SQLite'ta named FK için batch gerekir; prod PG'de doğrudan çalışır.
    with op.batch_alter_table("alarm_events") as batch:
        batch.create_foreign_key(
            "fk_alarm_events_resolved_by",
            "users",
            ["resolved_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("alarm_events") as batch:
        batch.drop_constraint("fk_alarm_events_resolved_by", type_="foreignkey")
    op.drop_column("alarm_events", "false_positive")
    op.drop_column("alarm_events", "resolution_note")
    op.drop_column("alarm_events", "resolved_by_user_id")
    op.drop_column("alarm_events", "resolved_at")
