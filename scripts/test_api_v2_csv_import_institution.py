"""CSV toplu öğrenci kaydı — kurum genişlemesi (2026-09-27).

Kurum anlaşması (~25 öğrenci): CSV artık öğrenci telefonu, şube, veli bilgisi
ve akademik yıl taşır. Doğrular:
  1. Türkçe başlıklar tanınır (ad soyad, e-posta, sınıf, alan, şube, telefon,
     veli adı, veli e-posta, veli telefonu, yakınlık)
  2. Telefon E.164'e normalize edilir; tanınmayan telefon UYARI (satır geçerli)
  3. Veli e-postası öğrenciyle aynı → hata; veli adı var e-posta yok → uyarı
  4. Commit: phone + class_group + academic_year_id öğrenciye yazılır
  5. Veli daveti açılır (ad/telefon dolu) + e-posta gönderilir; davet bilgisi
     (public) ön doldurma alanlarını döner
  6. Veli e-postası başka rolde → skipped_other_role (öğrenci yine oluşur)
  7. Başka koçun akademik yılı → 422 invalid_academic_year
  8. Solo paket kotası CSV'de de uygulanır (fazlası → hiç oluşturulmaz)
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
from app.models import AcademicYear, AuditLog, NotificationLog, ParentInvitation, User, UserRole
from app.services import email_service
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"csvk_{secrets.token_hex(3)}"
PWD = "TestPass123!@xyz"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {detail}")


def seed() -> dict:
    with SessionLocal() as db:
        coach = User(email=f"{PFX}_t@test.invalid", password_hash=hash_password(PWD),
                     full_name="CSV Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", subscription_status="active")
        other = User(email=f"{PFX}_t2@test.invalid", password_hash=hash_password(PWD),
                     full_name="Diğer Koç", role=UserRole.TEACHER, is_active=True)
        db.add_all([coach, other])
        db.flush()
        yr = AcademicYear(teacher_id=coach.id, name=f"2026-2027 {PFX}", start_year=2026)
        oyr = AcademicYear(teacher_id=other.id, name=f"2026-2027 {PFX}", start_year=2026)
        db.add_all([yr, oyr])
        db.commit()
        return {"coach": coach.id, "other": other.id, "email": coach.email,
                "other_email": other.email, "year": yr.id, "oyear": oyr.id}


def cleanup(d: dict) -> None:
    with SessionLocal() as db:
        sids = [u.id for u in db.query(User).filter(User.email.like(f"%.{PFX}@test.invalid"))]
        db.execute(sa_delete(ParentInvitation).where(ParentInvitation.student_id.in_(sids or [0])))
        db.execute(sa_delete(NotificationLog).where(NotificationLog.student_id.in_(sids or [0])))
        db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_([d["coach"], d["other"]])))
        db.execute(sa_delete(User).where(User.id.in_(sids or [0])))
        db.execute(sa_delete(AcademicYear).where(AcademicYear.id.in_([d["year"], d["oyear"]])))
        db.execute(sa_delete(User).where(User.id.in_([d["coach"], d["other"]])))
        db.commit()


def main() -> int:
    print(f"\n=== CSV kurum genişlemesi smoke — {PFX} ===\n")
    get_login_limiter().reset()
    sent: list[str] = []
    orig = email_service.notify_parent_invitation

    def fake_notify(inv, *, teacher, student, relation_label):
        sent.append(inv.invited_email)
        return True

    email_service.notify_parent_invitation = fake_notify
    d = seed()
    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": d["email"], "password": PWD})
        assert r.status_code == 200, r.text

        csv_text = (
            "Ad Soyad;E-posta;Sınıf;Alan;Şube;Telefon;Veli Adı;Veli E-posta;Veli Telefonu;Yakınlık\n"
            f"Ali Kaya;ali.{PFX}@test.invalid;8;;8-A;0532 111 22 33;Ayşe Kaya;veli1.{PFX}@test.invalid;+90 533 444 55 66;anne\n"
            f"Zeynep Ak;zeynep.{PFX}@test.invalid;11;sayisal;11-B;12345;;;;\n"
            f"Can Er;can.{PFX}@test.invalid;10;;10-A;;Mehmet Er;;05341112233;baba\n"
            f"Hatalı;hata.{PFX}@test.invalid;10;;;;;hata.{PFX}@test.invalid;;\n"
            f"Çakışma;cak.{PFX}@test.invalid;10;;10-A;;Koç Veli;{d['other_email']};;\n"
        )
        r = c.post("/api/v2/teacher/csv/import/students/preview", json={"csv_text": csv_text})
        pv = r.json()
        rows = {row["email"] or row["raw"].get("E-posta"): row for row in pv["rows"]}
        a = rows[f"ali.{PFX}@test.invalid"]
        check("1. Türkçe başlıklar + ';' ayırıcı tanındı (5 satır, 4 geçerli)",
              pv["total_rows"] == 5 and pv["valid_count"] == 4, str(pv["valid_count"]))
        check("2. telefon + şube + veli alanları normalize",
              a["phone"] == "905321112233" and a["class_group"] == "8-A"
              and a["parent_phone"] == "905334445566" and a["parent_relation"] == "anne", str(a))
        z = rows[f"zeynep.{PFX}@test.invalid"]
        check("3. tanınmayan telefon uyarı, satır geçerli",
              z["is_valid"] and z["phone"] is None and any("telefon" in w for w in z["warnings"]))
        cn = rows[f"can.{PFX}@test.invalid"]
        check("4. veli e-postası yok → uyarı (davet gitmeyecek)",
              cn["is_valid"] and any("veli e-postası yok" in w for w in cn["warnings"]))
        h = next(row for row in pv["rows"] if row["row_num"] == 4)
        check("5. veli e-postası = öğrenci e-postası → hata", not h["is_valid"], str(h["errors"]))

        r = c.post("/api/v2/teacher/csv/import/students/commit",
                   json={"csv_text": csv_text, "academic_year_id": d["oyear"]})
        check("6. başka koçun akademik yılı → 422", r.status_code == 422
              and r.json()["detail"]["code"] == "invalid_academic_year", r.text[:200])

        r = c.post("/api/v2/teacher/csv/import/students/commit",
                   json={"csv_text": csv_text, "academic_year_id": d["year"]})
        res = r.json()["data"]
        check("7. 4 öğrenci oluştu", res["created_count"] == 4, str(res["created_count"]))
        by = {x["email"]: x for x in res["created"]}
        check("8. veli daveti sayıları (1 gönderildi, 1 başka rol)",
              res["parents_invited"] == 1 and res["parents_failed"] == 1,
              f'{res["parents_invited"]}/{res["parents_failed"]}')
        check("9. başka rolde veli e-postası → skipped_other_role",
              by[f"cak.{PFX}@test.invalid"]["parent_status"] == "skipped_other_role")
        check("10. davet e-postası yalnız geçerli veliye gitti", sent == [f"veli1.{PFX}@test.invalid"], str(sent))
        with SessionLocal() as db:
            u = db.query(User).filter(User.email == f"ali.{PFX}@test.invalid").one()
            check("11. öğrenciye telefon + şube + akademik yıl yazıldı",
                  u.phone == "905321112233" and u.phone_verified_at is None
                  and u.class_group == "8-A" and u.academic_year_id == d["year"]
                  and u.must_change_password)
            inv = db.query(ParentInvitation).filter(ParentInvitation.student_id == u.id).one()
            check("12. davet: ad + telefon + yakınlık kaydedildi",
                  inv.invited_name == "Ayşe Kaya" and inv.invited_phone == "905334445566"
                  and inv.relation.value == "anne" and inv.is_primary)
            token = inv.token
        info = TestClient(app).get(f"/api/v2/parent/invitation/{token}").json()
        check("13. davet bilgisi (public) ön doldurma alanlarını döner",
              info.get("invited_name") == "Ayşe Kaya" and info.get("invited_phone") == "905334445566", str(info))

        # Paket kotası: solo_free (3) koçu 4 satır → hiçbiri oluşmaz
        with SessionLocal() as db:
            o = db.get(User, d["other"])
            o.plan = "solo_free"
            db.commit()
        c2 = TestClient(app)
        c2.post("/api/v2/auth/login", json={"email": d["other_email"], "password": PWD})
        csv2 = "full_name,email,grade_level\n" + "".join(
            f"K{i},k{i}.{PFX}@test.invalid,8\n" for i in range(4))
        r = c2.post("/api/v2/teacher/csv/import/students/commit", json={"csv_text": csv2})
        res2 = r.json()["data"]
        check("14. solo paket sınırı CSV'de de uygulanır",
              res2["created_count"] == 0 and any("Paket sınırı" in e for e in res2["header_errors"]),
              str(res2["header_errors"]))
        r = c.get("/api/v2/teacher/csv/import/students/template")
        check("15. şablonda yeni sütunlar", "class_group" in r.text and "parent_email" in r.text)
    finally:
        email_service.notify_parent_invitation = orig
        cleanup(d)
    total = passed + len(failed)
    print(f"\n=== {passed}/{total} geçti ===")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
