"""Stage 11 — Goal tree smoke test.

Senaryolar:
1. create_goal — kök hedef
2. create_goal — child hedef + parent validation (cross-student rejection)
3. update_goal — current_value güncelleme + auto achievement detection
4. mark_achieved + mark_abandoned
5. list_student_goals — flat + abandon dahil/hariç
6. build_tree — hierarchical, doğru parent-child, aggregated_pct
7. progress_pct — leaf hesabı
8. aggregated_pct — üst düğüm = children ortalaması
9. student_goal_summary — total/active/achieved + overall_pct + next_target_date
10. institution_goal_summary — kurum geneli özet
11. seed_for_exam_target LGS — root + 6 subject
12. seed_for_exam_target YKS Sayısal — TYT 4 + AYT 4
13. seed_for_exam_target idempotent (mevcut varsa atla)
14. HTTP /student/goals — 200, başlık + ağaç render
15. HTTP /teacher/students/{id}/goals — 200, form, ağaç
16. HTTP POST /teacher/students/{id}/goals/create — yeni hedef oluştur
17. HTTP POST /teacher/goals/{id}/achieve — achieved
18. HTTP POST /teacher/goals/{id}/abandon — abandoned
19. HTTP POST /teacher/students/{id}/goals/seed — auto seed
20. HTTP /institution/goals — kurum özeti
21. HTTP /parent/students/{id}/goals — veli view + yetki kontrolü
22. Cross-tenant: öğretmen başka öğrenciye hedef ekleyemez (403)
"""

from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import joinedload
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.deps import get_current_user, require_institution_admin, require_teacher
from app.main import app
from app.models import (
    GoalKind,
    GoalStatus,
    Institution,
    ParentRelation,
    ParentStudentLink,
    StudentGoal,
    Track,
    User,
    UserRole,
)
from app.services.goals import (
    build_tree,
    create_goal,
    institution_goal_summary,
    list_student_goals,
    mark_abandoned,
    mark_achieved,
    student_goal_summary,
    update_goal,
)
from app.services.goals_auto import seed_for_exam_target


PFX = f"_g11_{secrets.token_hex(3)}"
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
    now = datetime.now(timezone.utc)

    # --- SEED ---
    print("\n=== SEED ===")
    with SessionLocal() as db:
        inst = Institution(
            name=f"{PFX}_inst", slug=f"{PFX}-inst",
            plan="etut_standart", is_active=True,
        )
        db.add(inst); db.flush()
        inst_id = inst.id

        admin = User(
            email=f"{PFX}_admin@test.invalid", password_hash="x" * 60,
            full_name="Goals Admin", role=UserRole.INSTITUTION_ADMIN,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        teacher = User(
            email=f"{PFX}_teach@test.invalid", password_hash="x" * 60,
            full_name="Goals Teacher", role=UserRole.TEACHER,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        db.add_all([admin, teacher]); db.flush()
        admin_id, teacher_id = admin.id, teacher.id

        # 8. sınıf LGS öğrencisi
        student_lgs = User(
            email=f"{PFX}_s_lgs@test.invalid", password_hash="x" * 60,
            full_name="LGS Öğrenci", role=UserRole.STUDENT,
            institution_id=inst_id, teacher_id=teacher_id,
            is_active=True, password_changed_at=now,
            grade_level=8,
        )
        # 12. sınıf YKS Sayısal öğrencisi
        student_yks = User(
            email=f"{PFX}_s_yks@test.invalid", password_hash="x" * 60,
            full_name="YKS Öğrenci", role=UserRole.STUDENT,
            institution_id=inst_id, teacher_id=teacher_id,
            is_active=True, password_changed_at=now,
            grade_level=12, track=Track.SAYISAL,
        )
        # Başka öğretmenin öğrencisi (cross-tenant test için)
        other_teacher = User(
            email=f"{PFX}_other@test.invalid", password_hash="x" * 60,
            full_name="Other Teacher", role=UserRole.TEACHER,
            institution_id=inst_id, is_active=True, password_changed_at=now,
        )
        db.add_all([student_lgs, student_yks, other_teacher]); db.flush()
        s_lgs_id, s_yks_id, other_t_id = (
            student_lgs.id, student_yks.id, other_teacher.id,
        )
        other_student = User(
            email=f"{PFX}_s_other@test.invalid", password_hash="x" * 60,
            full_name="Other Student", role=UserRole.STUDENT,
            institution_id=inst_id, teacher_id=other_t_id,
            is_active=True, password_changed_at=now, grade_level=8,
        )
        # Veli + link
        parent = User(
            email=f"{PFX}_parent@test.invalid", password_hash="x" * 60,
            full_name="Goal Parent", role=UserRole.PARENT,
            is_active=True, password_changed_at=now,
        )
        db.add_all([other_student, parent]); db.flush()
        other_s_id, parent_id = other_student.id, parent.id

        link = ParentStudentLink(
            parent_id=parent_id, student_id=s_lgs_id,
            relation=ParentRelation.ANNE, is_primary=True,
        )
        db.add(link); db.commit()
        print(f"  inst={inst_id}, teacher={teacher_id}, lgs_student={s_lgs_id}, yks_student={s_yks_id}, parent={parent_id}")

    # ============ STEP 1: create_goal kök ============
    print("\n=== STEP 1: create_goal kök ===")
    with SessionLocal() as db:
        s = db.get(User, s_lgs_id)
        root = create_goal(
            db, student=s, kind=GoalKind.EXAM_TARGET,
            title="LGS 2027 Hedefim",
            target_value=400, current_value=0, unit="puan",
            target_date=date(2027, 6, 7),
            created_by_user_id=teacher_id,
        )
        check("kök hedef oluştu", root.id is not None)
        check("parent_id None (kök)", root.parent_id is None)
        check("status active", root.status == GoalStatus.ACTIVE)

    # ============ STEP 2: child + cross-student validation ============
    print("\n=== STEP 2: child + cross-student validation ===")
    with SessionLocal() as db:
        s = db.get(User, s_lgs_id)
        root = (
            db.query(StudentGoal)
            .filter(StudentGoal.student_id == s_lgs_id, StudentGoal.parent_id.is_(None))
            .first()
        )
        child = create_goal(
            db, student=s, kind=GoalKind.SUBJECT,
            title="Matematik 18/20",
            target_value=18, current_value=10, unit="net",
            parent_id=root.id,
        )
        check("child oluştu", child.id is not None)
        check("child.parent_id = root.id", child.parent_id == root.id)

        # Cross-student: başka öğrenciye hedef bağlamaya çalış
        other_s = db.get(User, other_s_id)
        try:
            create_goal(
                db, student=other_s, kind=GoalKind.SUBJECT,
                title="Cross-tenant hatası", parent_id=root.id,
            )
            check("cross-student → PermissionError", False, "exception bekleniyordu")
        except PermissionError:
            check("cross-student → PermissionError", True)

    # ============ STEP 3: update_goal + auto achievement ============
    print("\n=== STEP 3: update_goal auto achievement ===")
    with SessionLocal() as db:
        # Matematik child'ı current_value=18 yap → target=18, achieved beklenir
        child = (
            db.query(StudentGoal)
            .filter(StudentGoal.title == "Matematik 18/20")
            .first()
        )
        update_goal(db, goal=child, current_value=18.0)

    with SessionLocal() as db:
        child = (
            db.query(StudentGoal)
            .filter(StudentGoal.title == "Matematik 18/20")
            .first()
        )
        check("auto achievement: status = achieved",
              child.status == GoalStatus.ACHIEVED)
        check("achieved_at set", child.achieved_at is not None)

    # ============ STEP 4: build_tree + aggregated_pct ============
    print("\n=== STEP 4: build_tree ===")
    with SessionLocal() as db:
        # Daha çok subject ekle ki ağaç anlamlı olsun
        s = db.get(User, s_lgs_id)
        root = (
            db.query(StudentGoal)
            .filter(StudentGoal.student_id == s_lgs_id, StudentGoal.parent_id.is_(None))
            .first()
        )
        create_goal(
            db, student=s, kind=GoalKind.SUBJECT,
            title="Türkçe 16/20", parent_id=root.id,
            target_value=16, current_value=8, unit="net",
        )
        create_goal(
            db, student=s, kind=GoalKind.SUBJECT,
            title="Fen 18/20", parent_id=root.id,
            target_value=18, current_value=4.5, unit="net",
        )

    with SessionLocal() as db:
        roots = build_tree(db, student_id=s_lgs_id)
        check("1 kök hedef", len(roots) == 1)
        if roots:
            root_node = roots[0]
            check("kök 3 child", len(root_node.children) == 3)
            # Aggregated: child'ların ortalaması — Matematik %100, Türkçe %50, Fen %25
            # Ortalama: (100 + 50 + 25) / 3 = 58
            check("kök aggregated_pct ≈ 58",
                  root_node.aggregated_pct is not None
                  and 55 <= root_node.aggregated_pct <= 60,
                  f"got {root_node.aggregated_pct}")
            check("achieved_count >= 1 (Matematik tamam)",
                  root_node.achieved_count >= 1)

    # ============ STEP 5: list_student_goals ============
    print("\n=== STEP 5: list_student_goals ===")
    with SessionLocal() as db:
        active_only = list_student_goals(
            db, student_id=s_lgs_id, include_abandoned=False,
        )
        check("aktif/achieved hedefler 4 adet (root + 3 child)",
              len(active_only) == 4)

    # ============ STEP 6: mark_abandoned ============
    print("\n=== STEP 6: mark_abandoned ===")
    with SessionLocal() as db:
        fen = (
            db.query(StudentGoal)
            .filter(StudentGoal.title == "Fen 18/20")
            .first()
        )
        mark_abandoned(db, goal=fen)

    with SessionLocal() as db:
        fen = (
            db.query(StudentGoal)
            .filter(StudentGoal.title == "Fen 18/20")
            .first()
        )
        check("abandoned status", fen.status == GoalStatus.ABANDONED)
        check("abandoned_at set", fen.abandoned_at is not None)

        # list_student_goals abandon dahil
        all_inc = list_student_goals(
            db, student_id=s_lgs_id, include_abandoned=True,
        )
        check("abandon dahil 4 hedef", len(all_inc) == 4)
        active_only = list_student_goals(
            db, student_id=s_lgs_id, include_abandoned=False,
        )
        check("abandon hariç 3 hedef", len(active_only) == 3)

    # ============ STEP 7: student_goal_summary ============
    print("\n=== STEP 7: student_goal_summary ===")
    with SessionLocal() as db:
        s = student_goal_summary(db, student_id=s_lgs_id)
        check("total = 4", s["total"] == 4)
        check("active = 2 (root + Türkçe)", s["active"] == 2)
        check("achieved = 1 (Matematik)", s["achieved"] == 1)
        check("abandoned = 1 (Fen)", s["abandoned"] == 1)
        check("overall_pct doludur", s["overall_pct"] is not None)
        check("next_target_date 2027-06-07",
              s["next_target_date"] == "2027-06-07")

    # ============ STEP 8: institution_goal_summary ============
    print("\n=== STEP 8: institution_goal_summary ===")
    with SessionLocal() as db:
        inst_summary = institution_goal_summary(db, institution_id=inst_id)
        check("students_with_goals = 1", inst_summary["students_with_goals"] == 1)
        check("students_without_goals = 2 (yks + other)",
              inst_summary["students_without_goals"] == 2)
        check("total_goals 4", inst_summary["total_goals"] == 4)

    # ============ STEP 9: seed_for_exam_target — LGS ============
    print("\n=== STEP 9: seed LGS ===")
    # YKS öğrencisi yerine 8. sınıf LGS öğrencisinde mevcut hedef olduğu için
    # idempotent çalışmalı (skipped_existing). Yeni öğrenci kuralım.
    with SessionLocal() as db:
        new_lgs = User(
            email=f"{PFX}_new_lgs@test.invalid", password_hash="x" * 60,
            full_name="New LGS", role=UserRole.STUDENT,
            institution_id=inst_id, teacher_id=teacher_id,
            is_active=True, password_changed_at=now, grade_level=8,
        )
        db.add(new_lgs); db.commit()
        new_lgs_id = new_lgs.id

    with SessionLocal() as db:
        s = db.get(User, new_lgs_id)
        result = seed_for_exam_target(db, student=s, created_by_user_id=teacher_id)
        check("seed_for_exam_target exam=LGS",
              result.get("exam_target") == "LGS")
        check("seed created >= 7 (root + 6 subject)",
              result.get("created", 0) >= 7)
        check("not skipped_existing", not result.get("skipped_existing"))

    with SessionLocal() as db:
        goals = list_student_goals(db, student_id=new_lgs_id)
        check("LGS seed sonrası 7 hedef", len(goals) == 7)
        root = next((g for g in goals if g.parent_id is None), None)
        check("root EXAM_TARGET kind",
              root is not None and root.kind == GoalKind.EXAM_TARGET)
        check("is_auto_generated True",
              root is not None and root.is_auto_generated is True)
        # Subject titles
        titles = sorted(g.title for g in goals if g.parent_id == (root.id if root else None))
        check("Matematik subject var", "Matematik" in titles)

    # ============ STEP 10: seed_for_exam_target — YKS Sayısal ============
    print("\n=== STEP 10: seed YKS Sayısal ===")
    with SessionLocal() as db:
        s = db.get(User, s_yks_id)
        result = seed_for_exam_target(db, student=s, created_by_user_id=teacher_id)
        check("seed YKS exam=YKS", result.get("exam_target") == "YKS")
        # TYT (4) + AYT Sayısal (4) + root = 9
        check("seed YKS Sayısal 9 hedef oluştu",
              result.get("created", 0) == 9, f"got {result.get('created')}")

    # ============ STEP 11: seed idempotent ============
    print("\n=== STEP 11: seed idempotent ===")
    with SessionLocal() as db:
        s = db.get(User, new_lgs_id)
        result = seed_for_exam_target(db, student=s, created_by_user_id=teacher_id)
        check("ikinci seed skipped_existing",
              result.get("skipped_existing") is True)
        check("ikinci seed created = 0",
              result.get("created", 0) == 0)

    # ============ STEP 12-15: HTTP testleri ============
    print("\n=== STEP 12-15: HTTP testleri ===")
    def make_user_override(uid: int):
        def _ov():
            with SessionLocal() as _db:
                u = (
                    _db.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == uid)
                    .first()
                )
                if u is not None:
                    if u.institution is not None:
                        _db.expunge(u.institution)
                    _db.expunge(u)
                return u
        return _ov

    client = TestClient(app)
    app.dependency_overrides.clear()

    # /student/goals (öğrenci)
    app.dependency_overrides[get_current_user] = make_user_override(s_lgs_id)
    r = client.get("/student/goals")
    check("/student/goals 200", r.status_code == 200)
    check("'Hedeflerim' başlığı", "Hedeflerim" in r.text)
    check("LGS root hedef render",
          "LGS 2027 Hedefim" in r.text)
    check("Matematik subject render", "Matematik 18/20" in r.text)
    app.dependency_overrides.clear()

    # /teacher/students/{id}/goals (öğretmen)
    app.dependency_overrides[get_current_user] = make_user_override(teacher_id)
    app.dependency_overrides[require_teacher] = make_user_override(teacher_id)
    r = client.get(f"/teacher/students/{s_lgs_id}/goals")
    check("/teacher/students/{id}/goals 200", r.status_code == 200)
    check("öğrenci adı görünür", "LGS Öğrenci" in r.text)
    check("yeni hedef formu var", "Yeni Hedef Ekle" in r.text)
    check("kind dropdown", "Sınav Hedefi" in r.text or "Ders Hedefi" in r.text)

    # POST create
    r = client.post(
        f"/teacher/students/{s_lgs_id}/goals/create",
        data={
            "title": "İngilizce 9/10",
            "kind": "subject",
            "target_value": "9",
            "current_value": "5",
            "unit": "net",
        },
        follow_redirects=False,
    )
    check("POST create → 303", r.status_code in (302, 303))
    check("redirect ?ok=created",
          "ok=created" in r.headers.get("location", ""))
    with SessionLocal() as db:
        g = (
            db.query(StudentGoal)
            .filter(
                StudentGoal.student_id == s_lgs_id,
                StudentGoal.title == "İngilizce 9/10",
            )
            .first()
        )
        check("DB'de yeni hedef var", g is not None)
        if g:
            new_goal_id = g.id

    # POST achieve
    r = client.post(
        f"/teacher/goals/{new_goal_id}/achieve", follow_redirects=False,
    )
    check("POST achieve → 303", r.status_code in (302, 303))
    with SessionLocal() as db:
        g = db.get(StudentGoal, new_goal_id)
        check("achieve sonrası status", g.status == GoalStatus.ACHIEVED)

    # POST seed (mevcut hedef olduğu için skipped)
    r = client.post(
        f"/teacher/students/{s_lgs_id}/goals/seed", follow_redirects=False,
    )
    check("POST seed → 303", r.status_code in (302, 303))
    check("redirect already_seeded",
          "already_seeded" in r.headers.get("location", ""))
    app.dependency_overrides.clear()

    # ============ STEP 16: Cross-tenant — başka öğretmen yetkisiz ============
    print("\n=== STEP 16: Cross-teacher 403 ===")
    app.dependency_overrides[get_current_user] = make_user_override(other_t_id)
    app.dependency_overrides[require_teacher] = make_user_override(other_t_id)
    r = client.get(f"/teacher/students/{s_lgs_id}/goals")
    check("başka öğretmen → 403",
          r.status_code == 403, f"got {r.status_code}")
    app.dependency_overrides.clear()

    # ============ STEP 17: /institution/goals ============
    print("\n=== STEP 17: /institution/goals ===")
    app.dependency_overrides[get_current_user] = make_user_override(admin_id)
    app.dependency_overrides[require_institution_admin] = make_user_override(admin_id)
    r = client.get("/institution/goals")
    check("/institution/goals 200", r.status_code == 200)
    check("'Hedef Analizi' başlığı", "Hedef Analizi" in r.text)
    check("students_with_goals sayım render",
          "Hedefli Öğrenci" in r.text)
    app.dependency_overrides.clear()

    # ============ STEP 18: /parent/students/{id}/goals ============
    print("\n=== STEP 18: /parent/students/{id}/goals ===")
    app.dependency_overrides[get_current_user] = make_user_override(parent_id)
    r = client.get(f"/parent/students/{s_lgs_id}/goals")
    check("/parent/students/{id}/goals 200", r.status_code == 200)
    check("Veli görünümü açıklama", "Veli Görünümü" in r.text)
    check("LGS hedef ağacı veliye görünür",
          "LGS 2027" in r.text)

    # Veli yetkisiz öğrenci → 403
    r = client.get(f"/parent/students/{s_yks_id}/goals")
    check("yetkisiz öğrenci → 403",
          r.status_code == 403, f"got {r.status_code}")
    app.dependency_overrides.clear()

    # ============ CLEANUP ============
    print("\n=== CLEANUP ===")
    with SessionLocal() as db:
        all_users = [
            admin_id, teacher_id, other_t_id, s_lgs_id, s_yks_id,
            new_lgs_id, other_s_id, parent_id,
        ]
        db.execute(delete(StudentGoal).where(
            StudentGoal.student_id.in_(all_users)
        ))
        db.execute(delete(ParentStudentLink).where(
            (ParentStudentLink.parent_id.in_(all_users))
            | (ParentStudentLink.student_id.in_(all_users))
        ))
        db.execute(delete(User).where(User.id.in_(all_users)))
        db.execute(delete(Institution).where(Institution.id == inst_id))
        db.commit()
    print("  cleanup OK")

    print(f"\n=== SONUÇ ===\nPASS: {passed}\nFAIL: {len(failed)}")
    for f in failed:
        print(f"  - {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
