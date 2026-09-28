"""Google Play / App Store incelemesi için veli demo verisi (2026-09-28).

Google Play "Misleading Claims" reddi: incelemeci veli özelliklerini (haftalık
çalışma, tamamlama oranı, son deneme netleri, haftalık rapor) göremedi — veli
hesabı verilmemişti ve demo öğrencinin verisi Haziran'da kalmıştı.

Bu betik demo öğrenci (demo-9d11ccce-ogrenci) için bugüne göre GÖRELİ veri kurar:
  - 3 haftalık program (2 hafta önce · geçen hafta · bu hafta), Pzt-Cmt günde
    2 test görevi (Matematik + Türkçe) + Çarşamba video görevi
  - geçmiş günlerin çoğu tamamlanmış (geçen hafta > önceki hafta → yükselen trend)
  - 3 LGS denemesi (yükselen net, ders kırılımlı)
  - veliye koç notu

Yalnız demo hesaplara dokunur. İdempotent: işaretli program varsa atlar.
Kullanım: python -m scripts.seed_play_review_parent_demo [--dry-run]
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, time, timedelta, timezone

from app.database import SessionLocal
from app.models import Task, TaskBookItem, TaskStatus, TaskType, User
from app.models.exam_result import ExamResult, ExamSection, compute_net
from app.models.parent import TeacherNoteToParent
from app.models.weekly_program import WeeklyProgram
from app.services import task_service

MARKER = "[play-review-demo]"
STUDENT_EMAIL = "demo-9d11ccce-ogrenci@etutkoc.com"
COACH_EMAIL = "demo-9d11ccce-koc@etutkoc.com"

MATH_BOOK, MATH_NAME = 137, "Demo Matematik Soru Bankası"
TR_BOOK, TR_NAME = 138, "Demo Türkçe Soru Bankası"
MATH_SECTIONS = [(631, "Eşitsizlikler"), (632, "Üçgenler"), (633, "Olasılık")]
TR_SECTIONS = [(634, "Sözcükte Anlam"), (635, "Cümlede Anlam"),
               (636, "Paragraf"), (637, "Cümlenin Ögeleri")]

# Hafta ofseti (-2/-1/0) → yapılmayacak (gün, ders) çiftleri. gün: 0=Pzt..5=Cmt
MISSED = {
    -2: {(1, "tr"), (3, "mat"), (4, "tr"), (5, "mat")},   # ~%67
    -1: {(4, "tr")},                                       # ~%92
    0: set(),
}


class Cursor:
    """Bölüm kapasitesini sırayla tüketen imleç (kalan < n ise sonrakine geçer)."""

    def __init__(self, db, student_id, book_id, sections):
        self.db, self.sid, self.book = db, student_id, book_id
        self.sections = sections
        self.i = 0

    def take(self, n):
        while self.i < len(self.sections):
            sec_id, label = self.sections[self.i]
            prog, section = task_service._get_progress(self.db, self.sid, self.book, sec_id)
            left = section.test_count - prog.reserved_count - prog.completed_count
            if left >= n:
                return sec_id, label
            self.i += 1
        raise RuntimeError(f"Kitap {self.book} kapasitesi bitti")


def main(dry_run: bool) -> None:
    db = SessionLocal()
    try:
        student = db.query(User).filter(User.email == STUDENT_EMAIL).one()
        coach = db.query(User).filter(User.email == COACH_EMAIL).one()
        if not (student.is_demo and coach.is_demo):
            raise SystemExit("Hedef hesaplar demo değil — durduruldu.")
        if db.query(WeeklyProgram).filter(
            WeeklyProgram.student_id == student.id,
            WeeklyProgram.notes == MARKER,
        ).first():
            print("Zaten kurulmuş (işaretli program var) — atlandı.")
            return

        today = date.today()
        monday = today - timedelta(days=today.weekday())
        now = datetime.now(timezone.utc)
        math = Cursor(db, student.id, MATH_BOOK, MATH_SECTIONS)
        tr = Cursor(db, student.id, TR_BOOK, TR_SECTIONS)
        created = done = 0

        for off in (-2, -1, 0):
            ws = monday + timedelta(weeks=off)
            db.add(WeeklyProgram(
                student_id=student.id, coach_id=coach.id,
                start_date=ws, end_date=ws + timedelta(days=6),
                name="Haftalık Program", notes=MARKER,
            ))
            for d in range(6):
                day = ws + timedelta(days=d)
                specs = [("mat", math, MATH_BOOK, MATH_NAME, 2),
                         ("tr", tr, TR_BOOK, TR_NAME, 3)]
                for order, (key, cur, book_id, book_name, n) in enumerate(specs):
                    sec_id, label = cur.take(n)
                    task_service.reserve_item(
                        db, student_id=student.id, book_id=book_id,
                        section_id=sec_id, count=n)
                    t = Task(
                        student_id=student.id, date=day, type=TaskType.TEST,
                        title=f"{book_name} — {label}: {n} test",
                        status=TaskStatus.PENDING, order=order,
                        is_draft=False, published_at=now,
                    )
                    t.book_items.append(TaskBookItem(
                        book_id=book_id, book_section_id=sec_id,
                        planned_count=n, completed_count=0))
                    db.add(t)
                    db.flush()
                    created += 1
                    is_past = day < today or (day == today and key == "mat")
                    if is_past and (d, key) not in MISSED[off]:
                        q = n * 10  # test başına ~10 soru
                        wrong = 2 + (d % 3)
                        task_service.complete_task(
                            db, t, correct=q - wrong - 1, wrong=wrong, blank=1)
                        t.completed_at = datetime.combine(
                            day, time(17, 30), tzinfo=timezone.utc)
                        done += 1
                if d == 2:  # Çarşamba video görevi
                    v = Task(
                        student_id=student.id, date=day, type=TaskType.VIDEO,
                        title="Matematik · Konu anlatım videosu",
                        status=TaskStatus.PENDING, order=2,
                        is_draft=False, published_at=now,
                        link_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    )
                    db.add(v)
                    created += 1
                    if day < today and off > -2:
                        v.status = TaskStatus.COMPLETED
                        v.completed_at = datetime.combine(
                            day, time(19, 0), tzinfo=timezone.utc)
                        done += 1

        # 3 LGS denemesi — yükselen net
        exams = [
            (-16, "LGS Genel Deneme - 1", [("Türkçe", 14, 5, 1), ("Matematik", 10, 7, 3),
                                          ("Fen Bilimleri", 13, 5, 2), ("T.C. İnkılap Tarihi", 7, 2, 1),
                                          ("Din Kültürü", 8, 2, 0), ("İngilizce", 7, 2, 1)]),
            (-9, "LGS Genel Deneme - 2", [("Türkçe", 16, 3, 1), ("Matematik", 12, 6, 2),
                                         ("Fen Bilimleri", 14, 4, 2), ("T.C. İnkılap Tarihi", 8, 2, 0),
                                         ("Din Kültürü", 9, 1, 0), ("İngilizce", 8, 1, 1)]),
            (-2, "LGS Genel Deneme - 3", [("Türkçe", 17, 2, 1), ("Matematik", 14, 4, 2),
                                         ("Fen Bilimleri", 16, 3, 1), ("T.C. İnkılap Tarihi", 9, 1, 0),
                                         ("Din Kültürü", 9, 1, 0), ("İngilizce", 9, 1, 0)]),
        ]
        for delta, title, subs in exams:
            payload = [{"name": s, "correct": c, "wrong": w, "blank": b,
                        "net": compute_net(c, w, ExamSection.LGS)} for s, c, w, b in subs]
            tc = sum(x[1] for x in subs)
            tw = sum(x[2] for x in subs)
            tb = sum(x[3] for x in subs)
            db.add(ExamResult(
                student_id=student.id, created_by_id=coach.id, title=title,
                exam_date=monday + timedelta(days=delta), section=ExamSection.LGS,
                total_correct=tc, total_wrong=tw, total_blank=tb,
                net=compute_net(tc, tw, ExamSection.LGS),
                subject_nets=json.dumps(payload, ensure_ascii=False),
            ))

        db.add(TeacherNoteToParent(
            student_id=student.id, teacher_id=coach.id,
            body=("Ayşe geçen hafta programın neredeyse tamamını bitirdi; son denemede "
                  "matematik neti yükseldi. Bu hafta Üçgenler konusuna ağırlık veriyoruz."),
            created_at=now - timedelta(days=2),
        ))

        print(f"Görev: {created} oluşturuldu, {done} tamamlandı · 3 deneme · 1 koç notu")
        if dry_run:
            db.rollback()
            print("DRY-RUN — geri alındı.")
        else:
            db.commit()
            print("Kaydedildi.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--dry-run" in sys.argv)
