# -*- coding: utf-8 -*-
"""Hedef Havuzu CSV toplu içe aktarma smoke (2026-08-05).

Kritik güvenceler: sabit hat reddedilir · mevcut kayıt EZİLMEZ · dosya içi
tekrar bir kez alınır · opt_in daima False (soğuk liste) · dry_run yazmaz.
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import SalesProspect, SuspiciousIp, User, UserRole
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"imp{secrets.token_hex(3)}"
PASSWORD = "ProspectImport!26"
# Test numaraları: gerçek kişilere denk gelmesin diye 555 000 xx xx bloğu
CSV_OK = """ad,telefon,tur,kurum_adi,eposta,sehir,not
Test Koç Bir,+905550001101,coach,Bir Akademi,bir@t.invalid,Ankara,web araması
Test Kurum İki,05550001102,institution,İki Koçluk,,İstanbul,web araması
Test Koç Üç,555 000 11 03,coach,,,İzmir,
"""


def main() -> int:
    passed = 0
    failed: list[str] = []

    def check(label, cond, detail=""):
        nonlocal passed
        if cond:
            passed += 1
            print(f"  [PASS] {label}")
        else:
            failed.append(label)
            print(f"  [FAIL] {label} ({detail})")

    print(f"\n=== Hedef Havuzu CSV import smoke — {PFX} ===\n")
    with SessionLocal() as db:
        sa = User(email=f"{PFX}-sa@t.invalid", password_hash=hash_password(PASSWORD),
                  full_name="Import Süper", role=UserRole.SUPER_ADMIN,
                  is_active=True, must_change_password=False)
        db.add(sa)
        db.commit()
        db.execute(sa_delete(SalesProspect).where(
            SalesProspect.phone.in_([
                "905550001101", "905550001102", "905550001103", "905550001104"])))
        db.commit()

    get_login_limiter().reset()
    with SessionLocal() as db:
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

    try:
        c = TestClient(app)
        c.post("/api/v2/auth/login",
               json={"email": f"{PFX}-sa@t.invalid", "password": PASSWORD})

        print("1) Yetki + doğrulama")
        r = TestClient(app).post("/api/v2/admin/prospects/import",
                                 json={"csv_text": CSV_OK})
        check("anonim 401", r.status_code == 401, str(r.status_code))
        r = c.post("/api/v2/admin/prospects/import", json={"csv_text": "a,b\n1,2\n"})
        check("ad/telefon sütunu yoksa 422 missing_columns",
              r.status_code == 422
              and r.json()["detail"]["code"] == "missing_columns", r.text[:120])

        print("\n2) dry_run: rapor verir, YAZMAZ")
        r = c.post("/api/v2/admin/prospects/import",
                   json={"csv_text": CSV_OK, "dry_run": True})
        d = r.json()["data"]
        check("dry_run 3 kayıt sayar", r.status_code == 200 and d["created"] == 3, r.text[:150])
        check("önizleme döner", len(d["preview"]) == 3, str(d["preview"]))
        with SessionLocal() as db:
            n = db.query(SalesProspect).filter(
                SalesProspect.phone.like("90555000110%")).count()
            check("DB'ye yazılmadı", n == 0, str(n))

        print("\n3) Gerçek aktarım + normalizasyon")
        r = c.post("/api/v2/admin/prospects/import", json={"csv_text": CSV_OK})
        d = r.json()["data"]
        check("3 kayıt oluştu", d["created"] == 3, str(d))
        with SessionLocal() as db:
            rows = db.query(SalesProspect).filter(
                SalesProspect.phone.like("90555000110%")).all()
            phones = sorted(p.phone for p in rows)
            check("telefonlar E.164'e normalize (3 farklı yazım)",
                  phones == ["905550001101", "905550001102", "905550001103"],
                  str(phones))
            byname = {p.name: p for p in rows}
            check("tür eşlemesi (coach/institution)",
                  byname["Test Koç Bir"].kind == "coach"
                  and byname["Test Kurum İki"].kind == "institution")
            check("opt_in DAİMA False (soğuk liste kuralı)",
                  all(p.opt_in is False for p in rows))
            check("kurum adı + e-posta + şehir taşındı",
                  byname["Test Koç Bir"].org_name == "Bir Akademi"
                  and byname["Test Koç Bir"].email == "bir@t.invalid"
                  and byname["Test Koç Bir"].city == "Ankara")

        print("\n4) Tekrar aktarım: mevcut kayıt EZİLMEZ")
        r = c.post("/api/v2/admin/prospects/import", json={"csv_text": CSV_OK})
        d = r.json()["data"]
        check("hepsi atlandı (skipped_existing=3)",
              d["created"] == 0 and d["skipped_existing"] == 3, str(d))

        print("\n5) Sabit hat + dosya içi tekrar + geçersiz ad")
        csv2 = """ad,telefon
Sabit Hatlı Kurum,02123334455
Tekrar Bir,+905550001104
Tekrar İki,0555 000 11 04
X,+905550001105
"""
        r = c.post("/api/v2/admin/prospects/import", json={"csv_text": csv2})
        d = r.json()["data"]
        check("sabit hat reddedildi (WhatsApp'a uygun değil)",
              any("sabit hat" in i["reason"] for i in d["invalid"]), str(d["invalid"]))
        check("dosya içi tekrar bir kez alındı",
              d["skipped_duplicate"] == 1 and d["created"] == 1, str(d))
        check("kısa ad reddedildi",
              any(i.get("name") == "X" for i in d["invalid"]), str(d["invalid"]))

        print("\n6) Noktalı virgüllü (Excel TR) dosya da okunur")
        r = c.post("/api/v2/admin/prospects/import",
                   json={"csv_text": "ad;telefon\nExcel Koç;+905550001106\n",
                         "dry_run": True})
        check("';' ayracı algılandı", r.json()["data"]["created"] == 1, r.text[:120])
    finally:
        with SessionLocal() as db:
            db.execute(sa_delete(SalesProspect).where(
                SalesProspect.phone.like("90555000110%")))
            db.execute(sa_delete(User).where(User.email.like(f"{PFX}-%")))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print("  FAIL:", f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
