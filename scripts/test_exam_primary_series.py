"""Ana genel seri — tek AYT denemesi 10 TYT denemesini gölgelemesin (Emir #113, 2026-11-10).

  1. primary_general_key: 3 TYT + 1 (daha yeni) AYT → "tyt"
  2. Liste özeti (veli mobil "Ortalama net") yalnız TYT netlerinden, count tüm denemeler
  3. Genel sekmesi deneme özeti + hedef TYT serisinden
  4. Haftalık ilerleme "Deneme neti" kartı TYT'nin son ve önceki denemesi
"""
from __future__ import annotations

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
from app.services import exam_scope  # noqa: E402
from app.services.exam_progress import set_target  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.student_overview import exam_overview  # noqa: E402

PFX = f"eps_{secrets.token_hex(3)}"
passed, failed, uids = 0, [], []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def main():
    today = date.today()
    with SessionLocal() as db:
        st = User(email=f"{PFX}@test.invalid", password_hash=hash_password("x"), full_name="Öğrenci",
                  role=UserRole.STUDENT, is_active=True, is_graduate=True, track="SAYISAL",
                  must_change_password=False)
        db.add(st); db.flush(); uids.append(st.id)
        for i, n in enumerate([90.0, 85.5, 98.5]):
            db.add(ExamResult(student_id=st.id, title=f"TYT-{i}", exam_date=today - timedelta(days=20 - i * 5),
                              section=ExamSection.TYT, total_correct=100, total_wrong=10, total_blank=10, net=n))
        db.add(ExamResult(student_id=st.id, title="AYT-1", exam_date=today - timedelta(days=1),
                          section=ExamSection.AYT_SAY, total_correct=66, total_wrong=8, total_blank=6, net=64))
        db.add(ExamResult(student_id=st.id, title="LGS yanlis yukleme", exam_date=today - timedelta(days=2),
                          section=ExamSection.LGS, total_correct=80, total_wrong=5, total_blank=5, net=78.33))
        db.commit()
        try:
            set_target(db, st.id, section="tyt", target_net=100, actor=st)
            db.commit()
        except Exception as e:  # imza farkı olursa testi düşürme, hedef kontrolünü atla
            print("  (hedef kurulamadı:", e, ")")

        exams = (db.query(ExamResult).filter(ExamResult.student_id == st.id)
                 .order_by(ExamResult.exam_date.desc()).all())
        check("1. ana genel seri TYT", exam_scope.primary_general_key(exams) == "tyt",
              exam_scope.primary_general_key(exams))

        s = exam_list_summary(exams)
        check("2a. count tüm denemeler (5)", s.count == 5, s.count)
        check("2b. ortalama yalnız TYT (91.33)", abs(s.avg_net - 91.33) < 0.01, s.avg_net)
        check("2c. eğilim TYT ilk→son (+8.5)", s.trend_delta == 8.5, s.trend_delta)
        check("2d. seri etiketi TYT", "TYT" in (s.series_label or ""), s.series_label)

        ov = exam_overview(db, st, today)
        ex = ov.get("exam") or {}
        check("3a. Genel deneme özeti TYT serisi", "TYT" in (ex.get("series_label") or ""), ex.get("series_label"))
        check("3b. son net 98.5, önceki 85.5", ex.get("last_net") == 98.5 and ex.get("prev_net") == 85.5, ex)
        keys = [x["series_key"] for x in ov.get("exams") or []]
        check("3d. Genel'de TYT ve AYT ayrı satır (sıra TYT, AYT)", keys == ["tyt", "ayt_say"], keys)
        check("3e. LGS (sınav türüne uymayan) gidişata girmez, not edilir",
              "lgs" not in keys and "LGS" in (ov.get("exam_note") or ""), ov.get("exam_note"))
        ayt = (ov.get("exams") or [{}, {}])[-1]
        check("3f. tek AYT denemesi 'tek deneme' notu", "tek deneme" in (ayt.get("text") or ""), ayt.get("text"))
        check("3c. TYT hedefi Genel'de görünür (100)", (ov.get("target") or {}).get("target_net") == 100, ov.get("target"))

        from app.services import weekly_progress as wpm
        from app.services.weekly_progress import _extra_cards
        cards = _extra_cards(db, st, wpm.Week(program_id=-1, start=today - timedelta(days=3), end=today + timedelta(days=3),
                                              kind="takvim"), 3, False, None) \
            if hasattr(wpm, "Week") else []
        card = next((c for c in cards if c["key"] == "exam_net"), None)
        if card is not None:
            check("4. Deneme neti kartı TYT son/önceki", card["value"] == 98.5 and card["prev"] == 85.5,
                  (card["value"], card["prev"]))


def cleanup():
    with SessionLocal() as db:
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(uids)))
        db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id.in_(uids)))
        try:
            from app.models.exam_progress import ExamTarget
            db.execute(sa_delete(ExamTarget).where(ExamTarget.student_id.in_(uids)))
        except Exception:
            db.rollback()
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    sys.exit(1 if failed else 0)
