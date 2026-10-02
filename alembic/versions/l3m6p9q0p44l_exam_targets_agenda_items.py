"""Deneme analizi Faz 2 kalıcı tablolar — 2026-10-02.

Faz 2 ilk sürümünde hedef net ve seans gündem kuyruğu, paralel bir oturumun
migration'ıyla çakışmamak için `app_settings` JSON anahtarlarında tutuluyordu
(`exam_target:{öğrenci}`, `agenda_queue:{öğrenci}`). Bu anahtarlar öğrenciye
FK ile bağlı olmadığından öğrenci silinince YETİM kalıyordu. Artık:

- exam_targets         : öğrenci × sınav türü başına hedef (CASCADE).
- session_agenda_items : "seansa ekle" kuyruğu (öğrenci CASCADE, deneme SET NULL).
- VERİ: app_settings'teki eski anahtarlar tablolara taşınır ve SİLİNİR
  (öğrencisi artık yoksa yalnız silinir — yetim temizliği).

Additive, downgrade'li (downgrade veriyi app_settings'e geri yazmaz).
"""
import json
from datetime import date, datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "l3m6p9q0p44l"
down_revision = "k2l5o8p9o33k"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(16), nullable=False),
        sa.Column("target_net", sa.Float(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("subject_targets", sa.Text(), nullable=True),
        sa.Column("note", sa.String(300), nullable=True),
        sa.Column("set_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("student_id", "section", name="uq_exam_target_student_section"),
    )
    op.create_index("ix_exam_targets_student_id", "exam_targets", ["student_id"])
    op.create_table(
        "session_agenda_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("item_key", sa.String(80), nullable=True),
        sa.Column("text", sa.String(400), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="exam"),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exam_results.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_session_agenda_items_student_id", "session_agenda_items", ["student_id"])

    # --- eski app_settings anahtarlarını taşı + sil
    bind = op.get_bind()
    rows = bind.execute(sa.text(
        "SELECT key, value_json FROM app_settings "
        "WHERE key LIKE 'exam_target:%' OR key LIKE 'agenda_queue:%'"
    )).fetchall()
    now = datetime.now(timezone.utc)
    for key, raw in rows:
        kind, _, sid_s = key.partition(":")
        try:
            sid = int(sid_s)
            data = json.loads(raw)
        except (ValueError, TypeError):
            data, sid = None, None
        exists = sid is not None and bind.execute(
            sa.text("SELECT 1 FROM users WHERE id = :i"), {"i": sid}).first() is not None
        if exists and kind == "exam_target" and isinstance(data, dict):
            for sec, t in data.items():
                if not isinstance(t, dict) or t.get("target_net") is None:
                    continue
                td = None
                if t.get("target_date"):
                    try:
                        td = date.fromisoformat(t["target_date"])
                    except ValueError:
                        td = None
                bind.execute(sa.text(
                    "INSERT INTO exam_targets (student_id, section, target_net, target_date, "
                    "subject_targets, note, set_by_id, created_at, updated_at) "
                    "VALUES (:s, :sec, :n, :d, :st, :note, :by, :c, :c)"),
                    {"s": sid, "sec": str(sec)[:16], "n": float(t["target_net"]), "d": td,
                     "st": json.dumps(t.get("subjects") or {}, ensure_ascii=False),
                     "note": t.get("note"), "by": t.get("set_by_id"), "c": now})
        elif exists and kind == "agenda_queue" and isinstance(data, list):
            for q in data:
                if not isinstance(q, dict) or not q.get("text"):
                    continue
                bind.execute(sa.text(
                    "INSERT INTO session_agenda_items (student_id, created_by_id, item_key, text, "
                    "source, exam_id, created_at) VALUES (:s, :by, :k, :t, :src, NULL, :c)"),
                    {"s": sid, "by": q.get("created_by_id"), "k": q.get("key"),
                     "t": str(q["text"])[:400], "src": (q.get("source") or "exam")[:20], "c": now})
        bind.execute(sa.text("DELETE FROM app_settings WHERE key = :k"), {"k": key})


def downgrade() -> None:
    op.drop_index("ix_session_agenda_items_student_id", "session_agenda_items")
    op.drop_table("session_agenda_items")
    op.drop_index("ix_exam_targets_student_id", "exam_targets")
    op.drop_table("exam_targets")
