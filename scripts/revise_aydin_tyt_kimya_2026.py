"""Aydın TYT Kimya — güncel baskıya geçiş (2026-10-13, koç isteği).

1) KATALOG: verified "Aydın TYT Kimya Soru Bankası" kaydı (eski tarama, 70 bölüm)
   YERİNDE güncel baskıya çevrilir: ad "Aydın TYT Kimya Konu Özetli Soru Bankası",
   bölümler data/kitap-katalog/aydin_tyt_kimya_guncel.json (82 bölüm / 139 test;
   kaynak: Aydın çözüm uygulaması kitap #532). Kayıt id'si korunur.
2) ÖĞRENCİ (--student N --old-book M): koçun eski kitabı başka öğrencilerde de
   kullanıldığı için ona DOKUNULMAZ. Koça katalogdan yeni kitap açılır, öğrenciye
   atanır; öğrencinin eski kitaptaki görev kalemleri yeni bölümlere TAŞINIR
   (ünite içi test SIRASINA göre: eski ve yeni baskıda ünite başına test sayısı
   aynı); bir kalem birden çok yeni bölüme düşüyorsa bölünür (D/Y orantılı).
   Sonra öğrencinin eski kitap ataması kaldırılır, sayaçlar kalemlerden kurulur.

  python -m scripts.revise_aydin_tyt_kimya_2026 --student 164 --old-book 358          # kuru
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
from app.services import book_catalog as catalog_svc  # noqa: E402
from app.services import section_counter_service as counters  # noqa: E402
from app.services import task_titles  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON = os.path.join(ROOT, "data/kitap-katalog/aydin_tyt_kimya_guncel.json")
OLD_NAME = "Aydın TYT Kimya Soru Bankası"
SCORE_FIELDS = ("correct_count", "wrong_count", "blank_count")


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


def main() -> int:
    apply = "--apply" in sys.argv
    sid, old_book_id = arg("--student"), arg("--old-book")
    data = json.load(open(JSON, encoding="utf-8"))
    secs = data["sections"]
    with SessionLocal() as db:
        # ---- 1) katalog
        tpl = (db.query(BookTemplate)
               .filter(BookTemplate.teacher_id.is_(None), BookTemplate.name.in_([OLD_NAME, data["name"]]))
               .first())
        if tpl is None:
            raise SystemExit("HATA: katalog kaydı yok")
        print(f"KATALOG #{tpl.id} '{tpl.name}' {len(tpl.sections)} bölüm/"
              f"{sum(s.default_test_count for s in tpl.sections)} test → '{data['name']}' "
              f"{len(secs)}/{sum(s['test_count'] for s in secs)}")
        new_tpl = [(s["label"], s["test_count"], topic_id(db, tpl.subject_id, s.get("topic"))) for s in secs]
        if apply:
            for s in list(tpl.sections):
                db.delete(s)
            db.flush()
            tpl.name = data["name"]
            tpl.name_normalized = catalog_svc.normalized_key(data["name"]) or None
            for i, (lab, cnt, tid) in enumerate(new_tpl):
                db.add(BookTemplateSection(template_id=tpl.id, label=lab, default_test_count=cnt,
                                           order=i, topic_id=tid))
            db.flush()
            db.refresh(tpl)

        if not sid:
            if apply:
                db.commit()
                print("UYGULANDI (yalnız katalog).")
            return 0

        # ---- 2) öğrenci
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
            ot, nt = sum(s.test_count for s in ou), sum(s["test_count"] for s in nu)
            if ot != nt:
                raise SystemExit(f"HATA: ünite {ui + 1} test sayısı farklı {ot}≠{nt}")
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

        rows = (db.query(TaskBookItem, Task).join(Task, Task.id == TaskBookItem.task_id)
                .filter(Task.student_id == st.id, TaskBookItem.book_id == old.id)
                .order_by(Task.date, Task.id, TaskBookItem.id).all())
        cursor: dict[int, int] = {}
        plan = []
        for it, t in rows:
            ui, positions = old_pos[it.book_section_id]
            c0 = cursor.get(it.book_section_id, 0)
            parts: dict[int, int] = {}
            for k in range(it.planned_count):
                pos = positions[min(c0 + k, len(positions) - 1)]
                ni = new_at[(ui, pos)]
                parts[ni] = parts.get(ni, 0) + 1
            cursor[it.book_section_id] = c0 + it.planned_count
            plan.append((it, t, sorted(parts.items())))
            print(f"  görev #{t.id} {t.date} '{it.section.label}' {it.completed_count}/{it.planned_count} → "
                  + " + ".join(f"'{secs[ni]['label']}' ×{n}" for ni, n in sorted(parts.items())))

        if not apply:
            db.rollback()
            print("\n(kuru çalışma — --apply ile uygula)")
            return 0

        book = Book(teacher_id=coach.id, subject_id=tpl.subject_id, name=tpl.name, publisher=tpl.publisher,
                    type=tpl.type, target_grade_min=tpl.target_grade_min, target_grade_max=tpl.target_grade_max,
                    target_graduate=bool(tpl.target_graduate), source_kind="catalog", source_template_id=tpl.id)
        db.add(book)
        db.flush()
        new_secs = []
        for ts in sorted(tpl.sections, key=lambda s: s.order):
            bs = BookSection(book_id=book.id, label=ts.label, test_count=ts.default_test_count,
                             order=ts.order, topic_id=ts.topic_id)
            db.add(bs)
            new_secs.append(bs)
        db.flush()
        catalog_svc.bump_usage(tpl)
        sb = StudentBook(student_id=st.id, book_id=book.id)
        db.add(sb)
        db.flush()
        for bs in new_secs:
            db.add(SectionProgress(student_book_id=sb.id, book_section_id=bs.id,
                                   reserved_count=0, completed_count=0))
        db.flush()

        touched = set()
        for it, t, parts in plan:
            total = it.planned_count or 1
            scores = {f: getattr(it, f) for f in SCORE_FIELDS}
            done_left = it.completed_count or 0
            for idx, (ni, n) in enumerate(parts):
                comp = min(n, done_left)
                done_left -= comp
                tgt = it if idx == 0 else TaskBookItem(task_id=t.id,
                                                      reservation_released_at=it.reservation_released_at)
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
        db.flush()

        for sp in db.query(SectionProgress).filter_by(student_book_id=old_sb.id).all():
            db.delete(sp)
        db.delete(old_sb)
        db.flush()

        res = counters.reconcile_student_book(db, student_book_id=sb.id)
        print(f"\nsayaç kurulumu: {res['fixed']} bölüm")
        for d in res["details"]:
            print("   ", d)
        db.flush()
        db.expire_all()  # kalemlerin eski bölüm ilişkisi önbellekte kalmasın (başlık eski adı alıyordu)
        for tid in touched:
            t = db.get(Task, tid)
            task_titles.refresh_auto_title(t)
        db.commit()
        print(f"\nUYGULANDI: yeni kitap #{book.id}, atama #{sb.id}; eski atama #{old_sb.id} kaldırıldı.")
        print("kalan sapma:", len(counters.compute_fixes(db, student_book_id=sb.id)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
