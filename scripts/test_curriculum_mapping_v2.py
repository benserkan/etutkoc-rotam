"""Kaynak-konu NORMALİZASYON katmanı — smoke (2026-09-08).

KOÇ: "TYT Matematik'te iki kaynak var; birinde 'Bölme Bölünebilme', diğerinde
'Bölme Bölünebilme Kuralları' — panel yalnız adı birebir uyanı sayıyor."

Katman (curriculum_mapping): exact → öğrenilmiş sözlük → anlamsız kuyruk →
kapsama (yalnız anlamsız artık, tek aday). Belirsiz ASLA otomatik bağlanmaz.

Senaryolar:
   1. kuyruk: "Bölme ve Bölünebilme Kuralları" → Bölme ve Bölünebilme [tail]
   2. öğrenilmiş: başka koçun kitabında "Sayma, Permütasyon" → Permütasyon
      uygulanmış → yeni kitapta aynı etiket [learned]
   3. öğrenilmiş + katalog: doğrulanmış katalogda "Yüzde Kar Zarar Problemleri"
      → Yüzde Problemleri [learned]
   4. KAPSAMA GUARD: "Asal Çarpanlara Ayırma ve Bölen Sayısı" → artan sözcükler
      anlamlı → BAĞLANMAZ ("Çarpanlara Ayırma"ya yanlış gitmesin)
   5. ÇELİŞKİ GUARD: iki kitapta "Karma" farklı konulara gitmiş → sözlükten
      DIŞLANIR → bağlanmaz
   6. TÜMEVARIM / ÖSYM gibi kümülatif etiketler bağlanmaz
   7. kuyruk + roma rakamı: "Fonksiyonlar - II" → Fonksiyonlar
   8. auto_apply_sections yalnız BOŞ olanlara yazar (dolu dokunulmaz)
   9. suggest_for_book aynı katmanı kullanır (source=auto, AI'sız)
  10. HTTP: sections/bulk → auto_mapped_count + topic_id set
  11. HTTP: tek bölüm ekle → topic_id otomatik
  12. backfill DRY-RUN yazmaz; --apply yazar; ikinci koşu 0 (idempotent)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Book,
    BookSection,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.models.book import (
    CATALOG_STATUS_VERIFIED,
    BookTemplate,
    BookTemplateSection,
    BookType,
)
from app.services import curriculum_mapping as cm
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"norm_{secrets.token_hex(3)}"
PWD = "Norm!234567"

passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def main() -> int:
    print(f"\n=== kaynak-konu normalizasyonu smoke — {PFX} ===\n")
    get_login_limiter().reset()
    ids: dict = {}
    try:
        with SessionLocal() as db:
            coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                         full_name="Norm Koç", role=UserRole.TEACHER, is_active=True)
            other = User(email=f"{PFX}_o@test.invalid", password_hash=hash_password(PWD),
                         full_name="Öteki Koç", role=UserRole.TEACHER, is_active=True)
            db.add_all([coach, other])
            db.flush()
            subj = Subject(name=f"{PFX} TYT Matematik", order=1, is_builtin=True, teacher_id=None)
            db.add(subj)
            db.flush()
            names = ["Bölme ve Bölünebilme", "Çarpanlara Ayırma", "Asal Sayılar",
                     "Permütasyon", "Kombinasyon", "Yüzde Problemleri",
                     "Kar - Zarar Problemleri", "Fonksiyonlar"]
            topics = {}
            for i, n in enumerate(names):
                t = Topic(subject_id=subj.id, name=n, order=i + 1, is_builtin=True, teacher_id=None)
                db.add(t)
                topics[n] = t
            db.flush()

            # Korpus 1 — başka koçun kitabı (uygulanmış eşleştirmeler)
            corp = Book(name=f"{PFX} Korpus SB", teacher_id=other.id, subject_id=subj.id,
                        type=BookType.SORU_BANKASI)
            db.add(corp)
            db.flush()
            db.add_all([
                BookSection(book_id=corp.id, label="Sayma, Permütasyon", order=0,
                            test_count=5, topic_id=topics["Permütasyon"].id),
                BookSection(book_id=corp.id, label="Karma", order=1, test_count=5,
                            topic_id=topics["Permütasyon"].id),
            ])
            corp2 = Book(name=f"{PFX} Korpus2 SB", teacher_id=other.id, subject_id=subj.id,
                         type=BookType.SORU_BANKASI)
            db.add(corp2)
            db.flush()
            db.add(BookSection(book_id=corp2.id, label="Karma", order=0, test_count=5,
                               topic_id=topics["Kombinasyon"].id))  # ÇELİŞKİ
            # Korpus 2 — doğrulanmış katalog kaydı
            tpl = BookTemplate(teacher_id=None, name=f"{PFX} Katalog", type=BookType.SORU_BANKASI,
                               subject_id=subj.id, is_verified=True,
                               catalog_status=CATALOG_STATUS_VERIFIED)
            db.add(tpl)
            db.flush()
            db.add(BookTemplateSection(template_id=tpl.id, label="Yüzde Kar Zarar Problemleri",
                                       default_test_count=4, order=0,
                                       topic_id=topics["Yüzde Problemleri"].id))

            # Hedef kitap (koçun) — hepsi boş
            book = Book(name=f"{PFX} 3D SB", teacher_id=coach.id, subject_id=subj.id,
                        type=BookType.SORU_BANKASI)
            db.add(book)
            db.flush()
            labels = [
                "Bölme ve Bölünebilme Kuralları",          # tail
                "Sayma, Permütasyon",                      # learned (koç korpusu)
                "Yüzde Kar Zarar Problemleri",             # learned (katalog)
                "Asal Çarpanlara Ayırma ve Bölen Sayısı",  # GUARD → bağlanmaz
                "Karma",                                   # çelişki → bağlanmaz
                "TÜMEVARIM - I",                           # bağlanmaz
                "Fonksiyonlar - II",                       # tail (roma)
                "Kombinasyon",                             # exact — önceden DOLU (dokunulmaz)
            ]
            secs = []
            for i, lab in enumerate(labels):
                s = BookSection(book_id=book.id, label=lab, order=i, test_count=3,
                                topic_id=(topics["Kombinasyon"].id if lab == "Kombinasyon" else None))
                db.add(s)
                secs.append(s)
            db.commit()
            ids = {
                "coach": coach.id, "other": other.id, "subject": subj.id,
                "book": book.id, "corp": corp.id, "corp2": corp2.id, "tpl": tpl.id,
                "topics": {k: v.id for k, v in topics.items()},
                "secs": {s.label: s.id for s in secs},
            }

            # ---- saf çözümleyici
            cands = cm.candidate_topics_for_book(db, book)
            index = cm._topics_by_norm(cands)
            learned = cm.learned_label_map(db, subj.id, exclude_book_id=book.id)

            def res(label):
                m = cm.resolve_label(label, index, learned)
                return (m.topic.name, m.source) if m else None

            check("1. kuyruk: 'Bölme ve Bölünebilme Kuralları' → Bölme ve Bölünebilme [tail]",
                  res("Bölme ve Bölünebilme Kuralları") == ("Bölme ve Bölünebilme", "tail"),
                  str(res("Bölme ve Bölünebilme Kuralları")))
            check("2. öğrenilmiş (koç korpusu): 'Sayma, Permütasyon' → Permütasyon",
                  res("Sayma, Permütasyon") == ("Permütasyon", "learned"), str(res("Sayma, Permütasyon")))
            check("3. öğrenilmiş (doğrulanmış katalog): 'Yüzde Kar Zarar Problemleri' → Yüzde",
                  res("Yüzde Kar Zarar Problemleri") == ("Yüzde Problemleri", "learned"),
                  str(res("Yüzde Kar Zarar Problemleri")))
            check("4. KAPSAMA GUARD: 'Asal Çarpanlara Ayırma ve Bölen Sayısı' BAĞLANMAZ",
                  res("Asal Çarpanlara Ayırma ve Bölen Sayısı") is None,
                  str(res("Asal Çarpanlara Ayırma ve Bölen Sayısı")))
            check("5. ÇELİŞKİ GUARD: 'Karma' iki konuya gitmiş → sözlük dışı → bağlanmaz",
                  res("Karma") is None and "karma" not in learned, str((res("Karma"), learned.get("karma"))))
            check("6. kümülatif etiket 'TÜMEVARIM - I' bağlanmaz", res("TÜMEVARIM - I") is None)
            check("7. kuyruk + roma: 'Fonksiyonlar - II' → Fonksiyonlar [tail]",
                  res("Fonksiyonlar - II") == ("Fonksiyonlar", "tail"), str(res("Fonksiyonlar - II")))

            # ---- 8. auto_apply yalnız boşlara yazar
            applied = cm.auto_apply_sections(db, book)
            db.commit()
            db.expire_all()
            got = {s.label: s.topic_id for s in db.query(BookSection).filter(BookSection.book_id == book.id)}
            T = ids["topics"]
            check("8. auto_apply: 4 bağ kuruldu, dolu (Kombinasyon) dokunulmadı, guard'lar boş",
                  len(applied) == 4
                  and got["Bölme ve Bölünebilme Kuralları"] == T["Bölme ve Bölünebilme"]
                  and got["Sayma, Permütasyon"] == T["Permütasyon"]
                  and got["Yüzde Kar Zarar Problemleri"] == T["Yüzde Problemleri"]
                  and got["Fonksiyonlar - II"] == T["Fonksiyonlar"]
                  and got["Kombinasyon"] == T["Kombinasyon"]
                  and got["Asal Çarpanlara Ayırma ve Bölen Sayısı"] is None
                  and got["Karma"] is None and got["TÜMEVARIM - I"] is None,
                  f"applied={len(applied)} got={got}")

            # ---- 9. suggest_for_book aynı katman (yeni boş bölümle)
            s9 = BookSection(book_id=book.id, label="Kar Zarar Problemleri Testleri", order=20, test_count=2)
            db.add(s9)
            db.commit()
            db.refresh(book)
            rows = cm.suggest_for_book(db, book, cands, use_ai=False)
            r9 = next(r for r in rows if r["section_id"] == s9.id)
            check("9. suggest_for_book: 'Kar Zarar Problemleri Testleri' → Kar - Zarar [auto, AI'sız]",
                  r9["source"] == "auto" and r9["suggested_topic_id"] == T["Kar - Zarar Problemleri"],
                  str(r9))
            ids["s9"] = s9.id

        # ---- HTTP
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_t@test.invalid", "password": PWD})
        assert r.status_code == 200, r.text
        r10 = c.post(f"/api/v2/teacher/library/books/{ids['book']}/sections/bulk",
                     json={"items": [
                         {"label": "Asal Sayılar Özellikleri", "test_count": 3},   # tail
                         {"label": "Bire Bir ÖSYM", "test_count": 2},              # kalır
                     ]})
        d10 = r10.json().get("data", {}) if r10.status_code == 200 else {}
        with SessionLocal() as db:
            s_asal = db.query(BookSection).filter(BookSection.book_id == ids["book"],
                                                  BookSection.label == "Asal Sayılar Özellikleri").first()
            s_osym = db.query(BookSection).filter(BookSection.book_id == ids["book"],
                                                  BookSection.label == "Bire Bir ÖSYM").first()
        check("10. HTTP sections/bulk: auto_mapped_count=1, 'Asal Sayılar Özellikleri' bağlı, ÖSYM boş",
              r10.status_code == 200 and d10.get("added_count") == 2 and d10.get("auto_mapped_count") == 1
              and s_asal is not None and s_asal.topic_id == ids["topics"]["Asal Sayılar"]
              and s_osym is not None and s_osym.topic_id is None,
              f"{r10.status_code} {d10}")

        r11 = c.post(f"/api/v2/teacher/library/books/{ids['book']}/sections",
                     json={"label": "Bölünebilme Kuralları Testleri", "test_count": 4})
        d11 = r11.json().get("data", {}) if r11.status_code == 200 else {}
        # "bolunebilme" ⊂ "bolme bolunebilme"? HAYIR — konu sözcükleri etikette
        # tamamen geçmiyor ('bolme' yok) → bağlanmaz; etiket dürüstçe boş kalır.
        check("11. HTTP tek bölüm: eksik sözcüklü etiket BAĞLANMAZ (yanlış bağ yok)",
              r11.status_code == 200 and d11.get("topic_id") is None, f"{r11.status_code} {d11}")
        r11b = c.post(f"/api/v2/teacher/library/books/{ids['book']}/sections",
                      json={"label": "Bölme ve Bölünebilme Testleri", "test_count": 4})
        d11b = r11b.json().get("data", {}) if r11b.status_code == 200 else {}
        check("11b. HTTP tek bölüm: 'Bölme ve Bölünebilme Testleri' → otomatik bağlı",
              r11b.status_code == 200 and d11b.get("topic_id") == ids["topics"]["Bölme ve Bölünebilme"],
              f"{r11b.status_code} {d11b}")

        # ---- 12. backfill dry-run / apply / idempotent
        from scripts import backfill_section_topics as bf
        with SessionLocal() as db:
            s12 = BookSection(book_id=ids["book"], label="Kombinasyon Kuralları", order=30, test_count=2)
            db.add(s12)
            db.commit()
            sid12 = s12.id
        with SessionLocal() as db:
            dry = bf.run(db, apply=False, book_id=ids["book"], verbose=False)
        with SessionLocal() as db:
            after_dry = db.get(BookSection, sid12).topic_id
        with SessionLocal() as db:
            ap = bf.run(db, apply=True, book_id=ids["book"], verbose=False)
        with SessionLocal() as db:
            after_apply = db.get(BookSection, sid12).topic_id
            again = bf.run(db, apply=True, book_id=ids["book"], verbose=False)
        check("12. backfill: dry-run yazmaz · --apply yazar · ikinci koşu 0 (idempotent)",
              dry["applied"] >= 1 and after_dry is None
              and ap["applied"] >= 1 and after_apply == ids["topics"]["Kombinasyon"]
              and again["applied"] == 0,
              f"dry={dry['applied']} after_dry={after_dry} apply={ap['applied']} after={after_apply} again={again['applied']}")
    finally:
        if ids:
            with SessionLocal() as db:
                bids = [ids["book"], ids["corp"], ids["corp2"]]
                db.execute(sa_delete(BookSection).where(BookSection.book_id.in_(bids)))
                db.execute(sa_delete(Book).where(Book.id.in_(bids)))
                db.execute(sa_delete(BookTemplateSection).where(BookTemplateSection.template_id == ids["tpl"]))
                db.execute(sa_delete(BookTemplate).where(BookTemplate.id == ids["tpl"]))
                db.execute(sa_delete(Topic).where(Topic.subject_id == ids["subject"]))
                db.execute(sa_delete(Subject).where(Subject.id == ids["subject"]))
                db.execute(sa_delete(User).where(User.id.in_([ids["coach"], ids["other"]])))
                db.commit()

    print(f"\n=== {passed}/{passed + len(failed)} geçti ===")
    for f in failed:
        print("  FAIL:", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
