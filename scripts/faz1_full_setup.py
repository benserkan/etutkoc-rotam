"""Faz 1 — TAM manuel test hazırlığı (tek komutla 5 rol ekosistemi).

Oluşturulan kullanıcılar:
  * Süper Admin             - Admin panel (whatsapp templates + dispatch log)
  * Bağımsız Koç A          - Koç paneli + tekli/toplu WA gönderim
  * Kurum X / Yönetici X    - Kurum paneli + toplu WA + öğretmen filtreleri
  * Kuruma Bağlı Öğretmen B - Öğretmen kuruma bağlı; kendi öğrencilerine WA
  * Öğrenci 1 (Bağımsız)    - A'nın öğrencisi, telefon doğrulu
  * Öğrenci 2 (Kurum)       - B'nin öğrencisi, telefon doğrulu
  * Veli 1 (Anne)           - Öğrenci 1'in velisi, telefon doğrulu
  * Veli 2 (Baba)           - Öğrenci 1'in velisi, TELEFONSUZ (skipped testi)
  * Veli 3 (Anne)           - Öğrenci 2'nin velisi, telefon doğrulu

Tüm WA dispatch_log temizlenir, koç banner sıfırdan başlar.

Kullanım:
    python scripts/faz1_full_setup.py
    python scripts/faz1_full_setup.py --inject-busy   # ek olarak 70 log enjekte (amber banner)
    python scripts/faz1_full_setup.py --inject-heavy  # ek olarak 120 log enjekte (rose banner)

Temizleme: python scripts/faz1_full_cleanup.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from datetime import datetime, timezone

from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Institution,
    NotificationLog,
    ParentNotificationPref,
    ParentRelation,
    ParentSessionLog,
    ParentStudentLink,
    PhoneVerification,
    SuspiciousIp,
    User,
    UserRole,
    WhatsAppDispatchLog,
)
from app.services.security import hash_password


PFX = "faz1"
PASSWORD = "TestFaz1!2026"

# Tüm e-postalar (cleanup için)
ADMIN_EMAIL = f"{PFX}_admin@test.invalid"
COACH_A_EMAIL = f"{PFX}_kocA_bagimsiz@test.invalid"
INST_ADMIN_EMAIL = f"{PFX}_kurum_yoneticisi@test.invalid"
INST_TEACHER_EMAIL = f"{PFX}_ogretmenB_kurum@test.invalid"
STUDENT1_EMAIL = f"{PFX}_ogrenci1_bagimsiz@test.invalid"
STUDENT2_EMAIL = f"{PFX}_ogrenci2_kurum@test.invalid"
PARENT1A_EMAIL = f"{PFX}_veli1A_anne@test.invalid"
PARENT1B_EMAIL = f"{PFX}_veli1B_baba_telefonsuz@test.invalid"
PARENT2_EMAIL = f"{PFX}_veli2_anne@test.invalid"

ALL_EMAILS = [
    ADMIN_EMAIL, COACH_A_EMAIL, INST_ADMIN_EMAIL, INST_TEACHER_EMAIL,
    STUDENT1_EMAIL, STUDENT2_EMAIL, PARENT1A_EMAIL, PARENT1B_EMAIL, PARENT2_EMAIL,
]

# Doğrulu telefon havuzu
PHONES = {
    "coach_a":     "905329000001",
    "inst_admin":  "905329000002",
    "inst_teacher": "905329000003",
    "student1":    "905329000004",
    "student2":    "905329000005",
    "parent1a":    "905329000006",
    "parent2":     "905329000007",
}

BASE_URL = "http://127.0.0.1:3000"


def cleanup_existing(db) -> None:
    """Mevcut faz1_* kullanıcıları + dispatch log kalıntılarını sil."""
    prev_users = db.query(User).filter(User.email.in_(ALL_EMAILS)).all()
    prev_ids = [u.id for u in prev_users]
    if prev_ids:
        db.execute(sa_delete(WhatsAppDispatchLog).where(
            WhatsAppDispatchLog.sender_user_id.in_(prev_ids)
        ))
        db.execute(sa_delete(ParentSessionLog).where(
            ParentSessionLog.parent_id.in_(prev_ids)
        ))
        db.execute(sa_delete(NotificationLog).where(
            NotificationLog.parent_id.in_(prev_ids)
        ))
        db.execute(sa_delete(ParentStudentLink).where(
            ParentStudentLink.parent_id.in_(prev_ids)
            | ParentStudentLink.student_id.in_(prev_ids)
        ))
        db.execute(sa_delete(ParentNotificationPref).where(
            ParentNotificationPref.parent_id.in_(prev_ids)
        ))
        db.execute(sa_delete(PhoneVerification).where(
            PhoneVerification.user_id.in_(prev_ids)
        ))
        db.execute(sa_delete(User).where(User.id.in_(prev_ids)))
    # Kurum kalıntısı
    db.execute(sa_delete(Institution).where(Institution.slug == f"{PFX}-kurum-x"))
    db.commit()


def main() -> int:
    inject_busy = "--inject-busy" in sys.argv
    inject_heavy = "--inject-heavy" in sys.argv

    now = datetime.now(timezone.utc)
    pwd = hash_password(PASSWORD)

    with SessionLocal() as db:
        cleanup_existing(db)

        # === Kurum X ===
        kurum = Institution(
            name="Etüt Kurum X",
            slug=f"{PFX}-kurum-x",
            plan="institution_free",
            is_active=True,
        )
        db.add(kurum)
        db.flush()

        # === Süper admin ===
        super_admin = User(
            email=ADMIN_EMAIL, password_hash=pwd,
            full_name="Faz1 Süper Admin", role=UserRole.SUPER_ADMIN,
            is_active=True, password_changed_at=now, must_change_password=False,
        )

        # === Bağımsız koç A ===
        coach_a = User(
            email=COACH_A_EMAIL, password_hash=pwd,
            full_name="Bağımsız Koç A", role=UserRole.TEACHER,
            institution_id=None, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES["coach_a"], phone_verified_at=now,
        )

        # === Kurum Yöneticisi ===
        inst_admin = User(
            email=INST_ADMIN_EMAIL, password_hash=pwd,
            full_name="Kurum X Yöneticisi", role=UserRole.INSTITUTION_ADMIN,
            institution_id=kurum.id, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES["inst_admin"], phone_verified_at=now,
        )

        # === Kuruma bağlı öğretmen B ===
        inst_teacher = User(
            email=INST_TEACHER_EMAIL, password_hash=pwd,
            full_name="Kuruma Bağlı Öğretmen B", role=UserRole.TEACHER,
            institution_id=kurum.id, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES["inst_teacher"], phone_verified_at=now,
        )

        db.add_all([super_admin, coach_a, inst_admin, inst_teacher])
        db.flush()

        # === Öğrenciler ===
        student1 = User(
            email=STUDENT1_EMAIL, password_hash=pwd,
            full_name="Öğrenci 1 (Bağımsız Koç A'nın)", role=UserRole.STUDENT,
            teacher_id=coach_a.id, grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES["student1"], phone_verified_at=now,
        )
        student2 = User(
            email=STUDENT2_EMAIL, password_hash=pwd,
            full_name="Öğrenci 2 (Kuruma bağlı Öğretmen B'nin)", role=UserRole.STUDENT,
            teacher_id=inst_teacher.id, institution_id=kurum.id,
            grade_level=8, is_active=True,
            password_changed_at=now, must_change_password=False,
            phone=PHONES["student2"], phone_verified_at=now,
        )

        # === Veliler ===
        parent1a = User(
            email=PARENT1A_EMAIL, password_hash=pwd,
            full_name="Veli 1A (Anne, Öğrenci 1)", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONES["parent1a"], phone_verified_at=now,
        )
        parent1b = User(
            email=PARENT1B_EMAIL, password_hash=pwd,
            full_name="Veli 1B (Baba, Öğrenci 1) — TELEFONSUZ",
            role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            # phone yok — "skipped" senaryosu
        )
        parent2 = User(
            email=PARENT2_EMAIL, password_hash=pwd,
            full_name="Veli 2 (Anne, Öğrenci 2)", role=UserRole.PARENT,
            is_active=True, password_changed_at=now, must_change_password=False,
            phone=PHONES["parent2"], phone_verified_at=now,
        )

        db.add_all([student1, student2, parent1a, parent1b, parent2])
        db.flush()

        # === Veli-öğrenci linkleri ===
        db.add_all([
            ParentStudentLink(parent_id=parent1a.id, student_id=student1.id,
                              relation=ParentRelation.ANNE, is_primary=True),
            ParentStudentLink(parent_id=parent1b.id, student_id=student1.id,
                              relation=ParentRelation.BABA, is_primary=False),
            ParentStudentLink(parent_id=parent2.id, student_id=student2.id,
                              relation=ParentRelation.ANNE, is_primary=True),
        ])
        db.commit()

        coach_id = coach_a.id
        coach_email = COACH_A_EMAIL
        student1_id = student1.id
        student2_id = student2.id

        # === Dispatch log enjeksiyon (banner görmek için) ===
        if inject_heavy or inject_busy:
            n = 120 if inject_heavy else 70
            for _ in range(n):
                db.add(WhatsAppDispatchLog(
                    sender_user_id=coach_id,
                    template_key="faz1_setup_inject",
                    character_count=50,
                    created_at=now,
                ))
            db.commit()

        # Suspicious IP temizliği (testclient)
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    print()
    print("=" * 76)
    print("FAZ 1 — TAM MANUEL TEST KURULUMU HAZIR")
    print("=" * 76)
    print()
    print(f"Şifre (hepsi için): {PASSWORD}")
    print()
    print("KULLANICILAR:")
    print("-" * 76)
    print(f"  Süper Admin            : {ADMIN_EMAIL}")
    print(f"  Bağımsız Koç A         : {COACH_A_EMAIL}")
    print(f"  Kurum Yöneticisi       : {INST_ADMIN_EMAIL}")
    print(f"  Kuruma Bağlı Öğretmen B: {INST_TEACHER_EMAIL}")
    print(f"  Öğrenci 1 (A'nın)      : {STUDENT1_EMAIL}  -> id={student1_id}")
    print(f"  Öğrenci 2 (B'nin)      : {STUDENT2_EMAIL}  -> id={student2_id}")
    print(f"  Veli 1A (Anne, S1)     : {PARENT1A_EMAIL}  [telefonu doğrulu]")
    print(f"  Veli 1B (Baba, S1)     : {PARENT1B_EMAIL}  [TELEFONSUZ — skipped testi]")
    print(f"  Veli 2 (Anne, S2)      : {PARENT2_EMAIL}  [telefonu doğrulu]")
    print()
    if inject_heavy:
        print("  ⚠ 120 dispatch log enjekte edildi — koç panelinde ROSE 'çok yoğun' banner")
    elif inject_busy:
        print("  ⚠ 70 dispatch log enjekte edildi — koç panelinde AMBER 'yoğun' banner")
    print()
    print("HIZLI LİNKLER:")
    print("-" * 76)
    print(f"  Giriş               : {BASE_URL}/login")
    print(f"  Koç A — öğrenci     : {BASE_URL}/teacher/students/{student1_id}")
    print(f"  Koç A — toplu WA    : {BASE_URL}/teacher/bulk-wa")
    print(f"  Koç A — Hesabım     : {BASE_URL}/me/account")
    print(f"  Süper admin — şablon: {BASE_URL}/admin/whatsapp-templates")
    print(f"  Süper admin — audit : {BASE_URL}/admin/whatsapp-dispatch-log")
    print(f"  Kurum yön. paneli   : {BASE_URL}/institution")
    print(f"  Kurum yön. toplu WA : {BASE_URL}/institution/bulk-wa")
    print()
    print(f"Detaylı rehber: scripts/faz1_manuel_test_rehberi.md")
    print(f"Bitirince     : python scripts/faz1_full_cleanup.py")
    print("=" * 76)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
