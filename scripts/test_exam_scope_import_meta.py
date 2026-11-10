"""AYT tam denemesi "Matematik + Fizik branş" görünüyordu — regresyon (2026-11-10, Emir #113).

Kök neden: PDF içe aktarma kapsam TAHMİNİNİ (ham ders sayısı ≤ 2 → "brans"; AYT Sayısal kitapçığı
yalnız AYT-MAT + AYT-FEN iki bölüm) analysis_meta["scope"]'a yazıyordu; aynı anahtar koçun
genel/branş kararıdır → tahmin koç kararı sanıldı.
  1. Eski kayıt (imported_at + scope=brans, koç işareti yok) → 80 soru → GENEL, "AYT Sayısal" serisi
  2. Koç işaretlediyse (scope_by=coach) → branş kararı geçerli
  3. Elle girilen kayıtta (imported_at yok) eski davranış: scope esas
  4. AYT konu analizinde TYT taksonomisinden eşleşen konunun dersi AYT adıyla ("TYT Biyoloji" → "AYT Biyoloji")
  5. Ders × deneme tablosunda konusu bağlanmayan satır işaretli ("Fen Bilimleri")
"""
from __future__ import annotations

import json
import os
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Topic, User, UserRole  # noqa: E402
from app.models.exam_result import ExamResult, ExamResultQuestion, ExamSection  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.services import exam_scope  # noqa: E402
from app.services.exam_overview import build_exam_overview  # noqa: E402
from app.services.exam_topic_analysis import build_exam_topic_analysis  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"esm_{secrets.token_hex(3)}"
passed = 0
failed: list[str] = []
uids: list[int] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def subj_nets():
    return json.dumps([
        {"name": "AYT Matematik", "correct": 25, "wrong": 2, "blank": 4, "net": 24.5},
        {"name": "AYT Geometri", "correct": 7, "wrong": 1, "blank": 1, "net": 6.75},
        {"name": "AYT Fizik", "correct": 13, "wrong": 0, "blank": 0, "net": 13},
        {"name": "Fen Bilimleri", "correct": 1, "wrong": 0, "blank": 0, "net": 1, "unmatched": True},
        {"name": "AYT Kimya", "correct": 9, "wrong": 3, "blank": 1, "net": 8.25},
        {"name": "AYT Biyoloji", "correct": 11, "wrong": 2, "blank": 0, "net": 10.5},
    ], ensure_ascii=False)


def make_exam(db, sid, meta: dict, source: str | None = "pdf_import") -> ExamResult:
    e = ExamResult(student_id=sid, created_by_id=sid, title="ÖZDEBİR 2027 Türkiye Geneli AYT-1",
                   exam_date=date.today() - timedelta(days=2), section=ExamSection.AYT_SAY,
                   total_correct=66, total_wrong=8, total_blank=6, net=64,
                   subject_nets=subj_nets(), import_source=source,
                   analysis_meta=json.dumps(meta, ensure_ascii=False))
    db.add(e); db.flush()
    return e


def main():
    with SessionLocal() as db:
        st = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password("x"), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, grade_level=None, is_graduate=True,
                  track="SAYISAL", must_change_password=False)
        db.add(st); db.flush()
        uids.append(st.id)

        print("— 1-3. Kapsam")
        legacy = make_exam(db, st.id, {"universe": "ayt", "scope": "brans", "imported_at": "2026-11-08T08:00:00"})
        sc = exam_scope.exam_scope(legacy)
        check("eski içe aktarma tahmini koç kararı sayılmaz → genel", sc.kind == "genel", sc)
        check("seri etiketi AYT alan adıyla, branş değil", "branş" not in sc.series_label
              and sc.series_key == "ayt_say", sc.series_label)

        coach = make_exam(db, st.id, {"scope": "brans", "scope_by": "coach", "imported_at": "2026-11-08T08:00:00"})
        check("koçun branş işareti geçerli", exam_scope.classify(coach) == "brans")

        manual = make_exam(db, st.id, {"scope": "brans"}, source=None)
        check("elle girilen kayıtta işaret eskisi gibi esas", exam_scope.classify(manual) == "brans")

        new_imp = make_exam(db, st.id, {"universe": "ayt", "import_scope": "brans", "imported_at": "2026-11-10T08:00:00"})
        check("yeni içe aktarma tahmini 'import_scope' anahtarında, sınıflamaya karışmaz",
              exam_scope.classify(new_imp) == "genel")
        db.delete(coach); db.delete(manual); db.delete(new_imp); db.flush()

        print("— 4. AYT konu analizinde ders adı")
        tyt_bio = db.query(Subject).filter(Subject.name == "TYT Biyoloji").first()
        ayt_bio = db.query(Subject).filter(Subject.name == "AYT Biyoloji").first()
        t_tyt = db.query(Topic).filter(Topic.subject_id == tyt_bio.id).first() if tyt_bio else None
        t_ayt = db.query(Topic).filter(Topic.subject_id == ayt_bio.id).first() if ayt_bio else None
        check("taksonomide TYT/AYT Biyoloji konusu var", t_tyt is not None and t_ayt is not None)
        if t_tyt and t_ayt:
            for i, (tp, res) in enumerate([(t_tyt, "yanlis"), (t_tyt, "yanlis"), (t_ayt, "dogru")]):
                db.add(ExamResultQuestion(exam_result_id=legacy.id, question_no=i + 1,
                                          subject_name_raw="Fen Bilimleri", topic_label_raw=tp.name,
                                          topic_id=tp.id, result=res))
            db.commit()
            ta = build_exam_topic_analysis(db, st, section="ayt_say")
            names = {t["subject_name"] for t in ta["topics"]}
            check("TYT taksonomisinden eşleşen konu AYT ders adıyla", "TYT Biyoloji" not in names
                  and "AYT Biyoloji" in names, names)

        print("— 5. Konusu bağlanmayan ders satırı")
        db.commit()
        ov = build_exam_overview(db, st, series="ayt_say")
        rows = {r["name"]: r for r in (ov.get("subjects") or [])}
        fen = rows.get("Fen Bilimleri")
        check("'Fen Bilimleri' satırı işaretli", fen is not None and fen.get("unmatched") is True, list(rows))
        check("okuma metni 'konusu bağlanmadı' der", fen is not None and "bağlanmadı" in (fen.get("reading") or ""))
        check("eşleşmiş ders satırı işaretsiz", rows.get("Fizik", {}).get("unmatched") is False, list(rows))


def cleanup():
    if not uids:
        return
    with SessionLocal() as db:
        ids = [e for (e,) in db.query(ExamResult.id).filter(ExamResult.student_id.in_(uids)).all()]
        if ids:
            db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_(ids)))
            db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(ids)))
        db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    if failed:
        sys.exit(1)
