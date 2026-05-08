"""parent notification system — UserRole.PARENT + 6 yeni tablo

Revision ID: c4f1d8a3e202
Revises: b8e4c2d11f01
Create Date: 2026-05-05 00:00:00.000000

Sprint 1 — Veli (PARENT) bildirim sistemi temeli:
- users.role enum'una 'PARENT' eklenir
- parent_student_links (çoğa-çoğa)
- parent_invitations (token'lı davet, 7 gün geçerli)
- parent_notification_prefs (tür×kanal toggle + WA telefon + sessiz saatler)
- notification_logs (append-only gönderim günlüğü)
- teacher_notes_to_parent (öğretmen-veli özel notu, öğrenci görmemeli)
- parent_session_logs (KVKK denetim izi)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c4f1d8a3e202"
down_revision: Union[str, None] = "b8e4c2d11f01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) UserRole enum'a 'PARENT' ekle
    # SQLite'da Enum bir CHECK constraint olarak tutulur. batch_alter_table ile
    # tabloyu yeniden oluşturup yeni constraint uygulanır.
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.Enum("TEACHER", "STUDENT", name="userrole"),
            type_=sa.Enum("TEACHER", "STUDENT", "PARENT", name="userrole"),
            existing_nullable=False,
        )

    # 2) parent_student_links — çoğa-çoğa veli↔öğrenci
    op.create_table(
        "parent_student_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "relation",
            sa.Enum("ANNE", "BABA", "VASI", "DIGER", name="parentrelation"),
            nullable=False,
            server_default="DIGER",
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_id", "student_id", name="uq_parent_student"),
    )
    with op.batch_alter_table("parent_student_links", schema=None) as batch_op:
        batch_op.create_index("ix_parent_student_parent", ["parent_id"], unique=False)
        batch_op.create_index("ix_parent_student_student", ["student_id"], unique=False)

    # 3) parent_invitations — token'lı davet
    op.create_table(
        "parent_invitations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invited_email", sa.String(length=255), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("invited_by_id", sa.Integer(), nullable=False),
        sa.Column(
            "relation",
            sa.Enum("ANNE", "BABA", "VASI", "DIGER", name="parentrelation"),
            nullable=False,
            server_default="DIGER",
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_parent_invitation_token"),
    )
    with op.batch_alter_table("parent_invitations", schema=None) as batch_op:
        batch_op.create_index("ix_parent_inv_email", ["invited_email"], unique=False)
        batch_op.create_index("ix_parent_inv_student", ["student_id"], unique=False)
        batch_op.create_index("ix_parent_inv_expires", ["expires_at"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_parent_invitations_token"), ["token"], unique=False
        )

    # 4) parent_notification_prefs — bildirim tercihleri
    op.create_table(
        "parent_notification_prefs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column(
            "daily_summary_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "weekly_report_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "empty_day_alert_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "drop_alert_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "new_program_alert_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "teacher_note_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("whatsapp_phone", sa.String(length=20), nullable=True),
        sa.Column(
            "whatsapp_phone_verified_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "quiet_hours_start", sa.Time(), nullable=False, server_default=sa.text("'22:00:00'")
        ),
        sa.Column(
            "quiet_hours_end", sa.Time(), nullable=False, server_default=sa.text("'07:00:00'")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("parent_id", name="uq_parent_pref"),
    )

    # 5) notification_logs — append-only gönderim günlüğü
    op.create_table(
        "notification_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "DAILY_SUMMARY",
                "EMPTY_DAY",
                "WEEKLY_REPORT",
                "NEW_PROGRAM",
                "DROP_ALERT",
                "TEACHER_NOTE",
                "INVITATION",
                "OTP",
                name="notificationkind",
            ),
            nullable=False,
        ),
        sa.Column(
            "channel",
            sa.Enum("EMAIL", "WHATSAPP", "SMS", name="notificationchannel"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("QUEUED", "SENT", "FAILED", "SUPPRESSED", name="notificationstatus"),
            nullable=False,
            server_default="QUEUED",
        ),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_notif_parent_sent", ["parent_id", "sent_at"], unique=False
        )
        batch_op.create_index(
            "ix_notif_student_kind_sent",
            ["student_id", "kind", "sent_at"],
            unique=False,
        )
        batch_op.create_index("ix_notif_status", ["status"], unique=False)

    # 6) teacher_notes_to_parent — özel not (öğrenci görmemeli)
    op.create_table(
        "teacher_notes_to_parent",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("teacher_notes_to_parent", schema=None) as batch_op:
        batch_op.create_index("ix_tnp_student", ["student_id"], unique=False)
        batch_op.create_index("ix_tnp_teacher", ["teacher_id"], unique=False)

    # 7) parent_session_logs — KVKK denetim izi
    op.create_table(
        "parent_session_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("parent_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("parent_session_logs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_psl_parent_created", ["parent_id", "created_at"], unique=False
        )


def downgrade() -> None:
    # Tabloları FK bağımlılık sırasında ters sıraya boşalt
    with op.batch_alter_table("parent_session_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_psl_parent_created")
    op.drop_table("parent_session_logs")

    with op.batch_alter_table("teacher_notes_to_parent", schema=None) as batch_op:
        batch_op.drop_index("ix_tnp_teacher")
        batch_op.drop_index("ix_tnp_student")
    op.drop_table("teacher_notes_to_parent")

    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_notif_status")
        batch_op.drop_index("ix_notif_student_kind_sent")
        batch_op.drop_index("ix_notif_parent_sent")
    op.drop_table("notification_logs")

    op.drop_table("parent_notification_prefs")

    with op.batch_alter_table("parent_invitations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_parent_invitations_token"))
        batch_op.drop_index("ix_parent_inv_expires")
        batch_op.drop_index("ix_parent_inv_student")
        batch_op.drop_index("ix_parent_inv_email")
    op.drop_table("parent_invitations")

    with op.batch_alter_table("parent_student_links", schema=None) as batch_op:
        batch_op.drop_index("ix_parent_student_student")
        batch_op.drop_index("ix_parent_student_parent")
    op.drop_table("parent_student_links")

    # users.role enum'undan PARENT'ı çıkar
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "role",
            existing_type=sa.Enum("TEACHER", "STUDENT", "PARENT", name="userrole"),
            type_=sa.Enum("TEACHER", "STUDENT", name="userrole"),
            existing_nullable=False,
        )
