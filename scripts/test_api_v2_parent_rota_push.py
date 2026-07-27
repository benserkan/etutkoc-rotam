# -*- coding: utf-8 -*-
"""P4 smoke — yeni deneme sonucu → veliye "Rota yorumlamaya hazır" push'u.

Push MOBİL-ONLY (e-posta yok), best-effort. Kapı: Rota gerçekten açık olmalı
(koç ücretli paket + AI onayı); muted veli linki atlanır; veli+öğrenci başına
6 saatte 1 (throttle). Tetikler: koç import-confirm · öğrenci import-confirm ·
koç manuel deneme girişi. Satır düzeltme/deneme güncelleme TETİKLEMEZ.

Senaryolar:
  1. unit: bağlı veliye push + data {type: parent_notification, kind:
     rota_commentary, student_id}
  2. muted veli linki atlanır (diğer veli almaya devam eder)
  3. throttle: aynı veli+öğrenci ikinci çağrıda push almaz
  4. free koç öğrencisi → hiç push (Rota kapalı — ölü karta davet yok)
  5. koçsuz öğrenci → hiç push
  6. entegrasyon: koç manuel deneme POST → yanıt sonrası bg push
  7. entegrasyon: deneme GÜNCELLEME (POST /teacher/exams/{id}) → push YOK
  8. entegrasyon: koç import-confirm ucu → bg push (svc.confirm stub)
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    ParentRelation, ParentStudentLink, User, UserRole,
)
from app.models.exam_result import ExamResult
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2rp_{secrets.token_hex(3)}"
PWD = "TestRotaPush!23"
passed = 0
failed: list[str] = []
pushes: list[dict] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _fake_send_push(db, *, user_id, title, body, data=None):
    pushes.append({"user_id": user_id, "title": title, "body": body, "data": data})
    return {"status": "ok"}


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    with SessionLocal() as db:
        paid_t = User(email=f"{PFX}_t@test.invalid", password_hash=pwd,
                      full_name=f"{PFX} Koc", role=UserRole.TEACHER, is_active=True,
                      plan="solo_pro", password_changed_at=now,
                      must_change_password=False, ai_capture_consent_at=now)
        free_t = User(email=f"{PFX}_tf@test.invalid", password_hash=pwd,
                      full_name=f"{PFX} KocF", role=UserRole.TEACHER, is_active=True,
                      plan="solo_free", password_changed_at=now,
                      must_change_password=False)
        db.add_all([paid_t, free_t]); db.flush()
        stu = User(email=f"{PFX}_s@test.invalid", password_hash=pwd,
                   full_name=f"{PFX} Ogr", role=UserRole.STUDENT,
                   teacher_id=paid_t.id, grade_level=8, is_active=True,
                   password_changed_at=now, must_change_password=False)
        free_s = User(email=f"{PFX}_sf@test.invalid", password_hash=pwd,
                      full_name=f"{PFX} OgrF", role=UserRole.STUDENT,
                      teacher_id=free_t.id, grade_level=8, is_active=True,
                      password_changed_at=now, must_change_password=False)
        orphan = User(email=f"{PFX}_so@test.invalid", password_hash=pwd,
                      full_name=f"{PFX} OgrO", role=UserRole.STUDENT,
                      teacher_id=None, grade_level=8, is_active=True,
                      password_changed_at=now, must_change_password=False)
        p1 = User(email=f"{PFX}_p1@test.invalid", password_hash=pwd,
                  full_name=f"{PFX} Veli1", role=UserRole.PARENT, is_active=True,
                  password_changed_at=now, must_change_password=False)
        p2 = User(email=f"{PFX}_p2@test.invalid", password_hash=pwd,
                  full_name=f"{PFX} Veli2", role=UserRole.PARENT, is_active=True,
                  password_changed_at=now, must_change_password=False)
        p3 = User(email=f"{PFX}_p3@test.invalid", password_hash=pwd,
                  full_name=f"{PFX} Veli3", role=UserRole.PARENT, is_active=True,
                  password_changed_at=now, must_change_password=False)
        db.add_all([stu, free_s, orphan, p1, p2, p3]); db.flush()
        db.add_all([
            ParentStudentLink(parent_id=p1.id, student_id=stu.id,
                              relation=ParentRelation.ANNE, is_primary=True),
            ParentStudentLink(parent_id=p2.id, student_id=stu.id,
                              relation=ParentRelation.BABA, is_primary=False,
                              muted=True),
            ParentStudentLink(parent_id=p3.id, student_id=free_s.id,
                              relation=ParentRelation.ANNE, is_primary=True),
            ParentStudentLink(parent_id=p3.id, student_id=orphan.id,
                              relation=ParentRelation.ANNE, is_primary=False),
        ])
        db.commit()
        return {"paid_t": paid_t.id, "free_t": free_t.id, "stu": stu.id,
                "free_s": free_s.id, "orphan": orphan.id,
                "p1": p1.id, "p2": p2.id, "p3": p3.id}


def _cleanup(seed: dict) -> None:
    from sqlalchemy import delete as sa_delete
    from app.models.exam_result import ExamResultQuestion
    with SessionLocal() as db:
        sids = [seed["stu"], seed["free_s"], seed["orphan"]]
        uids = sids + [seed["paid_t"], seed["free_t"],
                       seed["p1"], seed["p2"], seed["p3"]]
        eids = [e.id for e in db.query(ExamResult)
                .filter(ExamResult.student_id.in_(sids)).all()]
        if eids:
            db.execute(sa_delete(ExamResultQuestion)
                       .where(ExamResultQuestion.exam_result_id.in_(eids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(sids)))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_([seed["p1"], seed["p2"], seed["p3"]])))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed {email}: {r.status_code} {r.text}")
    return c


def main() -> int:
    print(f"\n=== P4 Rota veli push smoke — {PFX} ===\n")
    get_login_limiter().reset()

    import app.services.push_notifications as pn
    orig_send = pn.send_push_to_user
    pn.send_push_to_user = _fake_send_push
    pn._parent_rota_last.clear()

    seed = _seed()
    try:
        with SessionLocal() as db:
            pn.notify_parents_rota_exam_ready(
                db, student_id=seed["stu"], student_name="Test Ogr")
        got = [p for p in pushes if p["user_id"] == seed["p1"]]
        d = got[0]["data"] if got else {}
        check("1. bağlı veliye push + doğru data",
              len(got) == 1 and got[0]["title"] == "Rota yorumlamaya hazır"
              and d.get("type") == "parent_notification"
              and d.get("kind") == "rota_commentary"
              and d.get("student_id") == seed["stu"],
              str(pushes))

        check("2. muted veli atlanır",
              not any(p["user_id"] == seed["p2"] for p in pushes), str(pushes))

        n_before = len(pushes)
        with SessionLocal() as db:
            pn.notify_parents_rota_exam_ready(
                db, student_id=seed["stu"], student_name="Test Ogr")
        check("3. throttle: ikinci çağrı push üretmez",
              len(pushes) == n_before, f"{n_before}->{len(pushes)}")

        with SessionLocal() as db:
            pn.notify_parents_rota_exam_ready(
                db, student_id=seed["free_s"], student_name="Free Ogr")
        check("4. free koç öğrencisi → push yok (Rota kapısı)",
              not any(p["user_id"] == seed["p3"] for p in pushes), str(pushes))

        with SessionLocal() as db:
            pn.notify_parents_rota_exam_ready(
                db, student_id=seed["orphan"], student_name="Orphan Ogr")
        check("5. koçsuz öğrenci → push yok",
              not any(p["user_id"] == seed["p3"] for p in pushes), str(pushes))

        # --- entegrasyon ---
        coach = _login(f"{PFX}_t@test.invalid")
        pn._parent_rota_last.clear()
        pushes.clear()
        r = coach.post(f"/api/v2/teacher/students/{seed['stu']}/exams", json={
            "title": "LGS Deneme P4", "exam_date": date.today().isoformat(),
            "section": "lgs", "total_correct": 60, "total_wrong": 20,
            "total_blank": 10,
        })
        exam_id = r.json()["data"]["id"] if r.status_code == 200 else None
        check("6. manuel deneme girişi → bg push",
              r.status_code == 200 and len(pushes) == 1
              and pushes[0]["user_id"] == seed["p1"]
              and pushes[0]["data"]["kind"] == "rota_commentary",
              f"{r.status_code} pushes={pushes} {r.text[:120]}")

        pushes.clear()
        r = coach.post(f"/api/v2/teacher/exams/{exam_id}", json={
            "title": "LGS Deneme P4 (düzeltildi)",
            "exam_date": date.today().isoformat(),
            "section": "lgs", "total_correct": 61, "total_wrong": 19,
            "total_blank": 10,
        })
        check("7. deneme güncelleme → push YOK",
              r.status_code == 200 and len(pushes) == 0,
              f"{r.status_code} pushes={pushes}")

        # 8. import-confirm ucu bg push'u zamanlar — ağır Gemini/satır akışı
        # yerine svc.confirm stub'lanır (uç yolunun kendisi test edilir).
        import app.routes.api_v2.exam_import as ei
        from app.models.curriculum import ExamSection

        def _stub_confirm(db, student, payload, *, pdf_bytes=None,
                          content_type=None, actor=None):
            exam = ExamResult(
                student_id=student.id, created_by_id=actor.id if actor else None,
                title=payload["title"], exam_date=date.today(),
                section=ExamSection.LGS, total_correct=50, total_wrong=30,
                total_blank=10, net=40.0, import_source="pdf_import",
            )
            db.add(exam); db.commit(); db.refresh(exam)
            return exam

        orig_confirm = ei.svc.confirm
        ei.svc.confirm = _stub_confirm
        pn._parent_rota_last.clear()
        pushes.clear()
        try:
            payload = json.dumps({
                "title": "Import P4", "exam_date": date.today().isoformat(),
                "section": "lgs", "rows": [],
            })
            r = coach.post(
                f"/api/v2/teacher/students/{seed['stu']}/exams/import-confirm",
                data={"payload": payload},
            )
        finally:
            ei.svc.confirm = orig_confirm
        check("8. import-confirm → bg push",
              r.status_code == 200 and len(pushes) == 1
              and pushes[0]["user_id"] == seed["p1"],
              f"{r.status_code} pushes={pushes} {r.text[:150]}")

    finally:
        pn.send_push_to_user = orig_send
        pn._parent_rota_last.clear()
        _cleanup(seed)

    print(f"\n  Sonuç: {passed} PASS / {len(failed)} FAIL")
    for f in failed:
        print(f"    FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
