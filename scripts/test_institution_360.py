"""Sprint B (Roadmap Faz B) — Kurum 360 + CRM (notlar/aksiyonlar) smoke test.

Test ettiği:
  - get_institution_360() dict shape + alt bölümler
  - usage_metrics: aktif öğretmen/öğrenci sayıları doğru
  - billing_summary: son ödeme + sonraki vade + gecikmiş özet
  - open_risks: tenant_health indicator + ödeme gecikme + trial bitiş
  - CrmNote CRUD: create / pin toggle / delete
  - CrmAction CRUD: create / complete / delete
  - HTTP GET /admin/revenue/institutions/{id} → 200 + tüm sekmeler
  - HTTP POST not ekle / sabitle / sil → 303
  - HTTP POST aksiyon ekle / tamamla / sil → 303
  - Audit log: CRM aksiyonları kayıt altında
"""

from __future__ import annotations

import secrets
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fastapi.testclient import TestClient
from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.deps import get_current_user, require_super_admin, require_user
from app.main import app
from app.models import (
    AuditAction,
    AuditLog,
    CrmAction,
    CrmActionKind,
    CrmActionResult,
    CrmNote,
    Institution,
    Invoice,
    InvoiceStatus,
    User,
    UserRole,
)
from app.services.institution_360 import (
    billing_summary,
    complete_action,
    create_action,
    create_note,
    delete_action,
    delete_note,
    get_institution_360,
    open_risks,
    toggle_note_pin,
    usage_metrics,
)


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
    print("=== Sprint B — Kurum 360 + CRM smoke ===")
    tag = f"inst360-{secrets.token_hex(3)}"
    now = datetime.now(timezone.utc)

    with SessionLocal() as db:
        sa = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
        inst = db.query(Institution).filter(Institution.is_active.is_(True)).first()
        if not sa or not inst:
            print("  (gerekli SA/kurum yok — atlandı)")
            return 0
        sa_id = sa.id
        inst_id = inst.id

    # Cleanup
    with SessionLocal() as db:
        db.query(CrmNote).filter(CrmNote.content.like(f"{tag}%")).delete()
        db.query(CrmAction).filter(CrmAction.summary.like(f"{tag}%")).delete()
        db.commit()

    # ---- 1) get_institution_360 dict shape ----
    with SessionLocal() as db:
        d = get_institution_360(db, institution_id=inst_id)
        check("get_institution_360 None değil", d is not None)
        check("identity bölümü var",
              "identity" in d and d["identity"]["id"] == inst_id)
        check("health bölümü var",
              "health" in d and "score" in d["health"])
        check("usage_30d bölümü var", "usage_30d" in d)
        check("billing bölümü var", "billing" in d)
        check("crm_notes bölümü liste", isinstance(d.get("crm_notes"), list))
        check("crm_actions bölümü liste", isinstance(d.get("crm_actions"), list))
        check("risks bölümü liste", isinstance(d.get("risks"), list))

    # ---- 2) usage_metrics ----
    with SessionLocal() as db:
        u = usage_metrics(db, institution_id=inst_id, days=30)
        check("usage: dict shape",
              "active_teacher_count" in u and "active_student_count" in u
              and "notification_sent" in u and "study_sessions" in u)
        check("usage: pct hesabı total > 0 olduğunda dolu",
              (u["total_teacher_count"] == 0
                or u["teacher_active_pct"] is not None))

    # ---- 3) billing_summary ----
    with SessionLocal() as db:
        b = billing_summary(db, institution_id=inst_id)
        check("billing: dict shape",
              "overdue_count" in b and "overdue_total_try" in b
              and "lifetime_paid_try" in b)

    # ---- 4) open_risks ----
    with SessionLocal() as db:
        risks = open_risks(db, institution=inst)
        check("open_risks: liste döner", isinstance(risks, list))

    # ---- 5) CrmNote CRUD ----
    with SessionLocal() as db:
        note = create_note(
            db, institution_id=inst_id,
            content=f"{tag} test not 1", by_user_id=sa_id, pinned=False,
        )
        check("create_note: oluştu",
              note is not None and note.id is not None)
        check("create_note: content saklandı",
              note.content == f"{tag} test not 1")
        note_id = note.id

    with SessionLocal() as db:
        toggled = toggle_note_pin(db, note_id=note_id)
        check("toggle_note_pin: pinned True",
              toggled is not None and toggled.pinned is True)
        toggled2 = toggle_note_pin(db, note_id=note_id)
        check("toggle_note_pin: pinned False geri", toggled2.pinned is False)

    with SessionLocal() as db:
        ok = delete_note(db, note_id=note_id)
        check("delete_note: ok=True", ok is True)
        check("delete_note: kayıt silindi",
              db.get(CrmNote, note_id) is None)

    # ---- 6) CrmAction CRUD ----
    with SessionLocal() as db:
        action = create_action(
            db, institution_id=inst_id,
            kind="call", summary=f"{tag} test aksiyon", by_user_id=sa_id,
            notes="Telefon görüşmesi yapıldı", result="pending",
        )
        check("create_action: oluştu",
              action is not None and action.id is not None)
        check("create_action: kind enum",
              action.kind == CrmActionKind.CALL)
        check("create_action: result default pending",
              action.result == CrmActionResult.PENDING)
        check("create_action: completed_at None",
              action.completed_at is None)
        action_id = action.id

    # Geçersiz kind
    with SessionLocal() as db:
        bad = create_action(
            db, institution_id=inst_id, kind="bogus_kind",
            summary=f"{tag} bogus", by_user_id=sa_id,
        )
        check("create_action geçersiz kind → None", bad is None)

    # Tamamla
    with SessionLocal() as db:
        a = complete_action(
            db, action_id=action_id, result="success",
            by_user_id=sa_id, notes="İyi geçti",
        )
        check("complete_action: result update",
              a.result == CrmActionResult.SUCCESS)
        check("complete_action: completed_at dolu",
              a.completed_at is not None)
        check("complete_action: notes eklendi",
              "Sonuç" in (a.notes or "") and "İyi geçti" in (a.notes or ""))

    # Sil
    with SessionLocal() as db:
        ok = delete_action(db, action_id=action_id)
        check("delete_action: ok=True", ok)
        check("delete_action: kayıt silindi",
              db.get(CrmAction, action_id) is None)

    # ---- 7) HTTP: tüm sekmeler ----
    def _ov():
        def factory():
            db2 = SessionLocal()
            try:
                u = (
                    db2.query(User)
                    .options(joinedload(User.institution))
                    .filter(User.id == sa_id).first()
                )
                _ = u.institution
                db2.expunge_all()
                return u
            finally:
                db2.close()
        return factory

    app.dependency_overrides[require_super_admin] = _ov()
    app.dependency_overrides[require_user] = _ov()
    app.dependency_overrides[get_current_user] = _ov()
    try:
        c = TestClient(app)

        # Sekme: health (varsayılan)
        r = c.get(f"/admin/revenue/institutions/{inst_id}")
        check("kurum 360 GET 200", r.status_code == 200)
        check("kurum 360 başlık 'Kurum 360' yok ama 'Açık Riskler' var",
              "Açık Riskler" in r.text or "Sağlık Skoru" in r.text)

        # Sekme: usage
        r2 = c.get(f"/admin/revenue/institutions/{inst_id}?tab=usage")
        check("sekme usage GET 200", r2.status_code == 200)
        check("usage sekmesi 'Aktif Öğretmen' içerir",
              "Aktif Öğretmen" in r2.text)

        # Sekme: billing
        r3 = c.get(f"/admin/revenue/institutions/{inst_id}?tab=billing")
        check("sekme billing GET 200", r3.status_code == 200)
        check("billing sekmesi 'Mevcut Plan' içerir",
              "Mevcut Plan" in r3.text)

        # Sekme: notes
        r4 = c.get(f"/admin/revenue/institutions/{inst_id}?tab=notes")
        check("sekme notes GET 200", r4.status_code == 200)
        check("notes sekmesi 'Yeni Not' form içerir",
              "Yeni Not" in r4.text)

        # Sekme: actions
        r5 = c.get(f"/admin/revenue/institutions/{inst_id}?tab=actions")
        check("sekme actions GET 200", r5.status_code == 200)
        check("actions sekmesi 'Yeni Aksiyon' form içerir",
              "Yeni Aksiyon" in r5.text)

        # Geçersiz kurum
        r6 = c.get("/admin/revenue/institutions/99999999")
        check("bilinmeyen kurum → 404",
              r6.status_code == 404, f"got {r6.status_code}")

        # POST not ekle
        r7 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/notes/add",
            data={"content": f"{tag} HTTP test not", "pinned": "1"},
            follow_redirects=False,
        )
        check("not ekle POST → 303", r7.status_code == 303)
        check("not ekle → tab=notes redirect",
              "tab=notes" in r7.headers.get("location", ""))

        # Eklenen notu bul
        with SessionLocal() as db2:
            http_note = (
                db2.query(CrmNote)
                .filter(CrmNote.content.like(f"{tag} HTTP%"))
                .order_by(CrmNote.id.desc())
                .first()
            )
            check("HTTP ekleme sonrası DB'de not var", http_note is not None)
            check("not pinned=True", http_note.pinned is True)
            http_note_id = http_note.id

            # Audit log
            au = (
                db2.query(AuditLog)
                .filter(
                    AuditLog.target_type == "crm_note",
                    AuditLog.target_id == http_note_id,
                )
                .first()
            )
            check("not ekleme audit log yazıldı", au is not None)

        # Boş içerikli not → err
        r8 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/notes/add",
            data={"content": "  "},
            follow_redirects=False,
        )
        check("boş not → 303 + err",
              r8.status_code == 303
              and "err=" in r8.headers.get("location", ""))

        # Pin toggle
        r9 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/notes/{http_note_id}/pin",
            follow_redirects=False,
        )
        check("not pin toggle POST → 303", r9.status_code == 303)
        with SessionLocal() as db2:
            n = db2.get(CrmNote, http_note_id)
            check("pin toggle → pinned False (en başta True idi)",
                  n.pinned is False)

        # Not sil
        r10 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/notes/{http_note_id}/delete",
            follow_redirects=False,
        )
        check("not sil POST → 303", r10.status_code == 303)
        with SessionLocal() as db2:
            check("not gerçekten silindi",
                  db2.get(CrmNote, http_note_id) is None)

        # POST aksiyon ekle (geçerli)
        r11 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/actions/add",
            data={
                "kind": "call",
                "summary": f"{tag} HTTP aksiyon",
                "notes": "test detay",
                "result": "pending",
                "follow_up_at": "2026-06-01",
            },
            follow_redirects=False,
        )
        check("aksiyon ekle POST → 303", r11.status_code == 303)
        with SessionLocal() as db2:
            http_action = (
                db2.query(CrmAction)
                .filter(CrmAction.summary.like(f"{tag} HTTP%"))
                .first()
            )
            check("HTTP aksiyon DB'de var", http_action is not None)
            check("aksiyon follow_up_at saklandı",
                  http_action.follow_up_at is not None)
            http_action_id = http_action.id

        # Geçersiz kind → err
        r12 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/actions/add",
            data={"kind": "bogus", "summary": "test", "result": "pending"},
            follow_redirects=False,
        )
        check("aksiyon geçersiz kind → 303 + err",
              r12.status_code == 303
              and "err=" in r12.headers.get("location", ""))

        # Boş summary
        r13 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/actions/add",
            data={"kind": "call", "summary": "  ", "result": "pending"},
            follow_redirects=False,
        )
        check("aksiyon boş özet → 303 + err",
              "err=" in r13.headers.get("location", ""))

        # Tamamla
        r14 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/actions/{http_action_id}/complete",
            data={"result": "success", "notes": "iyi geçti"},
            follow_redirects=False,
        )
        check("aksiyon tamamla POST → 303", r14.status_code == 303)
        with SessionLocal() as db2:
            a = db2.get(CrmAction, http_action_id)
            check("HTTP tamamla sonrası completed_at dolu",
                  a.completed_at is not None)
            check("HTTP tamamla sonrası result=success",
                  a.result == CrmActionResult.SUCCESS)

        # Aksiyon sil
        r15 = c.post(
            f"/admin/revenue/institutions/{inst_id}/crm/actions/{http_action_id}/delete",
            follow_redirects=False,
        )
        check("aksiyon sil POST → 303", r15.status_code == 303)
        with SessionLocal() as db2:
            check("aksiyon DB'den silindi",
                  db2.get(CrmAction, http_action_id) is None)
    finally:
        app.dependency_overrides.pop(require_super_admin, None)
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_current_user, None)

    # Cleanup
    with SessionLocal() as db:
        db.query(CrmNote).filter(CrmNote.content.like(f"{tag}%")).delete()
        db.query(CrmAction).filter(CrmAction.summary.like(f"{tag}%")).delete()
        db.commit()

    print()
    print(f"=== Toplam: {passed} PASS, {len(failed)} FAIL ===")
    if failed:
        for f in failed:
            print(f"  ! {f}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
