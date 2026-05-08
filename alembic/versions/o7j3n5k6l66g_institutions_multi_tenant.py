"""institutions tablosu + users.institution_id + ETUTKOC default kurumu

Revision ID: o7j3n5k6l66g
Revises: n6i2m4j5k55f
Create Date: 2026-05-08 23:30:00.000000

Sprint 11 — Multi-tenant başlangıcı. Kurumsal kullanıcılar için Institution
modeli + User.institution_id (nullable, SET NULL on delete).

Migration adımları:
1. institutions tablosu oluştur
2. users tablosuna institution_id kolonu ekle (nullable)
3. Default 'ETUTKOC' kurumu oluştur (idempotent)
4. Mevcut tüm TEACHER rolündeki kullanıcıları ETUTKOC'a bağla

UserRole enum'ına yeni değerler (INSTITUTION_ADMIN, SUPER_ADMIN) eklendi —
SQLAlchemy Enum string-tabanlı olduğu için schema değişikliği gerekmedi.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o7j3n5k6l66g"
down_revision: Union[str, None] = "n6i2m4j5k55f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. institutions tablosu
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column(
            "plan", sa.String(length=32), nullable=False,
            server_default=sa.text("'free'"),
        ),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("slug", name="uq_institution_slug"),
    )
    op.create_index("ix_institutions_slug", "institutions", ["slug"])

    # 2. users.institution_id
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("institution_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_users_institution_id",
            "institutions",
            ["institution_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index("ix_users_institution_id", ["institution_id"])

    # 3. Default ETUTKOC kurumu (idempotent — testlerde de güvenli)
    bind = op.get_bind()
    existing = bind.execute(
        sa.text("SELECT id FROM institutions WHERE slug = 'etutkoc'")
    ).fetchone()
    if existing:
        etutkoc_id = existing[0]
    else:
        result = bind.execute(
            sa.text(
                "INSERT INTO institutions (name, slug, contact_email, plan, is_active) "
                "VALUES (:name, :slug, :email, 'free', 1) "
            ).bindparams(
                name="ETUTKOC",
                slug="etutkoc",
                email=None,
            )
        )
        # SQLite + alembic context için lastrowid
        etutkoc_id = result.lastrowid if hasattr(result, "lastrowid") else (
            bind.execute(
                sa.text("SELECT id FROM institutions WHERE slug = 'etutkoc'")
            ).fetchone()[0]
        )

    # 4. Mevcut tüm öğretmenleri ETUTKOC'a bağla
    bind.execute(
        sa.text(
            "UPDATE users SET institution_id = :iid "
            "WHERE role = 'TEACHER' AND institution_id IS NULL"
        ).bindparams(iid=etutkoc_id)
    )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_institution_id")
        batch.drop_constraint("fk_users_institution_id", type_="foreignkey")
        batch.drop_column("institution_id")

    op.drop_index("ix_institutions_slug", table_name="institutions")
    op.drop_table("institutions")
