"""ai_book_structure okuma motoru birim smoke (12 senaryo).

Gemini monkeypatch'lenir — gerçek çağrı YOK. Kapsam:
  normalize (null korunur / clamp / boş etiket düşer) · merge (uyum / çelişki
  suspect / tek-null yazılı değeri alır / uzunluk farkı) · çift okuma + tek
  okuma fallback'i · NotATocError · eksik sayı uyarısı · identify_cover ·
  0 kredilik ölçüm kaydı + günlük sayım (kredi hesabına DOKUNMAZ).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
import secrets
import threading

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import User, UserRole
from app.services import ai_book_structure as abs_svc
from app.services import gemini
from app.services.security import hash_password

PFX = f"absmoke_{secrets.token_hex(3)}"

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


def main() -> int:
    print(f"\n=== ai_book_structure birim smoke — {PFX} ===\n")

    # ===== 1. _normalize_read: null korunur + boş etiket düşer + clamp =====
    n = abs_svc._normalize_read({
        "book_title": "  X Kitabı  ",
        "publisher": None,
        "subject_hint": "Matematik",
        "grade_hint": "8",
        "sections": [
            {"label": "1. Ünite", "test_count": 12},
            {"label": "2. Ünite", "test_count": None},      # null KORUNUR
            {"label": "", "test_count": 5},                  # boş etiket düşer
            {"label": "3. Ünite", "test_count": 0},          # <1 → null
            {"label": "4. Ünite", "test_count": 999},        # clamp 200
            {"label": "5. Ünite", "test_count": "abc"},      # parse edilemez → null
        ],
    })
    check(
        "1. normalize: null korunur + clamp + boş düşer",
        n["book_title"] == "X Kitabı"
        and n["grade_hint"] == 8
        and len(n["sections"]) == 5
        and n["sections"][1]["test_count"] is None
        and n["sections"][2]["test_count"] is None
        and n["sections"][3]["test_count"] == 200
        and n["sections"][4]["test_count"] is None,
        json.dumps(n, ensure_ascii=False)[:200],
    )

    # ===== 2. merge: birebir uyum → suspect yok =====
    r_ok = {
        "book_title": "K", "publisher": "Y", "subject_hint": None, "grade_hint": None,
        "sections": [
            {"label": "Sayılar", "test_count": 10},
            {"label": "Cebir", "test_count": 8},
        ],
    }
    m = abs_svc._merge_reads(r_ok, {**r_ok, "sections": [dict(s) for s in r_ok["sections"]]})
    check(
        "2. merge: uyum → suspect=0",
        all(not s["suspect"] for s in m["sections"]) and m["read_count"] == 2,
        str(m["sections"]),
    )

    # ===== 3. merge: test sayısı çelişkisi → suspect + uyarı =====
    r2 = {**r_ok, "sections": [
        {"label": "Sayılar", "test_count": 10},
        {"label": "Cebir", "test_count": 9},
    ]}
    m = abs_svc._merge_reads(r_ok, r2)
    check(
        "3. merge: çelişki → suspect + uyarı",
        m["sections"][1]["suspect"] is True
        and m["sections"][1]["test_count"] == 8
        and any("uyuşmadı" in w for w in m["warnings"]),
        str(m),
    )

    # ===== 4. merge: biri null + etiket uyumlu → yazılı değer, suspect yok =====
    r3 = {**r_ok, "sections": [
        {"label": "Sayılar", "test_count": None},
        {"label": "Cebir", "test_count": 8},
    ]}
    m = abs_svc._merge_reads(r3, r_ok)
    check(
        "4. merge: tek-null → yazılı değer alınır",
        m["sections"][0]["test_count"] == 10 and m["sections"][0]["suspect"] is False,
        str(m["sections"]),
    )

    # ===== 5. merge: uzunluk farkı → ekstra bölüm suspect + uyarı =====
    r4 = {**r_ok, "sections": [
        {"label": "Sayılar", "test_count": 10},
        {"label": "Cebir", "test_count": 8},
        {"label": "Geometri", "test_count": 6},
    ]}
    m = abs_svc._merge_reads(r_ok, r4)
    extra = [s for s in m["sections"] if s["label"] == "Geometri"]
    check(
        "5. merge: yalnız 2. okumadaki bölüm → suspect + uyarı",
        len(extra) == 1 and extra[0]["suspect"] is True
        and any("farklı bölüm sayısı" in w for w in m["warnings"]),
        str(m),
    )

    # ===== 6. read_structure çift okuma (monkeypatch) =====
    good_json = json.dumps({
        "book_title": "4K TYT Matematik", "publisher": "4K", "subject_hint": "Matematik",
        "grade_hint": None,
        "sections": [
            {"label": "Temel Kavramlar", "test_count": 14},
            {"label": "Sayı Basamakları", "test_count": 11},
            {"label": "Bölme ve Bölünebilme", "test_count": None},
        ],
    }, ensure_ascii=False)
    orig_generate = gemini.generate
    try:
        gemini.generate = lambda *a, **k: good_json  # type: ignore[assignment]
        res = abs_svc.read_structure([(b"fakejpg", "image/jpeg")])
        check(
            "6. read_structure: çift okuma birleşti",
            res["read_count"] == 2 and len(res["sections"]) == 3
            and res["sections"][0]["test_count"] == 14
            and res["sections"][2]["test_count"] is None,
            str(res)[:200],
        )
        # ===== 7. eksik sayı uyarısı =====
        check(
            "7. eksik test sayısı uyarısı üretildi",
            any("yazmıyor" in w for w in res["warnings"]),
            str(res["warnings"]),
        )

        # ===== 8. NotATocError (<2 bölüm) =====
        gemini.generate = lambda *a, **k: json.dumps(  # type: ignore[assignment]
            {"book_title": None, "publisher": None, "subject_hint": None,
             "grade_hint": None, "sections": []}
        )
        try:
            abs_svc.read_structure([(b"fakejpg", "image/jpeg")])
            check("8. not_a_toc: <2 bölüm → NotATocError", False, "exception yok")
        except abs_svc.NotATocError:
            check("8. not_a_toc: <2 bölüm → NotATocError", True)

        # ===== 9. tek okuma fallback (biri düşer) =====
        lock = threading.Lock()
        state = {"n": 0}

        def flaky(*a, **k):
            with lock:
                state["n"] += 1
                fail = state["n"] == 1
            if fail:
                raise abs_svc.AIServiceUnavailable("boom")
            return good_json

        gemini.generate = flaky  # type: ignore[assignment]
        res = abs_svc.read_structure([(b"fakejpg", "image/jpeg")])
        check(
            "9. tek okuma fallback: read_count=1 + uyarı",
            res["read_count"] == 1
            and any("Doğrulama okuması yapılamadı" in w for w in res["warnings"])
            and all(s["suspect"] is False for s in res["sections"]),
            str(res)[:200],
        )

        # ===== 10. identify_cover =====
        gemini.generate = lambda *a, **k: json.dumps({  # type: ignore[assignment]
            "book_title": "Apotemi TYT Matematik", "publisher": "Apotemi",
            "subject_hint": "Matematik", "grade_hint": 99, "exam_hint": "TYT",
        })
        info = abs_svc.identify_cover(b"fakejpg", "image/jpeg")
        check(
            "10. identify_cover: alanlar + grade clamp",
            info["book_title"] == "Apotemi TYT Matematik"
            and info["grade_hint"] is None and info["exam_hint"] == "TYT",
            str(info),
        )
    finally:
        gemini.generate = orig_generate  # type: ignore[assignment]

    # ===== 11-12. ölçüm kaydı + günlük sayım (0 kredi, hesap değişmez) =====
    with SessionLocal() as db:
        u = User(
            email=f"{PFX}@test.invalid", password_hash=hash_password("Xx123456!!abcd"),
            full_name="ABS Test Koç", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        db.add(u)
        db.commit()
        uid = u.id
        try:
            from app.models import CreditAccount, UsageEvent, UsageKind

            before = abs_svc.book_read_count_today(db, uid)
            abs_svc.record_book_read(db, u, mode="toc", section_count=3, autocommit=True)
            abs_svc.record_book_read(db, u, mode="cover", section_count=0, autocommit=True)
            after = abs_svc.book_read_count_today(db, uid)
            ev = (
                db.query(UsageEvent)
                .filter(UsageEvent.actor_user_id == uid, UsageEvent.kind == UsageKind.AI_BOOK_READ)
                .all()
            )
            check(
                "11. record_book_read: 2 kayıt + günlük sayım arttı",
                after == before + 2 and len(ev) == 2 and all(e.credits == 0 for e in ev),
                f"before={before} after={after} n={len(ev)}",
            )
            acc = (
                db.query(CreditAccount)
                .filter(CreditAccount.owner_id == uid)
                .all()
            )
            used_total = sum(a.used_credits or 0 for a in acc)
            check(
                "12. kredi hesabı DEĞİŞMEDİ (0 kredi)",
                used_total == 0,
                f"used_total={used_total}",
            )
        finally:
            from app.models import UsageEvent

            db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id == uid))
            try:
                from app.models import CreditAccount

                db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id == uid))
            except Exception:
                pass
            db.execute(sa_delete(User).where(User.id == uid))
            db.commit()

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
