"""Süper admin tam kitap tarama işleri smoke (2026-09-29).

Kapsam: rol kapıları · PDF doğrulaması · arka plan iş parçacığı (gerçek) +
sahte boru hattı (Gemini YOK) · ilerleme/sonuç/kapılar · geçici dosya silinir ·
boru hattı hatası → başarısız · koşan iş silinemez · nabzı kesilen iş düşer.
Ayrıca book_pipeline kapı hesabı (count_items_global/series) birim kontrolü.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import os
import secrets
import time
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import User, UserRole
from app.models.book_scan_job import JOB_FAILED, JOB_RUNNING, BookScanJob
from app.services import book_pipeline, book_scan_jobs
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"bscan_{secrets.token_hex(3)}"
PASSWORD = "TestPass123!@xyz"
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


def _pdf(pages: int) -> bytes:
    doc = book_pipeline.fitz.open()
    for i in range(pages):
        doc.new_page().insert_text((72, 72), f"Sayfa {i + 1}")
    data = doc.tobytes()
    doc.close()
    return data


FAKE_RESULT = {
    "book_title": "Sahte Kitap", "publisher": "Sahte Yayın", "subject_hint": "Matematik",
    "page_count": 30, "offset": 0, "mode": "vision",
    "sections": [
        {"label": "Kümeler", "test_count": 6, "source": "scan", "page": 5, "flag": None},
        {"label": "Fonksiyonlar", "test_count": 8, "source": "scan", "page": 17, "flag": "scan_mismatch"},
    ],
    "total_tests": 14,
    "warnings": ["'Fonksiyonlar': iki tarama uyuşmadı (8/7)"],
    "gates": [
        {"code": "unfilled", "label": "Her bölümün test sayısı bulundu", "ok": True, "detail": "Eksik yok."},
        {"code": "scan_agree", "label": "İki bağımsız tarama uyuştu", "ok": False, "detail": "1 bölüm"},
    ],
    "needs_review": True,
    "scan_debug": {"mode": "vision", "passes": []},
}


def _wait(client: TestClient, job_id: int, timeout: float = 20) -> dict:
    end = time.time() + timeout
    body: dict = {}
    while time.time() < end:
        r = client.get(f"/api/v2/admin/book-catalog/scan-jobs/{job_id}")
        body = r.json() if r.status_code == 200 else {}
        if body.get("status") in ("done", "failed"):
            return body
        time.sleep(0.3)
    return body


def main() -> int:
    print(f"\n=== Tam kitap tarama işleri smoke — {PFX} ===\n")
    get_login_limiter().reset()
    with SessionLocal() as db:
        admin = User(email=f"{PFX}_a@test.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Tarama Admin", role=UserRole.SUPER_ADMIN, is_active=True)
        coach = User(email=f"{PFX}_k@test.invalid", password_hash=hash_password(PASSWORD),
                     full_name="Tarama Koç", role=UserRole.TEACHER, is_active=True, plan="solo_pro")
        db.add_all([admin, coach])
        db.commit()
        ids = [admin.id, coach.id]
    orig_run = book_pipeline.run_pipeline
    seen_paths: list[str] = []
    try:
        anon = TestClient(app)
        r = anon.get("/api/v2/admin/book-catalog/scan-jobs")
        check("1. anonim → 401", r.status_code == 401, str(r.status_code))
        kc = TestClient(app)
        kc.post("/api/v2/auth/login", json={"email": f"{PFX}_k@test.invalid", "password": PASSWORD})
        r = kc.post("/api/v2/admin/book-catalog/scan-jobs",
                    files={"file": ("k.pdf", _pdf(3), "application/pdf")})
        check("2. koç → 403", r.status_code == 403, str(r.status_code))

        ac = TestClient(app)
        ac.post("/api/v2/auth/login", json={"email": f"{PFX}_a@test.invalid", "password": PASSWORD})
        r = ac.post("/api/v2/admin/book-catalog/scan-jobs",
                    files={"file": ("x.pdf", b"merhaba dunya", "application/pdf")})
        check("3. PDF olmayan içerik → 422 not_pdf",
              r.status_code == 422 and r.json()["detail"]["code"] == "not_pdf", r.text[:200])

        def fake_run(path, *, toc_pages=12, offset=None, progress=None):
            seen_paths.append(path)
            assert os.path.exists(path)
            if progress:
                progress(40, "Gövde taraması 1. geçiş: 10/30 sayfa")
            return dict(FAKE_RESULT, toc_pages_seen=toc_pages)

        book_pipeline.run_pipeline = fake_run  # type: ignore[assignment]
        r = ac.post("/api/v2/admin/book-catalog/scan-jobs",
                    files={"file": ("345 TYT Mat.pdf", _pdf(30), "application/pdf")},
                    data={"toc_pages": "14"})
        ok = r.status_code == 200
        job = r.json()["data"] if ok else {}
        check("4. PDF yüklendi → iş açıldı (hemen döner, sayfa sayısı okundu)",
              ok and job.get("page_count") == 30 and job.get("status") in ("queued", "running", "done")
              and "admin:book-catalog:scan-jobs" in r.json().get("invalidate", []),
              r.text[:300])
        body = _wait(ac, job.get("id", 0))
        res = body.get("result") or {}
        check("5. arka plan işi bitti → sonuç taslağı + kapılar + needs_review",
              body.get("status") == "done" and body.get("progress") == 100
              and len(res.get("sections", [])) == 2 and res.get("total_tests") == 14
              and any(not g["ok"] for g in res.get("gates", []))
              and body.get("needs_review") is True and "elle incele" in (body.get("stage") or ""),
              str(body)[:300])
        check("6. geçici PDF silindi + toc_pages işe iletildi",
              seen_paths and not os.path.exists(seen_paths[-1]),
              str(seen_paths))
        with SessionLocal() as db:
            j = db.get(BookScanJob, job["id"])
            check("6b. toc_pages kaydedildi (14)", j is not None and j.toc_pages == 14)
        r = ac.get("/api/v2/admin/book-catalog/scan-jobs")
        items = r.json().get("items", []) if r.status_code == 200 else []
        mine = next((i for i in items if i["id"] == job.get("id")), None)
        check("7. liste: özet (bölüm/test/başlık) + oluşturan adı",
              mine is not None and mine["section_count"] == 2 and mine["total_tests"] == 14
              and mine["book_title"] == "Sahte Kitap" and mine["created_by_name"] == "Tarama Admin",
              str(mine))

        def boom(path, **kw):
            raise book_pipeline.PipelineError("no_toc", "İlk 12 sayfada içindekiler bulunamadı")

        book_pipeline.run_pipeline = boom  # type: ignore[assignment]
        r = ac.post("/api/v2/admin/book-catalog/scan-jobs",
                    files={"file": ("bozuk.pdf", _pdf(5), "application/pdf")})
        bj = r.json()["data"]
        body = _wait(ac, bj["id"])
        check("8. boru hattı hatası → başarısız + açıklayıcı mesaj",
              body.get("status") == "failed" and "içindekiler" in (body.get("error") or ""),
              str(body)[:300])

        with SessionLocal() as db:
            j = db.get(BookScanJob, bj["id"])
            j.status = JOB_RUNNING
            j.heartbeat_at = datetime.now(timezone.utc)
            db.commit()
        r = ac.post(f"/api/v2/admin/book-catalog/scan-jobs/{bj['id']}/delete")
        check("9. koşan iş silinemez → 409", r.status_code == 409, str(r.status_code))
        with SessionLocal() as db:
            j = db.get(BookScanJob, bj["id"])
            j.heartbeat_at = datetime.now(timezone.utc) - timedelta(minutes=45)
            db.commit()
        ac.get("/api/v2/admin/book-catalog/scan-jobs")  # listeleme nabzı keseni düşürür
        with SessionLocal() as db:
            j = db.get(BookScanJob, bj["id"])
            check("10. nabzı kesilen iş → başarısız (yeniden yükle mesajı)",
                  j.status == JOB_FAILED and "yeniden" in (j.error or ""), j.status)
        r = ac.post(f"/api/v2/admin/book-catalog/scan-jobs/{bj['id']}/delete")
        r2 = ac.get(f"/api/v2/admin/book-catalog/scan-jobs/{bj['id']}")
        check("11. silme → 200 + sonra 404", r.status_code == 200 and r2.status_code == 404,
              f"{r.status_code}/{r2.status_code}")

        # ===== 12. kapı yardımcıları (birim) =====
        total, gaps = book_pipeline._series_walk([1, 1, 2, 4, 4])
        counts, warns = book_pipeline.count_items_global(
            [(0, [10, 11, 12], True)], {10: [(1, "test")], 11: [(2, "test")], 12: [(3, "test")]},
        )
        check("12. seri-yürüyüş: kopuk zincir yakalanır · sayım 1..3",
              total == 4 and gaps and counts.get(0) == 3 and not warns, f"{total} {gaps} {counts}")
    finally:
        book_pipeline.run_pipeline = orig_run  # type: ignore[assignment]
        with SessionLocal() as db:
            for j in db.query(BookScanJob).filter(BookScanJob.created_by_id.in_(ids)).all():
                if j.file_path and os.path.exists(j.file_path):
                    os.remove(j.file_path)
            db.execute(sa_delete(BookScanJob).where(BookScanJob.created_by_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
            db.commit()
    print(f"\n=== SONUÇ: {passed} PASS / {len(failed)} FAIL ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
