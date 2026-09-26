"""Haftalık İskelet — dönemli iskelet (F2-2)

Revision ID: d5e8h1i2h66d
Revises: c4d7g0h1g55c
Create Date: 2026-09-26

Bir öğrencinin BİRDEN ÇOK iskeleti olabilir (Yaz · Okul dönemi · Yarıyıl
tatili). Her iskelet yalnız başlangıç tarihi taşır ve bir sonraki dönem
başlayana kadar geçerlidir; bir gün için geçerli iskelet = valid_from ≤ gün
olanların en yenisi (NULL = en baştan beri).

- weekly_skeletons.student_id üzerindeki UNIQUE kaldırılır → sıradan indeks
- weekly_skeletons + valid_from (DATE, nullable)
Mevcut satırlar etkilenmez (valid_from NULL = mevcut davranış). Downgrade'li:
downgrade, öğrenci başına en yeni iskelet dışındakileri SİLMEZ — birden çok
iskelet varsa UNIQUE geri eklenemez; bu durumda downgrade hata verir (veri
kaybını önlemek için bilinçli).
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e8h1i2h66d"
down_revision = "c4d7g0h1g55c"
branch_labels = None
depends_on = None


def _table(meta: sa.MetaData, with_unique: bool, with_valid_from: bool) -> sa.Table:
    cols = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, unique=with_unique),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False, server_default="Haftalık iskelet"),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]
    if with_valid_from:
        cols.append(sa.Column("valid_from", sa.Date(), nullable=True))
    return sa.Table("weekly_skeletons", meta, *cols)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("weekly_skeletons_student_id_key", "weekly_skeletons", type_="unique")
        op.add_column("weekly_skeletons", sa.Column("valid_from", sa.Date(), nullable=True))
    else:
        # SQLite: isimsiz UNIQUE ancak tablo yeniden kurularak kaldırılır
        with op.batch_alter_table(
            "weekly_skeletons", recreate="always",
            copy_from=_table(sa.MetaData(), with_unique=True, with_valid_from=False),
        ) as b:
            b.add_column(sa.Column("valid_from", sa.Date(), nullable=True))
        with op.batch_alter_table(
            "weekly_skeletons", recreate="always",
            copy_from=_table(sa.MetaData(), with_unique=False, with_valid_from=True),
        ):
            pass
        op.create_index("ix_weekly_skeletons_coach_id", "weekly_skeletons", ["coach_id"])
    op.create_index(
        "ix_weekly_skeletons_student_valid", "weekly_skeletons", ["student_id", "valid_from"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    dup = bind.execute(sa.text(
        "SELECT student_id FROM weekly_skeletons GROUP BY student_id HAVING COUNT(*) > 1 LIMIT 1"
    )).first()
    if dup is not None:
        raise RuntimeError(
            "Bir öğrencide birden çok dönem iskeleti var; downgrade veri kaybına yol açar."
        )
    op.drop_index("ix_weekly_skeletons_student_valid", table_name="weekly_skeletons")
    if bind.dialect.name == "postgresql":
        op.drop_column("weekly_skeletons", "valid_from")
        op.create_unique_constraint(
            "weekly_skeletons_student_id_key", "weekly_skeletons", ["student_id"],
        )
    else:
        with op.batch_alter_table(
            "weekly_skeletons", recreate="always",
            copy_from=_table(sa.MetaData(), with_unique=False, with_valid_from=True),
        ) as b:
            b.drop_column("valid_from")
        with op.batch_alter_table(
            "weekly_skeletons", recreate="always",
            copy_from=_table(sa.MetaData(), with_unique=True, with_valid_from=False),
        ):
            pass
        op.create_index("ix_weekly_skeletons_coach_id", "weekly_skeletons", ["coach_id"])
