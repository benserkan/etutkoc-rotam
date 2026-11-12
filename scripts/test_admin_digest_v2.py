"""Kurum yöneticisi haftalık özeti — sürüm 2 (2026-11-12).

  1. Hafta: Pazartesi gönderimi → geçen Pazartesi–Pazar (eskiden Salı–Pazartesi)
  2. Uyum sayısı panel servisi ile bağımsız hesap birebir; koç satırları = kurum toplamı
  3. Programsız: koç satırları kurum toplamıyla aynı kuralla (3 günlük süre)
  4. Düzeltme yolu: panel servisi yanlış sayı verirse özet bağımsız hesabı kullanır,
     kontrol "fixed" olur ve skor düşer — bölüm ATILMAZ
  5. E-posta kurum markalı (platform listesinde değil), emoji yok, konu satırı kurum adlı
  6. Arşiv: liste skoru taşır; HTML ucu sürüm 2'de 200, sürüm 1 kayıtta 404; başka kurum 404
  7. Gönderim payload'ı kaydeder; aynı hafta ikinci kez gönderilmez
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
from datetime import date, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AdminWeeklyDigest, Institution, Task, TaskBookItem, User, UserRole  # noqa: E402
from app.models.book import Book, BookSection, BookType  # noqa: E402
from app.services import admin_digest, email_service  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"dg2_{secrets.token_hex(3)}"
PW = "Test-Pass-1234!"
passed, failed = 0, []
made: dict[str, list[int]] = {"inst": [], "users": [], "digests": []}

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def seed(db):
    inst = Institution(name=f"{PFX} Akademi", slug=f"{PFX}-akademi", plan="etut_standart", is_active=True)
    db.add(inst)
    db.flush()
    made["inst"].append(inst.id)
    coach = User(email=f"{PFX}-koc@test.invalid", password_hash=hash_password(PW), full_name="Koç Bir",
                 role=UserRole.TEACHER, is_active=True, institution_id=inst.id, must_change_password=False)
    admin = User(email=f"{PFX}-yon@test.invalid", password_hash=hash_password(PW), full_name="Yönetici",
                 role=UserRole.INSTITUTION_ADMIN, is_active=True, institution_id=inst.id,
                 must_change_password=False)
    db.add_all([coach, admin])
    db.flush()
    made["users"] += [coach.id, admin.id]
    book = Book(teacher_id=coach.id, name=f"{PFX} SB", type=BookType.SORU_BANKASI, subject_id=None)
    try:
        from app.models import Subject
        sub = db.query(Subject).first()
        book.subject_id = sub.id
    except Exception:
        pass
    db.add(book)
    db.flush()
    sec = BookSection(book_id=book.id, label="Bölüm 1", order=1, test_count=50)
    db.add(sec)
    db.flush()
    ws, we = admin_digest.report_week(date.today())
    studs = []
    for i in range(3):
        st = User(email=f"{PFX}-s{i}@test.invalid", password_hash=hash_password(PW), full_name=f"Öğr {i}",
                  role=UserRole.STUDENT, is_active=True, institution_id=inst.id, teacher_id=coach.id,
                  grade_level=8, must_change_password=False)
        st.created_at = __import__("datetime").datetime(2026, 1, 1)
        db.add(st)
        db.flush()
        made["users"].append(st.id)
        studs.append(st)
    # öğr0: 4/5 test, öğr1: 1/5 test (2 doğru 1 yanlış), öğr2: programsız
    for st, (p, c, ok, no) in zip(studs[:2], [(5, 4, None, None), (5, 1, 2, 1)]):
        t = Task(student_id=st.id, date=ws + timedelta(days=2), title="Test", is_draft=False)
        db.add(t)
        db.flush()
        db.add(TaskBookItem(task_id=t.id, book_id=book.id, book_section_id=sec.id, planned_count=p,
                            completed_count=c, correct_count=ok, wrong_count=no))
    db.commit()
    return inst, admin, studs, (ws, we)


def main():
    get_login_limiter().reset()
    with SessionLocal() as db:
        inst, admin, studs, (ws, we) = seed(db)

        print("— 1. Hafta")
        monday = date(2026, 11, 9)
        rws, rwe = admin_digest.report_week(monday)
        check("Pazartesi → geçen Pzt–Paz", (rws, rwe) == (date(2026, 11, 2), date(2026, 11, 8)), (rws, rwe))
        check("Perşembe → yine son tamamlanmış hafta", admin_digest.report_week(date(2026, 11, 12))
              == (date(2026, 11, 2), date(2026, 11, 8)))
        check("Pazar günü → bir önceki hafta (o hafta bitmedi)", admin_digest.report_week(date(2026, 11, 8))
              == (date(2026, 10, 26), date(2026, 11, 1)))

        print("— 2-3. Sayılar")
        p = admin_digest.build_weekly_digest_payload(db, institution=inst, week_end=we)
        k = p["kpis"]
        check("uyum 5/10 test = %50", (k["planned"], k["completed"], k["rate"]) == (10, 5, 50), k)
        check("doğru oranı yalnız sonucu girilen testten (2/3)", k["accuracy"] == 67, k["accuracy"])
        check("programsız 1 öğrenci", k["empty"] == 1, k["empty"])
        c = p["coaches"][0]
        check("koç satırı kurum toplamıyla aynı", (c["rate"], c["empty"], c["students"]) == (50, 1, 3), c)
        rel = p["reliability"]
        check("tutarlılık kontrollerinin hepsi 'ok'", all(x["status"] == "ok" for x in rel["checks"]),
              [(x["key"], x["status"]) for x in rel["checks"]])
        check("veri kalitesi: D/Y girişi ölçülmedi (10'dan az test)",
              next(x for x in rel["components"] if x["key"] == "results")["score"] is None)
        check("hafta etiketi Türkçe", p["week_label"].endswith(f"{we.year}") and "–" in p["week_label"], p["week_label"])
        check("sürüm 1 alanları korunuyor (arşiv uyumu)",
              {"totals", "completion", "at_risk", "highlight", "grade_cohorts"} <= set(p))

        print("— 4. Düzeltme yolu")
        import app.services.institution_compliance as ic
        real = ic.compute_compliance

        def broken(*a, **kw):
            out = real(*a, **kw)
            out["summary"]["planned"] += 7
            out["summary"]["rate"] = 99
            return out
        ic.compute_compliance = broken
        try:
            p2 = admin_digest.build_weekly_digest_payload(db, institution=inst, week_end=we)
        finally:
            ic.compute_compliance = real
        chk = {x["key"]: x for x in p2["reliability"]["checks"]}
        check("yanlış panel sayısı → 'fixed', bölüm ATILMADI", chk["compliance"]["status"] == "fixed"
              and p2["kpis"]["rate"] == 50, (chk["compliance"], p2["kpis"]["rate"]))
        check("düzeltme skoru düşürür", p2["reliability"]["consistency"] < rel["consistency"],
              (p2["reliability"]["consistency"], rel["consistency"]))
        check("düzeltilen sayı skorla birlikte kayıtta", p2["reliability"]["fixed_count"] >= 1)

        print("— 5. E-posta")
        check("kurum özeti platform listesinde DEĞİL (marka uygulanır)",
              "admin_weekly_summary" not in email_service.PLATFORM_TEMPLATES)
        subj, html = admin_digest.render_digest_html(db, institution=inst, payload=p)
        check("konu satırı kurum adıyla", subj.startswith(inst.name), subj)
        check("kurum adına gönderildi notu", f"{inst.name} adına gönderildi" in html)
        check("ETÜTKOÇ başlığı yok (kurum kimliği önde)", "Çalışma Takip Sistemi" not in html)
        check("emoji yok", not EMOJI.search(html), EMOJI.findall(html)[:5])
        check("güvenilirlik skoru mailde yok (yalnız arşiv ekranında)", "Veri güvenilirliği" not in html)
        nar = p["narrative"]
        check("özet cümleyle başlar", nar["paragraphs"][0].startswith("Kurumunuzdaki öğrencilerin program uyumu"),
              nar["paragraphs"][0])
        check("uyumlu ilerleyen öğrenci adı yazılı (Öğr 0 %80)", "Öğr 0" in nar["good_text"], nar["good_text"])
        check("programsız öğrenci 'neden' değil not olarak", not any("programı" in r for r in nar["reasons"])
              and any("Öğr 2" in t for t in nar["notes"]), (nar["reasons"], nar["notes"]))
        check("şablonda ham 'Karne: 55' kalıbı yok", "Karne:" not in html)

        print("— 6-7. Gönderim + arşiv")
        email_service_send = admin_digest.send_email
        sent_ctx: list[dict] = []
        admin_digest.send_email = lambda to, template, ctx, **kw: (sent_ctx.append(ctx) or True)
        try:
            d = admin_digest.send_admin_weekly_digest(db, institution=inst, today=we + timedelta(days=1))
            again = admin_digest.send_admin_weekly_digest(db, institution=inst, today=we + timedelta(days=1))
        finally:
            admin_digest.send_email = email_service_send
        made["digests"].append(d.id)
        check("gönderim kaydı Pzt–Paz haftası", (d.week_start_date, d.week_end_date) == (ws, we),
              (d.week_start_date, d.week_end_date))
        check("e-posta kurum markasıyla", sent_ctx and sent_ctx[0].get("brand_institution_id") == inst.id)
        check("aynı hafta ikinci kez gönderilmez", again.id == d.id and len(sent_ctx) == 1, len(sent_ctx))
        check("payload sürüm 2 + skor kayıtta", json.loads(d.payload_json).get("reliability", {}).get("score") is not None)
        old = AdminWeeklyDigest(institution_id=inst.id, week_start_date=ws - timedelta(days=7),
                                week_end_date=we - timedelta(days=7), payload_json=json.dumps({"totals": {}}),
                                send_status="sent", recipient_count=1)
        db.add(old)
        db.commit()
        made["digests"].append(old.id)
        did, oid = d.id, old.id

    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}-yon@test.invalid", "password": PW})
    check("yönetici girişi", r.status_code == 200, r.status_code)
    r = c.get("/api/v2/institution/admin-digest")
    items = {i["id"]: i for i in r.json()["items"]} if r.status_code == 200 else {}
    check("liste skor + sürüm taşır", items.get(did, {}).get("reliability_score") is not None
          and items.get(did, {}).get("version") == 2 and items.get(oid, {}).get("reliability_score") is None,
          items.get(did))
    r = c.get(f"/api/v2/institution/admin-digest/{did}/html")
    check("HTML görünümü 200 + kurum adı", r.status_code == 200 and "Akademi" in r.text, r.status_code)
    r = c.get(f"/api/v2/institution/admin-digest/{oid}/html")
    check("eski biçim kayıt → 404", r.status_code == 404, r.status_code)
    r = c.get(f"/api/v2/institution/admin-digest/{did}")
    check("ayrıntı: alıcı listesi satırlara bölünür", r.status_code == 200 and r.json()["recipient_emails"]
          == [f"{PFX}-yon@test.invalid"], r.json().get("recipient_emails") if r.status_code == 200 else r.text)


def cleanup():
    from sqlalchemy import delete as sa_delete
    from app.models import BookSection as BS
    with SessionLocal() as db:
        db.execute(sa_delete(AdminWeeklyDigest).where(AdminWeeklyDigest.id.in_(made["digests"] or [0])))
        tids = [t.id for t in db.query(Task).filter(Task.student_id.in_(made["users"] or [0]))]
        db.execute(sa_delete(TaskBookItem).where(TaskBookItem.task_id.in_(tids or [0])))
        db.execute(sa_delete(Task).where(Task.id.in_(tids or [0])))
        bids = [b.id for b in db.query(Book).filter(Book.teacher_id.in_(made["users"] or [0]))]
        db.execute(sa_delete(BS).where(BS.book_id.in_(bids or [0])))
        db.execute(sa_delete(Book).where(Book.id.in_(bids or [0])))
        db.query(User).filter(User.id.in_(made["users"] or [0])).delete(synchronize_session=False)
        db.query(Institution).filter(Institution.id.in_(made["inst"] or [0])).delete(synchronize_session=False)
        db.commit()


if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup()
    print(f"\n{passed} passed · {len(failed)} failed")
    sys.exit(1 if failed else 0)
