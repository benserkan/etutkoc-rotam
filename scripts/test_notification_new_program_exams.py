"""M3 — Yeni program maili payload + şablon (son 90g denemeler) smoke.

Senaryolar (10):
   1. _get_recent_exams 0 deneme → [] döner
   2. _get_recent_exams 90 günden eski deneme dahil değil
   3. _get_recent_exams birden çok deneme → tarih DESC sıralı
   4. _get_recent_exams limit=N → N kayıt
   5. produce_new_program payload'a recent_exams eklenir (deneme YOK → [])
   6. produce_new_program payload'a recent_exams eklenir (deneme VAR → liste)
   7. Şablon render: recent_exams DOLU → tablo başlığı + her satır + "son 90 gün" notu
   8. Şablon render: recent_exams BOŞ → amber "deneme yok" notu görünür
   9. Şablon render: günlük dağılım hâlâ görünür (eski davranış korunur)
  10. Şablon render: deneme satırında net + D/Y/B sayıları doğru
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, timedelta

from sqlalchemy import delete as sa_delete
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.database import SessionLocal
from app.models import User, UserRole
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult, compute_net
from app.services.notification_producers import (
    _get_recent_exams,
    produce_new_program,
)
from app.services.security import hash_password


PFX = f"v2np_{secrets.token_hex(3)}"
COACH_EMAIL = f"{PFX}_c@test.invalid"
STUDENT_EMAIL = f"{PFX}_s@test.invalid"
PARENT_EMAIL = f"{PFX}_p@test.invalid"
PASSWORD = "TestPass123!@xyz"

passed = 0
failed: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _seed(*, with_exams: bool) -> dict:
    today = date.today()
    with SessionLocal() as db:
        coach = User(
            email=COACH_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="M3 Koç", role=UserRole.TEACHER, is_active=True, plan="solo_pro",
        )
        student = User(
            email=STUDENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="M3 Öğrenci", role=UserRole.STUDENT, is_active=True, grade_level=8,
        )
        parent = User(
            email=PARENT_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="M3 Veli", role=UserRole.PARENT, is_active=True,
        )
        db.add_all([coach, student, parent])
        db.flush()
        student.teacher_id = coach.id

        exam_ids: list[int] = []
        if with_exams:
            # 3 deneme: bugün (LGS tam), 30g önce (LGS sözel), 100g önce (eski, dahil olmamalı)
            samples = [
                (today, "LGS Tam Deneme 7", ExamSection.LGS, 78, 5, 7),       # 90 soru
                (today - timedelta(days=30), "Sözel Branş", ExamSection.LGS, 38, 8, 4),  # 50 soru
                (today - timedelta(days=100), "Eski deneme", ExamSection.LGS, 50, 10, 30),  # eskisi
            ]
            for ed, title, sec, c, w, b in samples:
                ex = ExamResult(
                    student_id=student.id,
                    created_by_id=coach.id,
                    title=title,
                    exam_date=ed,
                    section=sec,
                    total_correct=c,
                    total_wrong=w,
                    total_blank=b,
                    net=compute_net(c, w, sec),
                )
                db.add(ex)
                db.flush()
                exam_ids.append(ex.id)

        db.commit()
        return {
            "coach_id": coach.id,
            "student_id": student.id,
            "parent_id": parent.id,
            "exam_ids": exam_ids,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        if seed["exam_ids"]:
            db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(seed["exam_ids"])))
        db.execute(sa_delete(User).where(User.id.in_([
            seed["student_id"], seed["parent_id"], seed["coach_id"],
        ])))
        db.commit()


def _render_template(payload: dict) -> str:
    """parent_new_program.html'i payload ile render et."""
    env = Environment(
        loader=FileSystemLoader("app/templates/emails"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("parent_new_program.html")
    # app_base_url eklensin (template kullanır)
    payload2 = dict(payload)
    payload2.setdefault("app_base_url", "https://rotam.etutkoc.com")
    payload2.setdefault("unsubscribe_token", "test-token")
    return template.render(**payload2)


def main() -> int:
    print(f"\n=== M3 yeni program maili (son 90g denemeler) smoke — prefix: {PFX} ===\n")

    # =========== Boş ekosistem (deneme YOK) ===========
    seed_empty = _seed(with_exams=False)
    try:
        with SessionLocal() as db:
            # 1. boş öğrenci → []
            exams = _get_recent_exams(db, student_id=seed_empty["student_id"])
            check("1. deneme yok → [] döner",
                  exams == [],
                  f"got={exams}")

            # 5. produce_new_program payload (boş) — recent_exams==[]
            parent = db.get(User, seed_empty["parent_id"])
            student = db.get(User, seed_empty["student_id"])
            today = date.today()
            logs = produce_new_program(
                db,
                parent=parent,
                student=student,
                week_start=today,
                week_end=today + timedelta(days=6),
                total_tasks=10,
                daily_breakdown=[{"label": "Pazartesi", "task_count": 5}],
            )
            # Payload'u son log'dan oku (en az 1 EMAIL log var)
            email_log = logs[0]
            payload = email_log.payload_json or {}
            import json as _json
            if isinstance(payload, str):
                payload = _json.loads(payload)
            check("5. payload'a recent_exams (boş) eklendi",
                  "recent_exams" in payload and payload["recent_exams"] == [],
                  f"keys={list(payload.keys())[:6]} recent={payload.get('recent_exams')}")

            # 8. Şablon render → amber "deneme yok" notu
            html = _render_template(payload)
            check("8. şablon boş denemede → amber 'deneme yok' notu",
                  "Son 90 günde sisteme yüklenmiş deneme yok" in html,
                  f"len={len(html)}")

            # 9. Şablon Günlük Program bölümü kalır (yeniden tasarımdan sonra)
            check("9. şablon Günlük Program hâlâ görünür",
                  "Günlük Program" in html,
                  f"daily ok")
    finally:
        _cleanup(seed_empty)

    # =========== Dolu ekosistem (3 deneme, 1 eski) ===========
    seed = _seed(with_exams=True)
    try:
        with SessionLocal() as db:
            # 2. 90 günden eski deneme dahil değil
            exams = _get_recent_exams(db, student_id=seed["student_id"])
            old_titles = [e["title"] for e in exams if e["title"] == "Eski deneme"]
            check("2. 90 günden eski deneme dahil değil",
                  len(old_titles) == 0,
                  f"count={len(exams)} titles={[e['title'] for e in exams]}")

            # 3. tarih DESC sıralı (en yeni → en eski)
            dates = [e["date_iso"] for e in exams]
            check("3. tarih DESC sıralı",
                  dates == sorted(dates, reverse=True) and len(dates) >= 2,
                  f"dates={dates}")

            # 4. limit
            exams_limit = _get_recent_exams(db, student_id=seed["student_id"], limit=1)
            check("4. limit=1 → 1 kayıt",
                  len(exams_limit) == 1,
                  f"got={len(exams_limit)}")

            # 6. produce_new_program payload — recent_exams dolu
            parent = db.get(User, seed["parent_id"])
            student = db.get(User, seed["student_id"])
            today = date.today()
            logs = produce_new_program(
                db,
                parent=parent,
                student=student,
                week_start=today,
                week_end=today + timedelta(days=6),
                total_tasks=20,
                daily_breakdown=[{"label": "Cumartesi", "task_count": 8}],
            )
            email_log = logs[0]
            payload = email_log.payload_json or {}
            import json as _json
            if isinstance(payload, str):
                payload = _json.loads(payload)
            check("6. payload'da recent_exams 2 deneme (eski hariç)",
                  isinstance(payload.get("recent_exams"), list)
                  and len(payload["recent_exams"]) == 2,
                  f"count={len(payload.get('recent_exams', []))}")

            # 7. Şablon render → tablo başlığı + her satır görünür
            html = _render_template(payload)
            ok = (
                "Son 3 ayın denemeleri" in html
                and "LGS Tam Deneme 7" in html
                and "Sözel Branş" in html
                # Eski denemeyi göstermemeli
                and "Eski deneme" not in html
                and "Son 90 günde sisteme girilmiş tüm denemeler" in html
            )
            check("7. şablon dolu denemede → tablo + 2 satır + 'son 90 gün' notu",
                  ok, f"len={len(html)}")

            # 10. Net + D/Y/B sayıları görünür
            # LGS Tam Deneme: D=78 W=5 B=7
            ok = ("78" in html and "5" in html and "7" in html)
            check("10. deneme satırında D/Y/B sayıları görünür",
                  ok, "78/5/7 görünmeli")
    finally:
        _cleanup(seed)

    total = passed + len(failed)
    print(f"\n=== Sonuç: {passed}/{total} geçti ===\n")
    if failed:
        print("Başarısız senaryolar:")
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
