"""Havuz modu erken uyarı katmanları (pool_flags, Adım 4 — K40–K57) smoke.

Senaryolar: P dönem (yok / ara / boş / 14 gün seanssız / beklenen gün gecikti) ·
K katılım kademeleri (giriş→kap→işaret→D/Y/B) · T tempo (ilk 2 dönem susar, ×1,5) ·
D doğruluk <%50 · E deneme çaprazı + zorunlu seans kuyruğu + anında push · A kaçınma ·
Z sona kalma deseni · kağıt öğrencisi eğilimi · K48 1 ana + ek · K52 veli green ·
risk puanı hizası · cron yönlendirme (günde bir) · HTTP: uyarı akışı / seans ekranı /
öğrenci ipuçları.

Çalıştır: PYTHONPATH=. python scripts/test_pool_flags.py
"""
from __future__ import annotations

import os
import secrets
import sys
from datetime import date, datetime, time, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, PanelVisitEvent, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole, WarningState,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.exam_progress import SessionAgendaItem  # noqa: E402
from app.models.exam_result import EQ_RESULT_DOGRU, EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion  # noqa: E402
from app.models.moment_event import MomentEvent  # noqa: E402
from app.models.pool import PERIOD_BREAK, PERIOD_CLOSED, UNIT_ETKINLIK, UNIT_TEST  # noqa: E402
from app.models.suspicious_ip import SuspiciousIp  # noqa: E402
from app.services import analytics, pool_cron, pool_flags as pf, pool_mode as pm, push_notifications  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.risk_analysis import compute_risk_score  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.student_flags import evaluate_flags  # noqa: E402

PFX = f"pfl_{secrets.token_hex(3)}"
PWD = "Flags!234567xy"
today = date.today()
now = datetime.now(timezone.utc)
analytics._tr_now = lambda: datetime.combine(today, time(12, 0), tzinfo=timezone.utc)
passed = 0
failed: list[str] = []
ids: dict = {"users": [], "subjects": [], "books": [], "exams": []}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def _student(db, coach, tag, *, last_seen=None, created_days=60):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PWD),
             full_name=f"Havuz {tag}", role=UserRole.STUDENT, is_active=True, teacher_id=coach.id,
             grade_level=12, track=Track.SAYISAL, program_mode="havuz",
             created_at=now - timedelta(days=created_days), last_seen_at=last_seen)
    db.add(u)
    db.flush()
    ids["users"].append(u.id)
    return u


def _cup_done(db, item, day, count, *, correct=None, wrong=None, tick=True):
    """Kaba koy + (isteğe bağlı) tamamla; D/Y None bırakılabilir (K43 D/Y/B kademesi)."""
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    if tick:
        for bi in t.book_items:
            bi.completed_count = count
            bi.correct_count = correct
            bi.wrong_count = wrong
        t.status = TaskStatus.COMPLETED
        t.completed_at = datetime.combine(day, time(20, 0), tzinfo=timezone.utc)
        db.flush()
        pm.sync_item_progress(db, item)
    return t


def _history(db, student, subject, book, sec, n_periods, *, end, units=14, mark_instead=None):
    """Kapanmış 7 günlük dönemler (en eskiden `end`e doğru). Öğrenci kaydı `units` birim,
    son gün kaba konur (K45 'sona kaldı' deseni). mark_instead → öğrenci kaydı yerine
    rehber seans işareti (kağıt öğrencisi, K51)."""
    for k in range(n_periods, 0, -1):
        opened = end - timedelta(days=7 * k)
        closed = opened + timedelta(days=7)
        p = pm.open_period(db, student=student, coach=None, opened_on=opened, expected_next_on=closed)
        it = pm.add_item(db, period=p, student=student, subject=subject, quantity=units, unit=UNIT_TEST,
                         book=book, section=sec)
        if mark_instead is None:
            _cup_done(db, it, closed - timedelta(days=1), units, correct=units * 8, wrong=units * 2)
        pm.close_period(db, p, closed_on=closed, status=PERIOD_CLOSED)
        if mark_instead is not None:
            it.session_marked = int(round(units * mark_instead[n_periods - k] / 100))
            db.flush()


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="Bayrak Rehber", role=UserRole.TEACHER, is_active=True)
        db.add(coach)
        db.flush()
        ids["users"].append(coach.id)
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        fiz = Subject(name=f"{PFX} TYT Fizik", teacher_id=coach.id, exam_section=ExamSection.TYT)
        db.add_all([tyt, fiz])
        db.flush()
        ids["subjects"] += [tyt.id, fiz.id]
        t1 = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        t2 = Topic(subject_id=tyt.id, name="Köklü Sayılar", order=2, teacher_id=coach.id)
        t3 = Topic(subject_id=fiz.id, name="Optik", order=1, teacher_id=coach.id)
        db.add_all([t1, t2, t3])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal TYT Mat", type=BookType.SORU_BANKASI)
        db.add(b)
        db.flush()
        ids["books"].append(b.id)
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=200, order=1, topic_id=t1.id)
        db.add(sec)
        db.flush()

        def assign(u):
            sb = StudentBook(student_id=u.id, book_id=b.id)
            db.add(sb)
            db.flush()
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id, reserved_count=0, completed_count=0))
            db.flush()

        yday = today - timedelta(days=1)
        # --- P katmanı
        s_none = _student(db, coach, "none", last_seen=now - timedelta(days=1))
        s_break = _student(db, coach, "break", last_seen=now - timedelta(days=1))
        p = pm.open_period(db, student=s_break, coach=coach, opened_on=today - timedelta(days=10))
        pm.close_period(db, p, closed_on=today - timedelta(days=3), status=PERIOD_BREAK)
        s_empty = _student(db, coach, "empty", last_seen=now - timedelta(days=1))
        pm.open_period(db, student=s_empty, coach=coach, opened_on=today - timedelta(days=2))
        s_over = _student(db, coach, "over", last_seen=now - timedelta(hours=20))
        assign(s_over)
        p = pm.open_period(db, student=s_over, coach=coach, opened_on=today - timedelta(days=15))
        it = pm.add_item(db, period=p, student=s_over, subject=tyt, quantity=20, unit=UNIT_TEST, book=b, section=sec)
        _cup_done(db, it, yday, 2, correct=15, wrong=5)
        s_late = _student(db, coach, "late", last_seen=now - timedelta(hours=20))
        assign(s_late)
        p = pm.open_period(db, student=s_late, coach=coach, opened_on=today - timedelta(days=8),
                           expected_next_on=today - timedelta(days=3))
        it = pm.add_item(db, period=p, student=s_late, subject=tyt, quantity=20, unit=UNIT_TEST, book=b, section=sec)
        _cup_done(db, it, yday, 2, correct=15, wrong=5)

        # --- s_main: 3 dönem geçmiş (günde 2 birim) + geride + doğruluk düşük + kaçınma + deneme çaprazı + sona kalma
        s_main = _student(db, coach, "main", last_seen=now - timedelta(hours=20))
        assign(s_main)
        _history(db, s_main, tyt, b, sec, 3, end=today - timedelta(days=3))
        p_main = pm.open_period(db, student=s_main, coach=coach, opened_on=today - timedelta(days=3),
                                expected_next_on=today + timedelta(days=4))
        i_tyt = pm.add_item(db, period=p_main, student=s_main, subject=tyt, quantity=30, unit=UNIT_TEST, book=b, section=sec)
        i_fiz = pm.add_item(db, period=p_main, student=s_main, subject=fiz, quantity=10, unit=UNIT_TEST, topic=t3)
        i_etk = pm.add_item(db, period=p_main, student=s_main, subject=fiz, quantity=None, unit=UNIT_ETKINLIK, label="Optik videosu")
        _cup_done(db, i_tyt, today - timedelta(days=2), 4, correct=10, wrong=30)
        _cup_done(db, i_tyt, yday, 4, correct=10, wrong=30)
        i_fiz.cup_attempts = 3  # K44: 3 kez kaba girip döndü
        db.flush()
        e = ExamResult(student_id=s_main.id, created_by_id=coach.id, title=f"{PFX} TYT Deneme",
                       exam_date=yday, section=ExamSection.TYT, total_correct=50, total_wrong=10,
                       total_blank=60, net=40.0)
        db.add(e)
        db.flush()
        ids["exams"].append(e.id)
        for n, (tid, res) in enumerate([(t1.id, EQ_RESULT_YANLIS), (t1.id, EQ_RESULT_YANLIS),
                                        (t2.id, EQ_RESULT_YANLIS), (t3.id, EQ_RESULT_DOGRU)], start=1):
            db.add(ExamResultQuestion(exam_result_id=e.id, question_no=n, subject_id=tyt.id, topic_id=tid, result=res))

        # --- s_one: yalnız 1 kapanmış dönem → tempo susar
        s_one = _student(db, coach, "one", last_seen=now - timedelta(hours=20))
        assign(s_one)
        _history(db, s_one, tyt, b, sec, 1, end=today - timedelta(days=3))
        p = pm.open_period(db, student=s_one, coach=coach, opened_on=today - timedelta(days=3),
                           expected_next_on=today + timedelta(days=4))
        it = pm.add_item(db, period=p, student=s_one, subject=tyt, quantity=40, unit=UNIT_TEST, book=b, section=sec)
        _cup_done(db, it, yday, 1, correct=8, wrong=2)

        # --- s_hollow: 3 BOŞ kapanmış dönem (kalem yazılmamış) → tempo tabanına girmez, kağıt öğrencisi sayılmaz
        s_hollow = _student(db, coach, "hollow", last_seen=now - timedelta(hours=20))
        for k in range(3):
            hp = pm.open_period(db, student=s_hollow, coach=coach, opened_on=today - timedelta(days=12 - k))
            pm.close_period(db, hp, closed_on=today - timedelta(days=11 - k), status=PERIOD_CLOSED)
        p = pm.open_period(db, student=s_hollow, coach=coach, opened_on=today - timedelta(days=1),
                           expected_next_on=today + timedelta(days=6))
        pm.add_item(db, period=p, student=s_hollow, subject=fiz, quantity=60, unit=UNIT_TEST, topic=t3)

        # --- K katmanı
        s_idle = _student(db, coach, "idle", last_seen=now - timedelta(days=10))
        p = pm.open_period(db, student=s_idle, coach=coach, opened_on=today - timedelta(days=6))
        pm.add_item(db, period=p, student=s_idle, subject=fiz, quantity=10, unit=UNIT_TEST, topic=t3)
        s_nocup = _student(db, coach, "nocup", last_seen=now - timedelta(hours=20))
        p = pm.open_period(db, student=s_nocup, coach=coach, opened_on=today - timedelta(days=6))
        pm.add_item(db, period=p, student=s_nocup, subject=fiz, quantity=10, unit=UNIT_TEST, topic=t3)
        for d in (yday, today - timedelta(days=2)):
            db.add(PanelVisitEvent(user_id=s_nocup.id, role="student", route_key="student.day", dwell_ms=5000,
                                   source="web", created_at=datetime.combine(d, time(12, 0), tzinfo=timezone.utc)))
        s_notick = _student(db, coach, "notick", last_seen=now - timedelta(hours=20))
        p = pm.open_period(db, student=s_notick, coach=coach, opened_on=today - timedelta(days=6))
        it = pm.add_item(db, period=p, student=s_notick, subject=fiz, quantity=10, unit=UNIT_TEST, topic=t3)
        _cup_done(db, it, today - timedelta(days=2), 2, tick=False)
        _cup_done(db, it, yday, 2, tick=False)
        s_dy = _student(db, coach, "dy", last_seen=now - timedelta(hours=20))
        assign(s_dy)
        p = pm.open_period(db, student=s_dy, coach=coach, opened_on=today - timedelta(days=5))
        it = pm.add_item(db, period=p, student=s_dy, subject=tyt, quantity=12, unit=UNIT_TEST, book=b, section=sec)
        for k in (3, 2, 1):
            _cup_done(db, it, today - timedelta(days=k), 2)  # D/Y None

        # --- kağıt öğrencisi (K40/K51): hiç girmedi; 4 dönem seans işareti %70→%40
        s_paper = _student(db, coach, "paper", last_seen=None)
        assign(s_paper)
        _history(db, s_paper, tyt, b, sec, 4, end=today - timedelta(days=6), units=10, mark_instead=[70, 60, 50, 40])
        p = pm.open_period(db, student=s_paper, coach=coach, opened_on=today - timedelta(days=6))
        pm.add_item(db, period=p, student=s_paper, subject=tyt, quantity=10, unit=UNIT_TEST, book=b, section=sec)
        db.commit()
        return {"coach": coach.id, "none": s_none.id, "break": s_break.id, "empty": s_empty.id, "over": s_over.id,
                "late": s_late.id, "main": s_main.id, "one": s_one.id, "idle": s_idle.id, "nocup": s_nocup.id,
                "notick": s_notick.id, "dy": s_dy.id, "paper": s_paper.id, "hollow": s_hollow.id, "tyt": tyt.id, "fiz": fiz.id,
                "t1": t1.id, "exam": e.id, "i_tyt": i_tyt.id, "p_main": p_main.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        db.execute(sa_delete(SessionAgendaItem).where(SessionAgendaItem.student_id.in_(u)))
        db.execute(sa_delete(ExamResultQuestion).where(ExamResultQuestion.exam_result_id.in_(ids["exams"])))
        db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(ids["exams"])))
        db.execute(sa_delete(PanelVisitEvent).where(PanelVisitEvent.user_id.in_(u)))
        db.execute(sa_delete(MomentEvent).where(MomentEvent.user_id.in_(u)))
        db.execute(sa_delete(WarningState).where(WarningState.student_id.in_(u)))
        from app.models.self_study import SelfStudyEntry
        db.execute(sa_delete(SelfStudyEntry).where(SelfStudyEntry.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def codes(rep):
    return [w.code for w in rep.primary], [w.code for w in rep.secondary], [w.code for w in rep.good]


def main() -> int:
    get_login_limiter().reset()
    pushes: list[dict] = []
    orig_push = push_notifications.safe_push
    orig_uft = analytics.usual_first_tick
    push_notifications.safe_push = lambda db, **kw: pushes.append(kw)  # type: ignore[assignment]
    d = seed()
    try:
        with SessionLocal() as db:
            S = {k: db.get(User, v) for k, v in d.items() if k in
                 ("none", "break", "empty", "over", "late", "main", "one", "idle", "nocup", "notick", "dy", "paper", "hollow")}

            # ---- P. dönem
            r = evaluate_flags(db, S["none"], today)
            pr, _, _ = codes(r)
            check("P1 açık dönem yok → pool_no_period KIRMIZI (rehber aksiyonu, coach_only)",
                  pr == ["pool_no_period"] and r.level == "red" and r.primary[0].coach_only, str(pr))
            r = evaluate_flags(db, S["break"], today)
            check("P2 son dönem 'ara' (tatil) → hiç bayrak yok, başlık Ara",
                  not r.primary and not r.secondary and r.headline.startswith("Ara"), r.headline)
            r = evaluate_flags(db, S["empty"], today)
            check("P3 dönem açık, kalem yok, 2 gün geçti → pool_empty SARI", codes(r)[0] == ["pool_empty"], str(codes(r)))
            r = evaluate_flags(db, S["over"], today)
            check("P4 15 gündür seans yok → pool_session_overdue KIRMIZI (K57)",
                  codes(r)[0] == ["pool_session_overdue"] and r.level == "red", str(codes(r)))
            r = evaluate_flags(db, S["late"], today)
            check("P5 beklenen seans 3+ gün geçti → pool_session_late SARI (K54)",
                  codes(r)[0] == ["pool_session_late"], str(codes(r)))
            check("P6 gün-gün kodu (program_none / empty_streak) havuz öğrencisinde HİÇ üretilmez",
                  not any(c.startswith(("program_", "empty_streak", "completion_")) for c in sum(codes(r), [])))

            # ---- s_main: hiyerarşi + T/D/E/A/Z
            r = evaluate_flags(db, S["main"], today)
            pr, sc, gd = codes(r)
            check("H1 K48: öğrenci başına 1 ANA kart (tempo), gerisi ek sinyal",
                  pr == ["pool_behind"] and len(pr) == 1, str(pr))
            check("T1 K42: kalan 33 birim / 4 gün = 8,3 > alışkanlık 2,0 × 1,5 → geride",
                  r.primary[0].need_per_day > 8 and abs(r.primary[0].baseline_per_day - 2.0) < 0.01,
                  f"{getattr(r.primary[0], 'need_per_day', None)} / {getattr(r.primary[0], 'baseline_per_day', None)}")
            check("D1 K46: TYT Mat 2 test · 20D/60Y = %25 → pool_accuracy_{sid} ek sinyal",
                  f"pool_accuracy_{d['tyt']}" in sc, str(sc))
            check("E1 K47: bu dönem çalışılan Üslü konusunda denemede yanlış → pool_exam_cross",
                  "pool_exam_cross" in sc, str(sc))
            check("A1 K44: 3 kez kaba girip dönen kalem → pool_avoided",
                  "pool_avoided" in sc, str(sc))
            check("Z1 K45: 3 dönemde TYT Mat hep son güne kaldı → pool_late_{sid} bilgi (yeşil)",
                  f"pool_late_{d['tyt']}" in sc and next(w for w in r.secondary if w.code.startswith("pool_late_")).level == "green", str(sc))
            check("H2 K52: veliye havuz uyarısı gitmez → parent_level green", r.parent_level == "green")
            check("H3 kanıt satırları dolu (gereken/alışkanlık/kural)",
                  any(a == "Kural" for a, _ in r.primary[0].evidence) and len(r.primary[0].evidence) >= 3)

            # ---- T. ilk 2 dönem susar
            r = evaluate_flags(db, S["one"], today)
            check("T2 K42: yalnız 1 kapanmış dönem → tempo SUSAR (pool_behind yok)",
                  "pool_behind" not in sum(codes(r), []), str(codes(r)))
            base, n = pf.pace_baseline(db, S["main"].id, pm.get_open_period(db, S["main"].id), today)
            check("T3 alışkanlık = son 3 dönem günlük ortalaması (14 birim/7 gün = 2,0)", abs(base - 2.0) < 0.01 and n == 3, f"{base} n={n}")

            # T4 (2026-10-14): boş dönem tabana girmez — #414 "son 3 dönemde günde 0.0" sahte "geride"
            base, n = pf.pace_baseline(db, S["hollow"].id, pm.get_open_period(db, S["hollow"].id), today)
            r = evaluate_flags(db, S["hollow"], today)
            check("T4 boş kapanmış dönemler tempo tabanına girmez (susar, pool_behind yok)",
                  base is None and n == 0 and "pool_behind" not in sum(codes(r), []), f"{base} n={n} {codes(r)}")
            check("T5 boş dönemli öğrenci kağıt öğrencisi sayılmaz", not pf.is_paper_student(db, S["hollow"], None))

            # ---- K. katılım kademeleri
            r = evaluate_flags(db, S["idle"], today)
            check("K1 K43: 5 gün giriş/kap/işaret yok → pool_idle_streak KIRMIZI",
                  codes(r)[0] == ["pool_idle_streak"] and r.level == "red", str(codes(r)))
            check("K1b 2 gün sarı / 3 gün kırmızı eşikleri", pf.IDLE_AMBER_DAYS == 2 and pf.IDLE_RED_DAYS == 3)
            r = evaluate_flags(db, S["nocup"], today)
            check("K2 K43: giriş var, kap yok (2 gün) → pool_no_cup SARI", codes(r)[0] == ["pool_no_cup"], str(codes(r)))
            r = evaluate_flags(db, S["notick"], today)
            check("K3 K43: kap var, işaret yok (2 gün) → pool_no_tick SARI", codes(r)[0] == ["pool_no_tick"], str(codes(r)))
            r = evaluate_flags(db, S["dy"], today)
            check("K4 K43: 3 işaretli test kaleminde D/Y boş → pool_dy_missing BİLGİ, ana kart yok, başlık 'yolunda'",
                  not r.primary and "pool_dy_missing" in codes(r)[1] and "yolunda" in r.headline, f"{codes(r)} {r.headline}")

            # ---- kağıt öğrencisi
            r = evaluate_flags(db, S["paper"], today)
            pr, sc, _ = codes(r)
            pap = next((w for w in r.secondary if w.code == "pool_paper"), None)
            check("N1 K40: hiç girmeyen öğrenci kağıt öğrencisi; dönem içi K/T SUSAR (idle yok)",
                  not pr and "pool_idle_streak" not in sc and pap is not None, str(codes(r)))
            check("N2 K51: eğilim çizgisi son 4 dönem %70→%60→%50→%40 (seans işaretinden)",
                  pap is not None and "%70 → %60 → %50 → %40" in pap.title, pap.title if pap else "-")

            # ---- risk hizası
            rk_idle = compute_risk_score(db, student=S["idle"], today=today, now=now)
            rk_main = compute_risk_score(db, student=S["main"], today=today, now=now)
            rk_none = compute_risk_score(db, student=S["none"], today=today, now=now)
            check("R1 kırmızı katılım sinyali → risk ≥60 (Risk)", rk_idle.score >= 60 and rk_idle.level != "ok", f"{rk_idle.score}/{rk_idle.level}")
            check("R2 sarı tempo sinyali → risk 30 (Dikkat)", rk_main.score == 30, str(rk_main.score))
            check("R3 P katmanı (dönem yok) risk puanını yükseltmez ama gösterge olarak listelenir",
                  rk_none.score == 0 and any(i.code == "flag_pool_no_period" for i in rk_none.indicators),
                  f"{rk_none.score} {[i.code for i in rk_none.indicators]}")

            # ---- K47 anında: kuyruk + push (idempotent)
            coach = db.get(User, d["coach"])
            pushes.clear()
            res = pf.exam_cross_check(db, student=S["main"], exam_id=d["exam"], actor=coach)
            db.commit()
            q = db.query(SessionAgendaItem).filter(SessionAgendaItem.student_id == S["main"].id).all()
            check("E2 K47: deneme kaydı → çalışılan Üslü konusu seans kuyruğuna ZORUNLU eklendi",
                  res["added"] == 1 and len(q) == 1 and q[0].item_key == f"pool_cross:{d['exam']}:{d['t1']}", str(res))
            check("E3 K47: rehbere ANINDA push", len(pushes) == 1 and pushes[0]["user_id"] == coach.id, str(pushes))
            res2 = pf.exam_cross_check(db, student=S["main"], exam_id=d["exam"], actor=coach)
            db.commit()
            check("E4 idempotent: ikinci çağrı eklemez, push atmaz", res2["added"] == 0 and len(pushes) == 1, str(res2))
            res3 = pf.exam_cross_check(db, student=S["idle"], exam_id=d["exam"], actor=coach)
            check("E5 başka öğrencinin denemesi → atlanır", res3.get("skipped") == "no_period" or res3.get("added") == 0, str(res3))

            # ---- öğrenci ipuçları (K41/K46/K48)
            hints = pf.student_hints(evaluate_flags(db, S["main"], today))
            hc = [h["code"] for h in hints]
            check("S1 öğrenci ipuçları: doğruluk + tempo cümleleri; kırmızı/yargı yok",
                  f"pool_accuracy_{d['tyt']}" in hc and "pool_behind" in hc and all("level" not in h for h in hints), str(hc))
            check("S2 kağıt öğrencisine ipucu yok", pf.student_hints(evaluate_flags(db, S["paper"], today)) == [])

            # ---- cron yönlendirme (K43)
            g_idle = pool_cron.guidance_message(db, student=S["idle"], day=today)
            g_paper = pool_cron.guidance_message(db, student=S["paper"], day=today)
            g_main = pool_cron.guidance_message(db, student=S["main"], day=today)
            check("C1 giriş yok → 'Havuzun seni bekliyor' yönlendirmesi", g_idle and g_idle[0] == "Havuzun seni bekliyor", str(g_idle))
            check("C2 kağıt öğrencisine yönlendirme yok (dönem içi susar)", g_paper is None)
            check("C3 düşük doğruluk → 'çözümlere bak' yönlendirmesi", g_main and "doğruluk" in g_main[0], str(g_main))
            pushes.clear()
            analytics.usual_first_tick = lambda db_, sid, day: (0, 5)  # type: ignore[assignment]
            fake_now = datetime.combine(today, time(7, 0), tzinfo=timezone.utc)  # 10:00 TR
            out = pool_cron.reminders(db, now=fake_now)
            guided = [p for p in pushes if p.get("title") == "Havuzun seni bekliyor"]
            check("C4 reminders: idle öğrenciye yönlendirme push'u gitti", out["guide"] >= 1 and len(guided) == 1, str(out))
            stamped = db.query(MomentEvent).filter(MomentEvent.user_id == S["idle"].id, MomentEvent.moment_key == "pool_guide").count()
            out2 = pool_cron.reminders(db, now=fake_now + timedelta(minutes=30))
            check("C5 günde bir kez: ikinci koşuda tekrar gitmez (moment_events damgası)",
                  stamped == 1 and out2["guide"] == 0, f"{stamped} {out2}")
            db.rollback()

        # ---- HTTP
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get("/api/v2/teacher/dashboard/warnings-feed")
        check("W1 uyarı akışı 200", r.status_code == 200, r.text[:200])
        rows = [x for x in r.json()["rows"] if x["student_id"] in (d["idle"], d["main"], d["none"])]
        by = {}
        for x in rows:
            by.setdefault(x["student_id"], []).append(x)
        check("W2 akışta havuz öğrencisi başına TEK satır (K48), kod pool_*",
              all(len(v) == 1 and v[0]["code"].startswith("pool_") for v in by.values()) and len(by) == 3, str({k: [x["code"] for x in v] for k, v in by.items()}))
        check("W3 kırmızı idle satırı seans ekranına, dönem-yok satırı havuz editörüne bağlanır",
              by[d["idle"]][0]["link"].endswith("/pool/session") and by[d["none"]][0]["link"].endswith("/pool"),
              f"{by[d['idle']][0]['link']} {by[d['none']][0]['link']}")
        r = c.post("/api/v2/teacher/dashboard/warnings/ack", json={"student_id": d["idle"], "code": "pool_idle_streak", "snooze_days": 3})
        r2 = c.get("/api/v2/teacher/dashboard/warnings-feed")
        check("W4 K50 Gördüm/Ertele havuz sinyalinde çalışır (3 gün gizlenir)",
              r.status_code == 200 and not any(x["student_id"] == d["idle"] for x in r2.json()["rows"])
              and any(x["student_id"] == d["idle"] for x in r2.json()["snoozed_rows"]))
        r = c.get(f"/api/v2/teacher/students/{d['main']}/pool/session")
        j = r.json()
        check("W5 seans ekranı: flags.primary 1 (tempo) + ek sinyallerde deneme çaprazı/kaçınma",
              r.status_code == 200 and [f["code"] for f in j["flags"]["primary"]] == ["pool_behind"]
              and {"pool_exam_cross", "pool_avoided"} <= {f["code"] for f in j["flags"]["secondary"]}, str(j.get("flags")))
        r = c.get(f"/api/v2/teacher/students/{d['paper']}/pool")
        check("W6 editör paketi: kağıt öğrencisi işareti + başlık", r.status_code == 200 and r.json()["flags"]["paper_student"] is True)
        r = c.get(f"/api/v2/teacher/students/{d['main']}/pool/session")
        check("W7 K47 kuyruğu seans ekranında görünür", any(q["source"] == "pool" for q in r.json()["agenda_queue"]))
        c.cookies.clear()
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_main@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r = c.get("/api/v2/student/pool")
        hs = r.json().get("hints", [])
        check("W8 öğrenci paketi: ipuçları (tempo + doğruluk), yönlendirme dili",
              r.status_code == 200 and {h["code"] for h in hs} >= {"pool_behind", f"pool_accuracy_{d['tyt']}"}
              and all("note" in h and h["note"] for h in hs), str(hs))
    finally:
        push_notifications.safe_push = orig_push  # type: ignore[assignment]
        analytics.usual_first_tick = orig_uft  # type: ignore[assignment]
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    if failed:
        print("Başarısız:", failed)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
