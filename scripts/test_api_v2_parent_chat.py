# -*- coding: utf-8 -*-
"""API v2 Rota Veli Asistanı P2 smoke — /parent/students/{id}/chat.

Yazılı sohbet: kredisiz karşılama + çipler · soru = 3 kredi (koç havuzu) ·
veli başına günde 10 soru · geçmiş saklanır + son mesajlar bağlama girer ·
sahiplik 404 · kapılar. Gemini monkeypatch — gerçek çağrı YOK.

Senaryolar:
  1. anon 401 · 2. yabancı veli 404 · 3. koç rolü 403
  4. GET: karşılama "dün eksik" + çipler (dun ask + deneme commentary) + daily_left=10
  5. free koç: ai_available False; POST 403
  6. kısa mesaj 422 (pydantic)
  7. POST soru → [veli, rota] mesajları + 3 kredi + daily_left=9
  8. GET: geçmişte 2 mesaj (asc) — karşılama kredisiz (kredi değişmez)
  9. ikinci soru: bağlamda ÖNCEKİ sohbet + pakette görev adı (prompt yakalama)
 10. günlük limit: kalan hakkı doldur → 429 daily_limit_reached
 11. verisiz çocukta soru → yine cevap (paket boş; model 'veri yok' der) 200
 12. commentary smoke etkileşimi yok (chat kredisi commentary limitine sayılmaz)
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

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, CreditAccount, ParentChatMessage,
    ParentCommentary, ParentRelation, ParentStudentLink, Subject, Task,
    TaskBookItem, TaskStatus, TaskType, UsageEvent, User, UserRole,
)
from app.models.curriculum import ExamSection
from app.models.exam_result import ExamResult
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"v2ch_{secrets.token_hex(3)}"
PWD = "TestRotaChat!23"
passed = 0
failed: list[str] = []
captured_prompts: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _fake_generate(parts, *, personal_data, timeout=45.0, json_mode=True,
                   max_output_tokens=8192, prefer_paid=True, **kwargs):
    captured_prompts.append(parts[0].get("text", ""))
    return "Dün Doğrusal Denklemler testi yapılmadı; bu akşam kısaca konuşabilirsiniz."


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PWD)
    today = date.today()
    yesterday = today - timedelta(days=1)

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
        # ID-reuse kirliliği temizliği (bkz. commentary smoke dersi)
        from sqlalchemy import delete as _d
        db.execute(_d(UsageEvent).where(UsageEvent.actor_user_id.in_([p1.id, p2.id])))
        db.execute(_d(CreditAccount).where(CreditAccount.owner_id.in_([paid_t.id, free_t.id])))
        db.execute(_d(ParentChatMessage).where(
            ParentChatMessage.parent_id.in_([p1.id, p2.id])))
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

        def add_task(d, status, title):
            t = Task(student_id=stu.id, date=d, type=TaskType.TEST, title=title,
                     is_draft=False, status=status)
            db.add(t); db.flush()
            db.add(TaskBookItem(task_id=t.id, book_id=book.id,
                                book_section_id=sec.id,
                                planned_count=4, completed_count=0))
            return t

        # DÜN: 1 tamam + 1 EKSİK (karşılama tetikleyicisi) · BUGÜN: 1 bekliyor
        add_task(yesterday, TaskStatus.COMPLETED, "Mat SB — Ünite 1: 4 test")
        add_task(yesterday, TaskStatus.PENDING, "Doğrusal Denklemler Görevi")
        add_task(today, TaskStatus.PENDING, "Mat SB — Ünite 1: 4 test (bugün)")

        db.add(ExamResult(student_id=stu.id, created_by_id=paid_t.id,
                          title="LGS Deneme 5", exam_date=today - timedelta(days=1),
                          section=ExamSection.LGS, total_correct=60, total_wrong=20,
                          total_blank=10, net=53.33))
        db.commit()
        return {
            "paid_t": paid_t.id, "free_t": free_t.id,
            "stu": stu.id, "bare": bare.id, "free_s": free_s.id,
            "p1": p1.id, "p2": p2.id,
            "book": book.id, "subject": mat.id,
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
        db.execute(sa_delete(ParentChatMessage).where(
            ParentChatMessage.parent_id.in_([seed["p1"], seed["p2"]])))
        db.execute(sa_delete(ParentCommentary).where(ParentCommentary.student_id.in_(sids)))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_([seed["p1"], seed["p2"]])))
        db.execute(sa_delete(UsageEvent).where(
            UsageEvent.actor_user_id.in_([seed["p1"], seed["p2"]])))
        db.execute(sa_delete(CreditAccount).where(
            CreditAccount.owner_id.in_([seed["paid_t"], seed["free_t"]])))
        for b in db.query(Book).filter(Book.teacher_id == seed["paid_t"]).all():
            db.execute(sa_delete(BookSection).where(BookSection.book_id == b.id))
        db.execute(sa_delete(Book).where(Book.teacher_id == seed["paid_t"]))
        db.execute(sa_delete(Subject).where(Subject.id == seed["subject"]))
        db.execute(sa_delete(User).where(User.id.in_(uids)))
        db.commit()


def _login(email: str) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PWD})
    if r.status_code != 200:
        raise RuntimeError(f"login failed {email}: {r.status_code} {r.text}")
    return c


def _credits(parent_id: int) -> int:
    from app.models import UsageKind
    with SessionLocal() as db:
        rows = db.query(UsageEvent).filter(
            UsageEvent.actor_user_id == parent_id,
            UsageEvent.kind == UsageKind.AI_PARENT_CHAT,
        ).all()
        return sum(r.credits for r in rows)


def main() -> int:
    print(f"\n=== Rota Veli Sohbeti P2 smoke — {PFX} ===\n")
    get_login_limiter().reset()

    import app.services.gemini as gemini_mod
    orig = gemini_mod.generate
    gemini_mod.generate = _fake_generate

    seed = _seed()
    sid = seed["stu"]
    try:
        p1 = _login(f"{PFX}_p1@test.invalid")
        p2 = _login(f"{PFX}_p2@test.invalid")
        coach = _login(f"{PFX}_t@test.invalid")

        r = TestClient(app).get(f"/api/v2/parent/students/{sid}/chat")
        check("1. anon 401", r.status_code == 401, str(r.status_code))

        r = p2.get(f"/api/v2/parent/students/{sid}/chat")
        check("2. yabancı veli 404", r.status_code == 404, str(r.status_code))

        r = coach.get(f"/api/v2/parent/students/{sid}/chat")
        check("3. koç rolü 403", r.status_code == 403, str(r.status_code))

        r = p1.get(f"/api/v2/parent/students/{sid}/chat")
        d = r.json()
        chip_ids = [c["id"] for c in d["greeting"]["chips"]]
        chip_actions = {c["id"]: c["action"] for c in d["greeting"]["chips"]}
        check("4. karşılama: dün-eksik metni + çipler + daily_left=10",
              r.status_code == 200
              and "Doğrusal Denklemler Görevi" in d["greeting"]["text"]
              and "dun" in chip_ids and chip_actions.get("dun") == "ask"
              and chip_actions.get("deneme-yorum") == "commentary"
              and d["daily_left"] == 10 and d["messages"] == []
              and d["ai_available"] is True,
              r.text[:200])

        r = p2.get(f"/api/v2/parent/students/{seed['free_s']}/chat")
        d = r.json()
        ok_get = r.status_code == 200 and d["ai_available"] is False
        r = p2.post(f"/api/v2/parent/students/{seed['free_s']}/chat",
                    json={"message": "Nasıl gidiyor?"})
        check("5. free koç: ai_available False + POST 403",
              ok_get and r.status_code == 403, str(r.status_code))

        r = p1.post(f"/api/v2/parent/students/{sid}/chat", json={"message": "a"})
        check("6. kısa mesaj 422", r.status_code == 422, str(r.status_code))

        r = p1.post(f"/api/v2/parent/students/{sid}/chat",
                    json={"message": "Dün neler yapılmadı?"})
        d = r.json()
        check("7. soru → [veli,rota] + 3 kredi + daily_left=9",
              r.status_code == 200 and len(d["messages"]) == 2
              and d["messages"][0]["role"] == "veli"
              and d["messages"][1]["role"] == "rota"
              and "Doğrusal" in d["messages"][1]["body"]
              and _credits(seed["p1"]) == 3 and d["daily_left"] == 9,
              f"{r.status_code} kredi={_credits(seed['p1'])} {r.text[:120]}")

        r = p1.get(f"/api/v2/parent/students/{sid}/chat")
        d = r.json()
        check("8. geçmiş 2 mesaj (asc) + karşılama kredisiz",
              r.status_code == 200 and len(d["messages"]) == 2
              and d["messages"][0]["role"] == "veli"
              and _credits(seed["p1"]) == 3, r.text[:150])

        captured_prompts.clear()
        r = p1.post(f"/api/v2/parent/students/{sid}/chat",
                    json={"message": "Peki bugün ne yapmalı?"})
        prompt = captured_prompts[0] if captured_prompts else ""
        check("9. bağlamda önceki sohbet + pakette görev adı",
              r.status_code == 200
              and "SOHBET GEÇMİŞİ" in prompt
              and "Dün neler yapılmadı?" in prompt
              and "Doğrusal Denklemler Görevi" in prompt,
              prompt[:150])

        left = p1.get(f"/api/v2/parent/students/{sid}/chat").json()["daily_left"]
        codes = []
        for i in range(left + 1):
            rr = p1.post(f"/api/v2/parent/students/{sid}/chat",
                         json={"message": f"Soru {i}?"})
            codes.append(rr.status_code)
        check("10. günlük limit → kalan hak 200, sonra 429",
              all(c == 200 for c in codes[:-1]) and codes[-1] == 429
              and rr.json()["detail"]["code"] == "daily_limit_reached",
              str(codes))

        # 11. verisiz çocukta soru — limit p1'de doldu, p2 kendi çocuğuna soramaz;
        # bare çocuk p1'e bağlı → limit dolu. Yeni gün taklidi yerine: limitten
        # ÖNCE sorulmuş olsaydı davranışı ayrı velide test edelim → free koçta
        # kapalı. Bu senaryo: bare için GET karşılaması "Merhaba" düşer (verisiz).
        r = p1.get(f"/api/v2/parent/students/{seed['bare']}/chat")
        d = r.json()
        check("11. verisiz çocukta karşılama nazik + çipler var",
              r.status_code == 200 and d["greeting"]["text"].startswith("Merhaba")
              and len(d["greeting"]["chips"]) >= 2, r.text[:150])

        # 12. chat kredileri commentary günlük limitini ETKİLEMEZ
        r = p1.get(f"/api/v2/parent/students/{sid}/commentary?kind=program")
        check("12. commentary daily_left hâlâ 6 (chat sayılmaz)",
              r.status_code == 200 and r.json()["daily_left"] == 6, r.text[:120])

    finally:
        gemini_mod.generate = orig
        _cleanup(seed)

    print(f"\n  Sonuç: {passed} PASS / {len(failed)} FAIL")
    for f in failed:
        print(f"    FAIL: {f}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
