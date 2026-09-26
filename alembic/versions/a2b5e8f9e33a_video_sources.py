"""Video Sepeti — kayıtlı listeler (video_sources) + video_basket_items.source_id

Revision ID: a2b5e8f9e33a
Revises: z1a4d7e8d22z
Create Date: 2026-09-25

Koçun getirdiği oynatma listeleri kaydedilir (tekrar YouTube'da aramaya gerek
kalmaz; ad/ders düzenlenir, silinir). Sepetteki her video geldiği listeyi
taşır → yeni liste eski listenin videolarına karışmaz. Mevcut kayıtlar
(koç + liste) çiftinden geriye dönük doldurulur. Additive, downgrade'li.
"""
from alembic import op
import sqlalchemy as sa

revision = "a2b5e8f9e33a"
down_revision = "z1a4d7e8d22z"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("coach_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_key", sa.String(length=80), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("playlist_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=True),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.Column("subject_id", sa.Integer(), sa.ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("video_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("coach_id", "source_key", name="uq_video_sources_coach_key"),
    )
    op.create_index("ix_video_sources_coach_id", "video_sources", ["coach_id"])
    with op.batch_alter_table("video_basket_items") as b:
        b.add_column(sa.Column("source_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_video_basket_items_source_id", "video_sources",
                             ["source_id"], ["id"], ondelete="SET NULL")
        b.create_index("ix_video_basket_items_source_id", ["source_id"])

    # Geriye dönük: (koç, liste) çiftleri → kayıtlı liste
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT coach_id, playlist_id, MAX(playlist_title), MIN(youtube_id), "
        "MIN(subject_id), COUNT(*) FROM video_basket_items "
        "WHERE coach_id IS NOT NULL AND playlist_id IS NOT NULL "
        "GROUP BY coach_id, playlist_id"
    )).fetchall()
    for coach_id, pl, title, _vid, subj, n in rows:
        conn.execute(sa.text(
            "INSERT INTO video_sources (coach_id, source_key, url, playlist_id, title, "
            "subject_id, video_count) VALUES (:c, :k, :u, :p, :t, :s, :n)"
        ), {"c": coach_id, "k": f"pl:{pl}", "u": f"https://www.youtube.com/playlist?list={pl}",
            "p": pl, "t": title, "s": subj, "n": n})
        sid = conn.execute(sa.text(
            "SELECT id FROM video_sources WHERE coach_id=:c AND source_key=:k"
        ), {"c": coach_id, "k": f"pl:{pl}"}).scalar()
        conn.execute(sa.text(
            "UPDATE video_basket_items SET source_id=:i WHERE coach_id=:c AND playlist_id=:p"
        ), {"i": sid, "c": coach_id, "p": pl})


def downgrade() -> None:
    with op.batch_alter_table("video_basket_items") as b:
        b.drop_index("ix_video_basket_items_source_id")
        b.drop_constraint("fk_video_basket_items_source_id", type_="foreignkey")
        b.drop_column("source_id")
    op.drop_index("ix_video_sources_coach_id", table_name="video_sources")
    op.drop_table("video_sources")
