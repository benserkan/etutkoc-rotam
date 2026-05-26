"""TaskRequest.task_id FK: CASCADE -> SET NULL (audit izi korunsun)

Revision ID: n1o4s6t7s66m
Revises: m0n3r5s6r55l
Create Date: 2026-05-26

Bug: REMOVE talebi onaylanırken request_service.approve_request task'ı siliyordu;
TaskRequest.task_id FK ondelete=CASCADE olduğu için DB cascade ile request'i
de siliyordu; sonra endpoint `db.refresh(req)` InvalidRequestError fırlattı
(HTTP 500). Veri tarafı doğru çalıştı (task silindi) ama UI hata aldı + cache
bayatladı + denetim izi (request) kayboldu.

Çözüm: FK ondelete=SET NULL. Task silinince request KALIR (task_id=NULL,
status=approved). Audit izi var, refresh çalışır, frontend invalidate atılır.
"""
from alembic import op
from sqlalchemy import text


revision = "n1o4s6t7s66m"
down_revision = "m0n3r5s6r55l"
branch_labels = None
depends_on = None


_FK_NAME = "task_requests_task_id_fkey"  # Postgres default naming


def upgrade() -> None:
    # Postgres: drop existing FK + recreate with SET NULL.
    # Constraint adı SQLAlchemy/Postgres default: <table>_<column>_fkey.
    op.execute(text(
        "ALTER TABLE task_requests "
        f"DROP CONSTRAINT IF EXISTS {_FK_NAME}"
    ))
    op.create_foreign_key(
        _FK_NAME,
        "task_requests", "tasks",
        ["task_id"], ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.execute(text(
        "ALTER TABLE task_requests "
        f"DROP CONSTRAINT IF EXISTS {_FK_NAME}"
    ))
    op.create_foreign_key(
        _FK_NAME,
        "task_requests", "tasks",
        ["task_id"], ["id"],
        ondelete="CASCADE",
    )
