"""Rehber (onboarding guide) ilerleme durumu — user_guide_states

Rol bazlı yapay zekâ rehberi (ilk giriş karşılaması + bölümlü sesli anlatım +
"şimdi sen yap" kontrol listesi) için kullanıcı başına ilerleme kaydı:
- guide_key: hangi rehber (coach_onboarding; ileride student/parent/institution)
- status: in_progress | completed | dismissed
- chapters_done: tamamlanan bölüm anahtarları (JSON liste)
- current_chapter: kalınan bölüm (cihazdan bağımsız devam)

Kontrol listesi (kitap eklendi mi, program yayınlandı mı...) SAKLANMAZ —
gerçek veriden her istekte hesaplanır (guide_service.coach_checklist).

Additive — mevcut veriyi ETKİLEMEZ. Downgrade'li.

Revision ID: z0a3d6e7d99z
Revises: y9z2c5d6c88y
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = "z0a3d6e7d99z"
down_revision = "y9z2c5d6c88y"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_guide_states",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
        ),
        sa.Column("guide_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="in_progress"),
        sa.Column("current_chapter", sa.String(length=64), nullable=True),
        sa.Column("chapters_done", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.UniqueConstraint("user_id", "guide_key", name="uq_user_guide_state"),
    )


def downgrade() -> None:
    op.drop_table("user_guide_states")
