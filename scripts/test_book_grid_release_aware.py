"""Rezerv sayaç tutarlılığı smoke'u — release-aware grid + sayaç bütünlüğü.

Kullanıcı şikâyeti (2026-07-13, Elif/Bilgi Sarmal TDE): kitap detay modalı
"Sayaç uyumsuzluğu: kayıtlı (rezerv 13) gerçek görev listesinden farklı (16)"
uyarısı veriyordu. Kök neden: modalın "gerçek görev listesi" türetimi
(build_book_grid_slots) reconcile/cron'un serbest bıraktığı (reservation_
released_at dolu) kalemleri hâlâ rezerv sayıyordu — kayıtlı sayaç doğruydu.

Bu test:
  A) build_book_grid_slots release-aware: released kalem rezerv slot üretmez;
     taslak yalnız include_drafts=True'da sayılır.
  B) HTTP grid endpoint'i (öğretmen): türetilmiş sayım == kayıtlı sayaç
     (uyarı koşulu FALSE) — baseline ("zaten çözmüştü") dolgusu dahil.
  C) Sayaç bütünlüğü: released kaleme tamamla/geri al/kısmi işaretleme
     başka görevlerin canlı rezervini ÇALMAZ / sahipsiz rezerv BIRAKMAZ.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    SuspiciousIp,
    Task,
    TaskBookItem,
    TaskStatus,
    TaskType,
    Topic,
    User,
    UserRole,
)
from app.services import task_service as ts
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"grid{secrets.token_hex(3)}"
PASSWORD = "Grid!2026X"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def main() -> int:
    print(f"\n=== book grid release-aware smoke — {PFX} ===\n")
    today = date.today()
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Koç", role=UserRole.TEACHER, is_active=True,
                       plan="solo_free", must_change_password=False)
        student = User(email=f"{PFX}-s@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Öğrenci", role=UserRole.STUDENT, is_active=True,
                       grade_level=10)
        db.add_all([teacher, student]); db.flush()
        student.teacher_id = teacher.id
        subj = Subject(name=f"{PFX} Ders", order=999, is_builtin=False, teacher_id=teacher.id)
        db.add(subj); db.flush()
        topic = Topic(name="Konu", order=1, subject_id=subj.id); db.add(topic); db.flush()
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Bölüm X", test_count=20, order=1,
                          topic_id=topic.id)
        db.add(sec); db.flush()
        sb = StudentBook(student_id=student.id, book_id=book.id); db.add(sb); db.flush()
        sp = SectionProgress(student_book_id=sb.id, book_section_id=sec.id,
                             reserved_count=7, completed_count=0)
        db.add(sp); db.flush()
        # Görev A: GEÇMİŞ hafta, yapılmamış (rezerv 4) — reconcile serbest bırakacak
        t_a = Task(student_id=student.id, date=today - timedelta(days=7),
                   type=TaskType.TEST, title="Geçmiş", status=TaskStatus.PENDING,
                   order=0, is_draft=False)
        db.add(t_a); db.flush()
        i_a = TaskBookItem(task_id=t_a.id, book_id=book.id, book_section_id=sec.id,
                           planned_count=4, completed_count=0)
        db.add(i_a)
        # Görev B: gelecek, canlı rezerv 3
        t_b = Task(student_id=student.id, date=today + timedelta(days=1),
                   type=TaskType.TEST, title="Gelecek", status=TaskStatus.PENDING,
                   order=0, is_draft=False)
        db.add(t_b); db.flush()
        i_b = TaskBookItem(task_id=t_b.id, book_id=book.id, book_section_id=sec.id,
                           planned_count=3, completed_count=0)
        db.add(i_b)
        db.commit()
        ids = {"teacher": teacher.id, "student": student.id, "subj": subj.id,
               "book": book.id, "sec": sec.id, "sp": sp.id,
               "t_a": t_a.id, "i_a": i_a.id, "t_b": t_b.id, "i_b": i_b.id}

    try:
        from app.routes.teacher_program import build_book_grid_slots

        with SessionLocal() as db:
            sid = ids["student"]

            # --- A) reconcile → released kalem rezerv slot üretmez ---
            res = ts.reconcile_past_reservations(db, student_id=sid, cutoff_date=today)
            db.commit()
            check("A1. reconcile geçmiş görevin 4 rezervini serbest bıraktı",
                  res["released_tests"] == 4 and
                  db.get(SectionProgress, ids["sp"]).reserved_count == 3,
                  f"res={res}, stored={db.get(SectionProgress, ids['sp']).reserved_count}")
            slots = build_book_grid_slots(db, sid, [ids["sec"]],
                                          teacher_student_id=sid)
            n_res = len(slots[ids["sec"]]["reserved"])
            check("A2. grid released kalemi REZERV SAYMAZ (3 slot — eski hâli 7 idi)",
                  n_res == 3, f"got {n_res}")
            check("A3. türetilmiş rezerv == kayıtlı sayaç (uyumsuzluk uyarısı biter)",
                  n_res == db.get(SectionProgress, ids["sp"]).reserved_count,
                  f"derived={n_res}")

            # Taslak görev: rezerv tutar → yalnız include_drafts=True'da görünür
            t_d = Task(student_id=sid, date=today + timedelta(days=2),
                       type=TaskType.TEST, title="Taslak", status=TaskStatus.PENDING,
                       order=0, is_draft=True)
            db.add(t_d); db.flush()
            db.add(TaskBookItem(task_id=t_d.id, book_id=ids["book"],
                                book_section_id=ids["sec"], planned_count=2,
                                completed_count=0))
            ts.reserve_item(db, student_id=sid, book_id=ids["book"],
                            section_id=ids["sec"], count=2)
            db.commit()
            ids["t_d"] = t_d.id
            slots_t = build_book_grid_slots(db, sid, [ids["sec"]],
                                            teacher_student_id=sid, include_drafts=True)
            slots_s = build_book_grid_slots(db, sid, [ids["sec"]],
                                            teacher_student_id=None)
            check("A4. taslak rezervi öğretmen görünümünde sayılır (3+2=5)",
                  len(slots_t[ids["sec"]]["reserved"]) == 5,
                  f"got {len(slots_t[ids['sec']]['reserved'])}")
            check("A5. öğrenci görünümünde taslak SIZMAZ (3)",
                  len(slots_s[ids["sec"]]["reserved"]) == 3,
                  f"got {len(slots_s[ids['sec']]['reserved'])}")

            # --- B) HTTP grid endpoint — türetilmiş == kayıtlı + baseline dolgu ---
            # Baseline: koç "öğrenci 2 test zaten çözmüştü" girdi (görevsiz completed)
            db.get(SectionProgress, ids["sp"]).completed_count += 2
            db.commit()

        get_login_limiter().reset()
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
        client = TestClient(app)
        r = client.post("/api/v2/auth/login",
                        json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        check("B1. koç login 200", r.status_code == 200, r.text[:120])
        r = client.get(f"/api/v2/teacher/students/{ids['student']}/books/{ids['book']}/book-grid")
        check("B2. book-grid 200", r.status_code == 200, r.text[:200])
        data = r.json()
        cell_done = sum(1 for s in data["sections"] for c in s["cells"] if c["state"] == "DONE")
        cell_res = sum(1 for s in data["sections"] for c in s["cells"] if c["state"] == "RESERVED")
        check("B3. hücrelerden sayılan rezerv == kayıtlı sayaç (5: canlı 3 + taslak 2)",
              cell_res == data["total_reserved"] == 5,
              f"cells={cell_res}, stored={data['total_reserved']}")
        check("B4. hücrelerden sayılan çözüldü == kayıtlı sayaç (baseline 2 dolgu)",
              cell_done == data["total_completed"] == 2,
              f"cells={cell_done}, stored={data['total_completed']}")
        baseline_cells = [c for s in data["sections"] for c in s["cells"]
                          if c["state"] == "DONE" and not c.get("task_date")]
        check("B5. baseline hücreleri görevsiz/tarihsiz DONE olarak geldi",
              len(baseline_cells) == 2, f"got {len(baseline_cells)}")

        # --- C) Sayaç bütünlüğü: released kalem üstünde işlemler ---
        with SessionLocal() as db:
            sp = db.get(SectionProgress, ids["sp"])
            base_res, base_comp = sp.reserved_count, sp.completed_count  # 5, 2

            # C1: released görevi TAMAMLA → reserved DEĞİŞMEZ (çalınmaz), completed +4
            t_a = db.get(Task, ids["t_a"])
            ts.complete_task(db, t_a); db.commit()
            sp = db.get(SectionProgress, ids["sp"])
            check("C1. released görevi tamamlamak canlı rezervi ÇALMAZ "
                  f"(reserved {base_res} sabit, completed +4)",
                  sp.reserved_count == base_res and sp.completed_count == base_comp + 4,
                  f"reserved={sp.reserved_count}, completed={sp.completed_count}")

            # C2: geri al → completed geri düşer, rezerv DİRİLMEZ (sahipsiz rezerv yok)
            ts.uncomplete_task(db, t_a); db.commit()
            sp = db.get(SectionProgress, ids["sp"])
            check("C2. geri almak released rezervi DİRİLTMEZ "
                  f"(reserved {base_res} sabit, completed eski değere döndü)",
                  sp.reserved_count == base_res and sp.completed_count == base_comp,
                  f"reserved={sp.reserved_count}, completed={sp.completed_count}")

            # C3: released kalemde kısmi işaretleme (2) → reserved sabit, completed +2
            i_a = db.get(TaskBookItem, ids["i_a"])
            ts.set_item_completion(db, i_a, 2); db.commit()
            sp = db.get(SectionProgress, ids["sp"])
            check("C3. released kalemde kısmi işaretleme rezervden DÜŞMEZ",
                  sp.reserved_count == base_res and sp.completed_count == base_comp + 2,
                  f"reserved={sp.reserved_count}, completed={sp.completed_count}")
            ts.set_item_completion(db, i_a, 0); db.commit()
            sp = db.get(SectionProgress, ids["sp"])
            check("C4. kısmi işaretlemeyi sıfırlamak rezervi ŞİŞİRMEZ",
                  sp.reserved_count == base_res and sp.completed_count == base_comp,
                  f"reserved={sp.reserved_count}, completed={sp.completed_count}")

            # C5: canlı (released olmayan) kalemde normal transfer hâlâ çalışır
            i_b = db.get(TaskBookItem, ids["i_b"])
            ts.set_item_completion(db, i_b, 2); db.commit()
            sp = db.get(SectionProgress, ids["sp"])
            check("C5. canlı kalemde işaretleme rezerv→çözüldü transferi yapar",
                  sp.reserved_count == base_res - 2 and sp.completed_count == base_comp + 2,
                  f"reserved={sp.reserved_count}, completed={sp.completed_count}")
            ts.set_item_completion(db, i_b, 0); db.commit()
            sp = db.get(SectionProgress, ids["sp"])
            check("C6. canlı kalemde geri alma rezervi geri getirir",
                  sp.reserved_count == base_res and sp.completed_count == base_comp,
                  f"reserved={sp.reserved_count}, completed={sp.completed_count}")

            # C7: released görev silinince çift-iade YOK (mevcut guard korunuyor)
            items = db.query(TaskBookItem).filter(TaskBookItem.task_id == ids["t_a"]).all()
            ts.release_task_items(db, ids["student"], items); db.commit()
            sp = db.get(SectionProgress, ids["sp"])
            check("C7. released görev silinirken çift-iade yok (reserved sabit)",
                  sp.reserved_count == base_res, f"reserved={sp.reserved_count}")
    finally:
        with SessionLocal() as db:
            tids = [ids.get("t_a"), ids.get("t_b"), ids.get("t_d")]
            tids = [t for t in tids if t]
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
            db.execute(sa_delete(Task).where(Task.id.in_(tids)))
            db.execute(sa_delete(SectionProgress).where(SectionProgress.id == ids["sp"]))
            db.execute(sa_delete(StudentBook).where(StudentBook.student_id == ids["student"]))
            db.execute(sa_delete(BookSection).where(BookSection.id == ids["sec"]))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.execute(sa_delete(User).where(User.id.in_([ids["student"], ids["teacher"]])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
