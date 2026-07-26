# -*- coding: utf-8 -*-
"""API v2 Rota Veli Asistanı P1 smoke — /parent/students/{id}/commentary*.

Yorumlayıcı (program | deneme): önbellekten okuma ücretsiz · üretim koç
kredisinden (6) · seslendirme ilk kez (2) sonrası ücretsiz · günlük veli
üretim limiti · bayatlık HESAPLANIR · sahiplik 404 · kapılar (paket/rıza).
Gemini + TTS monkeypatch — gerçek çağrı YOK.

Senaryolar:
  1. anon 401 · 2. yabancı veli 404 · 3. koç rolü 403 · 4. geçersiz kind 422
  5. ücretsiz koç → ai_available False; POST 403
  6. paid: GET boş + daily_left=6
  7. POST program → sections + speech; kredi 6 düştü
  8. GET cache ücretsiz + is_stale False
  9. bu haftaya görev eklenince program is_stale True
 10. POST deneme → 200; yeni deneme → deneme is_stale True
 11. verisiz çocukta POST → 422 not_enough_data
 12. yorumsuz çocukta voice → 404
 13. voice ilk → charged + kredi 2
 14. voice tekrar → charged False, kredi değişmez
 15. audio GET → bayt + content-type
 16. yeniden üretim sesi TEMİZLER (audio 404)
 17. günlük limit → 429 daily_limit_reached
 18. eski /insight GET hâlâ çalışır (regresyon)
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
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, CreditAccount, ParentCommentary, ParentRelation,
    ParentStudentLink, Subject, Task, TaskBookItem, TaskStatus, TaskType,
    UsageEvent, User, UserRole,
)
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2pc_{secrets.token_hex(3)}"
PWD = "TestRotaVeli!23"
passed = 0
failed: list[str] = []

FAKE_AUDIO = b"ID3fakemp3bytes-rota"


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _fake_gemini_generate(parts, *, personal_data, timeout=45.0, json_mode=True,
                          max_output_tokens=8192, prefer_paid=True, **kwargs):
    return json.dumps({
        "sections": [
            {"title": "Bu hafta ne oldu", "body": "Görevlerin çoğu tamamlandı."},
            {"title": "Evde nasıl destek olursunuz", "body": "Akşam kısa sohbet edin."},
        ],
        "speech_text": "Bu hafta işler yolunda gitti. Görevlerin çoğu tamamlandı.",
    }, ensure_ascii=False)


def _fake_tts(text, *, voice="Kore", timeout=120.0):
    return FAKE_AUDIO, "audio/mpeg"


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    today = date.today()
    this_mon = today - timedelta(days=today.weekday())
    prev_mon = this_mon - timedelta(days=7)

    with SessionLocal() as db:
        paid_t = User(email=f"{PFX}_t@test.invalid", password_hash=pwd,
                      full_name=f"{PFX} Koc", role=UserRole.TEACHER, is_active=True,
                      plan="solo_pro", password_changed_at=now,
                      must_change_password=False,
                      ai_capture_consent_at=now)
        free_t = User(email=f"{PFX}_tf@test.invalid", password_hash=pwd,
                      full_name=f"{PFX} KocF", role=UserRole.TEACHER, is_active=True,
                      plan="solo_free", password_changed_at=now,
                      must_change_password=False)
        db.add_all([paid_t, free_t]); db.flush()

        stu = User(email=f"{PFX}_s@test.invalid", password_hash=pwd,
                   full_name=f"{PFX} Ogr", role=UserRole.STUDENT,
                   teacher_id=paid_t.id, grade_level=8, is_active=True,
                   password_changed_at=now, must_change_password=False)
        bare = User(email=f"{PFX}_sb@test.invalid", password_hash=pwd,
                    full_name=f"{PFX} Bos", role=UserRole.STUDENT,
                    teacher_id=paid_t.id, grade_level=8, is_active=True,
                    password_changed_at=now, must_change_password=False)
        free_s = User(email=f"{PFX}_sf@test.invalid", password_hash=pwd,
                      full_name=f"{PFX} OgrF", role=UserRole.STUDENT,
                      teacher_id=free_t.id, grade_level=8, is_active=True,
                      password_changed_at=now, must_change_password=False)
        p1 = User(email=f"{PFX}_p1@test.invalid", password_hash=pwd,
                  full_name=f"{PFX} Veli1", role=UserRole.PARENT, is_active=True,
                  password_changed_at=now, must_change_password=False)
        p2 = User(email=f"{PFX}_p2@test.invalid", password_hash=pwd,
                  full_name=f"{PFX} Veli2", role=UserRole.PARENT, is_active=True,
                  password_changed_at=now, must_change_password=False)
        db.add_all([stu, bare, free_s, p1, p2]); db.flush()
        # ID-reuse kirliliği: silinmiş eski kullanıcıların UsageEvent/CreditAccount
        # kalıntıları yeniden kullanılan id'lere miras kalabilir → sayaçlar şaşar.
        from sqlalchemy import delete as _sa_delete
        db.execute(_sa_delete(UsageEvent).where(
            UsageEvent.actor_user_id.in_([p1.id, p2.id])))
        db.execute(_sa_delete(CreditAccount).where(
            CreditAccount.owner_id.in_([paid_t.id, free_t.id])))
        db.add_all([
            ParentStudentLink(parent_id=p1.id, student_id=stu.id,
                              relation=ParentRelation.ANNE, is_primary=True),
            ParentStudentLink(parent_id=p1.id, student_id=bare.id,
                              relation=ParentRelation.ANNE, is_primary=True),
            ParentStudentLink(parent_id=p2.id, student_id=free_s.id,
                              relation=ParentRelation.ANNE, is_primary=True),
        ])

        mat = Subject(teacher_id=paid_t.id, name="Mat", order=1)
        db.add(mat); db.flush()
        book = Book(teacher_id=paid_t.id, name="Mat SB",
                    type=BookType.SORU_BANKASI, subject_id=mat.id)
        db.add(book); db.flush()
        sec = BookSection(book_id=book.id, label="Ünite 1", order=1, test_count=100)
        db.add(sec); db.flush()

        def add_task(d, status, planned, completed):
            t = Task(student_id=stu.id, date=d, type=TaskType.TEST,
                     title=f"Mat SB — Ünite 1: {planned} test",
                     is_draft=False, status=status)
            db.add(t); db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=sec.id,
                                planned_count=planned, completed_count=completed))
            return t

        # geçen hafta (kıyas verisi) + bu hafta 1 tamam 1 eksik
        add_task(prev_mon, TaskStatus.COMPLETED, 10, 10)
        add_task(this_mon, TaskStatus.COMPLETED, 5, 5)
        add_task(min(this_mon + timedelta(days=1), today), TaskStatus.PENDING, 4, 0)

        db.add_all([
            ExamResult(student_id=stu.id, created_by_id=paid_t.id,
                       title="LGS Deneme 2", exam_date=today - timedelta(days=5),
                       section=ExamSection.LGS, total_correct=60, total_wrong=20,
                       total_blank=10, net=53.33),
            ExamResult(student_id=stu.id, created_by_id=paid_t.id,
                       title="LGS Deneme 1", exam_date=today - timedelta(days=20),
                       section=ExamSection.LGS, total_correct=50, total_wrong=25,
                       total_blank=15, net=41.67),
        ])
        db.commit()
        return {
            "paid_t": paid_t.id, "free_t": free_t.id,
            "stu": stu.id, "bare": bare.id, "free_s": free_s.id,
            "p1": p1.id, "p2": p2.id,
            "book": book.id, "sec": sec.id, "subject": mat.id,
            "this_mon": this_mon,
        }


def _cleanup(seed: dict) -> None:
    from sqlalchemy import delete as sa_delete
    with SessionLocal() as db:
        sids = [seed["stu"], seed["bare"], seed["free_s"]]
        uids = sids + [seed["paid_t"], seed["free_t"], seed["p1"], seed["p2"]]
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(sids)).all()]
        if tids:
            db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids)))
        db.execute(sa_delete(Task).where(Task.student_id.in_(sids)))
        db.execute(sa_delete(ExamResult).where(ExamResult.student_id.in_(sids)))
        db.execute(sa_delete(ParentCommentary).where(ParentCommentary.student_id.in_(sids)))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_([seed["p1"], seed["p2"]])))
        db.execute(sa_delete(UsageEvent).where(
            UsageEvent.actor_user_id.in_([seed["p1"], seed["p2"]])))
        db.execute(sa_delete(CreditAccount).where(
            CreditAccount.owner_id.in_([seed["paid_t"], seed["free_t"]])))
        db.execute(sa_delete(BookSection).where(BookSection.book_id == seed["book"]))
        db.execute(sa_delete(Book).where(Book.id == seed["book"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject"]))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed {email}: {r.status_code} {r.text}")
    return c


def _usage_counts(parent_id: int) -> dict:
    from app.models import UsageKind
    with SessionLocal() as db:
        rows = db.query(UsageEvent).filter(UsageEvent.actor_user_id == parent_id).all()
        out = {"gen": 0, "voice": 0, "credits": 0}
        for r in rows:
            out["credits"] += r.credits
            if r.kind == UsageKind.AI_PARENT_COMMENTARY:
                out["gen"] += 1
            elif r.kind == UsageKind.AI_PARENT_COMMENTARY_VOICE:
                out["voice"] += 1
        return out


def main() -> int:
    print(f"\n=== Rota Veli Asistanı P1 smoke — {PFX} ===\n")
    get_login_limiter().reset()

    # Monkeypatch: gerçek Gemini/TTS çağrısı yok
    import app.services.gemini as gemini_mod
    import app.services.tts as tts_mod
    orig_gen = gemini_mod.generate
    orig_tts = tts_mod.synthesize_speech
    gemini_mod.generate = _fake_gemini_generate
    tts_mod.synthesize_speech = _fake_tts

    seed = _seed()
    sid = seed["stu"]
    try:
        p1 = _login(f"{PFX}_p1@test.invalid")
        p2 = _login(f"{PFX}_p2@test.invalid")
        coach = _login(f"{PFX}_t@test.invalid")

        # 1. anon
        r = TestClient(app).get(f"/api/v2/parent/students/{sid}/commentary?kind=program")
        check("1. anon 401", r.status_code == 401, str(r.status_code))

        # 2. yabancı veli → 404
        r = p2.get(f"/api/v2/parent/students/{sid}/commentary?kind=program")
        check("2. yabancı veli 404", r.status_code == 404, str(r.status_code))

        # 3. koç rolü → 403
        r = coach.get(f"/api/v2/parent/students/{sid}/commentary?kind=program")
        check("3. koç rolü 403", r.status_code == 403, str(r.status_code))

        # 4. geçersiz kind
        r = p1.get(f"/api/v2/parent/students/{sid}/commentary?kind=abc")
        check("4. geçersiz kind 422", r.status_code == 422, str(r.status_code))

        # 5. ücretsiz koçun çocuğu
        r = p2.get(f"/api/v2/parent/students/{seed['free_s']}/commentary?kind=program")
        d = r.json()
        check("5a. free koç: ai_available False + reason",
              r.status_code == 200 and d["ai_available"] is False and d["unavailable_reason"],
              r.text[:150])
        r = p2.post(f"/api/v2/parent/students/{seed['free_s']}/commentary",
                    json={"kind": "program"})
        check("5b. free koç: POST 403", r.status_code == 403, str(r.status_code))

        # 6. paid: boş GET
        r = p1.get(f"/api/v2/parent/students/{sid}/commentary?kind=program")
        d = r.json()
        check("6. paid: GET boş + daily_left=6",
              r.status_code == 200 and d["commentary"] is None
              and d["ai_available"] is True and d["daily_left"] == 6, r.text[:150])

        # 7. üret (program)
        r = p1.post(f"/api/v2/parent/students/{sid}/commentary", json={"kind": "program"})
        d = r.json()
        u = _usage_counts(seed["p1"])
        check("7. POST program → sections + kredi 6",
              r.status_code == 200 and d["commentary"]
              and len(d["commentary"]["sections"]) >= 2
              and d["commentary"]["kind_label"] == "Program yorumu"
              and d["commentary"]["has_audio"] is False
              and u == {"gen": 1, "voice": 0, "credits": 6},
              f"{r.status_code} {u} {r.text[:120]}")

        # 8. cache okuma ücretsiz
        r = p1.get(f"/api/v2/parent/students/{sid}/commentary?kind=program")
        d = r.json()
        u = _usage_counts(seed["p1"])
        check("8. GET cache + taze + ücretsiz",
              r.status_code == 200 and d["commentary"] and d["is_stale"] is False
              and u["gen"] == 1, f"{r.status_code} {u}")

        # 9. bu haftaya yeni görev → stale
        with SessionLocal() as db:
            t = Task(student_id=sid, date=seed["this_mon"], type=TaskType.TEST,
                     title="Ek görev", is_draft=False, status=TaskStatus.COMPLETED)
            db.add(t); db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=seed["book"],
                                book_section_id=seed["sec"],
                                planned_count=2, completed_count=2))
            db.commit()
        r = p1.get(f"/api/v2/parent/students/{sid}/commentary?kind=program")
        check("9. görev değişince is_stale True",
              r.status_code == 200 and r.json()["is_stale"] is True, r.text[:150])

        # 10. deneme yorumu + yeni denemeyle bayatlama
        r = p1.post(f"/api/v2/parent/students/{sid}/commentary", json={"kind": "deneme"})
        check("10a. POST deneme 200", r.status_code == 200, r.text[:150])
        with SessionLocal() as db:
            db.add(ExamResult(student_id=sid, created_by_id=seed["paid_t"],
                              title="LGS Deneme 3", exam_date=date.today(),
                              section=ExamSection.LGS, total_correct=70,
                              total_wrong=15, total_blank=5, net=65.0))
            db.commit()
        r = p1.get(f"/api/v2/parent/students/{sid}/commentary?kind=deneme")
        check("10b. yeni deneme → is_stale True",
              r.status_code == 200 and r.json()["is_stale"] is True, r.text[:150])

        # 11. verisiz çocuk → 422
        r = p1.post(f"/api/v2/parent/students/{seed['bare']}/commentary",
                    json={"kind": "deneme"})
        check("11. verisiz çocuk 422 not_enough_data",
              r.status_code == 422 and r.json()["detail"]["code"] == "not_enough_data",
              r.text[:150])

        # 12. yorumsuz çocukta voice → 404
        r = p1.post(f"/api/v2/parent/students/{seed['bare']}/commentary/voice",
                    json={"kind": "program"})
        check("12. yorumsuz voice 404", r.status_code == 404, str(r.status_code))

        # 13. voice ilk kez → kredi 2
        r = p1.post(f"/api/v2/parent/students/{sid}/commentary/voice",
                    json={"kind": "program"})
        d = r.json()
        u = _usage_counts(seed["p1"])
        check("13. voice ilk → charged + kredi 2",
              r.status_code == 200 and d["charged"] is True
              and d["audio_content_type"] == "audio/mpeg"
              and u["voice"] == 1 and u["credits"] == 6 + 6 + 2,
              f"{r.status_code} {u} {r.text[:120]}")

        # 14. voice tekrar → ücretsiz
        r = p1.post(f"/api/v2/parent/students/{sid}/commentary/voice",
                    json={"kind": "program"})
        u = _usage_counts(seed["p1"])
        check("14. voice tekrar → charged False + kredi değişmedi",
              r.status_code == 200 and r.json()["charged"] is False
              and u["voice"] == 1, f"{r.status_code} {u}")

        # 15. audio stream
        r = p1.get(f"/api/v2/parent/students/{sid}/commentary/audio?kind=program")
        check("15. audio GET bayt + content-type",
              r.status_code == 200 and r.content == FAKE_AUDIO
              and r.headers["content-type"].startswith("audio/mpeg"), str(r.status_code))

        # 16. yeniden üretim sesi temizler
        r = p1.post(f"/api/v2/parent/students/{sid}/commentary", json={"kind": "program"})
        d = r.json()
        r2 = p1.get(f"/api/v2/parent/students/{sid}/commentary/audio?kind=program")
        check("16. yeniden üretim → has_audio False + audio 404",
              r.status_code == 200 and d["commentary"]["has_audio"] is False
              and r2.status_code == 404, f"{r.status_code}/{r2.status_code}")

        # 17. günlük limit (şu ana kadar 3 üretim; 6'ya tamamla → 7. 429)
        codes = []
        for _ in range(4):
            rr = p1.post(f"/api/v2/parent/students/{sid}/commentary",
                         json={"kind": "program"})
            codes.append(rr.status_code)
        check("17. günlük limit → 3 x 200 sonra 429",
              codes[:3] == [200, 200, 200] and codes[3] == 429
              and rr.json()["detail"]["code"] == "daily_limit_reached",
              str(codes))

        # 18. eski insight ucu hâlâ çalışıyor (regresyon)
        r = p1.get(f"/api/v2/parent/students/{sid}/insight")
        check("18. eski /insight GET 200", r.status_code == 200, str(r.status_code))

    finally:
        gemini_mod.generate = orig_gen
        tts_mod.synthesize_speech = orig_tts
        _cleanup(seed)

    print(f"\n  Sonuç: {passed} PASS / {len(failed)} FAIL")
    for f in failed:
        print(f"    FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
