"""Müfredat eşleştirme (Faz 0) smoke — auto-map + AI öneri + apply.

Kitap ünitesi (BookSection) → resmi konu (Topic). Deterministik auto-map (normalize
exact + önek temizleme + bağlaç/alias) + Gemini semantik (monkeypatch) + uygula.
Hibrit müfredat omurgasının ön şartı.

Aşama 1 (2026-06-24): auto-map artık yayınevi/ünite önekini ("1. Ünite —", "BS",
"TYT", "Konu:") temizler + bağlaç (ve/ile) atar + alias (OBEB OKEK = EBOB EKOK)
uygular → AI çağrısından önce çok daha fazla ünite ücretsiz/anlık eşleşir.
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
        t4 = Topic(subject_id=subj.id, name="EBOB EKOK", order=3, is_builtin=True)
        t5 = Topic(subject_id=subj.id, name="Veri ve İstatistik", order=4, is_builtin=True)
        db.add_all([t1, t2, t3, t4, t5]); db.flush()
        # Koç kitabı + section'lar — Aşama 1 katmanlarını kapsar:
        book = Book(name=f"{PFX} Kitap", subject_id=subj.id, type=BookType.SORU_BANKASI,
                    teacher_id=teacher.id)
        db.add(book); db.flush()
        s_exact = BookSection(book_id=book.id, label="Olasılık", test_count=10, order=0)  # auto exact
        s_prefix = BookSection(book_id=book.id, label="5. Ünite — Doğrunun Analitiği",
                               test_count=8, order=1)  # auto: sayı+ünite öneki temizle
        s_alias = BookSection(book_id=book.id, label="OBEB OKEK", test_count=10, order=2)  # auto: alias
        s_ve = BookSection(book_id=book.id, label="Veri İstatistik", test_count=10, order=3)  # auto: bağlaç
        s_semantic = BookSection(book_id=book.id, label="İhtimal Hesapları",
                                 test_count=8, order=4)  # auto ÇÖZEMEZ → AI
        s_mapped = BookSection(book_id=book.id, label="Üslü", test_count=5, order=5,
                               topic_id=t3.id)  # zaten eşli
        db.add_all([s_exact, s_prefix, s_alias, s_ve, s_semantic, s_mapped]); db.flush()
        db.commit()
        ids = {"teacher": teacher.id, "subj": subj.id, "book": book.id,
               "t1": t1.id, "t2": t2.id, "t3": t3.id, "t4": t4.id, "t5": t5.id,
               "s_exact": s_exact.id, "s_prefix": s_prefix.id, "s_alias": s_alias.id,
               "s_ve": s_ve.id, "s_semantic": s_semantic.id, "s_mapped": s_mapped.id}

    try:
        # --- Birim: anahtar üretici katmanları (önek/bağlaç/alias) ---
        check("0a. önek temizleme: '5. Ünite — Doğrunun Analitiği' = 'Doğrunun Analitiği'",
              cm._label_key("5. Ünite — Doğrunun Analitiği") == cm._topic_key("Doğrunun Analitiği"))
        check("0b. yayınevi öneki: 'BS Üslü Sayılar' = 'Üslü Sayılar'",
              cm._label_key("BS Üslü Sayılar") == cm._topic_key("Üslü Sayılar"))
        check("0c. bağlaç: 'Veri İstatistik' = 'Veri ve İstatistik'",
              cm._label_key("Veri İstatistik") == cm._topic_key("Veri ve İstatistik"))
        check("0d. alias: 'OBEB OKEK' = 'EBOB EKOK'",
              cm._label_key("OBEB OKEK") == cm._topic_key("EBOB EKOK"))

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
            check("2. önekli '5. Ünite — Doğrunun Analitiği' → auto t1 (PREFIX)",
                  by_sec[ids["s_prefix"]]["suggested_topic_id"] == ids["t1"]
                  and by_sec[ids["s_prefix"]]["source"] == "auto",
                  f"{by_sec[ids['s_prefix']]}")
            check("3. 'OBEB OKEK' → auto t4 (ALIAS)",
                  by_sec[ids["s_alias"]]["suggested_topic_id"] == ids["t4"]
                  and by_sec[ids["s_alias"]]["source"] == "auto",
                  f"{by_sec[ids['s_alias']]}")
            check("4. 'Veri İstatistik' → auto t5 (BAĞLAÇ)",
                  by_sec[ids["s_ve"]]["suggested_topic_id"] == ids["t5"]
                  and by_sec[ids["s_ve"]]["source"] == "auto",
                  f"{by_sec[ids['s_ve']]}")
            check("5. 'İhtimal Hesapları' → auto ÇÖZEMEZ (source=none)",
                  by_sec[ids["s_semantic"]]["suggested_topic_id"] is None
                  and by_sec[ids["s_semantic"]]["source"] == "none",
                  f"{by_sec[ids['s_semantic']]}")
            check("6. zaten eşli section → source=mapped, öneri yok",
                  by_sec[ids["s_mapped"]]["source"] == "mapped"
                  and by_sec[ids["s_mapped"]]["current_topic_id"] == ids["t3"])

        # --- Servis: AI öneri (monkeypatch gemini) — yalnız çözülemeyen için ---
        import app.services.gemini as gem
        orig = gem.generate
        gem.generate = lambda parts, **kw: (
            '{"mappings":[{"section_id":%d,"topic_id":%d,"confidence":"high"}]}'
            % (ids["s_semantic"], ids["t2"])
        )
        try:
            with SessionLocal() as db:
                book = db.get(Book, ids["book"])
                topics = db.query(Topic).filter(Topic.subject_id == ids["subj"]).all()
                rows = cm.suggest_for_book(db, book, topics, use_ai=True)
                by_sec = {r["section_id"]: r for r in rows}
                check("7. AI 'İhtimal Hesapları' → t2 (Olasılık), source=ai",
                      by_sec[ids["s_semantic"]]["suggested_topic_id"] == ids["t2"]
                      and by_sec[ids["s_semantic"]]["source"] == "ai"
                      and by_sec[ids["s_semantic"]]["confidence"] == "high",
                      f"{by_sec[ids['s_semantic']]}")
                check("8. AI auto'yu EZMEZ (exact + önek + alias hâlâ auto)",
                      by_sec[ids["s_exact"]]["source"] == "auto"
                      and by_sec[ids["s_prefix"]]["source"] == "auto"
                      and by_sec[ids["s_alias"]]["source"] == "auto")
        finally:
            gem.generate = orig

        # --- HTTP: suggestions + apply ---
        get_login_limiter().reset()
        client = TestClient(app)
        with SessionLocal() as db:
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient")); db.commit()
        r = client.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        check("9. login 200", r.status_code == 200, r.text[:100])

        r = client.get(f"/api/v2/teacher/library/books/{ids['book']}/mapping-suggestions")
        j = r.json()
        check("10. suggestions 200 + mapped_count=1 + 5 aday konu",
              r.status_code == 200 and j["mapped_count"] == 1
              and len(j["candidate_topics"]) == 5, f"{r.status_code} {j.get('mapped_count')}")
        check("11. önekli section auto öneri taşır (t1)",
              any(row["section_id"] == ids["s_prefix"] and row["suggested_topic_id"] == ids["t1"]
                  and row["source"] == "auto" for row in j["rows"]))

        # apply: önekli'yi t1'e + alias'ı t4'e
        r = client.post(
            f"/api/v2/teacher/library/books/{ids['book']}/apply-mapping",
            json={"items": [
                {"section_id": ids["s_prefix"], "topic_id": ids["t1"]},
                {"section_id": ids["s_alias"], "topic_id": ids["t4"]},
            ]},
        )
        check("12. apply 200 + changed=2", r.status_code == 200
              and r.json()["data"]["changed"] == 2, r.text[:150])
        with SessionLocal() as db:
            check("13. apply sonrası section'lar eşli",
                  db.get(BookSection, ids["s_prefix"]).topic_id == ids["t1"]
                  and db.get(BookSection, ids["s_alias"]).topic_id == ids["t4"])

        # apply ile kaldırma: topic_id=None
        r = client.post(
            f"/api/v2/teacher/library/books/{ids['book']}/apply-mapping",
            json={"items": [{"section_id": ids["s_prefix"], "topic_id": None}]},
        )
        with SessionLocal() as db:
            check("14. topic_id=None → eşleme kaldırıldı",
                  db.get(BookSection, ids["s_prefix"]).topic_id is None
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
