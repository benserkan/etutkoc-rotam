"""Öğrenci rehberi çekimleri için Elif'e öğrenci-yüzeyi demo verisi (additive).

Rehber sahneleri gerçek panelden çekilir; öğrenci ekranlarının dolu ve gerçekçi
görünmesi için Elif'e eklenenler:
  - BUGÜN: tamamlanmış test görevi (D/Y girili) + video görevi + günün notu
  - Yanlış Soru Arşivi: 4 kayıt (due'su gelen + foto'lu + AI ipucu'lu + kapanmış
    + deneme kaynaklı) — soru fotoğrafları Chrome ile sentetik üretilir
  - Tekrar (FSRS): 3 konu kartı (2'si vadesi gelmiş)
  - Hedefler: 2 hedef (haftalık test + LGS hedefi)
  - Odak: son günlere yayılmış 5 Pomodoro oturumu
  - Talepler: 1 bekleyen + 1 yanıtlanmış görev talebi
  - Anketler: 2 atama (bekliyor)
  - Bağımsız çalışma: 1 bekleyen beyan (Fen kitabı)

  python -m scripts.seed_guide_demo_student          # kur (idempotent işaret: WQ notu)
YALNIZ dev içindir; start.sh'e EKLENMEZ.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.database import SessionLocal
from app.models import (
    Book,
    BookSection,
    ExamResult,
    PomodoroSession,
    ReviewCard,
    SelfStudyEntry,
    StudentBook,
    StudentDayNote,
    StudentGoal,
    SurveyAssignment,
    SurveyTemplate,
    Task,
    TaskBookItem,
    TaskRequest,
    User,
    WrongQuestion,
    WrongQuestionImage,
)
from app.models.focus import PomodoroKind
from app.models.student_goal import GoalKind, GoalStatus
from app.models.task import TaskStatus, TaskType
from app.models.task_request import RequestStatus, RequestType
from app.models.wrong_question import (
    WQ_ERROR_BILGI,
    WQ_ERROR_DIKKAT,
    WQ_ERROR_ISLEM,
    WQ_IMAGE_QUESTION,
    WQ_SOURCE_DENEME,
    WQ_SOURCE_DIGER,
    WQ_SOURCE_GOREV,
)

ROOT = Path(__file__).resolve().parent.parent
IDS = json.loads((ROOT / "scripts" / "guide_demo_ids.json").read_text())
MARK = "[rehber-demo]"


def make_question_png(text_lines: list[str]) -> bytes:
    """Sentetik soru fotoğrafı — Chrome render (PIL metin çizimi bu ortamda çökük)."""
    from playwright.sync_api import sync_playwright

    body = "<br>".join(text_lines)
    html = f"""<!doctype html><meta charset="utf-8"><style>
      body {{ font-family:'Segoe UI'; background:#f6f3ec; margin:0; padding:28px;
             width:520px; color:#222; }}
      .q {{ background:#fff; border:1px solid #ddd; border-radius:8px;
            padding:22px; font-size:17px; line-height:1.7;
            box-shadow:0 2px 8px rgba(0,0,0,.08); }}
      .n {{ color:#0e6478; font-weight:700; }}</style>
      <div class="q"><span class="n">SORU 7.</span> {body}</div>"""
    tmp = ROOT / "scripts" / "_wq_tmp.html"
    tmp.write_text(html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        page = b.new_page(viewport={"width": 580, "height": 320})
        page.goto(tmp.as_uri())
        png = page.screenshot()
        b.close()
    tmp.unlink(missing_ok=True)
    return png


def main() -> int:
    now = datetime.now(timezone.utc)
    today = date.today()
    with SessionLocal() as db:
        elif_id = IDS["elif"]
        coach_id = IDS["coach"]

        if db.execute(
            select(WrongQuestion).where(
                WrongQuestion.student_id == elif_id, WrongQuestion.note.like(f"%{MARK}%")
            )
        ).scalars().first():
            print("Öğrenci demo verisi zaten var — dokunulmadı.")
            return 0

        book = db.get(Book, IDS["book"])
        secs = (
            db.query(BookSection).filter_by(book_id=book.id).order_by(BookSection.order).all()
        )
        by_label = {s.label: s for s in secs}

        # --- BUGÜN: tamamlanmış test + video görevi + günün notu ---------------
        t_done = Task(
            student_id=elif_id, date=today, type=TaskType.TEST,
            title=f"{book.name} — Kareköklü İfadeler: 3 test",
            status=TaskStatus.COMPLETED, is_draft=False,
            published_at=now, completed_at=now - timedelta(hours=2),
        )
        db.add(t_done)
        db.flush()
        db.add(TaskBookItem(
            task_id=t_done.id, book_id=book.id,
            book_section_id=by_label["Kareköklü İfadeler"].id,
            planned_count=3, completed_count=3, correct_count=24, wrong_count=6,
        ))
        db.add(Task(
            student_id=elif_id, date=today, type=TaskType.VIDEO,
            title="Matematik · Doğrusal denklemler konu videosu",
            link_url="https://www.youtube.com/watch?v=ornekvideo",
            status=TaskStatus.PENDING, is_draft=False, published_at=now,
        ))
        db.add(StudentDayNote(
            student_id=elif_id, date=today,
            body="Kareköklerde çarpma iyi gitti; paragraf sorularında yavaşım, "
                 "yarın kronometreyle deneyeceğim.",
        ))

        # --- Yanlış Soru Arşivi -------------------------------------------------
        mat_subject_id = book.subject_id
        exam = (
            db.query(ExamResult)
            .filter(ExamResult.student_id == elif_id)
            .order_by(ExamResult.exam_date.desc())
            .first()
        )

        def topic_of(label: str):
            s = by_label.get(label)
            return s.topic_id if s else None

        wq1 = WrongQuestion(
            student_id=elif_id, subject_id=mat_subject_id,
            topic_id=topic_of("Üslü İfadeler"), book_id=book.id,
            book_section_id=by_label["Üslü İfadeler"].id,
            source_kind=WQ_SOURCE_GOREV, error_type=WQ_ERROR_BILGI,
            note=f"Negatif üste kafam karıştı {MARK}",
            ai_hint="Negatif üs, tabanın tersini almak demektir: a üzeri eksi n "
                    "eşittir bir bölü a üzeri n. Önce tabanı ters çevir, sonra "
                    "pozitif üsle hesapla.",
            difficulty_guess="orta", ai_tagged_at=now,
            status="acik", due_at=now - timedelta(hours=6),
            fsrs_state="learning", attempts_count=1,
            last_attempt_at=now - timedelta(days=2),
        )
        wq2 = WrongQuestion(
            student_id=elif_id, subject_id=mat_subject_id,
            topic_id=topic_of("Eşitsizlikler"), book_id=book.id,
            book_section_id=by_label["Eşitsizlikler"].id,
            source_kind=WQ_SOURCE_GOREV, error_type=WQ_ERROR_ISLEM,
            note=f"Eksi ile çarparken yön değiştirmeyi unuttum {MARK}",
            status="acik", due_at=now + timedelta(days=1),
            fsrs_state="learning",
        )
        wq3 = WrongQuestion(
            student_id=elif_id, subject_id=mat_subject_id,
            topic_id=topic_of("Çarpanlar ve Katlar"), book_id=book.id,
            book_section_id=by_label["Çarpanlar ve Katlar"].id,
            source_kind=WQ_SOURCE_DIGER, error_type=WQ_ERROR_DIKKAT,
            note=f"Soruyu yanlış okumuşum {MARK}",
            status="kapandi", correct_streak=2, attempts_count=3,
            closed_at=now - timedelta(days=3), fsrs_state="review",
            last_attempt_at=now - timedelta(days=3),
        )
        wq4 = WrongQuestion(
            student_id=elif_id, subject_id=mat_subject_id,
            topic_id=topic_of("Üslü İfadeler"),
            exam_result_id=exam.id if exam else None,
            source_kind=WQ_SOURCE_DENEME, error_type=WQ_ERROR_BILGI,
            note=f"L G S Deneme 3 · Soru 4 {MARK}",
            status="acik", due_at=now - timedelta(hours=2), fsrs_state="new",
        )
        db.add_all([wq1, wq2, wq3, wq4])
        db.flush()

        png1 = make_question_png([
            "2<sup>-3</sup> · 4<sup>2</sup> işleminin sonucu kaçtır?",
            "A) 2 &nbsp;&nbsp; B) 4 &nbsp;&nbsp; C) 8 &nbsp;&nbsp; D) 16",
        ])
        png2 = make_question_png([
            "-3x + 6 &gt; 12 eşitsizliğinin çözüm kümesi nedir?",
            "A) x &gt; -2 &nbsp;&nbsp; B) x &lt; -2 &nbsp;&nbsp; C) x &gt; 2 &nbsp;&nbsp; D) x &lt; 2",
        ])
        db.add(WrongQuestionImage(
            wrong_question_id=wq1.id, kind=WQ_IMAGE_QUESTION,
            content_type="image/png", data=png1, size_bytes=len(png1),
        ))
        db.add(WrongQuestionImage(
            wrong_question_id=wq2.id, kind=WQ_IMAGE_QUESTION,
            content_type="image/png", data=png2, size_bytes=len(png2),
        ))

        # --- Tekrar (FSRS konu kartları) ---------------------------------------
        for label, days, state in [
            ("Üslü İfadeler", -1, "review"),
            ("Kareköklü İfadeler", 0, "review"),
            ("Doğrusal Denklemler", +4, "review"),
        ]:
            tid = topic_of(label)
            if tid:
                db.add(ReviewCard(
                    student_id=elif_id, topic_id=tid, state=state,
                    stability=3.5, difficulty=5.2,
                    due_at=now + timedelta(days=days),
                    last_reviewed_at=now - timedelta(days=4),
                    last_rating=3, review_count=3, lapse_count=1,
                ))

        # --- Hedefler ----------------------------------------------------------
        db.add(StudentGoal(
            student_id=elif_id, kind=GoalKind.WEEKLY, status=GoalStatus.ACTIVE,
            title="Bu hafta 60 test çöz", target_value=60, current_value=38,
            unit="test", target_date=today + timedelta(days=2),
        ))
        db.add(StudentGoal(
            student_id=elif_id, kind=GoalKind.EXAM_TARGET, status=GoalStatus.ACTIVE,
            title="L G S denemelerinde 75 net", target_value=75, current_value=61,
            unit="net", target_date=date(2027, 6, 1),
        ))

        # --- Odak (Pomodoro) ---------------------------------------------------
        for d, mins, done in [(0, 25, True), (0, 25, True), (1, 25, True), (2, 25, False), (3, 40, True)]:
            start = now - timedelta(days=d, hours=3)
            db.add(PomodoroSession(
                student_id=elif_id, kind=PomodoroKind.WORK,
                started_at=start,
                ended_at=start + timedelta(minutes=mins if done else 12),
                planned_minutes=mins, actual_minutes=mins if done else 12,
                interrupted=not done, label="Matematik",
            ))

        # --- Talepler ----------------------------------------------------------
        db.add(TaskRequest(
            student_id=elif_id, teacher_id=coach_id, type=RequestType.CHANGE,
            status=RequestStatus.PENDING,
            message="Cuma günkü Eşitsizlikler görevini 4 yerine 2 test yapabilir miyiz? "
                    "Okul sınavına çalışacağım.",
            proposed_count=2,
        ))
        db.add(TaskRequest(
            student_id=elif_id, teacher_id=coach_id, type=RequestType.QUESTION,
            status=RequestStatus.RESOLVED,
            message="Kareköklü sorularında hangi kaynaktan ek soru çözebilirim?",
            teacher_response="Aferin! 3D kitabındaki karekök ünitesinin son iki testini "
                             "bitir; ek olarak arşivindeki yanlışları yeniden çöz.",
        ))

        # --- Anketler ----------------------------------------------------------
        for code in ("coklu-zeka", "sinav-kaygisi"):
            tpl = db.execute(
                select(SurveyTemplate).where(SurveyTemplate.code == code)
            ).scalar_one_or_none()
            if tpl:
                db.add(SurveyAssignment(
                    template_id=tpl.id, teacher_id=coach_id, student_id=elif_id,
                    note="Seni daha iyi tanımak için — 5 dakikanı alır.",
                ))

        # --- Bağımsız çalışma beyanı (Fen kitabı) -------------------------------
        fen_book = (
            db.query(Book)
            .filter(Book.teacher_id == coach_id, Book.name.like("%Fen Bilimleri Soru Bankas%"))
            .order_by(Book.id.desc())
            .first()
        )
        if fen_book:
            sb = db.execute(
                select(StudentBook).where(
                    StudentBook.student_id == elif_id, StudentBook.book_id == fen_book.id
                )
            ).scalar_one_or_none()
            fsec = (
                db.query(BookSection).filter_by(book_id=fen_book.id).order_by(BookSection.order).first()
            )
            if sb and fsec:
                db.add(SelfStudyEntry(
                    student_id=elif_id, student_book_id=sb.id, book_section_id=fsec.id,
                    test_count=4, source="student", status="pending",
                    note="Hafta sonu kendim çözdüm",
                    period_start=today - timedelta(days=2), period_end=today,
                ))

        db.commit()
        print("Öğrenci demo verisi kuruldu (Elif): bugün görevleri + not, 4 yanlış (2 foto),")
        print("3 tekrar kartı, 2 hedef, 5 odak oturumu, 2 talep, 2 anket, 1 bağımsız beyan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
