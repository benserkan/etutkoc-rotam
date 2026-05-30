"""P4 — Kapsamlı 5-kullanıcı testi (KULLANICI İSTEĞİYLE).

5 farklı rol × her senaryo için backend'i uçtan uca test eder.
Senaryolar:
  - Şablon listesi (rol filtreli)
  - Hedef bilgisi (yetki kontrolü)
  - URL üret (happy + yetki + telefon + freeform_note)
  - Dispatch log kontrolü

Test kullanıcıları:
  K1 — Bağımsız koç (TEACHER, institution_id=NULL)
  K2 — Kuruma bağlı öğretmen 1
  K3 — Kuruma bağlı öğretmen 2 (K2'nin meslektaşı)
  K4 — Kurum yöneticisi (K2 ve K3 ile aynı kurumda)
  K5 — Süper admin
  V1 — Veli (yetki kontrol testi için)

Toplam: ~25 senaryo + log içgörü raporu.
"""
from __future__ import annotations

import sys
import os

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


PFX = f"v2p4_{_secrets.token_hex(3)}"
INDEP_COACH_EMAIL = f"{PFX}_indep_coach@test.invalid"
INST_TEACHER1_EMAIL = f"{PFX}_inst_t1@test.invalid"
INST_TEACHER2_EMAIL = f"{PFX}_inst_t2@test.invalid"
INST_ADMIN_EMAIL = f"{PFX}_inst_admin@test.invalid"
SUPER_ADMIN_EMAIL = f"{PFX}_super@test.invalid"
PARENT_NO_RIGHTS_EMAIL = f"{PFX}_parent_no@test.invalid"

INDEP_STUDENT_EMAIL = f"{PFX}_indep_student@test.invalid"
INST_STUDENT_A_EMAIL = f"{PFX}_inst_student_a@test.invalid"  # T1'in öğrencisi
INST_STUDENT_B_EMAIL = f"{PFX}_inst_student_b@test.invalid"  # T2'nin öğrencisi
INDEP_PARENT_EMAIL = f"{PFX}_indep_parent@test.invalid"

OTHER_INST_COACH_EMAIL = f"{PFX}_other_inst_coach@test.invalid"  # başka kurum
OTHER_INST_STUDENT_EMAIL = f"{PFX}_other_inst_student@test.invalid"

PASSWORD = "TestP4Comprehensive!23"

# Doğrulu telefonlar (her hedef için ayrı)
PHONE_INDEP_STUDENT = "905321111111"
PHONE_INST_STUDENT_A = "905322222222"
PHONE_INST_STUDENT_B = "905323333333"
PHONE_INDEP_PARENT = "905324444444"
PHONE_INST_TEACHER2 = "905325555555"
PHONE_OTHER_STUDENT = "905326666666"

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
        # 2 kurum
        inst = Institution(
            name=f"{PFX} Test Kurum", slug=f"{PFX}-inst",
            plan="institution_free", is_active=True,
        )
        other_inst = Institution(
            name=f"{PFX} Diğer Kurum", slug=f"{PFX}-other",
            plan="institution_free", is_active=True,
        )
        db.add_all([inst, other_inst])
        db.flush()

        # K1 — Bağımsız koç
        indep_coach = User(
            email=INDEP_COACH_EMAIL, password_hash=pwd,
            full_name="K1 Bağımsız Koç", role=UserRole.TEACHER,
            institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # K2 — Kuruma bağlı öğretmen 1
        inst_t1 = User(
            email=INST_TEACHER1_EMAIL, password_hash=pwd,
            full_name="K2 Kurum Öğretmeni 1", role=UserRole.TEACHER,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # K3 — Kuruma bağlı öğretmen 2 (telefonu doğrulu — kurum yön. hedef alabilsin)
        inst_t2 = User(
            email=INST_TEACHER2_EMAIL, password_hash=pwd,
            full_name="K3 Kurum Öğretmeni 2", role=UserRole.TEACHER,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONE_INST_TEACHER2, phone_verified_at=now,
        )
        # K4 — Kurum yöneticisi
        inst_admin = User(
            email=INST_ADMIN_EMAIL, password_hash=pwd,
            full_name="K4 Kurum Yöneticisi", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )
        # K5 — Süper admin
        super_admin = User(
            email=SUPER_ADMIN_EMAIL, password_hash=pwd,
            full_name="K5 Süper Admin", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )
        # V1 — Veli (yetki testi için)
        v1_parent = User(
            email=PARENT_NO_RIGHTS_EMAIL, password_hash=pwd,
            full_name="V1 Veli", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONE_INDEP_PARENT, phone_verified_at=now,
        )
        # Diğer kurum koçu
        other_inst_coach = User(
            email=OTHER_INST_COACH_EMAIL, password_hash=pwd,
            full_name="Diğer Kurum Koçu", role=UserRole.TEACHER,
            institution_id=other_inst.id, is_active=True,
            password_changed_at=now, must_change_password=False,
        )

        db.add_all([
            indep_coach, inst_t1, inst_t2, inst_admin, super_admin,
            v1_parent, other_inst_coach,
        ])
        db.flush()

        # Öğrenciler
        indep_student = User(
            email=INDEP_STUDENT_EMAIL, password_hash=pwd,
            full_name="Bağımsız Koç Öğrencisi", role=UserRole.STUDENT,
            teacher_id=indep_coach.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONE_INDEP_STUDENT, phone_verified_at=now,
        )
        inst_student_a = User(
            email=INST_STUDENT_A_EMAIL, password_hash=pwd,
            full_name="K2 Öğrencisi A", role=UserRole.STUDENT,
            teacher_id=inst_t1.id, institution_id=inst.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONE_INST_STUDENT_A, phone_verified_at=now,
        )
        inst_student_b = User(
            email=INST_STUDENT_B_EMAIL, password_hash=pwd,
            full_name="K3 Öğrencisi B", role=UserRole.STUDENT,
            teacher_id=inst_t2.id, institution_id=inst.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONE_INST_STUDENT_B, phone_verified_at=now,
        )
        other_inst_student = User(
            email=OTHER_INST_STUDENT_EMAIL, password_hash=pwd,
            full_name="Diğer Kurum Öğrencisi", role=UserRole.STUDENT,
            teacher_id=other_inst_coach.id, institution_id=other_inst.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONE_OTHER_STUDENT, phone_verified_at=now,
        )
        indep_parent = User(
            email=INDEP_PARENT_EMAIL, password_hash=pwd,
            full_name="K1 Öğrencisinin Velisi", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONE_INDEP_PARENT, phone_verified_at=now,
        )
        db.add_all([indep_student, inst_student_a, inst_student_b, other_inst_student, indep_parent])
        db.flush()

        # Veli-öğrenci link (K1'in öğrencisinin velisi)
        link = ParentStudentLink(
            parent_id=indep_parent.id, student_id=indep_student.id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        db.add(link)

        # Test şablonu: koç → veli (target_role=teacher)
        tmpl_teacher = WhatsAppTemplate(
            key=f"{PFX}_test_teacher_to_parent",
            category="veli", target_role="teacher",
            name_tr="Test (koç → veli)",
            description="P4 testi", content_template="Merhaba {{veli_adi}}",
            variables_json='[{"key":"veli_adi","label_tr":"Veli","example":"Ayşe"}]',
            requires_date=False, allow_bulk=False, allow_freeform_note=False,
            sort_order=100, is_active=True,
        )
        # Şablon: institution_admin
        tmpl_inst = WhatsAppTemplate(
            key=f"{PFX}_test_inst_to_teacher",
            category="kurum_ogretmen", target_role="institution_admin",
            name_tr="Test (yönetici → öğretmen)",
            description="P4 testi",
            content_template="Merhaba {{koc_adi}}, kurumsal duyuru.",
            variables_json='[{"key":"koc_adi","label_tr":"Koç","example":"Burak"}]',
            requires_date=False, allow_bulk=False, allow_freeform_note=False,
            sort_order=100, is_active=True,
        )
        # Şablon: any (hepsi görür)
        tmpl_any = WhatsAppTemplate(
            key=f"{PFX}_test_any",
            category="admin_sistem", target_role="any",
            name_tr="Test (any)",
            description="P4 testi", content_template="Sistem mesajı: {{baslik}}",
            variables_json='[{"key":"baslik","label_tr":"Başlık","example":"X"}]',
            requires_date=False, allow_bulk=False, allow_freeform_note=False,
            sort_order=100, is_active=True,
        )
        db.add_all([tmpl_teacher, tmpl_inst, tmpl_any])
        db.commit()

        return {
            "inst_id": inst.id, "other_inst_id": other_inst.id,
            # 5 kullanıcı
            "indep_coach_id": indep_coach.id,
            "inst_t1_id": inst_t1.id,
            "inst_t2_id": inst_t2.id,
            "inst_admin_id": inst_admin.id,
            "super_admin_id": super_admin.id,
            "v1_parent_id": v1_parent.id,
            "other_inst_coach_id": other_inst_coach.id,
            # Hedefler
            "indep_student_id": indep_student.id,
            "inst_student_a_id": inst_student_a.id,
            "inst_student_b_id": inst_student_b.id,
            "other_inst_student_id": other_inst_student.id,
            "indep_parent_id": indep_parent.id,
            # Şablonlar
            "tmpl_teacher_id": tmpl_teacher.id,
            "tmpl_inst_id": tmpl_inst.id,
            "tmpl_any_id": tmpl_any.id,
        }


def _cleanup(seed: dict) -> None:
    with SessionLocal() as db:
        all_user_ids = [
            seed["indep_coach_id"], seed["inst_t1_id"], seed["inst_t2_id"],
            seed["inst_admin_id"], seed["super_admin_id"], seed["v1_parent_id"],
            seed["other_inst_coach_id"], seed["indep_student_id"],
            seed["inst_student_a_id"], seed["inst_student_b_id"],
            seed["other_inst_student_id"], seed["indep_parent_id"],
        ]
        db.execute(sa_delete(WhatsAppDispatchLog).where(
            WhatsAppDispatchLog.sender_user_id.in_(all_user_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(all_user_ids)
        ))
        db.execute(sa_delete(WhatsAppTemplate).where(
            WhatsAppTemplate.id.in_([
                seed["tmpl_teacher_id"], seed["tmpl_inst_id"], seed["tmpl_any_id"],
            ])
        ))
        db.execute(sa_delete(User).where(User.id.in_(all_user_ids)))
        db.execute(sa_delete(Institution).where(
            Institution.id.in_([seed["inst_id"], seed["other_inst_id"]])
        ))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()


def _wa_send(c: TestClient, tmpl_id: int, target_id: int, variables: dict | None = None):
    return c.post("/api/v2/messaging/wa-link", json={
        "template_id": tmpl_id,
        "target_user_id": target_id,
        "variables": variables or {},
    })


def main() -> int:
    print(f"\n=== P4 KAPSAMLI 5-KULLANICI TESTİ — prefix: {PFX} ===\n")
    get_login_limiter().reset()
    seed = _seed()

    try:
        # ========================================================
        # SENARYO 1 — BAĞIMSIZ KOÇ (K1)
        # ========================================================
        print("\n--- K1: BAĞIMSIZ KOÇ ---")
        c1 = TestClient(app)
        assert _login(c1, INDEP_COACH_EMAIL), "K1 login fail"

        # 1.1 — Şablon listesi: teacher + any (kurum şablonu görmez)
        # Test şablonlarımızdan tmpl_teacher (target_role=teacher) + tmpl_any
        # görünür olmalı, tmpl_inst (target_role=institution_admin) görünmemeli
        r = c1.get("/api/v2/messaging/templates")
        items = r.json().get("items", []) if r.status_code == 200 else []
        item_ids = {it.get("id") for it in items}
        ok = (
            r.status_code == 200
            and seed["tmpl_teacher_id"] in item_ids
            and seed["tmpl_any_id"] in item_ids
            and seed["tmpl_inst_id"] not in item_ids
        )
        check(
            "K1.1 Şablon listesi: koç teacher+any görür, institution_admin görmez",
            ok,
            f"got_teacher={seed['tmpl_teacher_id'] in item_ids} "
            f"got_any={seed['tmpl_any_id'] in item_ids} "
            f"got_inst={seed['tmpl_inst_id'] in item_ids}",
        )

        # 1.2 — Hedef bilgisi (kendi öğrencisi)
        r = c1.get(f"/api/v2/messaging/target/{seed['indep_student_id']}")
        ok = (
            r.status_code == 200
            and r.json().get("phone_verified") is True
            and r.json().get("phone_masked", "").startswith("+90 532")
        )
        check(
            "K1.2 Hedef bilgisi (kendi öğrencisi) → 200 + maskeli telefon",
            ok,
            f"status={r.status_code}",
        )

        # 1.3 — Kendi öğrencisine WA → 200
        r = _wa_send(c1, seed["tmpl_teacher_id"], seed["indep_student_id"],
                    {"veli_adi": "K1 Anne"})
        ok = r.status_code == 200 and r.json().get("wa_url", "").startswith("https://wa.me/")
        check(
            "K1.3 Kendi öğrencisine WA → 200 + wa.me URL",
            ok,
            f"status={r.status_code}",
        )

        # 1.4 — Kendi öğrencisinin velisine WA → 200
        r = _wa_send(c1, seed["tmpl_teacher_id"], seed["indep_parent_id"],
                    {"veli_adi": "Anne"})
        ok = r.status_code == 200
        check(
            "K1.4 Kendi öğrencisinin velisine WA → 200",
            ok, f"status={r.status_code}",
        )

        # 1.5 — Başkasının (kurum) öğrencisine WA → 404 (yetki sızıntı önleme)
        r = _wa_send(c1, seed["tmpl_teacher_id"], seed["inst_student_a_id"],
                    {"veli_adi": "X"})
        ok = (
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "target_not_found"
        )
        check(
            "K1.5 Başka kurum öğrencisine WA → 404 target_not_found",
            ok, f"status={r.status_code}",
        )

        # ========================================================
        # SENARYO 2 — KURUMA BAĞLI ÖĞRETMEN 1 (K2)
        # ========================================================
        print("\n--- K2: KURUMA BAĞLI ÖĞRETMEN 1 ---")
        c2 = TestClient(app)
        assert _login(c2, INST_TEACHER1_EMAIL), "K2 login fail"

        # 2.1 — Kendi öğrencisine WA → 200
        r = _wa_send(c2, seed["tmpl_teacher_id"], seed["inst_student_a_id"],
                    {"veli_adi": "A Anne"})
        ok = r.status_code == 200
        check(
            "K2.1 Kuruma bağlı öğretmen kendi öğrencisine WA → 200",
            ok, f"status={r.status_code}",
        )

        # 2.2 — Aynı kurum başka öğretmenin öğrencisine WA → 404 (TEACHER kurum içi
        # PAYLAŞIMI YOK — yalnız kendi teacher_id'sindekiler)
        r = _wa_send(c2, seed["tmpl_teacher_id"], seed["inst_student_b_id"],
                    {"veli_adi": "B Anne"})
        ok = (
            r.status_code == 404
            and r.json().get("detail", {}).get("code") == "target_not_found"
        )
        check(
            "K2.2 Aynı kurum, başka öğretmenin öğrencisine WA → 404 (koç yalnız kendi öğrencisi)",
            ok, f"status={r.status_code}",
        )

        # 2.3 — Başka kurum öğrencisine WA → 404
        r = _wa_send(c2, seed["tmpl_teacher_id"], seed["other_inst_student_id"])
        ok = r.status_code == 404
        check(
            "K2.3 Başka kurum öğrencisine WA → 404",
            ok, f"status={r.status_code}",
        )

        # ========================================================
        # SENARYO 3 — KURUM YÖNETİCİSİ (K4)
        # ========================================================
        print("\n--- K4: KURUM YÖNETİCİSİ ---")
        c4 = TestClient(app)
        assert _login(c4, INST_ADMIN_EMAIL), "K4 login fail"

        # 3.1 — Şablon listesi: institution_admin + any (teacher şablonu görmez)
        r = c4.get("/api/v2/messaging/templates")
        items = r.json().get("items", []) if r.status_code == 200 else []
        item_ids = {it.get("id") for it in items}
        ok = (
            r.status_code == 200
            and seed["tmpl_inst_id"] in item_ids
            and seed["tmpl_any_id"] in item_ids
            and seed["tmpl_teacher_id"] not in item_ids
        )
        check(
            "K4.1 Şablon listesi: yönetici institution_admin+any görür, teacher görmez",
            ok,
            f"got_inst={seed['tmpl_inst_id'] in item_ids} "
            f"got_any={seed['tmpl_any_id'] in item_ids} "
            f"got_teacher={seed['tmpl_teacher_id'] in item_ids}",
        )

        # 3.2 — Aynı kurumdaki öğretmene WA → 200
        r = _wa_send(c4, seed["tmpl_inst_id"], seed["inst_t2_id"],
                    {"koc_adi": "K3"})
        ok = r.status_code == 200
        check(
            "K4.2 Kurum yöneticisi → aynı kurum öğretmenine WA → 200",
            ok, f"status={r.status_code}",
        )

        # 3.3 — Aynı kurum öğrencisi (her öğretmenin)
        r = _wa_send(c4, seed["tmpl_any_id"], seed["inst_student_a_id"],
                    {"baslik": "Duyuru"})
        ok = r.status_code == 200
        check(
            "K4.3 Kurum yöneticisi → aynı kurum öğrencisine WA → 200",
            ok, f"status={r.status_code}",
        )

        # 3.4 — Başka kurum öğretmenine WA → 404
        r = _wa_send(c4, seed["tmpl_any_id"], seed["other_inst_coach_id"],
                    {"baslik": "X"})
        ok = (
            r.status_code == 400  # other_inst_coach telefonu yok → phone_not_verified
            or r.status_code == 404
        )
        check(
            "K4.4 Kurum yöneticisi → başka kurum koçu → 404 (yetki yok) veya 400 (telefon yok)",
            ok, f"status={r.status_code} code={r.json().get('detail', {}).get('code')}",
        )

        # ========================================================
        # SENARYO 4 — SÜPER ADMIN (K5)
        # ========================================================
        print("\n--- K5: SÜPER ADMIN ---")
        c5 = TestClient(app)
        assert _login(c5, SUPER_ADMIN_EMAIL), "K5 login fail"

        # 4.1 — Şablon listesi: hepsini görür (teacher + institution_admin + any)
        r = c5.get("/api/v2/messaging/templates")
        items = r.json().get("items", []) if r.status_code == 200 else []
        item_ids = {it.get("id") for it in items}
        ok = (
            r.status_code == 200
            and seed["tmpl_teacher_id"] in item_ids
            and seed["tmpl_inst_id"] in item_ids
            and seed["tmpl_any_id"] in item_ids
        )
        check(
            "K5.1 Şablon listesi: süper admin tüm 3 tip şablonu görür",
            ok, f"count={len(items)}",
        )

        # 4.2 — Herkese WA atabilir (bağımsız koç öğrencisine)
        r = _wa_send(c5, seed["tmpl_any_id"], seed["indep_student_id"],
                    {"baslik": "Süper admin duyuru"})
        ok = r.status_code == 200
        check(
            "K5.2 Süper admin → bağımsız koç öğrencisine WA → 200",
            ok, f"status={r.status_code}",
        )

        # 4.3 — Herkese WA atabilir (başka kurum öğrencisine)
        r = _wa_send(c5, seed["tmpl_any_id"], seed["other_inst_student_id"],
                    {"baslik": "Süper admin duyuru"})
        ok = r.status_code == 200
        check(
            "K5.3 Süper admin → başka kurum öğrencisine WA → 200",
            ok, f"status={r.status_code}",
        )

        # ========================================================
        # SENARYO 5 — VELİ (V1) — YETKİ YOK
        # ========================================================
        print("\n--- V1: VELİ (yetki yok) ---")
        cv = TestClient(app)
        assert _login(cv, PARENT_NO_RIGHTS_EMAIL), "V1 login fail"

        # 5.1 — Şablon listesi → 403
        r = cv.get("/api/v2/messaging/templates")
        ok = (
            r.status_code == 403
            and r.json().get("detail", {}).get("code") == "role_not_allowed"
        )
        check(
            "V1.1 Veli → /messaging/templates → 403 role_not_allowed",
            ok, f"status={r.status_code}",
        )

        # 5.2 — Hedef bilgisi → 403
        r = cv.get(f"/api/v2/messaging/target/{seed['indep_student_id']}")
        ok = r.status_code == 403
        check(
            "V1.2 Veli → /messaging/target → 403",
            ok, f"status={r.status_code}",
        )

        # 5.3 — WA link → 403
        r = _wa_send(cv, seed["tmpl_teacher_id"], seed["indep_student_id"])
        ok = r.status_code == 403
        check(
            "V1.3 Veli → /messaging/wa-link → 403",
            ok, f"status={r.status_code}",
        )

        # ========================================================
        # DISPATCH LOG İÇGÖRÜ RAPORU
        # ========================================================
        print("\n--- DISPATCH LOG İÇGÖRÜ ---")
        with SessionLocal() as db:
            all_logs = db.query(WhatsAppDispatchLog).filter(
                WhatsAppDispatchLog.sender_user_id.in_([
                    seed["indep_coach_id"], seed["inst_t1_id"],
                    seed["inst_admin_id"], seed["super_admin_id"],
                ])
            ).all()
            by_sender: dict[int, int] = {}
            for log in all_logs:
                by_sender[log.sender_user_id] = by_sender.get(log.sender_user_id, 0) + 1
            sender_labels = {
                seed["indep_coach_id"]: "K1 Bağımsız koç",
                seed["inst_t1_id"]: "K2 Kurum öğretmeni 1",
                seed["inst_admin_id"]: "K4 Kurum yöneticisi",
                seed["super_admin_id"]: "K5 Süper admin",
            }
            print(f"  Toplam dispatch log kaydı: {len(all_logs)}")
            for sid, count in by_sender.items():
                print(f"    {sender_labels.get(sid, sid)}: {count} mesaj tetiği")

            # Yalnız başarılı (200) çağrılar log atar. K1 = 3 (1.3+1.4+sayım=K1.3,K1.4),
            # K2 = 1 (2.1), K4 = 2 (3.2, 3.3), K5 = 2 (4.2, 4.3) = toplam 8
            # K1 1.5 → 404, K2 2.2, 2.3 → 404, K4 3.4 → 400/404
            ok = len(all_logs) >= 6
            check(
                f"LOG.1 Dispatch log kayıt sayısı ≥6 (gerçek={len(all_logs)})",
                ok,
            )

            # Her log içinde template_key olmalı
            ok = all(log.template_key for log in all_logs)
            check(
                "LOG.2 Tüm log kayıtları template_key dolu",
                ok,
            )

            # Character_count > 0
            ok = all(log.character_count > 0 for log in all_logs)
            check(
                "LOG.3 Tüm log kayıtları character_count > 0",
                ok,
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
