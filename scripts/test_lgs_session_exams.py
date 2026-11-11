"""LGS tek oturum karneleri (sözel 50 / sayısal 40) — 2026-11-11 Beril testi sonrası.

  1. Ders adı varyasyonları ("Din", "DKAB", "TÜR", "Tarih", "İNG", "Fen Bilimleri") tek anahtara iner
  2. Sözel/sayısal oturum kendi serisi ("LGS Sözel" / "LGS Sayısal"); branş ya da genel değil
  3. Tam LGS (90 soru, 6 ders) genel kalır; yalnız Türkçe → branş; koç "genel" derse genel
  4. Program denemesi tek satır "Sayısal bölüm" → aynı "LGS Sayısal" serisi
  5. Mükerrer: aynı ad+tarih ama ders kümesi örtüşmüyorsa mükerrer DEĞİL; aynı oturum ise uyarı
  6. Karne puanı doğrulaması: nete eşit / aralık dışı → işaretli (reddedilmez)
  7. Liste özeti: tam deneme yokken sözel+sayısal birlikte ortalanmaz; ders bazlı ilerleme döner
  8. Genel sekmesi: tam deneme yokken oturumları söyleyen not
  9. Tür seçici: 8. sınıfa TYT/AYT gösterilmez
 10. Tür tespiti: 50 soruluk sözel karne LGS, yüksek güven
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
from app.models import User, UserRole  # noqa: E402
from app.models.exam_result import ExamResult, ExamSection  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.routes.api_v2.teacher import exam_list_summary  # noqa: E402
from app.services import exam_duplicate, exam_scope  # noqa: E402
from app.services.exam_import_jobs import section_choices  # noqa: E402
from app.services.exam_import_service import _check_score, detect_universe  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.student_overview import exam_overview  # noqa: E402

PFX = f"lgss_{secrets.token_hex(3)}"
passed, failed, uids = 0, [], []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


SOZEL = [("Türkçe", 19, 1), ("T.C. İnkılap Tarihi ve Atatürkçülük", 9, 1),
         ("Din Kültürü ve Ahlak Bilgisi", 8, 2), ("İngilizce", 10, 0)]
SAYISAL = [("Matematik", 19, 1), ("Fen Bilimleri", 17, 3)]


def nets(rows):
    return json.dumps([{"name": n, "correct": c, "wrong": w, "blank": 0, "net": round(c - w / 3, 2)}
                       for n, c, w in rows], ensure_ascii=False)


def mk(db, sid, title, rows, d, meta=None):
    c = sum(r[1] for r in rows)
    w = sum(r[2] for r in rows)
    e = ExamResult(student_id=sid, title=title, exam_date=d, section=ExamSection.LGS,
                   total_correct=c, total_wrong=w, total_blank=0, net=round(c - w / 3, 2),
                   subject_nets=nets(rows), analysis_meta=json.dumps(meta or {}))
    db.add(e)
    db.flush()
    return e


def main():
    today = date.today()
    print("— 1. Ders adı varyasyonları")
    k = exam_scope.lgs_subject_key
    for name, exp in [("Din", "din"), ("Din K.ve A.B.", "din"), ("DKAB", "din"), ("TÜR", "turkce"),
                      ("Tarih", "inkilap"), ("İnkılap", "inkilap"), ("İNG", "ingilizce"),
                      ("Yabancı Dil", "ingilizce"), ("MAT", "matematik"), ("Fen Bilimleri", "fen"),
                      ("FEN", "fen"), ("Biyoloji", None)]:
        check(f"  {name} → {exp}", k(name) == exp, k(name))
    s = exam_scope.lgs_session_of_subjects
    check("sözel varyantlı küme", s(["TÜR", "Tarih", "Din", "İNG"]) == "sozel")
    check("İngilizcesiz sözel (3 ders) de oturum", s(["Türkçe", "İnkılap", "DKAB"]) == "sozel")
    check("Mat+Fen sayısal", s(["MAT", "Fen"]) == "sayisal")
    check("yalnız Türkçe oturum değil", s(["Türkçe"]) is None)
    check("karışık küme oturum değil", s(["Türkçe", "Matematik"]) is None)
    check("tanınmayan ders → karar yok", s(["Matematik", "Fen", "Biyoloji"]) is None)

    with SessionLocal() as db:
        st = User(email=f"{PFX}@test.invalid", password_hash=hash_password("x"), full_name="Öğr",
                  role=UserRole.STUDENT, is_active=True, grade_level=8, must_change_password=False)
        db.add(st)
        db.flush()
        uids.append(st.id)
        d0 = today - timedelta(days=1)

        print("— 2-4. Seriler")
        soz = mk(db, st.id, "6 SON VİRAJ", SOZEL, d0)
        say = mk(db, st.id, "6 SON VİRAJ", SAYISAL, d0)
        a, b = exam_scope.exam_scope(soz), exam_scope.exam_scope(say)
        check("sözel → LGS Sözel serisi", (a.series_key, a.series_label, a.session) == ("lgs~sozel", "LGS Sözel", "sozel"), a)
        check("sayısal → LGS Sayısal serisi", (b.series_key, b.series_label) == ("lgs~sayisal", "LGS Sayısal"), b)
        check("oturum genel değil (gidişata girmez)", exam_scope.classify(soz) != "genel")
        full = mk(db, st.id, "Tam LGS", SOZEL + SAYISAL, today - timedelta(days=20))
        check("tam LGS genel kalır", exam_scope.exam_scope(full).series_key == "lgs")
        tr = mk(db, st.id, "Türkçe branş", [("Türkçe", 15, 5)], today - timedelta(days=15))
        check("yalnız Türkçe → branş", exam_scope.exam_scope(tr).series_key == "lgs~türkçe")
        forced = mk(db, st.id, "Koç genel dedi", SOZEL, today - timedelta(days=30), {"scope": "genel"})
        check("koç 'genel' işaretlediyse genel", exam_scope.classify(forced) == "genel")
        prog = ExamResult(student_id=st.id, title="LGS Sayısal Bölüm · 1. deneme", exam_date=d0,
                          section=ExamSection.LGS, total_correct=30, total_wrong=6, total_blank=4, net=28,
                          subject_nets=json.dumps([{"name": "Sayısal bölüm", "correct": 30, "wrong": 6,
                                                    "blank": 4, "net": 28}]), import_source="task")
        db.add(prog)
        db.flush()
        check("program denemesi 'Sayısal bölüm' → LGS Sayısal", exam_scope.series_key(prog) == "lgs~sayisal")
        db.delete(prog); db.delete(tr); db.delete(forced)
        db.commit()

        print("— 5. Mükerrer")
        rows_say = [{"subject_raw": n} for n, *_ in SAYISAL]
        dup = exam_duplicate.find_duplicate(db, st.id, section="lgs", rows=rows_say,
                                            title="6 SON VİRAJ", exam_date=d0, exclude_exam_id=say.id)
        check("sayısal ↔ sözel aynı ad+tarih → mükerrer DEĞİL", dup is None, dup)
        rows_soz = [{"subject_raw": n} for n in ("TÜR", "Tarih", "Din", "İNG")]
        dup2 = exam_duplicate.find_duplicate(db, st.id, section="lgs", rows=rows_soz,
                                             title="6 SON VİRAJ", exam_date=d0, exclude_exam_id=say.id)
        check("ikinci kez sözel (varyant adlarla) → mükerrer uyarısı", dup2 is not None and dup2.exam_id == soz.id, dup2)
        dup3 = exam_duplicate.find_duplicate(db, st.id, section="lgs", title="6 SON VİRAJ", exam_date=d0,
                                             subjects={"matematik", "fen"}, exclude_exam_id=say.id)
        check("elle giriş (ders listesi) de aynı kural", dup3 is None, dup3)

        print("— 6. Puan doğrulaması")
        subs = [{"net": 44.67}]
        ck: list = []
        i1 = _check_score({"score": 44.67}, subs, "lgs", ck)
        check("nete eşit puan işaretli, reddedilmez", i1 and i1.get("score_issue") and i1.get("score") == 44.67)
        check("kontrol listesine düşer", any(c["code"] == "score_suspect" and not c["ok"] for c in ck))
        ck2: list = []
        check("geçerli LGS puanı işaretsiz", "score_issue" not in (_check_score({"score": 465.63}, subs, "lgs", ck2) or {}) and not ck2)
        check("aralık dışı (600) işaretli", "score_issue" in _check_score({"score": 600}, subs, "lgs", []))
        check("okul sınavında aralık kontrolü yok", "score_issue" not in _check_score({"score": 85}, subs, "okul", []))

        print("— 7. Liste özeti")
        db.delete(full)
        db.commit()
        soz2 = mk(db, st.id, "Sözel 2", [("Türkçe", 17, 3), ("İnkılap", 8, 2), ("Din", 9, 1), ("İngilizce", 9, 1)], today)
        exams = (db.query(ExamResult).filter(ExamResult.student_id == st.id)
                 .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc()).all())
        sm = exam_list_summary(exams)
        check("özet en çok denemesi olan seriden (LGS Sözel, 2)", sm.series_label == "LGS Sözel" and sm.series_count == 2,
              (sm.series_label, sm.series_count))
        check("sayısal net ortalamaya karışmaz", abs(sm.avg_net - round((44.67 + soz2.net) / 2, 2)) < 0.02, sm.avg_net)
        names = {x["name"]: x for x in sm.subject_progress}
        check("ders bazlı ilerleme: Türkçe 18,67 → 16", names.get("Türkçe", {}).get("change") == -2.67,
              names.get("Türkçe"))
        check("Matematik tek kayıt (değişim yok)", names.get("Matematik", {}).get("change") is None
              and names.get("Matematik", {}).get("count") == 1, names.get("Matematik"))

        print("— 8. Genel sekmesi notu")
        ov = exam_overview(db, st, today)
        check("tam deneme yokken gidişat satırı yok", ov["exams"] == [])
        check("not oturumları sayar", "LGS Sözel 2 deneme" in (ov["exam_note"] or "")
              and "LGS Sayısal 1 deneme" in (ov["exam_note"] or ""), ov["exam_note"])

        print("— 9. Tür seçici")
        vals = {c["value"] for c in section_choices(st, keep="lgs")}
        check("8. sınıf: LGS var, TYT/AYT yok", "lgs" in vals and "tyt" not in vals and "ayt_say" not in vals, vals)

        print("— 10. Tür tespiti")
        read = {"questions": [{"subject": n} for n, c, w in SOZEL for _ in range(c + w)],
                "type_hints": [], "exam_title": "6 SON VİRAJ GERİ SAYIM", "grade_hint": 8}
        det = detect_universe(read, st)
        check("sözel 50 soru → LGS yüksek güven + oturum", det["universe"] == "lgs" and det["confidence"] == "high"
              and det.get("session") == "sozel", det)


def cleanup():
    with SessionLocal() as db:
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(uids)))
        db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(uids)))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    sys.exit(1 if failed else 0)
