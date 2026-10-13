"""Aydın TYT Kimya — güncel baskıya geçiş (2026-10-13, koç isteği).

1) KATALOG: verified "Aydın TYT Kimya Soru Bankası" kaydı (eski tarama, 70 bölüm)
   YERİNDE güncel baskıya çevrilir: ad "Aydın TYT Kimya Konu Özetli Soru Bankası",
   bölümler data/kitap-katalog/aydin_tyt_kimya_guncel.json (82 bölüm / 139 test;
   kaynak: Aydın çözüm uygulaması kitap #532). Kayıt id'si korunur. Kayıt zaten
   güncelse yalnız konu eşlemeleri JSON'dan senkronlanır (katalog + bu kayıttan
   açılmış koç kitapları).
2) ÖĞRENCİ (--student N --old-book M): koçun kataloğun güncel kaydından açılmış
   kitabı varsa o kullanılır, yoksa açılır; öğrenciye atanır. Öğrencinin eski
   kitaptaki görev kalemleri + bağımsız çalışma kayıtları yeni bölümlere TAŞINIR
   (ünite içi test SIRASINA göre: önce görev kalemleri tarih sırasıyla, sonra
   bağımsız çalışma kayıtları; eski ve yeni baskıda ünite başına test sayısı
   aynı). Birden çok yeni bölüme düşen kayıt bölünür (D/Y orantılı). Öğrencinin
   iskelet satırları yeni kitaba bağlanır. Eski atama kaldırılır; eski kitaba
   (başka öğrenciler için) dokunulmaz.

  python -m scripts.revise_aydin_tyt_kimya_2026                                         # kuru (katalog)
  python -m scripts.revise_aydin_tyt_kimya_2026 --student 164 --old-book 358 --apply
"""
from __future__ import annotations

import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Book, BookSection, BookTemplate, BookTemplateSection, SectionProgress, StudentBook,
    Task, TaskBookItem, Topic, User,
)
from app.models.self_study import SelfStudyEntry  # noqa: E402
from app.models.weekly_skeleton import WeeklySkeleton, WeeklySkeletonSlot  # noqa: E402
from app.services import book_catalog as catalog_svc  # noqa: E402
from app.services import section_counter_service as counters  # noqa: E402
from app.services import task_titles  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON = os.path.join(ROOT, "data/kitap-katalog/aydin_tyt_kimya_guncel.json")
OLD_NAME = "Aydın TYT Kimya Soru Bankası"
SCORE_FIELDS = ("correct_count", "wrong_count", "blank_count")
SS_COPY = ("student_id", "source", "status", "note", "period_start", "period_end", "created_by_id",
           "created_at", "reviewed_by_id", "reviewed_at", "review_note")


def arg(name):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else None
    return None


def topic_id(db, subject_id, name):
    if not name:
        return None
    t = db.query(Topic).filter(Topic.subject_id == subject_id, Topic.name == name).first()
    if t is None:
        raise SystemExit(f"HATA: '{name}' konusu ders #{subject_id} içinde yok")
    return t.id


def split_units(sections, is_end):
    units, cur = [], []
    for s in sections:
        cur.append(s)
        if is_end(s):
            units.append(cur)
            cur = []
    if cur:
        units.append(cur)
    return units


def catalog_step(db, data, apply):
    secs = data["sections"]
    tpl = (db.query(BookTemplate)
           .filter(BookTemplate.teacher_id.is_(None), BookTemplate.name.in_([OLD_NAME, data["name"]]))
           .first())
    if tpl is None:
        raise SystemExit("HATA: katalog kaydı yok")
    wanted = [(s["label"], s["test_count"], topic_id(db, tpl.subject_id, s.get("topic"))) for s in secs]
    if tpl.name == data["name"]:
        # zaten güncel → yalnız konu eşlemesi senkronu
        by_label = {lab: tid for lab, _, tid in wanted}
        books = db.query(Book).filter(Book.source_template_id == tpl.id, Book.name == data["name"]).all()
        n = 0
        for row in list(tpl.sections) + [s for b in books for s in b.sections]:
            tid = by_label.get(row.label)
            if row.label in by_label and row.topic_id != tid:
                print(f"  konu: '{row.label}' → {tid}")
                row.topic_id = tid
                n += 1
        print(f"KATALOG #{tpl.id} güncel; {n} konu eşlemesi düzeltildi ({len(books)} koç kitabı dahil)")
        return tpl
    print(f"KATALOG #{tpl.id} '{tpl.name}' {len(tpl.sections)} bölüm → '{data['name']}' "
          f"{len(secs)}/{sum(s['test_count'] for s in secs)}")
    if apply:
        for s in list(tpl.sections):
            db.delete(s)
        db.flush()
        tpl.name = data["name"]
        tpl.name_normalized = catalog_svc.normalized_key(data["name"]) or None
        for i, (lab, cnt, tid) in enumerate(wanted):
            db.add(BookTemplateSection(template_id=tpl.id, label=lab, default_test_count=cnt,
                                       order=i, topic_id=tid))
        db.flush()
        db.refresh(tpl)
    return tpl


def main() -> int:
    apply = "--apply" in sys.argv
    sid, old_book_id = arg("--student"), arg("--old-book")
    data = json.load(open(JSON, encoding="utf-8"))
    secs = data["sections"]
    with SessionLocal() as db:
        tpl = catalog_step(db, data, apply)
        if not sid:
            if apply:
                db.commit()
                print("UYGULANDI (katalog).")
            else:
                db.rollback()
            return 0

        st = db.get(User, int(sid))
        old = db.get(Book, int(old_book_id))
        coach = db.get(User, st.teacher_id)
        old_sb = db.query(StudentBook).filter_by(student_id=st.id, book_id=old.id).first()
        if old_sb is None or old.teacher_id != coach.id:
            raise SystemExit("HATA: eski kitap öğrencide/koçta değil")
        print(f"\nÖĞRENCİ #{st.id} {st.full_name} · koç #{coach.id} · eski kitap #{old.id} '{old.name}'")

        old_secs = sorted(old.sections, key=lambda s: (s.order, s.id))
        old_units = split_units(old_secs, lambda s: s.label.startswith("Beceri Temelli"))
        new_units = split_units(secs, lambda s: s["label"].startswith("Beceri Temelli"))
        if not (len(old_units) == len(new_units) == 13):
            raise SystemExit(f"HATA: ünite sayısı {len(old_units)}/{len(new_units)}")
        old_pos, new_at = {}, {}
        gi = 0
        for ui, (ou, nu) in enumerate(zip(old_units, new_units)):
            if sum(s.test_count for s in ou) != sum(s["test_count"] for s in nu):
                raise SystemExit(f"HATA: ünite {ui + 1} test sayısı farklı")
            p = 0
            for s in ou:
                old_pos[s.id] = (ui, list(range(p, p + s.test_count)))
                p += s.test_count
            p = 0
            for s in nu:
                for _ in range(s["test_count"]):
                    new_at[(ui, p)] = gi
                    p += 1
                gi += 1

        cursor: dict[int, int] = {}

        def parts_for(sec_id, n):
            ui, positions = old_pos[sec_id]
            c0 = cursor.get(sec_id, 0)
            out: dict[int, int] = {}
            for k in range(n):
                ni = new_at[(ui, positions[min(c0 + k, len(positions) - 1)])]
                out[ni] = out.get(ni, 0) + 1
            cursor[sec_id] = c0 + n
            return sorted(out.items())

        def fmt(parts):
            return " + ".join(f"'{secs[ni]['label']}' ×{n}" for ni, n in parts)

        rows = (db.query(TaskBookItem, Task).join(Task, Task.id == TaskBookItem.task_id)
                .filter(Task.student_id == st.id, TaskBookItem.book_id == old.id)
                .order_by(Task.date, Task.id, TaskBookItem.id).all())
        item_plan = []
        for it, t in rows:
            parts = parts_for(it.book_section_id, it.planned_count)
            item_plan.append((it, t, parts))
            print(f"  görev #{t.id} {t.date} '{it.section.label}' {it.completed_count}/{it.planned_count} → {fmt(parts)}")
        ss_rows = (db.query(SelfStudyEntry)
                   .filter(SelfStudyEntry.student_id == st.id, SelfStudyEntry.student_book_id == old_sb.id)
                   .order_by(SelfStudyEntry.created_at, SelfStudyEntry.id).all())
        ss_plan = []
        for e in ss_rows:
            n = max(e.test_count or 0, e.applied_count or 0)
            parts = parts_for(e.book_section_id, n) if n else [(new_at[(old_pos[e.book_section_id][0], old_pos[e.book_section_id][1][0])], 0)]
            ss_plan.append((e, parts))
            print(f"  bağımsız #{e.id} [{e.status}] {db.get(BookSection, e.book_section_id).label} "
                  f"{e.applied_count}/{e.test_count} → {fmt(parts)}")
        slots = (db.query(WeeklySkeletonSlot).join(WeeklySkeleton, WeeklySkeleton.id == WeeklySkeletonSlot.skeleton_id)
                 .filter(WeeklySkeleton.student_id == st.id,
                         (WeeklySkeletonSlot.book_id == old.id) | (WeeklySkeletonSlot.second_book_id == old.id))
                 .all())
        print(f"  iskelet satırı: {len(slots)}")

        if not apply:
            db.rollback()
            print("\n(kuru çalışma — --apply ile uygula)")
            return 0

        book = (db.query(Book).filter(Book.teacher_id == coach.id, Book.source_template_id == tpl.id,
                                      Book.name == tpl.name).first())
        if book is None:
            book = Book(teacher_id=coach.id, subject_id=tpl.subject_id, name=tpl.name, publisher=tpl.publisher,
                        type=tpl.type, target_grade_min=tpl.target_grade_min, target_grade_max=tpl.target_grade_max,
                        target_graduate=bool(tpl.target_graduate), source_kind="catalog", source_template_id=tpl.id)
            db.add(book)
            db.flush()
            for ts in sorted(tpl.sections, key=lambda s: s.order):
                db.add(BookSection(book_id=book.id, label=ts.label, test_count=ts.default_test_count,
                                   order=ts.order, topic_id=ts.topic_id))
            db.flush()
            catalog_svc.bump_usage(tpl)
            db.refresh(book)
            print(f"  yeni kitap #{book.id}")
        else:
            print(f"  mevcut kitap #{book.id} kullanılıyor")
        new_secs = sorted(book.sections, key=lambda s: (s.order, s.id))
        if [s.label for s in new_secs] != [s["label"] for s in secs]:
            raise SystemExit("HATA: kitabın bölümleri JSON ile aynı değil")
        if db.query(StudentBook).filter_by(student_id=st.id, book_id=book.id).first():
            raise SystemExit("HATA: öğrenci yeni kitaba zaten atanmış")
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        sps = {}
        for bs in new_secs:
            sp = SectionProgress(student_book_id=sb.id, book_section_id=bs.id, reserved_count=0, completed_count=0)
            db.add(sp)
            sps[bs.id] = sp
        db.flush()

        touched = set()
        for it, t, parts in item_plan:
            total = it.planned_count or 1
            scores = {f: getattr(it, f) for f in SCORE_FIELDS}
            left = it.completed_count or 0
            for idx, (ni, n) in enumerate(parts):
                comp = min(n, left)
                left -= comp
                tgt = it if idx == 0 else TaskBookItem(task_id=t.id, reservation_released_at=it.reservation_released_at)
                if idx:
                    db.add(tgt)
                if len(parts) > 1:
                    for f, v in scores.items():
                        setattr(tgt, f, None if v is None else round(v * n / total))
                tgt.book_id = book.id
                tgt.book_section_id = new_secs[ni].id
                tgt.topic_id = None
                tgt.planned_count = n
                tgt.completed_count = comp
            touched.add(t.id)

        manual: dict[int, int] = {}
        for e, parts in ss_plan:
            applied_left = e.applied_count or 0
            for idx, (ni, n) in enumerate(parts):
                ap = min(n, applied_left)
                applied_left -= ap
                tgt = e if idx == 0 else SelfStudyEntry(**{f: getattr(e, f) for f in SS_COPY})
                if idx:
                    db.add(tgt)
                tgt.student_book_id = sb.id
                tgt.book_section_id = new_secs[ni].id
                if len(parts) > 1 or n:
                    tgt.test_count = n
                tgt.applied_count = ap
                manual[new_secs[ni].id] = manual.get(new_secs[ni].id, 0) + ap
        for sec_id, m in manual.items():
            sps[sec_id].manual_count = m
            sps[sec_id].completed_count = m
        for s in slots:
            if s.book_id == old.id:
                s.book_id = book.id
            if s.second_book_id == old.id:
                s.second_book_id = book.id
        db.flush()

        # tamamlanan = görev kalemi + bağımsız çalışma (compute_fixes yalnız kalemi sayar → önce elle kur)
        for sec_id, sp in sps.items():
            done = sum((i.completed_count or 0) for i in db.query(TaskBookItem).join(Task)
                       .filter(Task.student_id == st.id, TaskBookItem.book_section_id == sec_id))
            sp.completed_count = done + manual.get(sec_id, 0)
        for sp in db.query(SectionProgress).filter_by(student_book_id=old_sb.id).all():
            db.delete(sp)
        db.delete(old_sb)
        db.flush()

        res = counters.reconcile_student_book(db, student_book_id=sb.id)
        db.flush()
        db.expire_all()
        for tid in touched:
            task_titles.refresh_auto_title(db.get(Task, tid))
        db.commit()
        tot = db.query(SectionProgress).filter_by(student_book_id=sb.id).all()
        print(f"\nUYGULANDI: kitap #{book.id}, atama #{sb.id}; eski atama #{old_sb.id} kaldırıldı. "
              f"rezerv düzeltmesi {res['fixed']} bölüm · çözülen {sum(x.completed_count for x in tot)} "
              f"(elle {sum(x.manual_count or 0 for x in tot)}) · rezerv {sum(x.reserved_count for x in tot)} · "
              f"kalan sapma {len(counters.compute_fixes(db, student_book_id=sb.id))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
