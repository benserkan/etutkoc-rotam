"""exam_scope — genel deneme / branş denemesi ayrımı (2026-10-06).

DB'siz birim testi + rapor/puan tahmini entegrasyonu (geçici öğrenci).
  PYTHONPATH=. python scripts/test_exam_scope.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import ExamResult, User  # noqa: E402
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.services import exam_scope  # noqa: E402

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {extra}")


def mk(title, section, c, w, b, subjects=None, meta=None, d=None, sid=0):
    return ExamResult(
        student_id=sid, title=title, section=section,
        exam_date=d or date.today(), total_correct=c, total_wrong=w, total_blank=b,
        net=round(max(c - w / (3 if section == ExamSection.LGS else 4), 0), 2),
        subject_nets=json.dumps(subjects, ensure_ascii=False) if subjects else None,
        analysis_meta=json.dumps(meta) if meta else None,
    )


LGS_FULL = [{"name": n, "correct": 8, "wrong": 2, "blank": q - 10, "net": 7}
            for n, q in (("Türkçe", 20), ("Matematik", 20), ("Fen Bilimleri", 20),
                         ("T.C. İnkılap Tarihi", 10), ("Din Kültürü", 10), ("İngilizce", 10))]

print("== birim")
g = mk("LGS Genel Deneme 1", ExamSection.LGS, 60, 15, 15, LGS_FULL)
check("90 soruluk LGS → genel", exam_scope.classify(g) == "genel")
check("genel seri anahtarı = tür", exam_scope.series_key(g) == "lgs")
b = mk("LGS DENEME SINAVI - 3", ExamSection.LGS, 12, 4, 4,
       [{"name": "Matematik", "correct": 12, "wrong": 4, "blank": 4, "net": 10.67}])
check("20 soruluk tek ders → branş", exam_scope.classify(b) == "brans")
check("branş dersi Matematik", exam_scope.exam_scope(b).subject == "Matematik")
check("branş seri anahtarı lgs~matematik", exam_scope.series_key(b) == "lgs~matematik",
      exam_scope.series_key(b))
t = mk("Matematik Branş Denemesi 1", ExamSection.LGS, 15, 5, 5)
check("başlıkta 'branş' → branş, ders başlıktan", exam_scope.exam_scope(t).subject == "Matematik")
a = mk("KAL KDS 11.SINIF (MATEMATİK)", ExamSection.AYT_SAY, 20, 10, 10,
       [{"name": "AYT Matematik", "correct": 15, "wrong": 8, "blank": 7, "net": 13},
        {"name": "AYT Geometri", "correct": 5, "wrong": 2, "blank": 3, "net": 4.5}])
check("AYT 40 soru Mat+Geo → tek Matematik branşı", exam_scope.exam_scope(a).subject == "Matematik",
      exam_scope.exam_scope(a).subject)
tyt = mk("10 SINIF GİS-1", ExamSection.TYT, 50, 20, 30)
check("TYT 100 soru → genel", exam_scope.classify(tyt) == "genel")
f = mk("Genel ama kısa", ExamSection.LGS, 10, 5, 5, meta={"scope": "genel"})
check("koç işareti (genel) sınırı ezer", exam_scope.classify(f) == "genel")
f2 = mk("LGS Genel Deneme 2", ExamSection.LGS, 60, 15, 15, LGS_FULL, meta={"scope": "brans"})
check("koç işareti (branş) sınırı ezer", exam_scope.classify(f2) == "brans")
ok = mk("Okul yazılı", ExamSection.OKUL, 8, 2, 0,
        [{"name": "Fizik", "correct": 8, "wrong": 2, "blank": 0, "net": 7.5}])
check("standart yok + tek ders → branş", exam_scope.classify(ok) == "brans")
opts = exam_scope.series_options([b, g, t, g])
check("seçeneklerde genel önce", opts[0]["value"] == "lgs" and opts[0]["kind"] == "genel")
check("eski istemci section=lgs → genel seri", exam_scope.resolve_series("lgs", opts) == "lgs")
check("yalnız branş varken section=lgs → branş serisi",
      exam_scope.resolve_series("lgs", exam_scope.series_options([b])) == "lgs~matematik")

print("== entegrasyon (rapor + puan tahmini)")
db = SessionLocal()
email = "scope-test-ogrenci@etutkoc.test"
for u in db.query(User).filter(User.email == email).all():
    db.query(ExamResult).filter(ExamResult.student_id == u.id).delete()
    db.delete(u)
db.commit()
st = User(email=email, full_name="Kapsam Test", role=UserRole.STUDENT, password_hash="x",
          is_active=True, grade_level=8)
db.add(st)
db.commit()
try:
    base = date.today() - timedelta(days=20)
    rows = [
        mk("LGS Genel Deneme 1", ExamSection.LGS, 55, 15, 20, LGS_FULL, d=base, sid=st.id),
        mk("Matematik Branş 1", ExamSection.LGS, 12, 4, 4,
           [{"name": "Matematik", "correct": 12, "wrong": 4, "blank": 4, "net": 10.67}],
           d=base + timedelta(days=5), sid=st.id),
        mk("LGS Genel Deneme 2", ExamSection.LGS, 62, 12, 16, LGS_FULL, d=base + timedelta(days=10), sid=st.id),
        mk("Matematik Branş 2", ExamSection.LGS, 14, 3, 3,
           [{"name": "Matematik", "correct": 14, "wrong": 3, "blank": 3, "net": 13}],
           d=base + timedelta(days=15), sid=st.id),
    ]
    db.add_all(rows)
    db.commit()
    from app.services.exam_progress import build_progress_report
    rep = build_progress_report(db, st, section="lgs", period="all")
    check("rapor varsayılan: genel seri, 2 deneme", rep["series"] == "lgs" and len(rep["exams"]) == 2,
          f"{rep['series']} {len(rep['exams'])}")
    check("genel seride değişim +7 (55→62 doğru netiyle)",
          rep["stats"]["last_net"] > rep["stats"]["first_net"])
    check("seçenekler: genel + Matematik branş", [o["value"] for o in rep["section_options"]]
          == ["lgs", "lgs~matematik"], rep["section_options"])
    rb = build_progress_report(db, st, section="lgs~matematik", period="all")
    check("branş seri: 2 deneme, hedef kapalı", len(rb["exams"]) == 2 and rb["target_allowed"] is False)
    from app.services import exam_faz3
    est = exam_faz3.score_estimate(db, st)
    check("puan tahmini genel denemeden", est["inputs"] and est["inputs"][0]["title"] == "LGS Genel Deneme 2",
          est["inputs"])
    from app.services.exam_parent_summary import _previous_same_section
    prev = _previous_same_section(db, rows[3])
    check("veli kıyası: branşın öncesi branş", prev is not None and prev.title == "Matematik Branş 1",
          prev.title if prev else None)
    prev2 = _previous_same_section(db, rows[2])
    check("veli kıyası: genelin öncesi genel", prev2 is not None and prev2.title == "LGS Genel Deneme 1")
finally:
    db.query(ExamResult).filter(ExamResult.student_id == st.id).delete()
    db.delete(st)
    db.commit()
    db.close()

print(f"\n  Sonuç: {PASS} PASS / {FAIL} FAIL")
sys.exit(1 if FAIL else 0)
