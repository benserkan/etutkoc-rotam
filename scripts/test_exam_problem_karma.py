"""TYT Matematik "Problemler (Karma)" — geniş karne etiketi tek konuya bağlanır.

Zeynep Ela #169 (Özdebir): "Denklemler ve eşitsizlikler ile ilgili problemler
çözer." etiketli 12 soru hiçbir konuya bağlanmıyordu (2026-10-02).
"""
import sys

sys.path.insert(0, ".")
from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Topic  # noqa: E402
from app.services import exam_import_service as svc  # noqa: E402
from app.services.curriculum_mapping import _label_key, _topic_key  # noqa: E402

ok = []


def chk(label, cond):
    ok.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + label)


LABEL = "Denklemler ve eşitsizlikler ile ilgili problemler çözer."
chk("etiket anahtarı = problemler", _label_key(LABEL) == "problemler")
chk("konu anahtarı = problemler", _topic_key("Problemler (Karma)") == "problemler")
chk("yaş problemleri ayrı kalır", _label_key("Yaş Problemleri") != "problemler")

with SessionLocal() as db:
    s = db.query(Subject).filter(Subject.name == "TYT Matematik",
                                 Subject.curriculum_model.is_(None)).first()
    topics = db.query(Topic).filter(Topic.subject_id == s.id).all()
    names = [t.name for t in topics]
    chk("TYT Matematik'te Problemler (Karma) var", "Problemler (Karma)" in names)
    rows = [{"subject_raw": "MATEMATİK", "question_no": i, "topic_raw": LABEL,
             "result": "dogru"} for i in range(1, 4)]
    rows.append({"subject_raw": "MATEMATİK", "question_no": 9,
                 "topic_raw": "Yaş Problemleri", "result": "dogru"})
    stats = svc.normalize_topics(db, rows, universe="tyt", subjects=[s], topics=topics,
                                 use_ai=False) if "use_ai" in svc.normalize_topics.__code__.co_varnames \
        else svc.normalize_topics(db, rows, universe="tyt", subjects=[s], topics=topics)
    by_id = {t.id: t.name for t in topics}
    got = [by_id.get(r.get("topic_id")) for r in rows]
    chk("3 geniş etiket -> Problemler (Karma)", got[:3] == ["Problemler (Karma)"] * 3)
    chk("Yaş Problemleri kendi konusunda", got[3] == "Yaş Problemleri")
    db.rollback()

print(f"\n=== {sum(ok)} passed, {len(ok) - sum(ok)} failed ===")
sys.exit(0 if all(ok) else 1)
