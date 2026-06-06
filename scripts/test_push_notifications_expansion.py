"""Push bildirim genişletmesi smoke — tüm rol e-postaları → mobil push + koç ilerleme.

Expo Push API monkeypatch'lenir (gerçek ağ çağrısı YOK). Doğrulananlar:
   1. safe_push: token yoksa no-op; token varsa gönderir; asla raise etmez
   2. notify_coach_student_progress: koça push + data.type=coach_student + throttle
   3. _notify_new_safe: koça push (type=coach, screen=requests) — yeni öğrenci talebi
   4. _notify_resolved_safe: öğrenciye push (type=student, screen=requests) — talep yanıtı
   5. deep-link data alanları doğru (mobil router ile uyumlu)
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import DevicePushToken, RequestType, TaskRequest, User, UserRole
from app.services import push_notifications as pn
from app.services.security import hash_password

PFX = f"push_{_secrets.token_hex(3)}"
PASSWORD = "PushTest!2026x"

passed = 0
failed: list[str] = []
_captured: list[dict] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _fake_expo_send(messages):
    """Gerçek Expo yerine — mesajları yakala, hepsi 'ok' receipt döndür."""
    _captured.extend(messages)
    return [{"status": "ok"} for _ in messages]


def _seed():
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=pwd,
                     full_name=f"{PFX} Coach", role=UserRole.TEACHER, is_active=True,
                     password_changed_at=now, must_change_password=False)
        db.add(coach)
        db.flush()
        student = User(email=f"{PFX}_student@test.invalid", password_hash=pwd,
                       full_name=f"{PFX} Ogrenci", role=UserRole.STUDENT, teacher_id=coach.id,
                       grade_level=8, is_active=True, password_changed_at=now, must_change_password=False)
        db.add(student)
        db.flush()
        # Cihaz token'ları
        db.add(DevicePushToken(user_id=coach.id, token=f"ExponentPushToken[{PFX}_coach]", platform="ios"))
        db.add(DevicePushToken(user_id=student.id, token=f"ExponentPushToken[{PFX}_student]", platform="android"))
        db.commit()
        return {"coach_id": coach.id, "student_id": student.id}


def _cleanup(seed):
    with SessionLocal() as db:
        ids = [seed["coach_id"], seed["student_id"]]
        db.execute(sa_delete(TaskRequest).where(TaskRequest.teacher_id.in_(ids)))
        db.execute(sa_delete(DevicePushToken).where(DevicePushToken.user_id.in_(ids)))
        db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.commit()


def main() -> int:
    print(f"\n=== push genişletme smoke — prefix: {PFX} ===\n")
    orig = pn._expo_send
    pn._expo_send = _fake_expo_send
    seed = _seed()
    coach_id = seed["coach_id"]
    student_id = seed["student_id"]
    coach_token = f"ExponentPushToken[{PFX}_coach]"
    student_token = f"ExponentPushToken[{PFX}_student]"

    try:
        with SessionLocal() as db:
            # 1. safe_push — token yok (rastgele id) → no-op, raise yok
            _captured.clear()
            pn.safe_push(db, user_id=99_999_999, title="X", body="Y", data={"type": "coach"})
            check("1a. safe_push tokensız kullanıcı → gönderim yok + raise yok", len(_captured) == 0)

            # safe_push — user_id None → no-op
            pn.safe_push(db, user_id=None, title="X", body="Y")
            check("1b. safe_push user_id=None → no-op", len(_captured) == 0)

            # safe_push — koça (token var)
            pn.safe_push(db, user_id=coach_id, title="Test", body="Gövde", data={"type": "coach", "screen": "plan"})
            sent = [m for m in _captured if m["to"] == coach_token]
            check("1c. safe_push token'lı kullanıcı → push gider + data taşır",
                  len(sent) == 1 and sent[0]["data"].get("screen") == "plan",
                  f"captured={_captured}")

            # 2. notify_coach_student_progress — koça push + data + throttle
            _captured.clear()
            pn._coach_progress_last.pop(student_id, None)
            pn.notify_coach_student_progress(db, student_id=student_id, student_name="Ali", coach_id=coach_id)
            first = list(_captured)
            check("2a. öğrenci ilerleme → koça push (type=coach_student + student_id)",
                  len(first) == 1 and first[0]["data"].get("type") == "coach_student"
                  and first[0]["data"].get("student_id") == student_id,
                  f"captured={first}")

            # 2b. throttle — hemen ikinci çağrı → push YOK
            _captured.clear()
            pn.notify_coach_student_progress(db, student_id=student_id, student_name="Ali", coach_id=coach_id)
            check("2b. throttle: pencere içinde ikinci push gönderilmez", len(_captured) == 0)

            # 2c. coach_id None → no-op
            _captured.clear()
            pn.notify_coach_student_progress(db, student_id=student_id, student_name="Ali", coach_id=None)
            check("2c. koç yoksa push yok", len(_captured) == 0)

            # 3. _notify_new_safe — yeni öğrenci talebi → koça push
            from app.services.request_service import _notify_new_safe, _notify_resolved_safe
            coach = db.get(User, coach_id)
            student = db.get(User, student_id)
            req = TaskRequest(student_id=student_id, teacher_id=coach_id, type=RequestType.QUESTION)
            req.teacher = coach
            req.student = student
            _captured.clear()
            _notify_new_safe(db, req)
            coach_push = [m for m in _captured if m["to"] == coach_token]
            check("3. yeni talep → koça push (type=coach, screen=requests)",
                  len(coach_push) == 1 and coach_push[0]["data"].get("screen") == "requests"
                  and coach_push[0]["data"].get("type") == "coach",
                  f"captured={_captured}")

            # 4. _notify_resolved_safe — talep yanıtı → öğrenciye push
            _captured.clear()
            _notify_resolved_safe(db, req, "approved")
            stu_push = [m for m in _captured if m["to"] == student_token]
            check("4. talep yanıtı → öğrenciye push (type=student, screen=requests)",
                  len(stu_push) == 1 and stu_push[0]["data"].get("type") == "student"
                  and stu_push[0]["data"].get("screen") == "requests",
                  f"captured={_captured}")

            # 5. başlık/gövde dolu (boş push gönderilmez)
            check("5. push başlık + gövde dolu",
                  all(m.get("title") and m.get("body") for m in [coach_push[0], stu_push[0]]))

    finally:
        pn._expo_send = orig
        _cleanup(seed)

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
