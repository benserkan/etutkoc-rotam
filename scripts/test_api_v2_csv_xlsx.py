"""Smoke: Excel (.xlsx) öğrenci listesi → CSV metni (toplu öğrenci ekleme).

  POST /api/v2/teacher/csv/import/students/xlsx
Dönen metin mevcut CSV ayrıştırıcısıyla (başlık eşanlamları dahil) önizlenir.
"""
from __future__ import annotations

import io
import os
import secrets
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, SuspiciousIp, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PW = "XlsxSmoke!2345"
PFX = f"xlsx_{secrets.token_hex(3)}"
FAILS: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> None:
    print(("  OK   " if cond else "  FAIL ") + label + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        FAILS.append(label)


def _xlsx(rows: list[list]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Liste"
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main() -> int:
    get_login_limiter().reset()
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        t = User(email=f"{PFX}@test.invalid", password_hash=hash_password(PW), full_name="Xlsx Koç",
                 role=UserRole.TEACHER, is_active=True, password_changed_at=now,
                 must_change_password=False, email_verified_at=now)
        s = User(email=f"{PFX}_s@test.invalid", password_hash=hash_password(PW), full_name="Xlsx Öğr",
                 role=UserRole.STUDENT, is_active=True, password_changed_at=now,
                 must_change_password=False, email_verified_at=now)
        db.add_all([t, s])
        db.commit()
        tid, sid = t.id, s.id
    try:
        c = TestClient(app)
        r = c.post("/api/v2/auth/login", json={"email": f"{PFX}@test.invalid", "password": PW})
        assert r.status_code == 200, r.text
        url = "/api/v2/teacher/csv/import/students/xlsx"
        xmime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        data = _xlsx([
            ["Ad Soyad", "E-posta", "Sınıf", "Alan", "Çalışma Şekli", "Telefon", "Şube",
             "Veli Adı", "Veli E-posta", "Veli Telefonu", "Yakınlık"],
            ["Güneş Deri", "gunes@ornek.com", 10, None, None, 5412100591, None,
             "Ercan Deri", "ercan@ornek.com", 5302224860, "Baba"],
            [None, None, None, None, None, None, None, None, None, None, None],
            ["Semih Aydın", "semih@ornek.com", 10.0, None, None, None, None, "Bilge", None, None, "Anne"],
        ])
        r = c.post(url, files={"file": ("liste.xlsx", data, xmime)})
        check("1 xlsx → 200", r.status_code == 200, r.text)
        body = r.json() if r.status_code == 200 else {}
        text = body.get("csv_text", "")
        check("2 sayfa adı + veri satırı (boş satır atlanır)",
              body.get("sheet") == "Liste" and body.get("row_count") == 2, str(body)[:200])
        check("3 telefon tam sayı (5412100591, .0 yok)", "5412100591" in text and "5412100591.0" not in text)
        check("4 sınıf 10.0 → 10", ",10," in text.splitlines()[2])

        r2 = c.post("/api/v2/teacher/csv/import/students/preview", json={"csv_text": text})
        pv = r2.json()
        check("5 önizleme 2 geçerli satır (Türkçe başlıklar tanınır)",
              r2.status_code == 200 and pv.get("valid_count") == 2 and not pv.get("header_errors"),
              str(pv)[:300])

        r = c.post(url, files={"file": ("liste.xls", b"abc", "application/vnd.ms-excel")})
        check("6 .xls → 422 invalid_file_type", r.status_code == 422
              and r.json()["detail"]["code"] == "invalid_file_type")
        r = c.post(url, files={"file": ("bozuk.xlsx", b"not a zip", xmime)})
        check("7 bozuk dosya → 422 xlsx_unreadable", r.status_code == 422
              and r.json()["detail"]["code"] == "xlsx_unreadable")
        r = c.post(url, files={"file": ("bos.xlsx", _xlsx([]), xmime)})
        check("8 boş sayfa → 422 xlsx_empty", r.status_code == 422
              and r.json()["detail"]["code"] == "xlsx_empty")

        c2 = TestClient(app)
        c2.post("/api/v2/auth/login", json={"email": f"{PFX}_s@test.invalid", "password": PW})
        r = c2.post(url, files={"file": ("liste.xlsx", data, xmime)})
        check("9 öğrenci rolü → 403", r.status_code == 403, str(r.status_code))
        r = TestClient(app).post(url, files={"file": ("liste.xlsx", data, xmime)})
        check("10 anonim → 401", r.status_code == 401, str(r.status_code))
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(AuditLog).where(AuditLog.actor_id.in_([tid, sid])))
            db.execute(sa_delete(User).where(User.id.in_([tid, sid])))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()
    print(f"\n{10 - len(FAILS)}/10 passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    raise SystemExit(main())
