"""User güvenlik kolonları + audit_logs tablosu

Revision ID: p8k4o6l7m77h
Revises: o7j3n5k6l66g
Create Date: 2026-05-09 09:00:00.000000

Sprint 2 — multi-tenant security infrastructure.

Eklenenler:
1. users tablosu güvenlik kolonları:
   - failed_login_count (int, default 0)
   - locked_until (datetime, nullable) — geçici lockout sonu
   - last_login_at, last_login_ip — başarılı giriş izi
   - password_changed_at — diğer oturumları invalidate etmek için stamp
2. audit_logs tablosu — adli iz: actor, action, target, ip, ua, details_json

Eski kullanıcılar için: failed_login_count=0 default, diğer alanlar NULL.
İlk başarılı login'de last_* alanları dolar, password_changed_at sadece
kullanıcı şifresini değiştirdiğinde set olur.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p8k4o6l7m77h"
down_revision: Union[str, None] = "o7j3n5k6l66g"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "failed_login_count", sa.Integer(),
            nullable=False, server_default=sa.text("0"),
        ))
        batch.add_column(sa.Column(
            "locked_until", sa.DateTime(timezone=True), nullable=True,
        ))
        batch.add_column(sa.Column(
            "last_login_at", sa.DateTime(timezone=True), nullable=True,
        ))
        batch.add_column(sa.Column(
            "last_login_ip", sa.String(length=64), nullable=True,
        ))
        batch.add_column(sa.Column(
            "password_changed_at", sa.DateTime(timezone=True), nullable=True,
        ))

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("email_attempted", sa.String(length=255), nullable=True),
        sa.Column(
            "action",
            sa.Enum(
                "LOGIN_SUCCESS", "LOGIN_FAILED", "LOGIN_LOCKED", "LOGOUT",
                "PASSWORD_CHANGE", "PASSWORD_RESET", "PERMISSION_DENIED",
                "USER_CREATE", "USER_UPDATE", "USER_DELETE", "USER_DEACTIVATE",
                "INSTITUTION_CREATE", "INSTITUTION_UPDATE", "INSTITUTION_DELETE",
                "IMPERSONATE_START", "IMPERSONATE_END", "ROLE_CHANGE",
                name="auditaction",
            ),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_audit_actor_created", "audit_logs", ["actor_id", "created_at"],
    )
    op.create_index(
        "ix_audit_action_created", "audit_logs", ["action", "created_at"],
    )
    op.create_index(
        "ix_audit_target", "audit_logs", ["target_type", "target_id"],
    )
    op.create_index(
        "ix_audit_logs_actor_id", "audit_logs", ["actor_id"],
    )
    op.create_index(
        "ix_audit_logs_created_at", "audit_logs", ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_target", table_name="audit_logs")
    op.drop_index("ix_audit_action_created", table_name="audit_logs")
    op.drop_index("ix_audit_actor_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    with op.batch_alter_table("users") as batch:
        batch.drop_column("password_changed_at")
        batch.drop_column("last_login_ip")
        batch.drop_column("last_login_at")
        batch.drop_column("locked_until")
        batch.drop_column("failed_login_count")
