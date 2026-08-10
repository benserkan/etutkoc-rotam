"""API v2 Ortak Kitap Kataloğu smoke (~27 senaryo).

Kapsam: koç arama/detay (yalnız verified) · kişisel şablon ↔ katalog
izolasyonu · POST /books katalog kabulü (topic taşıma + usage_count) ·
contribute (pending + dedup + builtin süzgeci) · admin CRUD/verify/hide/
delete + audit + rozet · okuma uçları (monkeypatch — gerçek Gemini YOK) ·
günlük tavan 429 · 0 kredi güvencesi.
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
    AuditAction,
    AuditLog,
    Book,
    BookSection,
    BookTemplate,
    BookTemplateSection,
    BookType,
    CreditAccount,
    Subject,
    Topic,
    UsageEvent,
    UsageKind,
    User,
    UserRole,
)
from app.services import ai_book_structure as abs_svc
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"bkcat_{secrets.token_hex(3)}"
COACH_EMAIL = f"{PFX}_koc@test.invalid"
COACH_B_EMAIL = f"{PFX}_kocb@test.invalid"
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
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


def _seed() -> dict:
    with SessionLocal() as db:
        coach = User(
            email=COACH_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Katalog Koç A", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        coach_b = User(
            email=COACH_B_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Katalog Koç B", role=UserRole.TEACHER, is_active=True,
            plan="solo_pro",
        )
        admin = User(
            email=ADMIN_EMAIL, password_hash=hash_password(PASSWORD),
            full_name="Katalog Süper Admin", role=UserRole.SUPER_ADMIN, is_active=True,
        )
        db.add_all([coach, coach_b, admin])
        db.flush()

        # Builtin ders + 2 builtin LEAF konu (katalog eşleştirmesi bunlara bağlanır)
        bsubj = Subject(name=f"KatalogDers {PFX}", order=997, is_builtin=True, teacher_id=None)
        db.add(bsubj)
        db.flush()
        bt1 = Topic(name=f"Katalog Konu Bir {PFX}", order=0, subject_id=bsubj.id, is_builtin=True)
        bt2 = Topic(name=f"Katalog Konu İki {PFX}", order=1, subject_id=bsubj.id, is_builtin=True)
        db.add_all([bt1, bt2])
        db.flush()

        # Koç A'nın KİŞİSEL dersi + konusu (kataloğa SIZMAMALI)
        psubj = Subject(name=f"Kişisel Ders {PFX}", order=998, is_builtin=False, teacher_id=coach.id)
        db.add(psubj)
        db.flush()
        pt1 = Topic(name=f"Kişisel Konu {PFX}", order=0, subject_id=psubj.id, teacher_id=coach.id)
        db.add(pt1)
        db.flush()

        # Koç B'nin kişisel şablonu (koç A create'te kullanamamalı → 404)
        btpl = BookTemplate(
            teacher_id=coach_b.id, name=f"B Kişisel Şablon {PFX}",
            type=BookType.SORU_BANKASI, subject_id=bsubj.id, is_verified=True,
        )
        db.add(btpl)
        db.flush()
        db.add(BookTemplateSection(template_id=btpl.id, label="B Bölüm", default_test_count=5, order=0))

        # Koç A'nın kişisel şablonu (katalog aramasında GÖRÜNMEMELİ)
        atpl = BookTemplate(
            teacher_id=coach.id, name=f"4K Kişisel {PFX}",
            type=BookType.SORU_BANKASI, subject_id=bsubj.id, is_verified=True,
        )
        db.add(atpl)
        db.flush()
        db.add(BookTemplateSection(template_id=atpl.id, label="A Bölüm", default_test_count=7, order=0))
        db.commit()
        return {
            "coach_id": coach.id,
            "coach_b_id": coach_b.id,
            "admin_id": admin.id,
            "builtin_subject_id": bsubj.id,
            "builtin_topic1_id": bt1.id,
            "builtin_topic2_id": bt2.id,
            "personal_subject_id": psubj.id,
            "personal_topic_id": pt1.id,
            "b_personal_template_id": btpl.id,
            "a_personal_template_id": atpl.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        user_ids = [seed["coach_id"], seed["coach_b_id"], seed["admin_id"]]
        db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id.in_(user_ids)))
        db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(user_ids)))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_(user_ids)))
        # Katalog + kişisel şablonlar (PFX adlı)
        tpl_ids = [
            t.id for t in db.query(BookTemplate.id)
            .filter(BookTemplate.name.like(f"%{PFX}%"))
            .all()
        ]
        if tpl_ids:
            db.execute(sa_delete(BookTemplateSection).where(
                BookTemplateSection.template_id.in_(tpl_ids)
            ))
            db.execute(sa_delete(BookTemplate).where(BookTemplate.id.in_(tpl_ids)))
        book_ids = [
            b.id for b in db.query(Book.id).filter(Book.teacher_id.in_(user_ids)).all()
        ]
        if book_ids:
            db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(book_ids)))
            db.execute(sa_delete(Book).where(Book.id.in_(book_ids)))
        db.execute(sa_delete(Topic).where(Topic.id.in_([
            seed["builtin_topic1_id"], seed["builtin_topic2_id"], seed["personal_topic_id"],
        ])))
        db.execute(sa_delete(Subject).where(Subject.id.in_([
            seed["builtin_subject_id"], seed["personal_subject_id"],
        ])))
        db.execute(sa_delete(User).where(User.id.in_(user_ids)))
        db.commit()


def _login(client: TestClient, email: str) -> None:
    r = client.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"


def main() -> int:
    print(f"\n=== API v2 Ortak Kitap Kataloğu smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()
    orig_read = abs_svc.read_structure
    orig_cover = abs_svc.identify_cover

    try:
        anon = TestClient(app)

        # ===== 1. anonim → 401 =====
        r = anon.get("/api/v2/teacher/library/book-catalog/search", params={"q": "test"})
        check("1. anonim katalog araması → 401", r.status_code == 401, f"status={r.status_code}")

        admin = TestClient(app)
        _login(admin, ADMIN_EMAIL)

        # ===== 2. süper admin koç ucunda → 403 =====
        r = admin.get("/api/v2/teacher/library/book-catalog/search", params={"q": "test"})
        check("2. admin koç ucunda → 403", r.status_code == 403, f"status={r.status_code}")

        # ===== 3. admin create (publish) + konu eşleştirme =====
        create_body = {
            "name": f"4K TYT Matematik {PFX}",
            "publisher": "4K Yayınları",
            "type": "soru_bankasi",
            "subject_id": seed["builtin_subject_id"],
            "target_grade_min": 11,
            "target_grade_max": 12,
            "sections": [
                {"label": "Temel Kavramlar", "test_count": 14, "topic_id": seed["builtin_topic1_id"]},
                {"label": "Sayı Basamakları", "test_count": 11, "topic_id": seed["builtin_topic2_id"]},
                {"label": "Bölme Bölünebilme", "test_count": 9},
            ],
            "publish": True,
        }
        r = admin.post("/api/v2/admin/book-catalog", json=create_body)
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        entry_id = d.get("id")
        check(
            "3. admin create → verified + mapped_count=2 + total_tests=34",
            r.status_code == 200 and d.get("status") == "verified"
            and d.get("mapped_count") == 2 and d.get("total_tests") == 34
            and len(d.get("sections", [])) == 3,
            f"status={r.status_code} d={str(d)[:200]}",
        )

        # ===== 4. admin duplicate → 409 =====
        r = admin.post("/api/v2/admin/book-catalog", json=create_body)
        check(
            "4. admin mükerrer → 409 already_in_catalog",
            r.status_code == 409 and r.json()["detail"]["code"] == "already_in_catalog",
            f"status={r.status_code}",
        )

        coach = TestClient(app)
        _login(coach, COACH_EMAIL)

        # ===== 5. koç arama verified bulur =====
        r = coach.get("/api/v2/teacher/library/book-catalog/search", params={"q": "4k tyt"})
        items = r.json().get("items", []) if r.status_code == 200 else []
        check(
            "5. koç arama → verified kayıt",
            r.status_code == 200 and any(i["id"] == entry_id for i in items),
            f"status={r.status_code} n={len(items)}",
        )

        # ===== 6. pending koça görünmez =====
        r = admin.post("/api/v2/admin/book-catalog", json={
            **create_body,
            "name": f"Palme AYT Fizik {PFX}",
            "publisher": "Palme",
            "sections": [{"label": "Vektörler", "test_count": 8}],
            "publish": False,
        })
        pending_id = r.json()["data"]["id"] if r.status_code == 200 else None
        r2 = coach.get("/api/v2/teacher/library/book-catalog/search", params={"q": "palme ayt"})
        check(
            "6. pending kayıt koç aramasında YOK",
            r.status_code == 200 and r2.status_code == 200
            and len(r2.json().get("items", [])) == 0,
            f"create={r.status_code} search_n={len(r2.json().get('items', []))}",
        )

        # ===== 7. koç detay: verified 200 · pending 404 =====
        r = coach.get(f"/api/v2/teacher/library/book-catalog/{entry_id}")
        r2 = coach.get(f"/api/v2/teacher/library/book-catalog/{pending_id}")
        check(
            "7. koç detay verified=200, pending=404",
            r.status_code == 200 and len(r.json().get("sections", [])) == 3
            and r2.status_code == 404,
            f"v={r.status_code} p={r2.status_code}",
        )

        # ===== 8. kişisel şablon ↔ katalog izolasyonu =====
        r = coach.get("/api/v2/teacher/library/book-catalog/search", params={"q": "4k kişisel"})
        n_cat = len(r.json().get("items", []))
        r2 = coach.get("/api/v2/teacher/library/templates")
        tpl_items = r2.json().get("items", [])
        has_catalog_in_personal = any(t["id"] == entry_id for t in tpl_items)
        has_own_personal = any(t["id"] == seed["a_personal_template_id"] for t in tpl_items)
        check(
            "8. kişisel şablon katalogda YOK + katalog kişisel listede YOK",
            n_cat == 0 and not has_catalog_in_personal and has_own_personal,
            f"n_cat={n_cat} cat_in_personal={has_catalog_in_personal}",
        )

        # ===== 9. POST /books katalog kaydıyla → bölüm + konu + usage =====
        r = coach.post("/api/v2/teacher/library/books", json={
            "name": f"4K TYT Matematik {PFX}",
            "subject_id": seed["builtin_subject_id"],
            "type": "soru_bankasi",
            "publisher": "4K Yayınları",
            "template_id": entry_id,
        })
        bd = r.json().get("data", {}) if r.status_code == 200 else {}
        secs = bd.get("sections", [])
        mapped = [s for s in secs if s.get("topic_id")]
        r2 = admin.get(f"/api/v2/admin/book-catalog/{entry_id}")
        usage = r2.json().get("usage_count") if r2.status_code == 200 else None
        check(
            "9. katalogdan kitap: 3 bölüm + 2 konu eşli + usage_count=1",
            r.status_code == 200 and len(secs) == 3
            and secs[0]["test_count"] == 14 and len(mapped) == 2 and usage == 1,
            f"status={r.status_code} secs={len(secs)} mapped={len(mapped)} usage={usage}",
        )

        # ===== 10. farklı ders seçilirse konu taşınmaz =====
        r = coach.post("/api/v2/teacher/library/books", json={
            "name": f"Farklı Ders Kitabı {PFX}",
            "subject_id": seed["personal_subject_id"],
            "type": "soru_bankasi",
            "template_id": entry_id,
        })
        secs = r.json().get("data", {}).get("sections", []) if r.status_code == 200 else []
        check(
            "10. farklı derste konu kopyalanmaz (test sayısı kopyalanır)",
            r.status_code == 200 and len(secs) == 3
            and all(s.get("topic_id") is None for s in secs)
            and secs[0]["test_count"] == 14,
            f"status={r.status_code} secs={str(secs)[:150]}",
        )

        # ===== 11. başka koçun kişisel şablonu → 404 =====
        r = coach.post("/api/v2/teacher/library/books", json={
            "name": f"Sızıntı Deneme {PFX}",
            "subject_id": seed["builtin_subject_id"],
            "type": "soru_bankasi",
            "template_id": seed["b_personal_template_id"],
        })
        check(
            "11. başka koçun şablonu create'te → 404",
            r.status_code == 404 and r.json()["detail"]["code"] == "template_not_found",
            f"status={r.status_code}",
        )

        # ===== 12. pending entry create'te → 404 =====
        r = coach.post("/api/v2/teacher/library/books", json={
            "name": f"Pending Deneme {PFX}",
            "subject_id": seed["builtin_subject_id"],
            "type": "soru_bankasi",
            "template_id": pending_id,
        })
        check(
            "12. pending kayıt create'te → 404",
            r.status_code == 404,
            f"status={r.status_code}",
        )

        # ===== 13. koç contribute → pending (builtin süzgeci) =====
        r = coach.post("/api/v2/teacher/library/book-catalog/contribute", json={
            "name": f"Karekök LGS Fen {PFX}",
            "publisher": "Karekök",
            "type": "soru_bankasi",
            "subject_id": seed["builtin_subject_id"],
            "target_grade_min": 8,
            "target_grade_max": 8,
            "sections": [
                {"label": "Basınç", "test_count": 6, "topic_id": seed["builtin_topic1_id"]},
                {"label": "Kaldırma Kuvveti", "test_count": 5, "topic_id": seed["personal_topic_id"]},
            ],
        })
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        contrib_id = d.get("entry_id")
        with SessionLocal() as db:
            ce = db.query(BookTemplate).filter(BookTemplate.id == (contrib_id or 0)).first()
            db_ok = (
                ce is not None and ce.teacher_id is None
                and ce.catalog_status == "pending"
                and ce.contributed_by_id == seed["coach_id"]
                and ce.source == "coach_contribution"
            )
            topics = sorted(
                [(s.label, s.topic_id) for s in (ce.sections if ce else [])],
            )
        check(
            "13. contribute → pending + anonim iz + kişisel konu düştü",
            r.status_code == 200 and d.get("status") == "pending" and db_ok
            and ("Basınç", seed["builtin_topic1_id"]) in topics
            and ("Kaldırma Kuvveti", None) in topics,
            f"status={r.status_code} d={d} topics={topics}",
        )

        # ===== 14. contribute mükerrer → already_in_catalog =====
        r = coach.post("/api/v2/teacher/library/book-catalog/contribute", json={
            "name": f"4K TYT Matematik {PFX}",
            "publisher": "4K Yayınları",
            "type": "soru_bankasi",
            "sections": [{"label": "X", "test_count": 3}],
        })
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        check(
            "14. contribute mükerrer → already_in_catalog + entry_id",
            r.status_code == 200 and d.get("status") == "already_in_catalog"
            and d.get("entry_id") == entry_id,
            f"status={r.status_code} d={d}",
        )

        # ===== 15. admin liste + sayımlar + filtre =====
        r = admin.get("/api/v2/admin/book-catalog")
        body = r.json() if r.status_code == 200 else {}
        r2 = admin.get("/api/v2/admin/book-catalog", params={"status": "pending", "q": "karekök"})
        pend_items = r2.json().get("items", []) if r2.status_code == 200 else []
        check(
            "15. admin liste: sayımlar + pending/q filtresi",
            r.status_code == 200 and body.get("verified_count", 0) >= 1
            and body.get("pending_count", 0) >= 2
            and len(pend_items) == 1 and pend_items[0]["id"] == contrib_id,
            f"status={r.status_code} v={body.get('verified_count')} p={body.get('pending_count')} n={len(pend_items)}",
        )

        # ===== 16. admin rozeti =====
        r = admin.get("/api/v2/admin/badges")
        check(
            "16. admin badges.book_catalog_pending ≥ 2",
            r.status_code == 200 and r.json().get("book_catalog_pending", 0) >= 2,
            f"status={r.status_code} badge={r.json().get('book_catalog_pending')}",
        )

        # ===== 17. verify → koç görür =====
        r = admin.post(f"/api/v2/admin/book-catalog/{contrib_id}/verify")
        r2 = coach.get("/api/v2/teacher/library/book-catalog/search", params={"q": "karekök lgs"})
        items = r2.json().get("items", []) if r2.status_code == 200 else []
        check(
            "17. admin verify → koç aramasında görünür",
            r.status_code == 200 and r.json()["data"]["status"] == "verified"
            and any(i["id"] == contrib_id for i in items),
            f"verify={r.status_code} n={len(items)}",
        )

        # ===== 18. admin update: sections replace + geçersiz sayı 422 =====
        r = admin.post(f"/api/v2/admin/book-catalog/{contrib_id}", json={
            "name": f"Karekök LGS Fen Bilimleri {PFX}",
            "sections": [
                {"label": "Basınç", "test_count": 7, "topic_id": seed["builtin_topic1_id"]},
                {"label": "Kaldırma Kuvveti", "test_count": 5},
                {"label": "Elektrik", "test_count": 4},
            ],
        })
        d = r.json().get("data", {}) if r.status_code == 200 else {}
        r2 = admin.post(f"/api/v2/admin/book-catalog/{contrib_id}", json={
            "sections": [{"label": "Bozuk", "test_count": 0}],
        })
        check(
            "18. admin update replace + test_count<1 → 422",
            r.status_code == 200 and d.get("section_count") == 3
            and d.get("total_tests") == 16
            and r2.status_code == 422
            and r2.json()["detail"]["code"] == "invalid_test_count",
            f"u={r.status_code} d={str(d)[:120]} bad={r2.status_code}",
        )

        # ===== 19. hide → koçtan kaybolur =====
        r = admin.post(f"/api/v2/admin/book-catalog/{entry_id}/hide")
        r2 = coach.get("/api/v2/teacher/library/book-catalog/search", params={"q": "4k tyt"})
        r3 = coach.get(f"/api/v2/teacher/library/book-catalog/{entry_id}")
        check(
            "19. hide → arama boş + koç detay 404",
            r.status_code == 200 and len(r2.json().get("items", [])) == 0
            and r3.status_code == 404,
            f"hide={r.status_code} n={len(r2.json().get('items', []))} det={r3.status_code}",
        )

        # ===== 20. delete: kullanılmış 409 · kullanılmamış 200 =====
        r = admin.post(f"/api/v2/admin/book-catalog/{entry_id}/delete")
        r2 = admin.post(f"/api/v2/admin/book-catalog/{pending_id}/delete")
        check(
            "20. delete kullanılmış=409 entry_in_use · kullanılmamış=200",
            r.status_code == 409 and r.json()["detail"]["code"] == "entry_in_use"
            and r2.status_code == 200,
            f"used={r.status_code} unused={r2.status_code}",
        )

        # ===== 21. koç okuma ucu (monkeypatch) + 0 kredi ölçüm =====
        abs_svc.read_structure = lambda files: {  # type: ignore[assignment]
            "book_title": "Mock Kitap", "publisher": "Mock", "subject_hint": None,
            "grade_hint": 8,
            "sections": [
                {"label": "Ünite 1", "test_count": 10, "suspect": False},
                {"label": "Ünite 2", "test_count": None, "suspect": True},
            ],
            "warnings": ["1 bölümde test sayısı içindekilerde yazmıyor — elle doldurun."],
            "read_count": 2,
        }
        r = coach.post(
            "/api/v2/teacher/library/book-structure/read",
            files=[("files", ("ic.jpg", b"fakejpeg", "image/jpeg"))],
        )
        body = r.json() if r.status_code == 200 else {}
        with SessionLocal() as db:
            ev = (
                db.query(UsageEvent)
                .filter(
                    UsageEvent.actor_user_id == seed["coach_id"],
                    UsageEvent.kind == UsageKind.AI_BOOK_READ,
                )
                .all()
            )
            acc_used = sum(
                a.used_credits or 0
                for a in db.query(CreditAccount).filter(CreditAccount.owner_id == seed["coach_id"]).all()
            )
        check(
            "21. koç okuma → 200 + reads_left=29 + 0 kredi ölçüm",
            r.status_code == 200 and len(body.get("sections", [])) == 2
            and body.get("reads_left_today") == 29
            and body["sections"][1]["test_count"] is None
            and len(ev) == 1 and ev[0].credits == 0 and acc_used == 0,
            f"status={r.status_code} left={body.get('reads_left_today')} ev={len(ev)} used={acc_used}",
        )

        # ===== 22. dosya kapıları =====
        r = coach.post("/api/v2/teacher/library/book-structure/read", files=[])
        r2 = coach.post(
            "/api/v2/teacher/library/book-structure/read",
            files=[("files", ("a.gif", b"gif", "image/gif"))],
        )
        check(
            "22. dosya kapıları: boş=422 no_files · gif=422 invalid_media_type",
            r.status_code == 422 and r.json()["detail"]["code"] == "no_files"
            and r2.status_code == 422
            and r2.json()["detail"]["code"] == "invalid_media_type",
            f"empty={r.status_code} gif={r2.status_code}",
        )

        # ===== 23. not_a_toc → 422 (tavana sayılır) =====
        def _raise_toc(files):
            raise abs_svc.NotATocError("İçindekiler değil.")

        abs_svc.read_structure = _raise_toc  # type: ignore[assignment]
        r = coach.post(
            "/api/v2/teacher/library/book-structure/read",
            files=[("files", ("kapak.jpg", b"fake", "image/jpeg"))],
        )
        check(
            "23. not_a_toc → 422 + tavana sayıldı",
            r.status_code == 422 and r.json()["detail"]["code"] == "not_a_toc",
            f"status={r.status_code}",
        )

        # ===== 24. günlük tavan → 429 =====
        with SessionLocal() as db:
            u = db.query(User).filter(User.id == seed["coach_id"]).first()
            current = abs_svc.book_read_count_today(db, seed["coach_id"])
            for _ in range(max(0, abs_svc.AI_BOOK_READ_DAILY_LIMIT - current)):
                abs_svc.record_book_read(db, u, mode="toc", section_count=1)
            db.commit()
        r = coach.post(
            "/api/v2/teacher/library/book-structure/read",
            files=[("files", ("ic.jpg", b"fake", "image/jpeg"))],
        )
        check(
            "24. günlük tavan → 429 daily_read_limit",
            r.status_code == 429 and r.json()["detail"]["code"] == "daily_read_limit",
            f"status={r.status_code}",
        )

        # ===== 25. identify-cover → katalog eşleşmesi (koç B — tavanı dolmadı) =====
        abs_svc.identify_cover = lambda img, mt: {  # type: ignore[assignment]
            "book_title": f"Karekök LGS Fen Bilimleri {PFX}", "publisher": "Karekök",
            "subject_hint": "Fen Bilimleri", "grade_hint": 8, "exam_hint": "LGS",
        }
        coach_b = TestClient(app)
        _login(coach_b, COACH_B_EMAIL)
        r = coach_b.post(
            "/api/v2/teacher/library/book-structure/identify-cover",
            files=[("file", ("kapak.jpg", b"fake", "image/jpeg"))],
        )
        body = r.json() if r.status_code == 200 else {}
        check(
            "25. kapak tanıma → kimlik + katalog eşleşmesi",
            r.status_code == 200
            and any(m["id"] == contrib_id for m in body.get("catalog_matches", [])),
            f"status={r.status_code} matches={len(body.get('catalog_matches', []))}",
        )

        # ===== 26. admin okuma ucu tavansız + koç admin ucunda 403 =====
        abs_svc.read_structure = lambda files: {  # type: ignore[assignment]
            "book_title": None, "publisher": None, "subject_hint": None, "grade_hint": None,
            "sections": [
                {"label": "A", "test_count": 3, "suspect": False},
                {"label": "B", "test_count": 4, "suspect": False},
            ],
            "warnings": [], "read_count": 2,
        }
        r = admin.post(
            "/api/v2/admin/book-catalog/read",
            files=[("files", ("ornek.pdf", b"%PDF-fake", "application/pdf"))],
        )
        r2 = coach.get("/api/v2/admin/book-catalog")
        check(
            "26. admin read: 200 + tavansız · koç admin ucunda 403",
            r.status_code == 200 and r.json().get("reads_left_today") is None
            and r2.status_code == 403,
            f"admin={r.status_code} koc={r2.status_code}",
        )

        # ===== 26b. etiket-bazlı toplu bölüm (fotoğraf akışının 'Uygula'sı) =====
        r = coach_b.post("/api/v2/teacher/library/books", json={
            "name": f"Bulk Test Kitabı {PFX}",
            "subject_id": seed["builtin_subject_id"],
            "type": "soru_bankasi",
        })
        bulk_book_id = r.json()["data"]["id"] if r.status_code == 200 else None
        r2 = coach_b.post(
            f"/api/v2/teacher/library/books/{bulk_book_id}/sections/bulk",
            json={"items": [
                {"label": "Ünite 1", "test_count": 12},
                {"label": "Ünite 2", "test_count": 9},
                {"label": "Ünite 1", "test_count": 5},   # mükerrer etiket atlanır
            ]},
        )
        d2 = r2.json().get("data", {}) if r2.status_code == 200 else {}
        r3 = coach_b.post(
            f"/api/v2/teacher/library/books/{bulk_book_id}/sections/bulk",
            json={"items": [{"label": "  ", "test_count": 0}]},
        )
        check(
            "26b. sections/bulk: 2 eklendi + 1 mükerrer atlandı + boş 422",
            r2.status_code == 200 and d2.get("added_count") == 2
            and d2.get("skipped_existing_count") == 1
            and r3.status_code == 422 and r3.json()["detail"]["code"] == "no_sections",
            f"create={r.status_code} bulk={r2.status_code} d={d2} bad={r3.status_code}",
        )

        # ===== 27. audit izi =====
        with SessionLocal() as db:
            n_audit = (
                db.query(AuditLog)
                .filter(
                    AuditLog.actor_id == seed["admin_id"],
                    AuditLog.action == AuditAction.BOOK_CATALOG_UPDATE,
                )
                .count()
            )
        check(
            "27. BOOK_CATALOG_UPDATE audit kayıtları (create/verify/update/hide/delete)",
            n_audit >= 6,
            f"n={n_audit}",
        )

    finally:
        abs_svc.read_structure = orig_read  # type: ignore[assignment]
        abs_svc.identify_cover = orig_cover  # type: ignore[assignment]
        _cleanup(seed)

    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
