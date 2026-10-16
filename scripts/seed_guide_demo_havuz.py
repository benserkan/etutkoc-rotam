"""Rota Rehberi — HAVUZ serisi için demo öğrenci (yalnız DEV; start.sh'e EKLENMEZ).

Demo koç Aylin Demir'e (rehber-koc@etutkoc.demo) haftalık havuz modunda
12. sınıf Sayısal bir öğrenci kurar: Deniz Arslan (rehber-deniz@etutkoc.demo).

  · 12-A şubesi + dershane ders programı
  · katalogdan 4 gerçek kitap (345 TYT Matematik/Kimya/Fizik, Biyotik AYT Biyoloji)
  · 3 kapanmış dönem (geçmiş kartları + tempo tabanı) — sonuncusundan devirler
  · bugünden 4 gün önce açılmış GÜNCEL dönem: kitaplı / müfredat konulu / öğretmen
    ödevi / video etkinliği / onay bekleyen öğrenci kalemi / 2. kez devredilen kalem /
    kaçınılan kalem; geçmiş günlerde işaretlenmiş kaplar + bugünün açık kabı

Bugüne GÖRELİ kurulur; çekimden önce yeniden koş:

  python -m scripts.seed_guide_demo_havuz           # kur (varsa silip yeniden)
  python -m scripts.seed_guide_demo_havuz --delete
"""
from __future__ import annotations

import os
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
    Book,
    BookSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskBookItem,
    Topic,
    User,
    UserRole,
)
from app.models.book import BookTemplate  # noqa: E402
from app.models.pool import ClassGroup, PoolItem, StudyPeriod  # noqa: E402
from app.models.task import TaskStatus  # noqa: E402
from app.models.user import Track  # noqa: E402
from app.services import pool_mode as pm  # noqa: E402
from app.services.book_assign import assign_books_to_student  # noqa: E402
from app.services.security import hash_password  # noqa: E402

COACH_EMAIL = "rehber-koc@etutkoc.demo"
STUDENT_EMAIL = "rehber-deniz@etutkoc.demo"
ECE_EMAIL = "rehber-ece@etutkoc.demo"
PARENT_EMAIL = "rehber-veli-deniz@etutkoc.demo"
PASSWORD = "RehberDemo2026!"
CLASS_NAME = "12-A"
TODAY = date.today()

CATALOG = [
    "345 TYT Matematik Soru Bankası",
    "345 TYT Kimya Soru Bankası",
    "345 TYT Fizik Soru Bankası",
    "Biyotik AYT Biyoloji Soru Bankası",
]


def d(n: int) -> date:
    return TODAY + timedelta(days=n)


def _subject(db, name: str) -> Subject:
    s = db.query(Subject).filter(Subject.name == name, Subject.teacher_id.is_(None)).first()
    if s is None:
        raise SystemExit(f"Ders yok: {name}")
    return s


def _topic(db, subject: Subject, name: str) -> Topic:
    t = db.query(Topic).filter(Topic.subject_id == subject.id, Topic.name == name).first()
    if t is None:
        raise SystemExit(f"Konu yok: {subject.name} / {name}")
    return t


def _book_from_catalog(db, coach: User, name: str) -> Book:
    existing = db.query(Book).filter(Book.teacher_id == coach.id, Book.name == name).first()
    if existing:
        return existing
    tpl = db.query(BookTemplate).filter(BookTemplate.name == name, BookTemplate.catalog_status == "verified").first()
    if tpl is None:
        raise SystemExit(f"Katalogda yok: {name}")
    b = Book(teacher_id=coach.id, subject_id=tpl.subject_id, name=tpl.name, publisher=tpl.publisher,
             type=tpl.type, target_grade_min=tpl.target_grade_min, target_grade_max=tpl.target_grade_max,
             target_graduate=tpl.target_graduate, source_kind="catalog", source_template_id=tpl.id)
    db.add(b)
    db.flush()
    for s in sorted(tpl.sections, key=lambda x: x.order):
        db.add(BookSection(book_id=b.id, label=s.label, test_count=s.default_test_count,
                           order=s.order, topic_id=s.topic_id))
    db.flush()
    return b


def _section(db, book: Book, label_start: str) -> BookSection:
    for s in sorted(book.sections, key=lambda x: x.order):
        if s.label.startswith(label_start):
            return s
    raise SystemExit(f"Bölüm yok: {book.name} / {label_start}")


def _cup(db, item: PoolItem, day: date, count: int, done: int | None = None, dyb=None,
         hour: int = 20) -> Task:
    """Kaba al; done verilirse öğrencinin işaretlemesini taklit et (kitap sayacı dahil)."""
    t = pm.put_in_cup(db, item=item, day=day, count=count)
    if done:
        for bi in t.book_items:
            bi.completed_count = done
            if dyb:
                bi.correct_count, bi.wrong_count, bi.blank_count = dyb
            if bi.book_section_id:
                sb = db.query(StudentBook).filter(StudentBook.student_id == item.student_id,
                                                  StudentBook.book_id == bi.book_id).first()
                sp = db.query(SectionProgress).filter(SectionProgress.student_book_id == sb.id,
                                                      SectionProgress.book_section_id == bi.book_section_id).first()
                if sp:
                    sp.completed_count = (sp.completed_count or 0) + done
        t.status = TaskStatus.COMPLETED if done >= count else TaskStatus.PARTIAL
        t.completed_at = datetime.combine(day, time(hour, 30), tzinfo=timezone.utc)
        db.flush()
        pm.sync_item_progress(db, item)
    return t


def delete() -> None:
    for email in (STUDENT_EMAIL, ECE_EMAIL):
        _delete_one(email)
    with SessionLocal() as db:
        from app.models import ParentStudentLink

        v = db.query(User).filter(User.email == PARENT_EMAIL).first()
        if v is not None:
            db.execute(sa_delete(ParentStudentLink).where(ParentStudentLink.parent_id == v.id))
            db.execute(sa_delete(User).where(User.id == v.id))
            db.commit()


def _delete_one(email: str) -> None:
    with SessionLocal() as db:
        s = db.query(User).filter(User.email == email).first()
        if s is None:
            return
        tids = [r[0] for r in db.query(Task.id).filter(Task.student_id == s.id).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id == s.id))
        db.execute(sa_delete(PoolItem).where(PoolItem.student_id == s.id))
        db.execute(sa_delete(StudyPeriod).where(StudyPeriod.student_id == s.id))
        sbs = [r[0] for r in db.query(StudentBook.id).filter(StudentBook.student_id == s.id).all()]
        if sbs:
            db.execute(sa_delete(SectionProgress).where(SectionProgress.student_book_id.in_(sbs)))
        db.execute(sa_delete(StudentBook).where(StudentBook.student_id == s.id))
        from app.models import CoachingSession

        db.execute(sa_delete(CoachingSession).where(CoachingSession.student_id == s.id))
        db.execute(sa_delete(User).where(User.id == s.id))
        db.commit()
        print(f"{s.full_name} (#{s.id}) ve havuz verisi silindi.")


def seed() -> None:
    delete()
    with SessionLocal() as db:
        coach = db.query(User).filter(User.email == COACH_EMAIL).first()
        if coach is None:
            raise SystemExit("Önce: python -m scripts.seed_guide_demo")
        s = User(email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD), full_name="Deniz Arslan",
                 role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                 track=Track.SAYISAL, program_mode="gun_gun", class_group=CLASS_NAME,
                 email_verified_at=datetime.now(timezone.utc),
                 created_at=datetime.now(timezone.utc) - timedelta(days=60),
                 last_seen_at=datetime.now(timezone.utc) - timedelta(hours=3))
        db.add(s)
        db.flush()

        books = [_book_from_catalog(db, coach, n) for n in CATALOG]
        assign_books_to_student(db, s.id, books)
        b_mat, b_kim, b_fiz, b_bio = books

        mat = db.get(Subject, b_mat.subject_id)
        kim = db.get(Subject, b_kim.subject_id)
        fiz = db.get(Subject, b_fiz.subject_id)
        bio = db.get(Subject, b_bio.subject_id)
        tur = _subject(db, "TYT Türkçe")
        geo = _subject(db, "TYT Geometri")

        cg = pm.get_or_create_class_group(db, coach=coach, name=CLASS_NAME)
        pm.set_lesson_days(db, cg, {
            0: [mat.id, fiz.id], 1: [kim.id, tur.id], 2: [mat.id, bio.id],
            3: [fiz.id, geo.id], 4: [kim.id, mat.id], 5: [tur.id],
        })

        s.program_mode = "havuz"
        db.flush()

        sec_mat = [_section(db, b_mat, x) for x in ("Köklü", "Çarpanlara")]
        sec_mat_past = [_section(db, b_mat, x) for x in ("Gerçel Sayılar - 1", "Mutlak", "Üslü")]
        sec_kim_past = _section(db, b_kim, "Periyodik Özellikler")
        sec_kim = _section(db, b_kim, "Mol")
        sec_fiz = _section(db, b_fiz, "Madde")
        sec_bio = sorted(b_bio.sections, key=lambda x: x.order)[0]

        t_fiz_hareket = _topic(db, fiz, "Hareket")
        t_fiz_past = _topic(db, fiz, "Kütle, Hacim ve Özkütle")
        t_par = _topic(db, tur, "Paragrafta Ana Düşünce")
        t_par2 = _topic(db, tur, "Paragrafta Yardımcı Düşünce")
        t_geo = _topic(db, geo, "Üçgende Açılar")

        # ---- 3 kapanmış dönem (her biri 7 gün) — tempo tabanı + geçmiş kartları
        starts = [d(-25), d(-18), d(-11)]
        prev_leftover: PoolItem | None = None
        for k, st in enumerate(starts):
            nxt = st + timedelta(days=7)
            p = pm.open_period(db, student=s, coach=coach, opened_on=st, expected_next_on=nxt)
            i1 = pm.add_item(db, period=p, student=s, subject=mat, quantity=9, unit="test",
                             book=b_mat, section=sec_mat_past[k])
            i2 = pm.add_item(db, period=p, student=s, subject=kim, quantity=3, unit="test",
                             book=b_kim, section=sec_kim_past)
            i3 = pm.add_item(db, period=p, student=s, subject=tur, quantity=8, unit="test", topic=t_par)
            i5 = pm.add_item(db, period=p, student=s, subject=fiz, quantity=6, unit="test", topic=t_fiz_past)
            i4 = pm.add_item(db, period=p, student=s, subject=geo, quantity=4, unit="test", topic=t_geo)
            if prev_leftover is not None:
                pm.carry_item(db, item=prev_leftover, target=p, student=s, coach=coach, quantity=None)
            days = [
                [(i1, 2, 2, (17, 3, 0)), (i3, 2, 2, (18, 2, 0))],
                [(i1, 2, 2, (15, 4, 1)), (i5, 2, 2, (14, 5, 1))],
                [(i2, 1, 1, (7, 2, 1)), (i3, 2, 2, (17, 3, 0))],
                [(i1, 2, 2, (16, 3, 1)), (i5, 2, 2, (13, 6, 1))],
                [(i3, 2, 2, (19, 1, 0)), (i1, 2, 1, (8, 2, 0))],
                [(i5, 2, 2, (15, 4, 1)), (i3, 2, 1, (9, 1, 0))],
            ]
            for off, entries in enumerate(days):
                for item, n, done, dyb in entries:
                    _cup(db, item, st + timedelta(days=off), n, done=done, dyb=dyb)
                pm.close_day(db, student=s, day=st + timedelta(days=off))
            if k == 1:
                pm.session_mark(db, item=i2, actor=coach, count=2)
            pm.close_period(db, p, closed_on=nxt)
            # Geometri hep yarım kalır: 2. dönemden sonra devredilir → güncel dönemde "Devir ×2"
            prev_leftover = i4 if k >= 1 else None

        # ---- GÜNCEL dönem: 4 gün önce açıldı, beklenen seans 3 gün sonra
        last_closed = pm.latest_closed_period(db, s.id)
        geo_left = [it for it in last_closed.items if it.subject_id == geo.id and it.remaining > 0]
        geo_left.sort(key=lambda it: -(it.carry_count or 0))
        cur = pm.open_period(db, student=s, coach=coach, opened_on=d(-4), expected_next_on=d(3),
                             carry=[(geo_left[0].id, None)] if geo_left else None)
        c_mat = pm.add_item(db, period=cur, student=s, subject=mat, quantity=8, unit="test",
                            book=b_mat, section=sec_mat[0])
        c_mat2 = pm.add_item(db, period=cur, student=s, subject=mat, quantity=5, unit="test",
                             book=b_mat, section=sec_mat[1])
        c_kim = pm.add_item(db, period=cur, student=s, subject=kim, quantity=6, unit="test",
                            book=b_kim, section=sec_kim)
        c_fiz = pm.add_item(db, period=cur, student=s, subject=fiz, quantity=5, unit="test",
                            topic=t_fiz_hareket)
        c_fiz_b = pm.add_item(db, period=cur, student=s, subject=fiz, quantity=4, unit="test",
                              book=b_fiz, section=sec_fiz)
        c_bio = pm.add_item(db, period=cur, student=s, subject=bio, quantity=4, unit="test",
                            book=b_bio, section=sec_bio)
        c_tur = pm.add_item(db, period=cur, student=s, subject=tur, quantity=6, unit="test", topic=t_par2)
        c_hw = pm.add_item(db, period=cur, student=s, subject=mat, quantity=12, unit="sayfa",
                           label="Okul ödevi: fonksiyonlar çalışma kâğıdı", teacher_homework=True)
        c_vid = pm.add_item(db, period=cur, student=s, subject=fiz, quantity=None, unit="etkinlik",
                            label="Hareket konu anlatım videosu")
        c_own = pm.add_item(db, period=cur, student=s, subject=tur, quantity=3, unit="test",
                            label="Kendi paragraf denemem", source="ogrenci", created_by=s)
        for it in cur.items:
            it.created_at = datetime.combine(d(-4), time(18), tzinfo=timezone.utc)
        c_own.created_at = datetime.combine(d(-1), time(21), tzinfo=timezone.utc)
        db.flush()

        # Geçmiş günler (öğrencinin kapları + işaretleri)
        plan = [
            (-4, [(c_mat, 3, 3, (25, 4, 1)), (c_fiz, 2, 2, (13, 6, 1)), (c_vid, None, 1, None)]),
            (-3, [(c_kim, 2, 2, (16, 3, 1)), (c_tur, 2, 2, (19, 1, 0)), (c_bio, 2, 1, (8, 3, 1))]),
            (-2, [(c_mat, 3, 2, (15, 7, 2)), (c_hw, 6, 6, None)]),
            (-1, [(c_mat2, 2, 2, (17, 4, 3)), (c_tur, 2, 2, (18, 2, 0)), (c_fiz_b, 2, 2, (14, 5, 1))]),
        ]
        for off, entries in plan:
            for item, n, done, dyb in entries:
                _cup(db, item, d(off), n if n else 1, done=done, dyb=dyb, hour=19)
            pm.close_day(db, student=s, day=d(off))

        # Kaçınılan kalem: Kimya — 3 kez kaba alınıp hiç dokunulmadan döndü
        geo_cur = [it for it in cur.items if it.subject_id == geo.id]
        for off in (-3, -2, -1):
            pm.put_in_cup(db, item=geo_cur[0] if geo_cur else c_kim, day=d(off), count=2)
            pm.close_day(db, student=s, day=d(off))

        # Bugünün kabı (açık)
        _cup(db, c_mat, d(0), 2, done=1, dyb=(8, 2, 0))
        _cup(db, c_kim, d(0), 2)
        _cup(db, c_tur, d(0), 2)

        # ---- Ece: dünkü seansta dönemi kapandı, yeni dönem henüz açılmadı (devir listesi)
        e = User(email=ECE_EMAIL, password_hash=hash_password(PASSWORD), full_name="Ece Yıldız",
                 role=UserRole.STUDENT, is_active=True, teacher_id=coach.id, grade_level=12,
                 track=Track.SAYISAL, program_mode="havuz", class_group=CLASS_NAME,
                 email_verified_at=datetime.now(timezone.utc),
                 created_at=datetime.now(timezone.utc) - timedelta(days=40),
                 last_seen_at=datetime.now(timezone.utc) - timedelta(hours=20))
        db.add(e)
        db.flush()
        assign_books_to_student(db, e.id, [b_mat, b_kim])
        pe = pm.open_period(db, student=e, coach=coach, opened_on=d(-8), expected_next_on=d(-1))
        e1 = pm.add_item(db, period=pe, student=e, subject=mat, quantity=8, unit="test",
                         book=b_mat, section=sec_mat[0])
        e2 = pm.add_item(db, period=pe, student=e, subject=kim, quantity=5, unit="test",
                         book=b_kim, section=sec_kim)
        e3 = pm.add_item(db, period=pe, student=e, subject=tur, quantity=6, unit="test", topic=t_par)
        e4 = pm.add_item(db, period=pe, student=e, subject=fiz, quantity=4, unit="test", topic=t_fiz_hareket)
        for off, entries in [
            (-8, [(e1, 2, 2, (16, 3, 1)), (e3, 2, 2, (18, 2, 0))]),
            (-7, [(e1, 2, 2, (15, 4, 1)), (e4, 2, 2, (14, 5, 1))]),
            (-5, [(e2, 2, 1, (7, 2, 1)), (e3, 2, 2, (17, 3, 0))]),
            (-3, [(e4, 2, 2, (13, 6, 1)), (e1, 2, 1, (8, 2, 0))]),
        ]:
            for item, n, done, dyb in entries:
                _cup(db, item, d(off), n, done=done, dyb=dyb)
            pm.close_day(db, student=e, day=d(off))
        pm.close_period(db, pe, closed_on=d(-1))

        # Deniz'in velisi (veli rehberinde havuz kartı ekranı için; Elif'in velisine dokunmaz)
        from app.models import ParentStudentLink
        from app.models.parent import ParentRelation

        v = User(email=PARENT_EMAIL, password_hash=hash_password(PASSWORD), full_name="Selin Arslan",
                 role=UserRole.PARENT, is_active=True, email_verified_at=datetime.now(timezone.utc),
                 created_at=datetime.now(timezone.utc) - timedelta(days=50))
        db.add(v)
        db.flush()
        db.add(ParentStudentLink(parent_id=v.id, student_id=s.id, relation=ParentRelation.ANNE, is_primary=True))

        db.commit()
        n_items = db.query(PoolItem).filter(PoolItem.period_id == cur.id).count()
        print(f"Deniz Arslan #{s.id} · havuz · güncel dönem #{cur.id} ({n_items} kalem) · 3 kapanmış dönem")
        print(f"  öğrenci: {STUDENT_EMAIL} / {PASSWORD}")
        print(f"  havuz:   /teacher/students/{s.id}/pool")
        print(f"Ece Yıldız #{e.id} · dönemi dün kapandı, devir bekliyor → /teacher/students/{e.id}/pool")


if __name__ == "__main__":
    if "--delete" in sys.argv:
        delete()
    else:
        seed()
