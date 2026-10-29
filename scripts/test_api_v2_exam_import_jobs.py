"""Deneme karnesi arka plan okuma işi — smoke (2026-10-29).

Kapsam: yükleme hızlı döner (okuma arkada) · kredi YALNIZ okuma bitince düşer ·
okuma bitmeden durum sorgusu · taslak + PDF'siz kaydetme (job_id) · aynı PDF
koruması (iş açıkken + kayıt sonrası) · servis hatası → başarısız + ücretsiz +
yeniden dene · belge okunamadı → yeniden denenemez · başkasının işi 404 ·
çoklu yükleme (sıra) · sunucu yeniden başladı kurtarması · deneme sınırı ·
bildirim (yükleyen + öğrenci yüklediyse koç) · ekran bilgisini kapat · vazgeç ·
7 gün temizliği · eski tek-istekli uç hâlâ çalışır.

Gemini monkeypatch'lenir — gerçek yapay zekâ çağrısı YOK. İş parçacıkları
GERÇEK (yürütücünün kendisi sınanır).
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import copy
import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    CreditAccount,
    ExamResult,
    ExamResultQuestion,
    ExamTopicAlias,
    SuspiciousIp,
    UsageEvent,
    User,
    UserRole,
)
from app.models.ai_job import AiJob
from app.services import ai_exam_import
from app.services import exam_import_jobs as jobs
from app.services import exam_import_service as svc
from app.services import push_notifications
from app.services.ai_book_template import AIInvalidResponse, AIServiceUnavailable
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password
from scripts.test_api_v2_exam_import import build_tyt_read

PFX = f"exjob{secrets.token_hex(3)}"
PASSWORD = "ExamJobs!2026X"
passed = 0
failed: list[str] = []


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label} ({detail})")


def pdf_bytes() -> bytes:
    return b"%PDF-1.4 fake exam " + secrets.token_bytes(32) + b"0" * 200


def fpdf(data: bytes):
    return ("karne-12.10.2026.pdf", data, "application/pdf")


def exam_credits(actor_ids: list[int]) -> int:
    with SessionLocal() as db:
        return sum(
            e.credits for e in db.query(UsageEvent)
            .filter(UsageEvent.actor_user_id.in_(actor_ids)).all()
            if e.kind and "ai_exam_import" in getattr(e.kind, "value", str(e.kind))
        )


def wait_status(cli: TestClient, job_id: int, want: set[str], timeout: float = 20.0) -> dict:
    t0 = time.time()
    last = {}
    while time.time() - t0 < timeout:
        r = cli.get(f"/api/v2/me/ai-jobs/{job_id}")
        if r.status_code == 200:
            last = r.json()
            if last["job"]["status"] in want:
                return last
        time.sleep(0.2)
    return last


def main() -> int:
    print(f"\n=== Karne arka plan okuma işi smoke — {PFX} ===\n")
    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        coach = User(email=f"{PFX}-t@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="İş Koçu", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", subscription_status="active",
                     must_change_password=False, ai_capture_consent_at=now)
        other = User(email=f"{PFX}-o@t.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Başka Koç", role=UserRole.TEACHER, is_active=True,
                     plan="solo_pro", must_change_password=False, ai_capture_consent_at=now)
        st = [User(email=f"{PFX}-s{i}@t.invalid", password_hash=hash_password(PASSWORD),
                   full_name=f"Öğrenci {i}", role=UserRole.STUDENT, is_active=True,
                   grade_level=12, must_change_password=False) for i in range(5)]
        db.add_all([coach, other, *st])
        db.flush()
        for s in st:
            s.teacher_id = coach.id
        db.commit()
        cid, oid = coach.id, other.id
        sids = [s.id for s in st]
    uids = [cid, oid, *sids]

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    behavior = {"mode": "ok", "delay": 1.2}
    pushes: list[tuple[int, str]] = []

    def fake_double(pdf_b64: str):
        time.sleep(behavior["delay"])
        if behavior["mode"] == "unavailable":
            raise AIServiceUnavailable("geçici kesinti")
        if behavior["mode"] == "unreadable":
            raise AIInvalidResponse("Bu bir karne değil.")
        r = ai_exam_import._normalize_read(copy.deepcopy(build_tyt_read()))
        return r, copy.deepcopy(r)

    def fake_generate(parts, **kw):
        return json.dumps({"mappings": []})

    def fake_push(db, *, user_id, title, body, data=None):
        pushes.append((user_id, title))

    orig = (ai_exam_import.read_exam_pdf_double, svc.gemini.generate, push_notifications.safe_push)
    ai_exam_import.read_exam_pdf_double = fake_double
    svc.gemini.generate = fake_generate
    push_notifications.safe_push = fake_push

    try:
        ct, co, cs, anon = TestClient(app), TestClient(app), TestClient(app), TestClient(app)
        ct.post("/api/v2/auth/login", json={"email": f"{PFX}-t@t.invalid", "password": PASSWORD})
        co.post("/api/v2/auth/login", json={"email": f"{PFX}-o@t.invalid", "password": PASSWORD})
        cs.post("/api/v2/auth/login", json={"email": f"{PFX}-s0@t.invalid", "password": PASSWORD})
        base = f"/api/v2/teacher/students/{sids[0]}/exams"

        # 1) anon
        r = anon.post(f"{base}/import-jobs", files={"file": fpdf(pdf_bytes())})
        check("1. anonim 401", r.status_code == 401, r.status_code)

        # 2) hızlı dönüş + kredi henüz düşmedi
        p1 = pdf_bytes()
        t0 = time.time()
        r = ct.post(f"{base}/import-jobs", files={"file": fpdf(p1)},
                    data={"declared_section": "tyt", "declared_grade": "12"})
        took = time.time() - t0
        j1 = r.json() if r.status_code == 202 else {}
        check("2a. yükleme 202 ve okumayı beklemeden döner",
              r.status_code == 202 and took < 1.0 and j1.get("status") in ("queued", "running"),
              f"{r.status_code} {took:.2f}s {r.text[:150]}")
        check("2b. okuma bitmeden kredi düşmedi", exam_credits(uids) == 0, exam_credits(uids))
        lst = ct.get("/api/v2/me/ai-jobs").json()
        check("2c. açık işler listesinde aktif iş görünür",
              lst["active_count"] >= 1 and any(i["id"] == j1.get("id") for i in lst["items"]),
              str(lst)[:200])

        # 3) aynı PDF iş açıkken
        r = ct.post(f"{base}/import-jobs", files={"file": fpdf(p1)})
        check("3. aynı PDF okunurken tekrar yükleme 409 job_exists",
              r.status_code == 409 and r.json()["detail"]["code"] == "job_exists", r.text[:150])

        # 4) bitti → taslak + kredi
        d = wait_status(ct, j1["id"], {"done", "failed"})
        check("4a. okuma bitince durum 'done' + taslak satırları",
              d.get("job", {}).get("status") == "done" and len((d.get("draft") or {}).get("rows") or []) == 12,
              str(d)[:200])
        check("4b. kredi yalnız şimdi düştü (6)", exam_credits(uids) == 6, exam_credits(uids))
        check("4c. tarih dosya adından önerildi",
              (d.get("draft") or {}).get("exam_date") in ("2026-04-02", "2026-10-12"),
              (d.get("draft") or {}).get("exam_date"))
        check("4d. bildirim yükleyen koça gitti",
              any(u == cid and t == "Karne okundu" for u, t in pushes), pushes)
        lst = ct.get("/api/v2/me/ai-jobs").json()
        check("4e. hazır sayacı 1", lst["ready_count"] >= 1, lst)

        # 5) başkasının işi
        r = co.get(f"/api/v2/me/ai-jobs/{j1['id']}")
        check("5a. başka koç işi göremez (404)", r.status_code == 404, r.status_code)
        r = cs.get(f"/api/v2/me/ai-jobs/{j1['id']}")
        check("5b. öğrenci koçun yüklediği işi göremez (404)", r.status_code == 404, r.status_code)

        # 6) ack
        r = ct.post(f"/api/v2/me/ai-jobs/{j1['id']}/ack")
        check("6. ekran bilgisi kapatılır (acknowledged)",
              r.status_code == 200 and r.json()["data"]["acknowledged"] is True, r.text[:150])

        # 7) PDF'siz kaydetme
        draft = d["draft"]
        payload = {
            "title": draft["title"], "exam_date": draft["exam_date"],
            "section": draft["section"], "scope": draft["scope"],
            "grade_hint": draft["grade_hint"], "score_info": draft["score_info"],
            "rows": [{k: x[k] for k in ("subject_raw", "question_no", "topic_raw", "topic_id",
                                        "correct_answer", "student_answer", "result",
                                        "is_suspect")} for x in draft["rows"]],
        }
        r = ct.post(f"{base}/import-confirm",
                    data={"payload": json.dumps(payload), "job_id": str(j1["id"])})
        ok7 = r.status_code == 200
        exam_id = r.json()["data"]["exam_id"] if ok7 else None
        check("7a. job_id ile PDF yüklemeden kaydetme 200", ok7, r.text[:250])
        with SessionLocal() as db:
            ex = db.get(ExamResult, exam_id) if exam_id else None
            job = db.get(AiJob, j1["id"])
            check("7b. PDF kanıtı işten deneme kaydına geçti",
                  ex is not None and ex.import_pdf_sha256 == hashlib.sha256(p1).hexdigest(),
                  getattr(ex, "import_pdf_sha256", None))
            check("7c. iş 'consumed' + PDF ve taslak silindi",
                  job.status == "consumed" and job.input_data is None and job.consumed_exam_id == exam_id,
                  f"{job.status} {job.consumed_exam_id}")
        r = ct.post(f"{base}/import-confirm",
                    data={"payload": json.dumps(payload), "job_id": str(j1["id"])})
        check("7d. aynı işle ikinci kayıt 409 job_not_ready",
              r.status_code == 409 and r.json()["detail"]["code"] == "job_not_ready", r.text[:150])
        lst = ct.get("/api/v2/me/ai-jobs").json()
        check("7e. kaydedilen iş listeden düştü", all(i["id"] != j1["id"] for i in lst["items"]), lst)

        # 8) kayıt sonrası aynı PDF
        r = ct.post(f"{base}/import-jobs", files={"file": fpdf(p1)})
        check("8. kaydedilmiş PDF yeniden yüklenemez (409 duplicate_exam)",
              r.status_code == 409 and r.json()["detail"]["code"] == "duplicate_exam", r.text[:150])

        # 9) başka koç başkasının işiyle kaydedemez
        r = co.post(f"/api/v2/teacher/students/{sids[0]}/exams/import-confirm",
                    data={"payload": json.dumps(payload), "job_id": str(j1["id"])})
        check("9. başka koç bu öğrenciye kaydedemez (404)", r.status_code == 404, r.status_code)

        # 10) servis hatası → ücretsiz başarısız → yeniden dene
        behavior.update(mode="unavailable", delay=0.2)
        before = exam_credits(uids)
        r = ct.post(f"/api/v2/teacher/students/{sids[1]}/exams/import-jobs", files={"file": fpdf(pdf_bytes())})
        j2 = r.json()
        d2 = wait_status(ct, j2["id"], {"done", "failed"})
        jb = d2.get("job", {})
        check("10a. servis hatası → 'failed' + ai_unavailable + yeniden denenebilir",
              jb.get("status") == "failed" and jb.get("error_code") == "ai_unavailable"
              and jb.get("retryable") is True, jb)
        check("10b. başarısız okumada kredi düşmedi", exam_credits(uids) == before, exam_credits(uids))
        check("10c. başarısızlık bildirimi gitti", any(t == "Karne okunamadı" for _, t in pushes), pushes)
        behavior.update(mode="ok")
        r = ct.post(f"/api/v2/me/ai-jobs/{j2['id']}/retry")
        d2 = wait_status(ct, j2["id"], {"done", "failed"})
        check("10d. yeniden dene → okundu + şimdi kredi düştü",
              r.status_code == 200 and d2.get("job", {}).get("status") == "done"
              and exam_credits(uids) == before + 6, f"{r.status_code} {d2.get('job')}")

        # 11) okunamayan belge → yeniden denenemez
        behavior.update(mode="unreadable")
        r = ct.post(f"/api/v2/teacher/students/{sids[2]}/exams/import-jobs", files={"file": fpdf(pdf_bytes())})
        j3 = r.json()
        d3 = wait_status(ct, j3["id"], {"done", "failed"})
        check("11a. okunamayan belge → pdf_unreadable, yeniden denenemez",
              d3.get("job", {}).get("error_code") == "pdf_unreadable"
              and d3["job"]["retryable"] is False, d3.get("job"))
        r = ct.post(f"/api/v2/me/ai-jobs/{j3['id']}/retry")
        check("11b. retry 409 not_retryable", r.status_code == 409, r.status_code)
        r = ct.post(f"/api/v2/me/ai-jobs/{j3['id']}/dismiss")
        check("11c. vazgeç → listeden düşer",
              r.status_code == 200 and all(i["id"] != j3["id"] for i in ct.get("/api/v2/me/ai-jobs").json()["items"]),
              r.text[:150])

        # 12) çoklu yükleme (sıra) — 4 öğrenci art arda
        behavior.update(mode="ok", delay=0.8)
        many = []
        t0 = time.time()
        for sid in sids[1:5]:
            if sid == sids[1]:
                continue
            r = ct.post(f"/api/v2/teacher/students/{sid}/exams/import-jobs", files={"file": fpdf(pdf_bytes())})
            many.append(r.json().get("id"))
        r = ct.post(f"/api/v2/teacher/students/{sids[4]}/exams/import-jobs", files={"file": fpdf(pdf_bytes())})
        many.append(r.json().get("id"))
        quick = time.time() - t0
        res = [wait_status(ct, j, {"done", "failed"}, 30).get("job", {}).get("status") for j in many]
        check("12. art arda 4 karne yüklemesi hızlı döner ve hepsi okunur",
              quick < 2.5 and res == ["done"] * 4, f"{quick:.2f}s {res}")

        # 13) koşan iş vazgeçilemez
        behavior.update(delay=2.0)
        r = ct.post(f"/api/v2/teacher/students/{sids[3]}/exams/import-jobs", files={"file": fpdf(pdf_bytes())})
        jr = r.json()["id"]
        r = ct.post(f"/api/v2/me/ai-jobs/{jr}/dismiss")
        check("13. okunurken vazgeç 409 job_running", r.status_code == 409, r.status_code)
        wait_status(ct, jr, {"done", "failed"})
        behavior.update(delay=0.2)

        # 14) sunucu yeniden başladı: nabzı kesik iş devralınır
        stale_pdf = pdf_bytes()
        with SessionLocal() as db:
            old = datetime.now(timezone.utc) - timedelta(minutes=5)
            sj = AiJob(kind="exam_import", owner_id=cid, student_id=sids[2], coach_id=cid,
                       status="running", stage="Okunuyor", params_json="{}",
                       input_data=stale_pdf, input_sha256=hashlib.sha256(stale_pdf).hexdigest(),
                       attempts=1, heartbeat_at=old, started_at=old,
                       expires_at=datetime.now(timezone.utc) + timedelta(days=7))
            dead = AiJob(kind="exam_import", owner_id=cid, student_id=sids[2], coach_id=cid,
                         status="running", stage="Okunuyor", params_json="{}",
                         input_data=pdf_bytes(), attempts=2, heartbeat_at=old, started_at=old,
                         expires_at=datetime.now(timezone.utc) + timedelta(days=7))
            db.add_all([sj, dead])
            db.commit()
            sj_id, dead_id = sj.id, dead.id
        ct.get("/api/v2/me/ai-jobs")  # bakım tetiklenir
        d14 = wait_status(ct, sj_id, {"done", "failed"})
        check("14a. nabzı kesik iş devralındı ve okundu",
              d14.get("job", {}).get("status") == "done", d14.get("job"))
        d15 = ct.get(f"/api/v2/me/ai-jobs/{dead_id}").json()
        check("14b. deneme sınırını aşan iş 'server_restarted' + yeniden denenebilir",
              d15["job"]["status"] == "failed" and d15["job"]["error_code"] == "server_restarted"
              and d15["job"]["retryable"] is True, d15["job"])

        # 15) öğrenci kendi yükler → koça da bildirim
        pushes.clear()
        r = cs.post("/api/v2/student/exams/import-jobs", files={"file": fpdf(pdf_bytes())})
        js = r.json()
        ds = wait_status(cs, js["id"], {"done", "failed"})
        check("15a. öğrenci yüklemesi okundu (own_upload)",
              ds.get("job", {}).get("status") == "done" and ds["job"]["own_upload"] is True, ds.get("job"))
        check("15b. bildirim öğrenciye ve koça gitti",
              (sids[0], "Karne okundu") in pushes and (cid, "Öğrencin karne yükledi") in pushes, pushes)
        check("15c. koçun listesinde öğrencinin işi yok (yalnız yükleyen)",
              all(i["id"] != js["id"] for i in ct.get("/api/v2/me/ai-jobs").json()["items"]))

        # 16) 7 gün temizliği
        with SessionLocal() as db:
            ex_job = db.get(AiJob, js["id"])
            ex_job.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.commit()
        cs.get("/api/v2/me/ai-jobs")
        with SessionLocal() as db:
            check("16. süresi dolan taslak silindi", db.get(AiJob, js["id"]) is None)

        # 17) eski tek istekli uç hâlâ çalışır
        r = ct.post(f"/api/v2/teacher/students/{sids[4]}/exams/import-analyze",
                    files={"file": fpdf(pdf_bytes())})
        check("17. eski tek-istekli analiz ucu 200 + taslak",
              r.status_code == 200 and len(r.json().get("rows") or []) == 12, r.text[:150])
    finally:
        ai_exam_import.read_exam_pdf_double, svc.gemini.generate, push_notifications.safe_push = orig
        time.sleep(0.5)
        with SessionLocal() as db:
            db.execute(sa_delete(AiJob).where(AiJob.owner_id.in_(uids)))
            exam_ids = [e.id for e in db.query(ExamResult).filter(ExamResult.student_id.in_(sids)).all()]
            if exam_ids:
                db.execute(sa_delete(ExamResultQuestion).where(
                    ExamResultQuestion.exam_result_id.in_(exam_ids)))
                db.execute(sa_delete(ExamResult).where(ExamResult.id.in_(exam_ids)))
            db.execute(sa_delete(ExamTopicAlias).where(ExamTopicAlias.created_by_id.in_(uids)))
            db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id.in_(uids)))
            db.execute(sa_delete(CreditAccount).where(
                CreditAccount.owner_id.in_(uids), CreditAccount.owner_type == "user"))
            db.execute(sa_delete(User).where(User.id.in_(uids)))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAILED: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
