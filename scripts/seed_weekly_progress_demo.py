"""Yerel inceleme için haftalık ilerleme örnek öğrencisi (YALNIZ DEV — start.sh'e eklenmez).

Öğrenci detayı "Haftalık ilerleme" bölümünün tüm parçaları (normal aralık şeritleri,
8 haftalık grafik, eğilim, ders dengesi, deneme analizi) ancak ≥4 geçmiş program
haftası olan öğrencide görünür; yerel veritabanında böyle öğrenci yok. Bu betik
Demo Öğretmen'e (ogretmen@lgs.local) 9 geçmiş + 1 süren haftası olan bir öğrenci kurar.

  python -m scripts.seed_weekly_progress_demo           # kur (varsa yeniden kurar)
  python -m scripts.seed_weekly_progress_demo --delete  # sil
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import date, datetime, time, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Subject, Task, TaskBookItem, Topic, User, UserRole, WeeklyProgram  # noqa: E402
from app.models.exam_result import ExamResult, ExamSection  # noqa: E402
from app.models.student_period import StudentGradePeriod  # noqa: E402
from app.models.task import TaskStatus, TaskType  # noqa: E402
from app.services.security import hash_password  # noqa: E402

EMAIL = "ornek-haftalik@lgs.local"
PWD = "OrnekHafta2026!"
COACH_EMAIL = "ogretmen@lgs.local"
PAST_WEEKS = 9

# Hafta başına (en eskiden yeniye) tamamlama olasılığı; son 3 hafta düşüş → eğilim işareti
RATES = [0.95, 0.9, 0.93, 0.91, 0.94, 0.9, 0.86, 0.82, 0.78]
# Gününde tamamlanmayan (2 gün sonra toplu işaretlenen) pay; son haftalarda artıyor
LATE = [0.05, 0.05, 0.08, 0.05, 0.06, 0.1, 0.15, 0.2, 0.25]
SUBJECTS = ["TYT Matematik", "TYT Türkçe", "TYT Fizik", "TYT Kimya"]


def _tr(d: date, hour: int) -> datetime:
    return datetime.combine(d, time(hour % 24)) + timedelta(days=hour // 24) - timedelta(hours=3)


def delete(db) -> None:
    st = db.query(User).filter(User.email == EMAIL).first()
    if st is None:
        return
    tids = [r[0] for r in db.query(Task.id).filter(Task.student_id == st.id).all()]
    if tids:
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id == st.id))
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
    db.execute(sa_delete(ExamResult).where(ExamResult.student_id == st.id))
    db.execute(sa_delete(Task).where(Task.student_id == st.id))
    db.execute(sa_delete(WeeklyProgram).where(WeeklyProgram.student_id == st.id))
    db.execute(sa_delete(StudentGradePeriod).where(StudentGradePeriod.student_id == st.id))
    db.execute(sa_delete(User).where(User.id == st.id))
    db.commit()


def seed(db) -> int:
    rnd = random.Random(20261020)
    coach = db.query(User).filter(User.email == COACH_EMAIL).first()
    if coach is None:
        raise SystemExit(f"Koç bulunamadı: {COACH_EMAIL}")
    today = date.today()
    cur_start = today - timedelta(days=5)          # bu hafta 6. gün → 5 gün kıyas
    first_start = cur_start - timedelta(days=7 * PAST_WEEKS)

    st = User(email=EMAIL, password_hash=hash_password(PWD), full_name="Örnek Öğrenci (Haftalık İlerleme)",
              role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, institution_id=coach.institution_id,
              grade_level=12, track="SAYISAL", must_change_password=False,
              created_at=datetime.combine(first_start - timedelta(days=3), time(9)))
    db.add(st)
    db.flush()
    db.add(StudentGradePeriod(student_id=st.id, started_on=first_start - timedelta(days=3), grade_level=12,
                              is_graduate=False, track="SAYISAL"))

    topics: dict[str, list[Topic]] = {}
    subj_ids: dict[str, int] = {}
    for name in SUBJECTS:
        sub = db.query(Subject).filter(Subject.name == name, Subject.curriculum_model.is_(None)).first()
        if sub is None:
            raise SystemExit(f"Ders yok: {name} (python -m scripts.seed çalıştır)")
        subj_ids[name] = sub.id
        topics[name] = (db.query(Topic).filter(Topic.subject_id == sub.id, Topic.parent_id.is_(None))
                        .order_by(Topic.order).limit(14).all())

    def add_week(start: date, wi: int | None) -> None:
        db.add(WeeklyProgram(student_id=st.id, coach_id=coach.id, start_date=start,
                             end_date=start + timedelta(days=6), name=None))
        rate = RATES[wi] if wi is not None else 0.62
        late = LATE[wi] if wi is not None else 0.3
        for day in range(7):
            d = start + timedelta(days=day)
            if d.weekday() == 6 and day != 1 and rnd.random() < 0.5:
                continue  # bazı pazarlar boş (deneme günü hariç)
            plan = [("TYT Matematik", 3), ("TYT Matematik", 2), ("TYT Türkçe", 2), ("TYT Fizik", 2)]
            if day % 2 == 0:
                plan.append(("TYT Kimya", 2))
            for order, (sname, n) in enumerate(plan):
                # Kimya son haftalarda bırakılıyor (ders dengesi kartı)
                r = rate - (0.35 if sname == "TYT Kimya" and (wi is None or wi >= 6) else 0)
                done = d < today and rnd.random() < r
                idx = (wi if wi is not None else PAST_WEEKS) + (order % 2)
                topic = topics[sname][min(idx, len(topics[sname]) - 1)]
                hour = 20 + rnd.randint(0, 3)
                if done and rnd.random() < 0.08:
                    hour = 25  # gece 01:00
                when = _tr(d + timedelta(days=2), 21) if done and rnd.random() < late else _tr(d, hour)
                acc = 0.78 if sname != "TYT Kimya" else 0.6
                q = n * 12
                c = int(q * acc + rnd.randint(-3, 3)) if done else None
                b = rnd.randint(0, 4) if done else None
                w = max(0, q - c - b) if done else None
                t = Task(student_id=st.id, date=d, title=f"{sname} · {topic.name}", type=TaskType.TEST,
                         status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, is_draft=False,
                         order=order, completed_at=when if done else None)
                t.book_items = [TaskBookItem(topic_id=topic.id, planned_count=n,
                                             completed_count=n if done else 0,
                                             correct_count=c, wrong_count=w, blank_count=b)]
                db.add(t)
            # Branş denemeleri (programdan; D3 köprüsü Denemeler'e düşürür). Üç ders, üç farklı
            # gidişat: Matematik dalgalı-yatay · Türkçe yükselen · Fizik düşen (analiz sayfası için).
            wk = wi if wi is not None else PAST_WEEKS
            branches = {
                1: ("TYT Matematik", 40, 70, lambda: (rnd.randint(22, 30), rnd.randint(5, 10))),
                3: ("TYT Türkçe", 40, 45, lambda: (min(38, 21 + wk * 2 + rnd.randint(-2, 2)),
                                                   max(2, 12 - wk + rnd.randint(-1, 1)))),
                5: ("TYT Fizik", 14, 25, lambda: (max(3, 11 - wk + rnd.randint(-1, 1)),
                                                  min(9, 2 + wk // 2 + rnd.randint(0, 1)))),
            }
            if day in branches:
                sname, qn, dur, gen = branches[day]
                done = d < today
                c, w = gen() if done else (None, None)
                if done and c + w > qn:
                    w = qn - c
                title = f"{sname} Branş Denemesi"
                t = Task(student_id=st.id, date=d, title=title, type=TaskType.OTHER,
                         status=TaskStatus.COMPLETED if done else TaskStatus.PENDING, is_draft=False, order=9,
                         completed_at=_tr(d, 19) if done else None)
                t.book_items = [TaskBookItem(label=title, planned_count=1,
                                             completed_count=1 if done else 0, exam_kind="brans",
                                             exam_section="tyt", subject_id=subj_ids[sname],
                                             question_count=qn, duration_minutes=dur if done else None,
                                             correct_count=c, wrong_count=w,
                                             blank_count=(qn - c - w) if done else None)]
                db.add(t)

    for i in range(PAST_WEEKS):
        add_week(first_start + timedelta(days=7 * i), i)
    add_week(cur_start, None)

    # Karne/elle genel deneme (deneme neti kartı) — gerçek TYT ders kırılımı, toplamlar tutarlı
    tyt = [("TYT Türkçe", 40), ("TYT Tarih", 5), ("TYT Coğrafya", 5), ("TYT Felsefe", 5),
           ("TYT Din Kültürü ve Ahlak Bilgisi", 5), ("TYT Matematik", 30), ("TYT Geometri", 10),
           ("TYT Fizik", 7), ("TYT Kimya", 7), ("TYT Biyoloji", 6)]
    for k, (back, ratio) in enumerate([(48, 0.66), (27, 0.71), (6, 0.69)]):
        rows, tc, tw, tb = [], 0, 0, 0
        for name, q in tyt:
            c = min(q, max(0, round(q * ratio) + rnd.randint(-1, 1)))
            b = min(q - c, rnd.randint(0, 2))
            w = q - c - b
            rows.append({"name": name, "correct": c, "wrong": w, "blank": b, "net": round(c - w / 4, 2)})
            tc, tw, tb = tc + c, tw + w, tb + b
        db.add(ExamResult(student_id=st.id, created_by_id=coach.id, title=f"TYT Genel Deneme {k + 1}",
                          exam_date=today - timedelta(days=back), section=ExamSection.TYT,
                          total_correct=tc, total_wrong=tw, total_blank=tb, net=round(tc - tw / 4, 2),
                          subject_nets=json.dumps(rows, ensure_ascii=False)))
    db.commit()
    # Köprü yalnız sonradan girilen sonucu eşitler; burada kalemler sonuçlu doğduğu için elle çağrılır.
    from app.services import deneme_bridge
    for it in (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
               .filter(Task.student_id == st.id, TaskBookItem.exam_kind.isnot(None)).all()):
        deneme_bridge.sync_item(db, it)
    db.commit()
    return st.id


def main() -> None:
    db = SessionLocal()
    try:
        delete(db)
        if "--delete" in sys.argv:
            print("Silindi.")
            return
        sid = seed(db)
        print(f"Kuruldu: öğrenci #{sid} — http://localhost:3000/teacher/students/{sid}")
        print(f"Koç girişi: {COACH_EMAIL} · öğrenci girişi: {EMAIL} / {PWD}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
