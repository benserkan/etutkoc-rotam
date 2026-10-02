"""Karma havuzda aynı adlı konu → okul müfredatı konusu seçilir (2026-10-02)."""
import sys

sys.path.insert(0, ".")
from app.database import SessionLocal  # noqa: E402
from app.models.curriculum import CurriculumModel, Subject, Topic  # noqa: E402
from app.services.exam_import_service import _prefer_school_topics, normalize_topics  # noqa: E402

ok: list[bool] = []


def chk(label, cond, extra=""):
    ok.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + label + (f"  [{extra}]" if not cond and extra else ""))


def subj(db, name, model):
    q = db.query(Subject).filter(Subject.name == name, Subject.teacher_id.is_(None))
    q = q.filter(Subject.curriculum_model.is_(None)) if model is None else q.filter(Subject.curriculum_model == model)
    return q.first()


def topic(db, s, name):
    return db.query(Topic).filter(Topic.subject_id == s.id, Topic.name == name).first()


with SessionLocal() as db:
    tf = subj(db, "TYT Fizik", None)
    mf = subj(db, "Fizik", CurriculumModel.MAARIF_LISE)
    tk = subj(db, "TYT Kimya", None)
    t_bas = topic(db, tf, "Basınç")
    m_bas = db.query(Topic).filter(Topic.subject_id == mf.id, Topic.name.ilike("Basınç")).first()
    chk("0 veri hazır (TYT + Maarif 'Basınç')", t_bas is not None and m_bas is not None)

    pool_subjects = [mf, tf, tk]
    pool_topics = (db.query(Topic).filter(Topic.subject_id.in_([mf.id, tf.id, tk.id])).all())
    sb = {s.id: s for s in pool_subjects}

    rows = [
        {"topic_id": t_bas.id, "topic_source": "ai"},
        {"topic_id": t_bas.id, "topic_source": "alias"},
        {"topic_id": t_bas.id, "topic_source": "auto"},
    ]
    n = _prefer_school_topics(rows, pool_topics, sb)
    chk("1 AI eşleşmesi okul konusuna çevrildi", rows[0]["topic_id"] == m_bas.id and rows[0]["subject_id"] == mf.id,
        rows[0])
    chk("2 sözlük (koç kararı) eşleşmesine dokunulmaz", rows[1]["topic_id"] == t_bas.id)
    chk("3 deterministik eşleşme de çevrildi + sayaç 2", rows[2]["topic_id"] == m_bas.id and n == 2)

    # saf sınav havuzu → no-op
    rows2 = [{"topic_id": t_bas.id, "topic_source": "ai"}]
    tyt_topics = [t for t in pool_topics if t.subject_id == tf.id]
    _prefer_school_topics(rows2, tyt_topics, {tf.id: tf})
    chk("4 saf TYT havuzunda değişiklik yok", rows2[0]["topic_id"] == t_bas.id)

    # okulda karşılığı olmayan TYT konusu yerinde kalır
    t_only = next(t for t in tyt_topics if t.name not in {x.name for x in pool_topics if x.subject_id == mf.id})
    rows3 = [{"topic_id": t_only.id, "topic_source": "ai"}]
    _prefer_school_topics(rows3, pool_topics, sb)
    chk("5 okulda karşılığı yoksa TYT konusu korunur", rows3[0]["topic_id"] == t_only.id, t_only.name)

    # uçtan uca: normalize_topics (AI kapalı) "Basınç" etiketi + ham ders "Fizik"
    rows4 = [{"subject_raw": "TYT Fizik", "topic_raw": "Basınç"}]
    normalize_topics(db, rows4, universe="tyt", subjects=pool_subjects, topics=pool_topics, use_ai=False)
    chk("6 normalize_topics karma havuzda okul konusunu seçer", rows4[0].get("topic_id") == m_bas.id, rows4[0])
    db.rollback()

print(f"\n{sum(ok)}/{len(ok)} passed")
sys.exit(0 if all(ok) else 1)
