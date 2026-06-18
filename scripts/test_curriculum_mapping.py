"""Müfredat eşleştirme (Faz 0) smoke — auto-map + AI öneri + apply.

Kitap ünitesi (BookSection) → resmi konu (Topic). Deterministik auto-map (normalize
exact) + Gemini semantik (monkeypatch) + uygula. Hibrit müfredat omurgasının ön şartı.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book, BookSection, BookType, Subject, SuspiciousIp, Topic, User, UserRole,
)
from app.services import curriculum_mapping as cm
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"cmap{secrets.token_hex(3)}"
PASSWORD = "Curric!2026X"
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
    print(f"\n=== curriculum mapping smoke — {PFX} ===\n")
    ids: dict = {}
    with SessionLocal() as db:
        teacher = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                       full_name="Koç", role=UserRole.TEACHER, is_active=True, plan="solo_free",
                       must_change_password=False)
        db.add(teacher); db.flush()
        # Resmi (built-in) ders + sıralı konular
        subj = Subject(name=f"{PFX} Matematik", order=1, is_builtin=True, teacher_id=None)
        db.add(subj); db.flush()
        t1 = Topic(subject_id=subj.id, name="Doğrunun Analitiği", order=0, is_builtin=True)
        t2 = Topic(subject_id=subj.id, name="Olasılık", order=1, is_builtin=True)
        t3 = Topic(subject_id=subj.id, name="Üslü Sayılar", order=2, is_builtin=True)
        db.add_all([t1, t2, t3]); db.flush()
        # Koç kitabı + section'lar: biri tam eşleşir, biri AI gerektirir, biri zaten eşli
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book); db.flush()
        s_exact = BookSection(book_id=book.id, label="Olasılık", test_count=10, order=0)  # auto
        s_fuzzy = BookSection(book_id=book.id, label="BS Doğrunun Analitiği", test_count=8, order=1)  # AI
        s_mapped = BookSection(book_id=book.id, label="Üslü", test_count=5, order=2, topic_id=t3.id)  # zaten eşli
        db.add_all([s_exact, s_fuzzy, s_mapped]); db.flush()
        db.commit()
        ids = {"teacher": teacher.id, "subj": subj.id, "book": book.id,
               "t1": t1.id, "t2": t2.id, "t3": t3.id,
               "s_exact": s_exact.id, "s_fuzzy": s_fuzzy.id, "s_mapped": s_mapped.id}

    try:
        # --- Servis: auto-map (AI'sız) ---
        with SessionLocal() as db:
            book = db.get(Book, ids["book"])
            topics = db.query(Topic).filter(Topic.subject_id == ids["subj"]).all()
            rows = cm.suggest_for_book(db, book, topics, use_ai=False)
            by_sec = {r["section_id"]: r for r in rows}
            check("1. exact 'Olasılık' → auto öneri t2",
                  by_sec[ids["s_exact"]]["suggested_topic_id"] == ids["t2"]
                  and by_sec[ids["s_exact"]]["source"] == "auto",
                  f"{by_sec[ids['s_exact']]}")
            check("2. 'BS Doğrunun Analitiği' → auto ÇÖZEMEZ (source=none)",
                  by_sec[ids["s_fuzzy"]]["suggested_topic_id"] is None
                  and by_sec[ids["s_fuzzy"]]["source"] == "none")
            check("3. zaten eşli section → source=mapped, öneri yok",
                  by_sec[ids["s_mapped"]]["source"] == "mapped"
                  and by_sec[ids["s_mapped"]]["current_topic_id"] == ids["t3"])

        # --- Servis: AI öneri (monkeypatch gemini) ---
        import app.services.gemini as gem
        orig = gem.generate
        gem.generate = lambda parts, **kw: (
            '{"mappings":[{"section_id":%d,"topic_id":%d,"confidence":"high"}]}'
            % (ids["s_fuzzy"], ids["t1"])
        )
        try:
            with SessionLocal() as db:
                book = db.get(Book, ids["book"])
                topics = db.query(Topic).filter(Topic.subject_id == ids["subj"]).all()
                rows = cm.suggest_for_book(db, book, topics, use_ai=True)
                by_sec = {r["section_id"]: r for r in rows}
                check("4. AI 'BS Doğrunun Analitiği' → t1 (Doğrunun Analitiği), source=ai",
                      by_sec[ids["s_fuzzy"]]["suggested_topic_id"] == ids["t1"]
                      and by_sec[ids["s_fuzzy"]]["source"] == "ai"
                      and by_sec[ids["s_fuzzy"]]["confidence"] == "high",
                      f"{by_sec[ids['s_fuzzy']]}")
                check("5. AI exact'i EZMEZ (Olasılık hâlâ auto)",
                      by_sec[ids["s_exact"]]["source"] == "auto")
        finally:
            gem.generate = orig

        # --- HTTP: suggestions + apply ---
        get_login_limiter().reset()
        client = TestClient(app)
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
        r = client.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        check("6. login 200", r.status_code == 200, r.text[:100])

        r = client.get(f"/api/v2/teacher/library/books/{ids['book']}/mapping-suggestions")
        j = r.json()
        check("7. suggestions 200 + mapped_count=1 + 3 aday konu",
              r.status_code == 200 and j["mapped_count"] == 1
              and len(j["candidate_topics"]) == 3, f"{r.status_code} {j.get('mapped_count')}")
        check("8. exact section auto öneri taşır",
              any(row["section_id"] == ids["s_exact"] and row["suggested_topic_id"] == ids["t2"]
                  for row in j["rows"]))

        # apply: exact'i uygula + fuzzy'yi t1'e
        r = client.post(
            f"/api/v2/teacher/library/books/{ids['book']}/apply-mapping",
            json={"items": [
                {"section_id": ids["s_exact"], "topic_id": ids["t2"]},
                {"section_id": ids["s_fuzzy"], "topic_id": ids["t1"]},
            ]},
        )
        check("9. apply 200 + changed=2", r.status_code == 200
              and r.json()["data"]["changed"] == 2, r.text[:150])
        with SessionLocal() as db:
            check("10. apply sonrası 3/3 section eşli (mapped_count=3)",
                  db.get(BookSection, ids["s_exact"]).topic_id == ids["t2"]
                  and db.get(BookSection, ids["s_fuzzy"]).topic_id == ids["t1"])

        # apply ile kaldırma: topic_id=None
        r = client.post(
            f"/api/v2/teacher/library/books/{ids['book']}/apply-mapping",
            json={"items": [{"section_id": ids["s_exact"], "topic_id": None}]},
        )
        with SessionLocal() as db:
            check("11. topic_id=None → eşleme kaldırıldı",
                  db.get(BookSection, ids["s_exact"]).topic_id is None
                  and r.json()["data"]["changed"] == 1)
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(BookSection).where(BookSection.book_id == ids["book"]))
            db.execute(sa_delete(Book).where(Book.id == ids["book"]))
            db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subj"]))
            db.execute(sa_delete(Subject).where(Subject.id == ids["subj"]))
            db.execute(sa_delete(User).where(User.id == ids["teacher"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
