"""Stage 3 — CSV toplu öğrenci içe aktarım kapsamlı smoke test."""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    Institution,
    User,
    UserRole,
)
from app.services.csv_import import bulk_create_students, parse_students_csv
from app.services.security import hash_password


PFX = f"_csv_{secrets.token_hex(3)}"
PWD = "TestPass!234567"

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
    # ============ SEED ============
    print("\n=== SEED ===")
    with SessionLocal() as db:
        pwd_hash = hash_password(PWD)
        now = datetime.now(timezone.utc)

        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            contact_email=f"{PFX}@test.invalid", plan="free", is_active=True,
        )
        db.add(inst); db.flush()
        inst_id = inst.id

        teacher = User(
            email=f"{PFX}_teacher@test.invalid", password_hash=pwd_hash,
            full_name="CSV Teacher", role=UserRole.TEACHER,
            institution_id=inst_id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        db.add(teacher); db.flush()
        teacher_id, teacher_email = teacher.id, teacher.email

        # Önceden kayıtlı bir e-posta — duplicate kontrolü için
        existing = User(
            email=f"{PFX}_existing@test.invalid", password_hash=pwd_hash,
            full_name="Önceden Var", role=UserRole.STUDENT,
            teacher_id=teacher_id, institution_id=inst_id,
            is_active=True, password_changed_at=now,
            must_change_password=False, grade_level=8,
        )
        db.add(existing); db.flush()
        existing_id = existing.id
        db.commit()

    print(f"  inst={inst_id} teacher={teacher_id} existing student={existing_id}")

    # ============ STEP 1: parser unit test ============
    print("\n=== STEP 1: parser ===")
    sample = f"""full_name,email,grade_level,track,is_graduate,graduate_mode
Ali Veli,{PFX}_ali@x.com,8,,,
Ayse Yilmaz,{PFX}_ayse@x.com,11,sayisal,,
Mezun Ogrenci,{PFX}_mezun@x.com,,sozel,evet,dershane
Hatali,bademail,7,,,
,{PFX}_no_name@x.com,8,,,
Eksik Alan,{PFX}_no_track@x.com,11,,,
Cift Email,{PFX}_ali@x.com,9,,,"""

    r = parse_students_csv(sample)
    check("header errors yok", not r.has_fatal_error, str(r.header_errors))
    check("3 valid satır", r.valid_count == 3, f"got {r.valid_count}")
    check("4 invalid satır", r.invalid_count == 4, f"got {r.invalid_count}")

    # Specific error checks
    invalid_errors = [r2.errors for r2 in r.rows if not r2.is_valid]
    flat_errors = [e for sub in invalid_errors for e in sub]
    check("e-posta format hatası tespit", any("e-posta format" in e for e in flat_errors))
    check("ad soyad zorunlu hatası", any("ad soyad" in e for e in flat_errors))
    check("11+ track zorunlu hatası", any("alan zorunlu" in e for e in flat_errors))
    check("mükerrer e-posta hatası", any("mükerrer" in e for e in flat_errors))

    # ============ STEP 2: header alias ============
    print("\n=== STEP 2: header alias ===")
    sample_alias = f"""Ad Soyad,E-posta,sınıf,alan
Ali,{PFX}_alias_ali@x.com,8,
Ayse,{PFX}_alias_ayse@x.com,11,sayisal"""
    r = parse_students_csv(sample_alias)
    check("Türkçe header alias çalışır",
          not r.has_fatal_error and r.valid_count == 2,
          f"errors={r.header_errors}, valid={r.valid_count}")

    # ============ STEP 3: missing required header ============
    print("\n=== STEP 3: eksik zorunlu sütun ===")
    sample_missing = f"""full_name,grade_level
Ali,8
Ayse,11"""
    r = parse_students_csv(sample_missing)
    check("eksik email -> header_errors", r.has_fatal_error)

    # ============ STEP 4: BOM tolerance ============
    print("\n=== STEP 4: UTF-8 BOM tolerance ===")
    bom_sample = "﻿full_name,email\nAli," + PFX + "_bom@x.com"
    r = parse_students_csv(bom_sample)
    check("BOM toleranslı parse", not r.has_fatal_error and r.valid_count == 1,
          f"valid={r.valid_count}")

    # ============ STEP 5: bulk_create_students ============
    print("\n=== STEP 5: bulk_create_students ===")
    sample_create = f"""full_name,email,grade_level,track
CSV Ali,{PFX}_create_ali@x.com,8,
CSV Ayse,{PFX}_create_ayse@x.com,11,sayisal
CSV Mevcut,{PFX}_existing@test.invalid,9,
CSV Hatali,bademail,7,"""
    r = parse_students_csv(sample_create)
    valid_rows = [row for row in r.rows if row.is_valid]
    print(f"  parse: valid={len(valid_rows)}, invalid={r.invalid_count}")

    with SessionLocal() as db:
        tch = db.query(User).filter(User.id == teacher_id).first()
        bulk = bulk_create_students(db, teacher=tch, parsed_rows=r.rows)
        # 2 valid (ali + ayse) + 1 mevcut e-posta atlanmış + 1 invalid atlanmış
        check("created 2 öğrenci", bulk.created_count == 2,
              f"got {bulk.created_count}")
        check("skipped existing 1", len(bulk.skipped_existing_email) == 1)
        check("skipped invalid 1", len(bulk.skipped_invalid) == 1)
        check("created'lar geçici şifreye sahip",
              all(c.temp_password and len(c.temp_password) >= 8 for c in bulk.created))

        # DB'de gerçekten oluşmuşlar mı + institution_id inherit edilmiş mi?
        ali = db.query(User).filter(
            User.email == f"{PFX}_create_ali@x.com"
        ).first()
        check("Ali DB'de var", ali is not None)
        if ali:
            check("Ali institution_id inherit edildi",
                  ali.institution_id == inst_id,
                  f"got {ali.institution_id}")
            check("Ali must_change_password=True", ali.must_change_password)
            check("Ali role=STUDENT", ali.role == UserRole.STUDENT)

    # ============ STEP 6: HTTP route ============
    print("\n=== STEP 6: HTTP routes ===")
    # Reset teacher password to known
    with SessionLocal() as db:
        tch = db.get(User, teacher_id)
        tch.password_hash = hash_password(PWD)
        tch.failed_login_count = 0
        tch.locked_until = None
        tch.must_change_password = False
        db.commit()

    c = TestClient(app)
    r = c.post("/login", data={"email": teacher_email, "password": PWD},
               follow_redirects=False)
    check("teacher login", r.status_code == 303, f"got {r.status_code}")

    r = c.get("/teacher/students/import")
    check("GET /import 200", r.status_code == 200)
    check("CSV form var", "csv_text" in r.text)
    check("Template indirme linki var", "/import/template.csv" in r.text)

    # Template download
    r = c.get("/teacher/students/import/template.csv")
    check("template.csv 200", r.status_code == 200)
    check("template UTF-8 BOM ile başlar",
          r.content.startswith(b"\xef\xbb\xbf"),
          "BOM yok")
    check("template örnek satır içerir",
          b"ali.veli@example.com" in r.content,
          "örnek e-posta yok")

    # Preview
    csv_payload = f"""full_name,email,grade_level,track
HTTP Ali,{PFX}_http_ali@x.com,8,
HTTP Ayse,{PFX}_http_ayse@x.com,11,sayisal
Bad Row,bademail,7,"""
    r = c.post("/teacher/students/import/preview",
               data={"csv_text": csv_payload}, follow_redirects=False)
    check("preview POST 200", r.status_code == 200)
    check("preview valid count görünür",
          "2 eklenecek" in r.text or "2</span>" in r.text,
          "valid count yok")
    check("preview invalid count görünür",
          "1 hatalı" in r.text or "1</span>" in r.text,
          "invalid count yok")
    check("preview 'Önceden Var' rezerve değil",
          "Önceden Var" not in r.text)

    # Confirm
    r = c.post("/teacher/students/import/confirm",
               data={"csv_text": csv_payload}, follow_redirects=False)
    check("confirm POST 200", r.status_code == 200)
    check("results created listede HTTP Ali var",
          "HTTP Ali" in r.text)
    check("temp_password görünür",
          "Geçici Şifre" in r.text or "temp" in r.text.lower())

    # DB check — yeni öğrenciler eklendi mi?
    with SessionLocal() as db:
        new_alis = db.query(User).filter(
            User.email.like(f"{PFX}_http_%@x.com")
        ).all()
        check("HTTP create -> 2 öğrenci DB'de",
              len(new_alis) == 2, f"got {len(new_alis)}")

    # ============ STEP 7: cross-tenant isolation ============
    print("\n=== STEP 7: cross-tenant ===")
    # Başka bir kurum teacher'ı oluşturup farklı institution_id ile test et
    with SessionLocal() as db:
        other_inst = Institution(
            name=f"{PFX}_other", slug=f"{PFX}-other",
            contact_email=f"{PFX}_other@test.invalid", plan="free", is_active=True,
        )
        db.add(other_inst); db.flush()
        other_inst_id = other_inst.id
        other_teacher = User(
            email=f"{PFX}_other_teacher@test.invalid", password_hash=hash_password(PWD),
            full_name="Other Teacher", role=UserRole.TEACHER,
            institution_id=other_inst_id, is_active=True,
            password_changed_at=datetime.now(timezone.utc),
            must_change_password=False,
        )
        db.add(other_teacher); db.flush()
        other_teacher_id = other_teacher.id
        other_teacher_email = other_teacher.email
        db.commit()

    c2 = TestClient(app)
    c2.post("/login", data={"email": other_teacher_email, "password": PWD},
            follow_redirects=False)
    csv_payload2 = f"full_name,email\nOther Student,{PFX}_otherstu@x.com"
    r = c2.post("/teacher/students/import/confirm",
                data={"csv_text": csv_payload2}, follow_redirects=False)
    check("other teacher confirm 200", r.status_code == 200)
    with SessionLocal() as db:
        other_stu = db.query(User).filter(
            User.email == f"{PFX}_otherstu@x.com"
        ).first()
        check("other_teacher öğrencisi other_inst'a bağlı",
              other_stu is not None and other_stu.institution_id == other_inst_id,
              f"got inst_id={other_stu.institution_id if other_stu else None}")

    # ============ STEP 8: anonim erişim ============
    print("\n=== STEP 8: anonim 303 ===")
    anon = TestClient(app)
    r = anon.get("/teacher/students/import", follow_redirects=False)
    check("anon GET /import -> 303", r.status_code == 303)
    r = anon.post("/teacher/students/import/preview",
                  data={"csv_text": "x"}, follow_redirects=False)
    check("anon POST /preview -> 303", r.status_code == 303)

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_test_users = db.query(User).filter(
            User.email.like(f"{PFX}_%")
        ).all()
        all_uids = [u.id for u in all_test_users]
        if all_uids:
            db.query(AuditLog).filter(
                AuditLog.actor_id.in_(all_uids)
            ).delete(synchronize_session=False)
            db.query(AuditLog).filter(
                AuditLog.target_id.in_(all_uids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(all_uids)).delete(
                synchronize_session=False
            )
        db.query(Institution).filter(
            Institution.id.in_([inst_id, other_inst_id])
        ).delete(synchronize_session=False)
        db.commit()
        print("  test verileri temizlendi")

    print(f"\n=== SONUC ===")
    print(f"  gecen: {passed}, basarisiz: {len(failed)}")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    print("  [OK] Stage 3 CSV import testi gecti")
    return 0


if __name__ == "__main__":
    sys.exit(main())
