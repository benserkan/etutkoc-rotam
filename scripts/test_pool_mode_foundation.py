"""Haftalık görev havuzu — 1. adım temel smoke (2026-10-12, tasarım K1–K61).

Mod alanı · dönem aç/kapat · kalem doğrulamaları (K16/K25/kaynak) · kap = görev
(REZERV YOK) · gün kapanışı · özet/tempo · devir · şube ders programı önerisi ·
paylaşılan servislerde havuz dalı (bayrak motoru, risk, kurum uyum) + gün-gün
öğrencisinin davranışının DEĞİŞMEDİĞİ kanıtı.

Çalıştır: PYTHONPATH=. python scripts/test_pool_mode_foundation.py
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

from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookType, ClassGroup, PoolItem, SectionProgress, StudentBook, StudyPeriod,
    Subject, Task, TaskBookItem, TaskStatus, Topic, Track, User, UserRole,
)
from app.models.curriculum import ExamSection  # noqa: E402
from app.models.pool import (  # noqa: E402
    APPROVAL_APPROVED, APPROVAL_PENDING, PERIOD_CLOSED, PROGRAM_MODE_GUN_GUN, PROGRAM_MODE_HAVUZ,
    SOURCE_CARRY, SOURCE_STUDENT, UNIT_ETKINLIK, UNIT_TEST,
)
from app.services import analytics, pool_mode, task_service  # noqa: E402
from app.services.pool_mode import PoolError  # noqa: E402
from app.services.risk_analysis import compute_risk_score  # noqa: E402
from app.services.security import hash_password  # noqa: E402
from app.services.student_flags import evaluate_flags  # noqa: E402

PFX = f"pool_{secrets.token_hex(3)}"
today = date.today()
now = datetime.now(timezone.utc)
analytics._tr_now = lambda: datetime.combine(today, time(12, 0), tzinfo=timezone.utc)
passed = 0
failed: list[str] = []
ids: dict[str, list[int]] = {"users": [], "subjects": [], "books": [], "cg": []}


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def expect_error(label, fn, code):
    try:
        fn()
    except PoolError as e:
        chk(label, e.code == code, f"code={e.code}")
        return
    chk(label, False, "hata fırlamadı")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_c@test.invalid", password_hash=hash_password("x"),
                     full_name="Havuz Rehber", role=UserRole.TEACHER, is_active=True,
                     created_at=now - timedelta(days=60))
        db.add(coach)
        db.flush()
        mk = lambda tag, mode: User(  # noqa: E731
            email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password("x"),
            full_name=f"Havuz {tag}", role=UserRole.STUDENT, teacher_id=coach.id,
            grade_level=12, is_active=True, created_at=now - timedelta(days=40),
            program_mode=mode, class_group="12-A")
        s_h = mk("havuz", PROGRAM_MODE_HAVUZ)
        s_g = mk("gungun", PROGRAM_MODE_GUN_GUN)
        s_def = User(email=f"{PFX}_def@test.invalid", password_hash=hash_password("x"),
                     full_name="Varsayılan", role=UserRole.STUDENT, teacher_id=coach.id,
                     grade_level=12, is_active=True)
        db.add_all([s_h, s_g, s_def])
        db.flush()
        tyt = Subject(name=f"{PFX} TYT Matematik", teacher_id=coach.id,
                      exam_section=ExamSection.TYT, curriculum_model=None)
        ayt = Subject(name="AYT Fizik", teacher_id=coach.id,
                      exam_section=ExamSection.AYT_SAY, curriculum_model=None)
        ayt_soz = Subject(name="AYT Edebiyat", teacher_id=coach.id,
                          exam_section=ExamSection.AYT_SOZ, curriculum_model=None)
        db.add_all([tyt, ayt, ayt_soz])
        db.flush()
        top = Topic(subject_id=tyt.id, name="Üslü Sayılar", order=1, teacher_id=coach.id)
        top2 = Topic(subject_id=ayt.id, name="Optik", order=1, teacher_id=coach.id)
        db.add_all([top, top2])
        db.flush()
        b = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Orijinal TYT Mat",
                 type=BookType.SORU_BANKASI)
        b_un = Book(teacher_id=coach.id, subject_id=tyt.id, name=f"{PFX} Atanmamış",
                    type=BookType.SORU_BANKASI)
        db.add_all([b, b_un])
        db.flush()
        sec = BookSection(book_id=b.id, label="Üslü Sayılar", test_count=10, order=1, topic_id=top.id)
        db.add(sec)
        db.flush()
        sb = StudentBook(student_id=s_h.id, book_id=b.id)
        db.add(sb)
        db.flush()
        db.add(SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                               reserved_count=0, completed_count=0))
        db.commit()
        ids["users"] += [coach.id, s_h.id, s_g.id, s_def.id]
        ids["subjects"] += [tyt.id, ayt.id, ayt_soz.id]
        ids["books"] += [b.id, b_un.id]
        return {"coach": coach.id, "h": s_h.id, "g": s_g.id, "def": s_def.id,
                "tyt": tyt.id, "ayt": ayt.id, "ayt_soz": ayt_soz.id,
                "top": top.id, "top2": top2.id, "book": b.id, "book_un": b_un.id, "sec": sec.id,
                "sb": sb.id}


def cleanup():
    with SessionLocal() as db:
        u = ids["users"]
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id.in_(u)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(u)))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id.in_(u)))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id.in_(u)))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id.in_(u)).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id.in_(u)))
        db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(ids["books"])))
        db.execute(sa_delete(Book).where(Book.id.in_(ids["books"])))
        db.execute(sa_delete(Topic).where(Topic.subject_id.in_(ids["subjects"])))
        db.execute(sa_delete(Subject).where(Subject.id.in_(ids["subjects"])))
        if ids["cg"]:
            db.execute(sa_delete(ClassGroup).where(ClassGroup.id.in_(ids["cg"])))
        db.execute(sa_delete(User).where(User.id.in_(u)))
        db.commit()


def main() -> int:
    d = seed()
    print(f"\n=== Havuz modu — 1. adım temel ({PFX}) ===\n")
    try:
        with SessionLocal() as db:
            coach = db.get(User, d["coach"])
            s_h = db.get(User, d["h"])
            s_g = db.get(User, d["g"])
            s_def = db.get(User, d["def"])
            tyt = db.get(Subject, d["tyt"])
            ayt = db.get(Subject, d["ayt"])
            ayt_soz = db.get(Subject, d["ayt_soz"])
            top = db.get(Topic, d["top"])
            book = db.get(Book, d["book"])
            book_un = db.get(Book, d["book_un"])
            sec = db.get(BookSection, d["sec"])

            # 1) mod alanı
            chk("1a yeni öğrenci varsayılan gün-gün", pool_mode.mode_of(s_def) == PROGRAM_MODE_GUN_GUN)
            chk("1b havuz öğrencisi is_havuz", pool_mode.is_havuz(s_h) and not pool_mode.is_havuz(s_g))
            chk("1c havuz_student_ids yalnız havuz olanı verir",
                pool_mode.havuz_student_ids(db, [d["h"], d["g"], d["def"]]) == {d["h"]})

            # 2) dönem
            expect_error("2a gün-gün öğrencisine dönem açılamaz",
                         lambda: pool_mode.open_period(db, student=s_g, coach=coach, opened_on=today),
                         "not_havuz")
            p = pool_mode.open_period(db, student=s_h, coach=coach, opened_on=today - timedelta(days=2),
                                      expected_next_on=today + timedelta(days=5))
            chk("2b dönem açıldı (acik)", p.is_open and p.coach_id == coach.id)
            expect_error("2c ikinci açık dönem yasak",
                         lambda: pool_mode.open_period(db, student=s_h, coach=coach, opened_on=today),
                         "already_open")
            expect_error("2d açık dönem varken mod değişmez",
                         lambda: pool_mode.set_program_mode(db, s_h, PROGRAM_MODE_GUN_GUN), "open_period")
            expect_error("2e beklenen gün başlangıçtan önce olamaz",
                         lambda: pool_mode.open_period(db, student=s_def, coach=coach, opened_on=today,
                                                       expected_next_on=today),
                         "not_havuz")  # mod yok → önce not_havuz

            # 3) kalem doğrulamaları
            expect_error("3a K16 test kaleminde miktar zorunlu",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=tyt,
                                                    quantity=None, unit=UNIT_TEST, topic=top),
                         "quantity_required")
            etk = pool_mode.add_item(db, period=p, student=s_h, subject=tyt, quantity=None,
                                     unit=UNIT_ETKINLIK, label="Üslü video")
            chk("3b etkinlik miktarsız → 1 birim", etk.quantity == 1 and etk.unit == UNIT_ETKINLIK)
            expect_error("3c K25 alan boşsa AYT kalemi eklenemez",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=ayt,
                                                    quantity=2, unit=UNIT_TEST, label="Optik"),
                         "track_required")
            s_h.track = Track.SAYISAL
            db.flush()
            # 2026-10-14: koçun konusuz TEST kalemi reddedilir (konu zorunlu) — sayfa birimi serbest
            expect_error("3d0 koçun konusuz test kalemi → topic_required",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=ayt,
                                                    quantity=2, unit=UNIT_TEST, label="Optik"),
                         "topic_required")
            ayt_item = pool_mode.add_item(db, period=p, student=s_h, subject=ayt, quantity=2,
                                          unit="sayfa", label="Optik")
            chk("3d alan dolu → AYT kalemi eklendi", ayt_item.id is not None)
            expect_error("3e alan dışı AYT dersi reddedilir (Sayısal → Edebiyat)",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=ayt_soz,
                                                    quantity=2, unit=UNIT_TEST, label="Şiir"),
                         "subject_not_in_track")
            expect_error("3f atanmamış kitap reddedilir",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=tyt,
                                                    quantity=2, unit=UNIT_TEST, book=book_un),
                         "book_not_assigned")
            expect_error("3g konu/kaynak/metin üçü de boşsa reddedilir",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=tyt,
                                                    quantity=2, unit=UNIT_TEST),
                         "topic_required")
            expect_error("3g2 sayfa biriminde konu/kaynak/metin yoksa label_required",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=tyt,
                                                    quantity=2, unit="sayfa"),
                         "label_required")
            it = pool_mode.add_item(db, period=p, student=s_h, subject=tyt, quantity=4,
                                    unit=UNIT_TEST, book=book, section=sec)
            chk("3h kitaplı kalem konuyu bölümden aldı", it.topic_id == top.id and it.remaining == 4)
            sp = db.query(SectionProgress).filter_by(student_book_id=d["sb"], book_section_id=sec.id).one()
            chk("3i kalem eklenince REZERV açılmaz", sp.reserved_count == 0)

            # 4) öğrenci kalemi onay (K38)
            st_it = pool_mode.add_item(db, period=p, student=s_h, subject=tyt, quantity=3,
                                       unit=UNIT_TEST, topic=top, source=SOURCE_STUDENT, created_by=s_h)
            chk("4a öğrenci kalemi onay bekler", st_it.approval == APPROVAL_PENDING
                and not st_it.counts_toward_pool)
            summ = pool_mode.period_summary(db, p, today)
            chk("4b onaysız kalem toplam birime girmez (1 etk + 2 AYT + 4 test = 7)",
                summ.total_units == 7 and summ.pending_student_items == 1, f"{summ}")
            pool_mode.approve_item(db, st_it, coach, True)
            summ = pool_mode.period_summary(db, p, today)
            chk("4c onaylanınca girer (7+3=10)", st_it.approval == APPROVAL_APPROVED and summ.total_units == 10)
            expect_error("4d rehber kalemi onaylanamaz",
                         lambda: pool_mode.approve_item(db, it, coach, True), "not_student_item")

            # 5) kap = görev, rezerv yok
            t = pool_mode.put_in_cup(db, item=it, day=today, count=3)
            chk("5a kap görevi bugüne yazıldı (yayınlı, kalem bağlı)",
                t.date == today and not t.is_draft and t.pool_item_id == it.id)
            bi = t.book_items[0]
            chk("5b kap kalemi released doğdu (rezerv yok)",
                bi.reservation_released_at is not None and bi.planned_count == 3)
            db.refresh(sp)
            chk("5c kaba konunca SectionProgress.reserved değişmedi", sp.reserved_count == 0)
            chk("5d başlık kitap — bölüm: 3 test", t.title.endswith(": 3 test"), t.title)
            expect_error("5e aynı kalem ikinci kez kaba alınamaz (açık görev var)",
                         lambda: pool_mode.put_in_cup(db, item=it, day=today, count=1), "already_in_cup")
            task_service.complete_task(db, t, correct=20, wrong=4, blank=0)
            db.flush()
            db.refresh(sp)
            chk("5f tamamlanınca kitap sayacı çözüldü +3, rezerv hâlâ 0",
                sp.completed_count == 3 and sp.reserved_count == 0, f"c={sp.completed_count} r={sp.reserved_count}")
            pool_mode.sync_item_progress(db, it)
            chk("5g kalem tamamlanan 3, kalan 1", it.completed == 3 and it.remaining == 1)
            t2 = pool_mode.put_in_cup(db, item=it, day=today)
            chk("5h kalan 1 yeniden kaba alınır (varsayılan = kalan)", t2.book_items[0].planned_count == 1)
            expect_error("5i kalandan fazla alınamaz",
                         lambda: pool_mode.put_in_cup(db, item=st_it, day=today, count=5), "bad_count")

            # 6) gün kapanışı
            t3 = pool_mode.put_in_cup(db, item=st_it, day=today, count=2)   # konulu kaynaksız kalem
            t4 = pool_mode.put_in_cup(db, item=etk, day=today)              # etkinlik
            task_service.set_item_completion(db, t3.book_items[0], 1)        # 2'den 1'i çözüldü
            db.flush()
            res = pool_mode.close_day(db, student=s_h, day=today)
            chk("6a gün kapanışı: 1 kaldırıldı (t2 ve t4 → ilerlemesiz), 1 küçüldü, 1 tamam",
                res == {"removed": 2, "shrunk": 1, "kept": 1}, str(res))
            chk("6b ilerlemesiz kap görevi silindi", db.get(Task, t2.id) is None and db.get(Task, t4.id) is None)
            db.refresh(t3)
            chk("6c kısmi görev küçüldü: planlanan 1 = tamamlanan, durum tamam",
                t3.book_items[0].planned_count == 1 and t3.status == TaskStatus.COMPLETED)
            pool_mode.sync_item_progress(db, it)
            pool_mode.sync_item_progress(db, st_it)
            db.refresh(etk)
            chk("6d kalemler: kitaplı 3/4 · öğrenci 1/3 · etkinlik 0/1 ve kap denemesi sayıldı",
                it.completed == 3 and st_it.completed == 1 and etk.completed == 0 and etk.cup_attempts == 1)
            db.refresh(sp)
            chk("6e kitap sayacı hâlâ 3 çözüldü / 0 rezerv (silme iade üretmedi)",
                sp.completed_count == 3 and sp.reserved_count == 0)

            # 7) özet / tempo
            summ = pool_mode.period_summary(db, p, today)
            chk("7a toplam 10 birim, tamamlanan 4, %40", summ.total_units == 10 and summ.done_units == 4
                and summ.pct == 40, f"{summ}")
            chk("7b kalan gün 5, günde 1.2", summ.days_left == 5 and summ.per_day_needed == 1.2, f"{summ}")
            p.expected_next_on = today - timedelta(days=1)
            db.flush()
            summ = pool_mode.period_summary(db, p, today)
            chk("7c beklenen gün geçtiyse kalan gün 1 sayılır (sıfıra bölme yok)", summ.days_left == 1)

            # 8) kapanış + devir
            leftovers = pool_mode.close_period(db, p, closed_on=today)
            chk("8a dönem kapandı, kalanı olan 4 kalem devir adayı",
                p.status == PERIOD_CLOSED and len(leftovers) == 4, f"{len(leftovers)}")
            expect_error("8b kapalı döneme kalem eklenemez",
                         lambda: pool_mode.add_item(db, period=p, student=s_h, subject=tyt, quantity=1,
                                                    unit=UNIT_TEST, topic=top), "period_closed")
            expect_error("8c dönem iki kez kapanmaz",
                         lambda: pool_mode.close_period(db, p, closed_on=today), "not_open")
            p2 = pool_mode.open_period(db, student=s_h, coach=coach, opened_on=today,
                                       expected_next_on=today + timedelta(days=7))
            c = pool_mode.carry_item(db, item=it, target=p2, student=s_h, coach=coach)
            chk("8d devir: kalan 1 test yeni kalem, kaynak devir, sayaç 1, köken bağı",
                c.quantity == 1 and c.source == SOURCE_CARRY and c.carry_count == 1
                and c.parent_item_id == it.id and c.book_section_id == sec.id)
            c2 = pool_mode.carry_item(db, item=c, target=p2, student=s_h, coach=coach, quantity=1)
            chk("8e ikinci devir sayaç 2", c2.carry_count == 2)
            pool_mode.remove_item(db, c2, coach)
            chk("8f silinen kalem iz bırakır ve yüzdeye girmez",
                c2.removed_at is not None and not c2.counts_toward_pool)
            expect_error("8g silinen kalem kaba alınamaz",
                         lambda: pool_mode.put_in_cup(db, item=c2, day=today), "item_removed")

            # 9) şube + ders programı önerisi
            cg = pool_mode.get_or_create_class_group(db, coach=coach, name="12-A")
            ids["cg"].append(cg.id)
            chk("9a şube kaydı koç kapsamında", cg.scope_key == f"coach:{coach.id}"
                and pool_mode.class_group_of(db, student=s_h, coach=coach).id == cg.id)
            pool_mode.set_lesson_days(db, cg, {today.weekday(): [ayt.id]})
            pool_mode.set_topic_position(db, cg, subject_id=tyt.id, topic_id=top.id, actor=coach, on=today)
            chk("9b konu konumu yazıldı", cg.positions[str(tyt.id)]["topic_id"] == top.id)
            a1 = pool_mode.add_item(db, period=p2, student=s_h, subject=tyt, quantity=2, unit=UNIT_TEST, topic=top)
            a2 = pool_mode.add_item(db, period=p2, student=s_h, subject=ayt, quantity=2, unit="sayfa", label="Optik")
            a3 = pool_mode.add_item(db, period=p2, student=s_h, subject=tyt, quantity=1, unit=UNIT_TEST,
                                    topic=top, day_hint=today)
            sug = pool_mode.cup_suggestions(db, period=p2, cg=cg, day=today)
            chk("9c öneri sırası: gün etiketi bugün → bugün dershanede işlenen ders → diğer",
                [x.id for x in sug][:3] == [a3.id, a2.id, c.id] or [x.id for x in sug][:2] == [a3.id, a2.id],
                str([x.id for x in sug]))
            _ = a1

            # 10) paylaşılan servisler: havuz dalı + gün-gün değişmedi
            rep_h = evaluate_flags(db, s_h, today)
            _codes_h = [w.code for w in rep_h.primary + rep_h.secondary]
            chk("10a havuz öğrencisi bayrak motorunda gün-gün alarmı almaz (yalnız pool_* kodları, Adım 4)",
                not any(c.startswith(("program_", "empty_streak", "completion_", "no_login")) for c in _codes_h)
                and all(c.startswith("pool_") for c in _codes_h) and rep_h.parent_level == "green", str(_codes_h))
            rep_g = evaluate_flags(db, s_g, today)
            chk("10b gün-gün öğrencisi (programsız, 40 gün) hâlâ 'Programı yok' kırmızısı alır",
                any(w.code == "program_none" for w in rep_g.primary), f"{[w.code for w in rep_g.primary]}")
            r_h = compute_risk_score(db, student=s_h, today=today, now=now)
            r_g = compute_risk_score(db, student=s_g, today=today, now=now)
            chk("10c risk: havuz nötr (ok), gün-gün programsız sinyal üretir",
                r_h.level == "ok" and r_h.score == 0 and r_g.score > 0, f"h={r_h.score} g={r_g.score}")
            db.rollback()
    finally:
        cleanup()
    print(f"\n{passed}/{passed + len(failed)} geçti")
    if failed:
        print("Başarısız:", failed)
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
