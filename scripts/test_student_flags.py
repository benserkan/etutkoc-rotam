"""Bayrak motoru (student_flags) — her bayrak + hiyerarşi + veli görünürlüğü (2026-09-29).

Her senaryo bayrağın ÇIKMASI ve ÇIKMAMASI gereken durumu birlikte sınar.
Desenler prod'daki gerçek öğrencilerden: Boran (program bitti + 4 gün boş),
Taha (AYT Kimya'dan kaçınma), Emir (toplu işaretleme), Zeynep (her gün tam).
"""
from __future__ import annotations

import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Book, BookSection, BookType, SectionProgress, StudentBook, Subject,
    Task, TaskBookItem, TaskStatus, TaskType, User, UserRole,
)
from app.models.exam_result import ExamResult, ExamSection
from app.services import analytics
from app.services.risk_analysis import compute_risk_score
from app.services.security import hash_password
from app.services.student_flags import evaluate_flags

PFX = f"sfl_{secrets.token_hex(3)}"
today = date.today()
now = datetime.now(timezone.utc)
ids = {"users": [], "books": [], "subjects": []}
coach = 0
passed = 0
failed: list[str] = []

# Gün içi bayrak saate bağlı; testler öğlen 12:00'de çalışıyormuş gibi
analytics._tr_now = lambda: datetime.combine(today, time(12, 0), tzinfo=timezone.utc)


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def student(tag, *, age=40, seen_days=0):
    with SessionLocal() as db:
        s = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password("x"),
                 full_name=f"{PFX} {tag}", role=UserRole.STUDENT, teacher_id=coach,
                 grade_level=12, is_active=True, created_at=now - timedelta(days=age),
                 last_login_at=now - timedelta(days=seen_days),
                 last_seen_at=now - timedelta(days=seen_days))
        db.add(s)
        db.commit()
        ids["users"].append(s.id)
        return s.id


def book(name, btype=BookType.SORU_BANKASI):
    with SessionLocal() as db:
        sub = Subject(name=f"{PFX} {name}", teacher_id=coach)
        db.add(sub)
        db.flush()
        b = Book(teacher_id=coach, subject_id=sub.id, name=f"{PFX} {name} K", type=btype)
        db.add(b)
        db.flush()
        sec = BookSection(book_id=b.id, label="Ü1", test_count=200)
        db.add(sec)
        db.commit()
        ids["subjects"].append(sub.id)
        ids["books"].append(b.id)
        return sub.id, b.id, sec.id


def task(sid, day, bk, done, *, draft=False, done_at=None, dy=True):
    b, sec = bk
    with SessionLocal() as db:
        t = Task(student_id=sid, date=day, type=TaskType.TEST, title=f"T{day}", is_draft=draft,
                 published_at=None if draft else now,
                 status=TaskStatus.COMPLETED if done else TaskStatus.PENDING,
                 completed_at=(done_at or datetime.combine(day, time(18, 0), tzinfo=timezone.utc)) if done else None)
        db.add(t)
        db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=b, book_section_id=sec, planned_count=2,
                            completed_count=2 if done else 0,
                            correct_count=(2 if (done and dy) else None), wrong_count=0 if (done and dy) else None))
        db.commit()


def activity(sid, day, done):
    with SessionLocal() as db:
        db.add(Task(student_id=sid, date=day, type=TaskType.OTHER, title="Video", is_draft=False,
                    published_at=now, status=TaskStatus.COMPLETED if done else TaskStatus.PENDING,
                    completed_at=datetime.combine(day, time(18, 0), tzinfo=timezone.utc) if done else None))
        db.commit()


def report(sid):
    with SessionLocal() as db:
        s = db.get(User, sid)
        proj = analytics.compute_projection(db, s, today, window_days=28, buffer_days=5)
        r = evaluate_flags(db, s, today, proj)
        return r, {w.code for w in r.primary}, {w.code for w in r.secondary}, {w.code for w in r.good}


def cleanup():
    with SessionLocal() as db:
        sids = [u for u in ids["users"] if u != coach]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(sids or [0]))]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids or [0])))
        db.execute(sa_delete(Task).where(Task.id.in_(tids or [0])))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(sids or [0])))
        sb = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(sids or [0]))]
        db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sb or [0])))
        db.execute(sa_delete(StudentBook).where(StudentBook.id.in_(sb or [0])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"] or [0])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"] or [0])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"] or [0])))
        db.execute(sa_delete(User).where(User.id.in_(ids["users"] or [0])))
        db.commit()


def D(n):
    return today - timedelta(days=n)


def main() -> int:
    global coach
    with SessionLocal() as db:
        c = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x"), full_name="c",
                 role=UserRole.TEACHER, is_active=True)
        db.add(c)
        db.commit()
        coach = c.id
    ids["users"].append(coach)
    try:
        _, mb, ms = book("Mat")
        _, kb, ks = book("Kimya")
        _, fb, fs = book("Fizik")
        _, db_, ds = book("Deneme", BookType.BRANS_DENEMESI)
        MAT, KIM, FIZ, DEN = (mb, ms), (kb, ks), (fb, fs), (db_, ds)

        # --- Boran: program 3 gün önce bitti, son 4 programlı gün boş, 25'te uygulamayı açtı
        s = student("boran", seen_days=5)
        for k in (8, 7, 6):
            task(s, D(k), MAT, True)
        for k in (6, 5, 4, 3):
            task(s, D(k), MAT, False)
            task(s, D(k), KIM, False)
        r, P, S_, G = report(s)
        chk("A1 program bitti → programı yok KIRMIZI", "program_none" in P
            and next(w for w in r.primary if w.code == "program_none").level == "red", str(P))
        es = next((w for w in r.primary if w.code == "empty_streak"), None)
        chk("B1 4 programlı gün boş → kırmızı + kanıtta son görülme", es is not None and es.level == "red"
            and any(l == "Son görülme" for l, _ in es.evidence), str(P))
        chk("Hiyerarşi: tamamlama düşüklüğü + giriş yok ek sinyale indi",
            "completion_low" not in P and "no_login" in S_, f"P={P} S={S_}")
        chk("Özet cümlesi kök nedenle başlar", r.headline.startswith("Programı yok"), r.headline)
        with SessionLocal() as db:
            ra = compute_risk_score(db, student=db.get(User, s), today=today)
        chk("Risk seviyesi motorla hizalı (en az Risk) + Programsız göstergesi",
            ra.level in ("high", "critical") and "no_program" in {i.code for i in ra.indicators},
            f"{ra.level} {[i.code for i in ra.indicators]}")

        # --- Program bugün bitiyor / taslakta
        s = student("ending")
        task(s, D(1), MAT, True)
        task(s, today, MAT, False)
        _, P, _, _ = report(s)
        chk("A2 yarından sonrası yok → program bitiyor SARI", "program_ending" in P and "program_none" not in P, str(P))
        s = student("draft")
        task(s, D(1), MAT, True)
        task(s, today + timedelta(days=1), MAT, False, draft=True)
        _, P, _, _ = report(s)
        chk("A3 yalnız taslak → taslakta uyarısı, programı yok DEĞİL", "draft_only" in P and "program_none" not in P, str(P))
        s = student("newbie", age=1)
        _, P, _, _ = report(s)
        chk("A1 yeni hesap (1 gün) → programı yok çıkmaz", "program_none" not in P, str(P))

        # --- 2 gün boş → sarı; bugün tik attıysa seri yok
        s = student("two")
        task(s, D(3), MAT, True)
        task(s, D(2), MAT, False)
        task(s, D(1), MAT, False)
        task(s, today + timedelta(days=1), MAT, False)
        _, P, _, _ = report(s)
        chk("B1 2 programlı gün boş → SARI", "empty_streak" in P, str(P))
        s = student("resumed")
        task(s, D(2), MAT, False)
        task(s, D(1), MAT, False)
        task(s, today, MAT, True)
        task(s, today + timedelta(days=1), MAT, False)
        _, P, _, _ = report(s)
        chk("B1 bugün tik attı → seri uyarısı yok (toparladı)", "empty_streak" not in P, str(P))

        # --- Tamamlama düşük / düşüş
        s = student("low")
        for k in range(1, 8):
            task(s, D(k), MAT, k % 3 == 0)   # 7 günde 2 tamam → %29
        task(s, today + timedelta(days=1), MAT, False)
        r, P, S_, _ = report(s)
        cl = next((w for w in r.primary + r.secondary if w.code == "completion_low"), None)
        chk("B2 %29 tamamlama → KIRMIZI", cl is not None and cl.level == "red", str(P | S_))
        s = student("drop")
        for k in range(8, 15):
            task(s, D(k), MAT, True)
        for k in range(1, 8):
            task(s, D(k), MAT, k % 2 == 0)   # %43
        task(s, today + timedelta(days=1), MAT, False)
        r, P, S_, _ = report(s)
        chk("B3 %100 → %43 düşüş işaretlenir", "completion_drop" in (P | S_), str(P | S_))

        # --- Giriş yok (programı sürerken)
        s = student("away", seen_days=4)
        task(s, D(1), MAT, True)
        task(s, today + timedelta(days=1), MAT, False)
        _, P, _, _ = report(s)
        chk("B5 4 gündür görülmedi → SARI", "no_login" in P, str(P))

        # --- Taha: Kimya'dan kaçınma (diğer dersler tam)
        s = student("taha")
        for k in range(1, 9):
            task(s, D(k), MAT, True)
            task(s, D(k), FIZ, True)
        for k in (2, 4, 6, 8):
            task(s, D(k), KIM, False)
        task(s, today + timedelta(days=1), MAT, False)
        r, P, _, _ = report(s)
        av = [w for w in r.primary if w.code.startswith("subject_avoid_")]
        chk("C1 Kimya %0, diğerleri %100 → kaçınma KIRMIZI", len(av) == 1 and av[0].level == "red", str(P))
        chk("C1 kaçınılan dersin durgunluk/başlanmadı kartı tekrar etmez",
            not any(c.startswith(("subject_stale_", "subject_untouched_")) for c in P), str(P))

        # --- Taha (prod): kaçınılan ders çok görevli → genel oran %40 altı, diğerleri iyi
        s = student("taha2")
        for k in range(1, 11):
            task(s, D(k), KIM, False)
        for k in range(1, 7):
            task(s, D(k), MAT, k != 3)
        task(s, today + timedelta(days=1), MAT, False)
        r, P, _, _ = report(s)
        chk("C1 genel oran düşük ama diğer dersler %83 → kaçınma ANA kartta kalır",
            any(c.startswith("subject_avoid_") for c in P), str(P))

        # --- Deneme aksatma (koça özel)
        s = student("deneme")
        for k in range(1, 7):
            task(s, D(k), MAT, True)
        task(s, D(2), DEN, False)
        task(s, D(4), DEN, False)
        task(s, today + timedelta(days=1), MAT, False)
        r, P, _, _ = report(s)
        dn = next((w for w in r.primary if w.code == "deneme_skipped"), None)
        chk("D1 2 deneme görevi yapılmadı → uyarı (koça özel)", dn is not None and dn.coach_only, str(P))
        chk("D1 veli seviyesi deneme uyarısından etkilenmez", r.parent_level == "green", r.parent_level)

        # --- Deneme neti düşüşü + artış
        s = student("exam")
        task(s, D(1), MAT, True)
        task(s, today + timedelta(days=1), MAT, False)
        with SessionLocal() as db:
            for d_, net in ((D(20), 70.0), (D(3), 60.0)):
                db.add(ExamResult(student_id=s, created_by_id=coach, title="TYT", exam_date=d_,
                                  section=ExamSection.TYT, total_correct=0, total_wrong=0,
                                  total_blank=0, net=net))
            db.commit()
        _, P, _, _ = report(s)
        chk("D2 aynı türde net 70 → 60 → düşüş uyarısı", "exam_drop" in P, str(P))
        s = student("examup")
        task(s, D(1), MAT, True)
        task(s, today + timedelta(days=1), MAT, False)
        with SessionLocal() as db:
            for d_, net in ((D(20), 60.0), (D(3), 70.0)):
                db.add(ExamResult(student_id=s, created_by_id=coach, title="TYT", exam_date=d_,
                                  section=ExamSection.TYT, total_correct=0, total_wrong=0,
                                  total_blank=0, net=net))
            db.commit()
        _, _, _, G = report(s)
        chk("G net artışı → iyi giden kartı", "good_net_up" in G, str(G))

        # --- Emir: toplu işaretleme (bilgi, koça özel) + D/Y boş
        s = student("emir")
        for k in range(1, 6):
            base = datetime.combine(D(k), time(23, 50), tzinfo=timezone.utc)
            for j in range(5):
                task(s, D(k), MAT, True, done_at=base + timedelta(seconds=20 * j), dy=False)
        task(s, today + timedelta(days=1), MAT, False)
        r, P, S_, G = report(s)
        chk("F1 5 gün toplu işaretleme → bilgi (ana kart değil, koça özel)",
            "bulk_marking" in S_ and "bulk_marking" not in P
            and next(w for w in r.secondary if w.code == "bulk_marking").coach_only, f"P={P} S={S_}")
        chk("F2 D/Y girilmiyor → bilgi", "dy_missing" in S_, str(S_))

        # --- Zeynep: her gün tam → iyi gidenler, uyarı yok
        s = student("zeynep")
        for k in range(1, 8):
            task(s, D(k), MAT, True)
            activity(s, D(k), True)
        task(s, today + timedelta(days=1), MAT, False)
        r, P, _, G = report(s)
        chk("G tam program → uyarı yok + seri + %100 kartı",
            not P and {"good_streak", "good_completion"} <= G, f"P={P} G={G}")
        chk("Özet cümlesi olumlu", "görevlerinin tamamını" in r.headline, r.headline)
    finally:
        cleanup()
    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
