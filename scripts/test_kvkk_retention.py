"""KVKK silme + saklama süresi (2026-11-01).

1. Pasife alınca deactivated_at yazılır, yeniden başlatınca silinir.
2. Anonimleştirme kişisel içeriği gerçekten temizler (telefon, 2FA, notlar,
   karne PDF'i, seans notu, yanlış soru fotoğrafı, veli bağı, sohbet…);
   sayısal kayıtlar (görev, net, seans tarihi) kalır.
3. Saklama süresi cron'u: 76. günde koça bir kez hatırlatma, 90. günde
   anonimleştirme; aktif / anonim öğrenciye dokunmaz.
4. Koç / veli / süper admin öğrenci adına talep açar; iptal yetkileri.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    CoachingSession, DataRequestStatus, DataSubjectRequest, DevicePushToken,
    ExamResult, ParentChatMessage, ParentStudentLink, StudentDayNote, Task,
    TotpBackupCode, User, UserRole, WrongQuestion, WrongQuestionImage,
)
from app.services import kvkk
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"kv_{secrets.token_hex(3)}"
PW = "TestPass123!@xyz"
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


def mk(db, role, name, **kw):
    u = User(email=f"{PFX}_{name}@test.invalid", password_hash=hash_password(PW),
             full_name=f"{name} {PFX}", role=role, is_active=True, **kw)
    db.add(u); db.flush()
    return u


def seed():
    with SessionLocal() as db:
        koc = mk(db, UserRole.TEACHER, "koc", plan="solo_pro")
        koc2 = mk(db, UserRole.TEACHER, "koc2", plan="solo_pro")
        s1 = mk(db, UserRole.STUDENT, "s1", grade_level=8, teacher_id=koc.id, phone="905321112233")
        s2 = mk(db, UserRole.STUDENT, "s2", grade_level=8, teacher_id=koc.id)
        s3 = mk(db, UserRole.STUDENT, "s3", grade_level=8, teacher_id=koc.id)
        s4 = mk(db, UserRole.STUDENT, "s4", grade_level=8, teacher_id=koc.id)
        veli = mk(db, UserRole.PARENT, "veli")
        db.add(ParentStudentLink(parent_id=veli.id, student_id=s1.id))
        db.add(ParentStudentLink(parent_id=veli.id, student_id=s3.id))
        # s1'e kişisel içerik
        s1.totp_secret = "ABC"; s1.totp_enabled_at = datetime.now(timezone.utc)
        db.add(TotpBackupCode(user_id=s1.id, code_hash="x"))
        db.add(DevicePushToken(user_id=s1.id, token=f"ExpoTok{PFX}", platform="android"))
        db.add(StudentDayNote(student_id=s1.id, date=date.today(), body="Bugün çok yoruldum"))
        db.add(Task(student_id=s1.id, title="Görev", date=date.today(), type="test"))
        db.add(ExamResult(student_id=s1.id, created_by_id=koc.id, title="LGS 1", exam_date=date.today(),
                          section="lgs", total_correct=50, total_wrong=10, total_blank=30, net=46.67,
                          note="okulda zor", import_pdf_data=b"%PDF-ad soyad okul", import_pdf_size=17,
                          import_pdf_content_type="application/pdf"))
        db.add(CoachingSession(coach_id=koc.id, student_id=s1.id, session_date=date.today(),
                               status="done", agenda="Ailesiyle sorun", coach_note="Gizli not"))
        wq = WrongQuestion(student_id=s1.id, source_kind="diger", note="foto")
        db.add(wq); db.flush()
        db.add(WrongQuestionImage(wrong_question_id=wq.id, kind="question", content_type="image/png",
                                  data=b"img", size_bytes=3))
        db.add(ParentChatMessage(parent_id=veli.id, student_id=s1.id, role="veli", body="Oğlum nasıl?"))
        db.commit()
        return dict(koc=koc.id, koc2=koc2.id, s1=s1.id, s2=s2.id, s3=s3.id, s4=s4.id, veli=veli.id)


def cleanup(ids):
    from app.models import AuditLog
    with SessionLocal() as db:
        uids = list(ids.values())
        db.query(DataSubjectRequest).filter(DataSubjectRequest.target_user_id.in_(uids)).delete(synchronize_session=False)
        db.query(AuditLog).filter(AuditLog.target_id.in_(uids), AuditLog.target_type == "user").delete(synchronize_session=False)
        for m, col in [(StudentDayNote, StudentDayNote.student_id), (Task, Task.student_id),
                       (ExamResult, ExamResult.student_id), (CoachingSession, CoachingSession.student_id),
                       (ParentChatMessage, ParentChatMessage.student_id), (ParentStudentLink, ParentStudentLink.student_id),
                       (TotpBackupCode, TotpBackupCode.user_id), (DevicePushToken, DevicePushToken.user_id)]:
            db.query(m).filter(col.in_(uids)).delete(synchronize_session=False)
        wq = [i for (i,) in db.query(WrongQuestion.id).filter(WrongQuestion.student_id.in_(uids)).all()]
        if wq:
            db.query(WrongQuestionImage).filter(WrongQuestionImage.wrong_question_id.in_(wq)).delete(synchronize_session=False)
        db.query(WrongQuestion).filter(WrongQuestion.student_id.in_(uids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(uids)).delete(synchronize_session=False)
        db.commit()


def login(c, name):
    get_login_limiter().reset()
    c.cookies.clear()
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{name}@test.invalid", "password": PW})
    assert r.status_code == 200, r.text


def main():
    ids = seed()
    sent = {"email": [], "push": []}
    import app.services.email_service as es
    import app.services.push_notifications as pn
    orig_email, orig_push = es.send_email, pn.safe_push
    es.send_email = lambda to, tpl, ctx, **k: sent["email"].append((to, tpl, ctx)) or True
    pn.safe_push = lambda db, **k: sent["push"].append(k)
    try:
        c = TestClient(app)
        login(c, "koc")

        # 1) deactivated_at
        r = c.post(f"/api/v2/teacher/students/{ids['s2']}/deactivate")
        with SessionLocal() as db:
            s2 = db.get(User, ids["s2"])
            check("1a. koçluk sonlandırılınca deactivated_at yazıldı",
                  r.status_code == 200 and s2.deactivated_at is not None)
        c.post(f"/api/v2/teacher/students/{ids['s2']}/reactivate")
        with SessionLocal() as db:
            check("1b. yeniden başlatınca sayaç sıfırlandı", db.get(User, ids["s2"]).deactivated_at is None)

        # 4) koç talebi
        r = c.post(f"/api/v2/teacher/students/{ids['s2']}/data-delete", json={})
        check("4a. aktif öğrenci için silme talebi → 409", r.status_code == 409)
        c.post(f"/api/v2/teacher/students/{ids['s2']}/deactivate")
        r = c.post(f"/api/v2/teacher/students/{ids['s2']}/data-delete", json={"reason": "Veli istedi"})
        d = r.json().get("data", {})
        check("4b. pasif öğrenci için talep açıldı (kaynak=request, ~30 gün)",
              r.status_code == 200 and d.get("source") == "request" and d.get("can_cancel") is True, str(d))
        r = c.get("/api/v2/teacher/students", params={"status": "pasif"})
        row = next((x for x in r.json()["items"] if x["id"] == ids["s2"]), {})
        check("4c. öğrenci listesinde silinme tarihi görünüyor",
              row.get("deletion_source") == "request" and row.get("deletion_scheduled_at"), str(row)[:160])
        r = c.post(f"/api/v2/teacher/students/{ids['s2']}/reactivate")
        with SessionLocal() as db:
            req = db.query(DataSubjectRequest).filter(DataSubjectRequest.target_user_id == ids["s2"]).first()
            check("4d. koç yeniden başlatınca KENDİ talebi iptal oldu",
                  r.status_code == 200 and req.status == DataRequestStatus.CANCELLED)

        # Veli talebi (s3)
        c.post(f"/api/v2/teacher/students/{ids['s3']}/deactivate")
        login(c, "veli")
        r = c.post(f"/api/v2/parent/students/{ids['s3']}/data-delete", json={"confirm": True})
        check("4e. veli çocuğu için talep açtı", r.status_code == 200, r.text[:150])
        check("4f. koça bildirim gitti", any("velisi" in p.get("body", "") for p in sent["push"]))
        r = c.post(f"/api/v2/parent/students/{ids['s2']}/data-delete", json={"confirm": True})
        check("4g. bağlı olmadığı öğrenci → 404", r.status_code == 404)
        login(c, "koc")
        r = c.post(f"/api/v2/teacher/students/{ids['s3']}/data-delete/cancel")
        check("4h. koç velinin talebini iptal EDEMEZ (403)", r.status_code == 403, str(r.status_code))
        r = c.post(f"/api/v2/teacher/students/{ids['s3']}/reactivate")
        check("4i. velinin talebi varken koçluk yeniden başlatılamaz (409)",
              r.status_code == 409 and r.json()["detail"]["code"] == "delete_requested_by_other")
        login(c, "veli")
        r = c.post(f"/api/v2/parent/students/{ids['s3']}/data-delete/cancel")
        check("4j. veli kendi talebini iptal etti", r.status_code == 200 and r.json()["data"]["request_id"] is None)

        # 2) Anonimleştirme kapsamı (s1)
        with SessionLocal() as db:
            s1 = db.get(User, ids["s1"])
            req = kvkk.request_deletion(db, target=s1, requester=s1)
            kvkk.apply_deletion(db, request=req)
            s1 = db.get(User, ids["s1"])
            check("2a. ad/e-posta anonim, telefon ve 2FA silindi",
                  s1.full_name == "(Silinen Kullanıcı)" and s1.phone is None and s1.totp_secret is None)
            check("2b. yedek kod + bildirim cihazı silindi",
                  db.query(TotpBackupCode).filter_by(user_id=s1.id).count() == 0
                  and db.query(DevicePushToken).filter_by(user_id=s1.id).count() == 0)
            check("2c. günün notu silindi", db.query(StudentDayNote).filter_by(student_id=s1.id).count() == 0)
            ex = db.query(ExamResult).filter_by(student_id=s1.id).first()
            check("2d. deneme neti KALDI, karne PDF'i ve not silindi",
                  ex is not None and float(ex.net) > 46 and ex.import_pdf_size is None and ex.note is None)
            cs = db.query(CoachingSession).filter_by(student_id=s1.id).first()
            check("2e. seans tarihi/durumu KALDI, içeriği silindi",
                  cs is not None and cs.agenda == "" and cs.coach_note is None)
            check("2f. yanlış soru + fotoğraf silindi",
                  db.query(WrongQuestion).filter_by(student_id=s1.id).count() == 0)
            check("2g. veli bağı + veli sohbeti silindi",
                  db.query(ParentStudentLink).filter_by(student_id=s1.id).count() == 0
                  and db.query(ParentChatMessage).filter_by(student_id=s1.id).count() == 0)
            check("2h. görev kaydı (istatistik) KALDI", db.query(Task).filter_by(student_id=s1.id).count() == 1)

        # 3) Saklama süresi cron'u
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            s4 = db.get(User, ids["s4"])
            s4.is_active = False
            db.commit()
            s4.deactivated_at = now - timedelta(days=77)
            db.commit()
        sent["email"].clear(); sent["push"].clear()
        with SessionLocal() as db:
            r1 = kvkk.cron_retention_inactive(db, now=now)
        check("3a. 77. günde koça hatırlatma (e-posta + bildirim)",
              any(t == "student_retention_warning" for _, t, _ in sent["email"]) and len(sent["push"]) >= 1,
              str(r1))
        n_email = len(sent["email"])
        with SessionLocal() as db:
            kvkk.cron_retention_inactive(db, now=now + timedelta(days=1))
        check("3b. hatırlatma bir kez gider", len(sent["email"]) == n_email)
        with SessionLocal() as db:
            check("3c. 13 gün kala henüz silinmedi",
                  not kvkk.is_anonymized(db.get(User, ids["s4"])))
            r3 = kvkk.cron_retention_inactive(db, now=now + timedelta(days=14))
            s4 = db.get(User, ids["s4"])
            req = db.query(DataSubjectRequest).filter_by(target_user_id=s4.id).first()
            check("3d. 91. günde anonimleştirildi + talep kaydı saklama süresi gerekçeli",
                  kvkk.is_anonymized(s4) and req is not None and req.status == DataRequestStatus.COMPLETED
                  and "Saklama süresi" in (req.reason or ""), str(r3))
            s2 = db.get(User, ids["s2"])
            check("3e. aktif öğrenciye dokunulmadı", s2.is_active and not kvkk.is_anonymized(s2))

        # Anonim öğrenci yeniden başlatılamaz
        r = c.post(f"/api/v2/teacher/students/{ids['s4']}/reactivate") if False else None
        login(c, "koc")
        r = c.post(f"/api/v2/teacher/students/{ids['s4']}/reactivate")
        check("3f. silinmiş öğrenci yeniden başlatılamaz (409)",
              r.status_code == 409 and r.json()["detail"]["code"] == "student_anonymized")

        # Başka koç → 404
        login(c, "koc2")
        r = c.post(f"/api/v2/teacher/students/{ids['s2']}/data-delete", json={})
        check("4k. başka koçun öğrencisi → 404", r.status_code == 404)
    finally:
        es.send_email, pn.safe_push = orig_email, orig_push
        cleanup(ids)

    print(f"\n{passed} passed, {len(failed)} failed")
    for f in failed:
        print("  -", f)
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
