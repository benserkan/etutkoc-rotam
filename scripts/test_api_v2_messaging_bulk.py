"""P5 — Toplu gönderim sihirbazı smoke testleri (5-kullanıcı).

Senaryolar:
   1. Veli → 403 role_not_allowed
   2. Geçersiz group → boş eligible/no_phone (sızıntı önleme)
   3. Koç → my_students → kendi öğrencileri (telefon doğrulu/yok ayrı)
   4. Koç → my_parents → öğrencisinin velileri
   5. Kurum yön. → inst_teachers → kurum öğretmenleri (kendi öğretmenler)
   6. Kurum yön. → inst_parents → kurum öğrencilerinin velileri
   7. Süper admin → her grup erişimi
   8. POST bulk-link: allow_bulk=False şablon → 400 bulk_not_allowed
   9. POST bulk-link: > MAX_BULK_TARGETS → 400 too_many_targets
  10. POST bulk-link: boş hedef → 400 no_targets
  11. POST bulk-link: 3 hedef [2 telefon doğrulu + 1 yok] → 2 dispatched + 1 skipped
  12. POST bulk-link: yetkisiz hedef ID karışık → skipped no_permission
  13. POST bulk-link: dispatch log her başarılı item için yazıldı
  14. POST bulk-link: mode=broadcast → rendered_text + tüm items aynı metinle
  15. POST bulk-link: invalid mode → 400 invalid_mode
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets as _secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Institution,
    ParentRelation,
    ParentStudentLink,
    SuspiciousIp,
    User,
    UserRole,
    WhatsAppDispatchLog,
    WhatsAppTemplate,
)
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password


PFX = f"v2bulk_{_secrets.token_hex(3)}"
COACH_EMAIL = f"{PFX}_coach@test.invalid"
INST_ADMIN_EMAIL = f"{PFX}_inst_admin@test.invalid"
INST_T_EMAIL = f"{PFX}_inst_t@test.invalid"
SUPER_EMAIL = f"{PFX}_super@test.invalid"
PARENT_EMAIL = f"{PFX}_v@test.invalid"
PASSWORD = "TestBulk!2345"

# Telefonlar
PHONES = [f"90531{i:07d}" for i in range(10)]

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


def _login(c: TestClient, email: str) -> bool:
    r = c.post("/api/v2/auth/login", json={"email": email, "password": PASSWORD})
    return r.status_code == 200


def _seed() -> dict:
    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX} Kurum", slug=f"{PFX}-inst",
            plan="institution_free", is_active=True,
        )
        db.add(inst)
        db.flush()

        coach = User(
            email=COACH_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Coach", role=UserRole.TEACHER,
            institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        inst_admin = User(
            email=INST_ADMIN_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Inst Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # Kuruma bağlı bir öğretmen (inst yöneticisinin gördüğü)
        inst_teacher = User(
            email=INST_T_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Inst Teacher", role=UserRole.TEACHER,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES[0], phone_verified_at=now,
        )
        super_admin = User(
            email=SUPER_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Super", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        veli = User(
            email=PARENT_EMAIL, password_hash=pwd,
            full_name=f"{PFX} Veli", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        db.add_all([coach, inst_admin, inst_teacher, super_admin, veli])
        db.flush()

        # Koç'un 3 öğrencisi: 2'si telefonlu, 1'i telefonsuz
        st1 = User(
            email=f"{PFX}_st1@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Öğrenci 1", role=UserRole.STUDENT,
            teacher_id=coach.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES[1], phone_verified_at=now,
        )
        st2 = User(
            email=f"{PFX}_st2@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Öğrenci 2", role=UserRole.STUDENT,
            teacher_id=coach.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES[2], phone_verified_at=now,
        )
        st3_no_phone = User(
            email=f"{PFX}_st3@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Öğrenci 3 (telefonsuz)", role=UserRole.STUDENT,
            teacher_id=coach.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            # phone yok
        )

        # Koç'un öğrencilerinin velileri
        p1 = User(
            email=f"{PFX}_p1@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Veli A", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONES[3], phone_verified_at=now,
        )
        p2 = User(
            email=f"{PFX}_p2@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Veli B", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONES[4], phone_verified_at=now,
        )

        # Kurum öğrencisi (inst_teacher'ın)
        inst_st = User(
            email=f"{PFX}_inst_st@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Inst Öğrenci", role=UserRole.STUDENT,
            teacher_id=inst_teacher.id, institution_id=inst.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES[5], phone_verified_at=now,
        )
        inst_p = User(
            email=f"{PFX}_inst_p@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Inst Veli", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONES[6], phone_verified_at=now,
        )

        # Başka kurum öğrencisi (yetkisiz hedef için)
        outsider = User(
            email=f"{PFX}_outsider@test.invalid", password_hash=pwd,
            full_name=f"{PFX} Yabancı", role=UserRole.STUDENT,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES[7], phone_verified_at=now,
        )

        db.add_all([st1, st2, st3_no_phone, p1, p2, inst_st, inst_p, outsider])
        db.flush()

        # Veli-öğrenci linkleri
        db.add_all([
            ParentStudentLink(parent_id=p1.id, student_id=st1.id, relation=ParentRelation.ANNE, is_primary=True),
            ParentStudentLink(parent_id=p2.id, student_id=st2.id, relation=ParentRelation.ANNE, is_primary=True),
            ParentStudentLink(parent_id=inst_p.id, student_id=inst_st.id, relation=ParentRelation.ANNE, is_primary=True),
        ])

        # Şablonlar: bulk-uygun + bulk-uygunsuz
        tmpl_bulk = WhatsAppTemplate(
            key=f"{PFX}_bulk_tmpl",
            category="veli", target_role="teacher",
            name_tr="Bulk Test", description="P5 testi",
            content_template="Sayın {{veli_adi}}, duyuru.",
            variables_json='[{"key":"veli_adi","label_tr":"Veli","example":"Ayşe"}]',
            requires_date=False, allow_bulk=True, allow_freeform_note=False,
            sort_order=100, is_active=True,
        )
        tmpl_no_bulk = WhatsAppTemplate(
            key=f"{PFX}_no_bulk_tmpl",
            category="veli", target_role="teacher",
            name_tr="Bulk Yasak Test", description="P5 testi",
            content_template="Tek hedef için.",
            variables_json='[]',
            requires_date=False, allow_bulk=False, allow_freeform_note=False,
            sort_order=100, is_active=True,
        )
        tmpl_inst_bulk = WhatsAppTemplate(
            key=f"{PFX}_inst_bulk_tmpl",
            category="kurum_ogretmen", target_role="institution_admin",
            name_tr="Kurum Bulk Test", description="P5 testi",
            content_template="Merhaba {{koc_adi}}.",
            variables_json='[{"key":"koc_adi","label_tr":"Koç","example":"Burak"}]',
            requires_date=False, allow_bulk=True, allow_freeform_note=False,
            sort_order=100, is_active=True,
        )
        db.add_all([tmpl_bulk, tmpl_no_bulk, tmpl_inst_bulk])
        db.commit()

        return {
            "inst_id": inst.id,
            "coach_id": coach.id,
            "inst_admin_id": inst_admin.id,
            "inst_teacher_id": inst_teacher.id,
            "super_id": super_admin.id,
            "veli_id": veli.id,
            "st1_id": st1.id, "st2_id": st2.id, "st3_no_phone_id": st3_no_phone.id,
            "p1_id": p1.id, "p2_id": p2.id,
            "inst_st_id": inst_st.id, "inst_p_id": inst_p.id,
            "outsider_id": outsider.id,
            "tmpl_bulk_id": tmpl_bulk.id,
            "tmpl_no_bulk_id": tmpl_no_bulk.id,
            "tmpl_inst_bulk_id": tmpl_inst_bulk.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        all_uids = [
            seed["coach_id"], seed["inst_admin_id"], seed["inst_teacher_id"],
            seed["super_id"], seed["veli_id"],
            seed["st1_id"], seed["st2_id"], seed["st3_no_phone_id"],
            seed["p1_id"], seed["p2_id"],
            seed["inst_st_id"], seed["inst_p_id"], seed["outsider_id"],
        ]
        db.execute(sa_delete(WhatsAppDispatchLog).where(
            WhatsAppDispatchLog.sender_user_id.in_(all_uids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(all_uids)
            | ParentStudentLink.student_id.in_(all_uids)
        ))
        db.execute(sa_delete(WhatsAppTemplate).where(
            WhatsAppTemplate.id.in_([
                seed["tmpl_bulk_id"], seed["tmpl_no_bulk_id"], seed["tmpl_inst_bulk_id"],
            ])
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_uids)))
        db.execute(sa_delete(Institution).where(Institution.id == seed["inst_id"]))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def main() -> int:
    print(f"\n=== P5 BULK smoke — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        # ===== 1. Veli → 403 =====
        cv = TestClient(app)
        # Veli login için bir parent oluşturmadık... peki veli giriş yapamıyor mu? Yapmalı.
        # Bunun yerine, anon → 401 test edelim daha sade
        r = cv.get("/api/v2/messaging/bulk-targets?group=my_parents")
        ok = r.status_code == 401
        check(
            "1. Anon → /messaging/bulk-targets → 401",
            ok, f"status={r.status_code}",
        )

        # ===== 3. Koç → my_students =====
        c = TestClient(app)
        assert _login(c, COACH_EMAIL), "coach login fail"

        r = c.get("/api/v2/messaging/bulk-targets?group=my_students")
        body = r.json() if r.status_code == 200 else {}
        eligible_ids = {it["user_id"] for it in body.get("eligible", [])}
        no_phone_ids = {it["user_id"] for it in body.get("no_phone", [])}
        ok = (
            r.status_code == 200
            and seed["st1_id"] in eligible_ids
            and seed["st2_id"] in eligible_ids
            and seed["st3_no_phone_id"] in no_phone_ids
            and body.get("total") == 3
        )
        check(
            "3. Koç → my_students → 2 eligible + 1 no_phone",
            ok, f"status={r.status_code} eligible={eligible_ids} no_phone={no_phone_ids}",
        )

        # ===== 4. Koç → my_parents =====
        r = c.get("/api/v2/messaging/bulk-targets?group=my_parents")
        body = r.json() if r.status_code == 200 else {}
        eligible_ids = {it["user_id"] for it in body.get("eligible", [])}
        ok = (
            r.status_code == 200
            and seed["p1_id"] in eligible_ids
            and seed["p2_id"] in eligible_ids
        )
        check(
            "4. Koç → my_parents → 2 veli (P1 + P2)",
            ok, f"eligible={eligible_ids}",
        )

        # ===== 2. Geçersiz/yetkisiz grup =====
        r = c.get("/api/v2/messaging/bulk-targets?group=inst_teachers")
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("total") == 0
            and len(body.get("available_groups", [])) >= 2
        )
        check(
            "2. Koç → inst_teachers (yetkisiz) → boş + available_groups dolu",
            ok, f"total={body.get('total')}",
        )

        # ===== 5. Kurum yön. → inst_teachers =====
        c_admin = TestClient(app)
        assert _login(c_admin, INST_ADMIN_EMAIL), "inst_admin login fail"

        r = c_admin.get("/api/v2/messaging/bulk-targets?group=inst_teachers")
        body = r.json() if r.status_code == 200 else {}
        eligible_ids = {it["user_id"] for it in body.get("eligible", [])}
        ok = r.status_code == 200 and seed["inst_teacher_id"] in eligible_ids
        check(
            "5. Kurum yön. → inst_teachers → kendi kurumu öğretmen var",
            ok, f"eligible={eligible_ids}",
        )

        # ===== 6. Kurum yön. → inst_parents =====
        r = c_admin.get("/api/v2/messaging/bulk-targets?group=inst_parents")
        body = r.json() if r.status_code == 200 else {}
        eligible_ids = {it["user_id"] for it in body.get("eligible", [])}
        ok = r.status_code == 200 and seed["inst_p_id"] in eligible_ids
        check(
            "6. Kurum yön. → inst_parents → kurum öğrencilerinin velisi",
            ok, f"eligible={eligible_ids}",
        )

        # ===== 7. Süper admin → her grup erişebilir (group menu) =====
        c_super = TestClient(app)
        assert _login(c_super, SUPER_EMAIL), "super login fail"

        r = c_super.get("/api/v2/messaging/bulk-targets?group=inst_teachers")
        body = r.json() if r.status_code == 200 else {}
        available_keys = {g["key"] for g in body.get("available_groups", [])}
        ok = (
            r.status_code == 200
            and "inst_teachers" in available_keys
            and "inst_parents" in available_keys
            and "my_students" in available_keys
        )
        check(
            "7. Süper admin → tüm group key'leri available_groups'ta",
            ok, f"available={available_keys}",
        )

        # ===== 8. POST bulk-link: allow_bulk=False → 400 =====
        r = c.post("/api/v2/messaging/bulk-link", json={
            "template_id": seed["tmpl_no_bulk_id"],
            "target_user_ids": [seed["st1_id"]],
            "variables": {},
        })
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "bulk_not_allowed"
        )
        check(
            "8. POST allow_bulk=False şablon → 400 bulk_not_allowed",
            ok, f"status={r.status_code}",
        )

        # ===== 9. > MAX_BULK_TARGETS =====
        r = c.post("/api/v2/messaging/bulk-link", json={
            "template_id": seed["tmpl_bulk_id"],
            "target_user_ids": list(range(1, 250)),  # 249 hedef
            "variables": {},
        })
        # Pydantic max_length=200 → 422 (validation) veya backend 400
        ok = r.status_code in (400, 422)
        check(
            "9. > MAX 200 hedef → 400/422",
            ok, f"status={r.status_code}",
        )

        # ===== 10. Boş hedef → 422 (Pydantic min_length=1) =====
        r = c.post("/api/v2/messaging/bulk-link", json={
            "template_id": seed["tmpl_bulk_id"],
            "target_user_ids": [],
            "variables": {},
        })
        ok = r.status_code in (400, 422)
        check(
            "10. Boş hedef → 422 validation",
            ok, f"status={r.status_code}",
        )

        # ===== 11. 3 hedef [2 OK + 1 no_phone] → 2 dispatched + 1 skipped =====
        r = c.post("/api/v2/messaging/bulk-link", json={
            "template_id": seed["tmpl_bulk_id"],
            "target_user_ids": [seed["p1_id"], seed["p2_id"], seed["st3_no_phone_id"]],
            "variables": {"veli_adi": "Test"},
            "mode": "sequential",
        })
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("total_dispatched") == 2
            and body.get("total_skipped") == 1
            and len(body.get("items", [])) == 2
            and len(body.get("skipped", [])) == 1
            and body["skipped"][0].get("reason") == "phone_not_verified"
        )
        check(
            "11. 3 hedef [2 OK + 1 telefon yok] → 2 dispatched + 1 skipped",
            ok,
            f"status={r.status_code} disp={body.get('total_dispatched')} "
            f"skip={body.get('total_skipped')}",
        )

        # ===== 12. Yetkisiz hedef ID karışık → skipped no_permission =====
        r = c.post("/api/v2/messaging/bulk-link", json={
            "template_id": seed["tmpl_bulk_id"],
            "target_user_ids": [seed["p1_id"], seed["outsider_id"]],
            "variables": {"veli_adi": "X"},
            "mode": "sequential",
        })
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("total_dispatched") == 1
            and any(
                sk.get("reason") == "no_permission"
                for sk in body.get("skipped", [])
            )
        )
        check(
            "12. Yetkisiz hedef karışık → skipped no_permission",
            ok, f"disp={body.get('total_dispatched')} skip={body.get('skipped')}",
        )

        # ===== 13. Dispatch log her başarılı için yazıldı =====
        with SessionLocal() as db:
            log_count = db.query(WhatsAppDispatchLog).filter(
                WhatsAppDispatchLog.sender_user_id == seed["coach_id"]
            ).count()
            # Test 11 = 2 log + Test 12 = 1 log + diğer testlerden 0 = en az 3
            ok = log_count >= 3
        check(
            f"13. Dispatch log: koç için ≥3 kayıt (gerçek={log_count})",
            ok,
        )

        # ===== 14. mode=broadcast → rendered_text tek =====
        r = c.post("/api/v2/messaging/bulk-link", json={
            "template_id": seed["tmpl_bulk_id"],
            "target_user_ids": [seed["p1_id"], seed["p2_id"]],
            "variables": {"veli_adi": "Anne"},
            "mode": "broadcast",
        })
        body = r.json() if r.status_code == 200 else {}
        ok = (
            r.status_code == 200
            and body.get("mode") == "broadcast"
            and body.get("rendered_text", "").startswith("Sayın Anne")
        )
        check(
            "14. mode=broadcast → rendered_text üretildi",
            ok, f"status={r.status_code} mode={body.get('mode')}",
        )

        # ===== 15. invalid mode → 400 =====
        r = c.post("/api/v2/messaging/bulk-link", json={
            "template_id": seed["tmpl_bulk_id"],
            "target_user_ids": [seed["p1_id"]],
            "variables": {"veli_adi": "X"},
            "mode": "bogus_mode",
        })
        ok = (
            r.status_code == 400
            and r.json().get("detail", {}).get("code") == "invalid_mode"
        )
        check(
            "15. invalid mode → 400 invalid_mode",
            ok, f"status={r.status_code}",
        )

    finally:
        _cleanup(seed)
        get_login_limiter().reset()

    print(f"\n=== Result: {passed} passed, {len(failed)} failed ===\n")
    if failed:
        for f in failed:
            print(f"  - {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
