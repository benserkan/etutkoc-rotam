"""Rol-bazlı talep sistemi (SupportRequest) — kapsamlı smoke (5+5+5).

Katılımcılar: 1 süper admin · 5 kurum (her biri 1 kurum yöneticisi + 1 öğretmen)
· 5 bağımsız koç.

Yönler:
  D1  Bağımsız koç → Süper Admin            (5 koç)
  D2  Kurum yöneticisi → Süper Admin         (5 yönetici)
  D3  Kuruma bağlı öğretmen → Kurum yöneticisi (5 öğretmen, kendi kurumuna)

Her yön için: oluştur → (muhatap) incele → cevapla → (talep eden) yanıtla →
(muhatap) çözümle. Ayrıca: geri çekme, tenant izolasyonu (kurum A yöneticisi
kurum B öğretmeninin talebini görmez/açamaz), yetki (koçun gelen kutusu yok;
öğretmen kendi talebini incele/çözümle yapamaz), sayımlar.
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.main import app
from app.models import (
    Institution,
    SupportRequest,
    SupportRequestMessage,
    User,
    UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

PFX = f"supp_{secrets.token_hex(3)}"
PWD = hash_password("SupportTest!23")
PWDH = "SupportTest!23"
now = datetime.now(timezone.utc)

passed = 0
failed: list[str] = []
ctx: dict = {}


def check(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(f"{label} -- {detail}")
        print(f"  [FAIL] {label}  ({detail})")


def _code(r):
    try:
        return (r.json().get("detail", {}) or {}).get("code")
    except Exception:
        return None


def setup():
    with SessionLocal() as db:
        sa = User(email=f"{PFX}_admin@test.invalid", password_hash=PWD,
                  full_name=f"{PFX} SuperAdmin", role=UserRole.SUPER_ADMIN,
                  institution_id=None, is_active=True,
                  password_changed_at=now, must_change_password=False)
        db.add(sa); db.flush()
        ctx["super_admin"] = sa.id

        inst_ids, admin_ids, teacher_ids = [], [], []
        for i in range(5):
            inst = Institution(name=f"{PFX} Kurum {i}", slug=f"{PFX}-k{i}",
                               plan="etut_standart", is_active=True)
            db.add(inst); db.flush()
            inst_ids.append(inst.id)
            adm = User(email=f"{PFX}_adm{i}@test.invalid", password_hash=PWD,
                       full_name=f"{PFX} Yönetici {i}", role=UserRole.INSTITUTION_ADMIN,
                       institution_id=inst.id, is_active=True,
                       password_changed_at=now, must_change_password=False)
            tch = User(email=f"{PFX}_tch{i}@test.invalid", password_hash=PWD,
                       full_name=f"{PFX} Öğretmen {i}", role=UserRole.TEACHER,
                       institution_id=inst.id, is_active=True,
                       password_changed_at=now, must_change_password=False)
            db.add(adm); db.add(tch); db.flush()
            admin_ids.append(adm.id); teacher_ids.append(tch.id)

        coach_ids = []
        for i in range(5):
            c = User(email=f"{PFX}_coach{i}@test.invalid", password_hash=PWD,
                     full_name=f"{PFX} Koç {i}", role=UserRole.TEACHER,
                     institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
            db.add(c); db.flush()
            coach_ids.append(c.id)

        db.commit()
        ctx.update(inst_ids=inst_ids, admin_ids=admin_ids,
                   teacher_ids=teacher_ids, coach_ids=coach_ids)


def login(email_local):
    # Çok sayıda login (16 kullanıcı) testclient IP'sinde rate-limit'e takılmasın.
    get_login_limiter().reset()
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{email_local}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {email_local}: {r.status_code} {r.text}")
    return c


def _create(cli, subject, body, category="other"):
    r = cli.post("/api/v2/support/requests", json={"subject": subject, "body": body, "category": category})
    return r


def _ids_in(items):
    return {it["id"] for it in items}


def main() -> int:
    print(f"\n=== ROL-BAZLI TALEP SİSTEMİ (5+5+5) — {PFX} ===\n")
    get_login_limiter().reset()
    setup()
    try:
        sa = login("admin")

        # ── D1: Bağımsız koç → Süper Admin ──
        print("D1 — Bağımsız koç → Süper Admin:")
        coach_clis = [login(f"coach{i}") for i in range(5)]
        coach_reqs = []
        ok_create = True
        for i, cc in enumerate(coach_clis):
            r = _create(cc, f"Koç sorunu {i}", f"Koç {i} mesaj gövdesi", "technical")
            ok_create = ok_create and r.status_code == 200
            if r.status_code == 200:
                d = r.json()["data"]
                coach_reqs.append(d["id"])
                if i == 0:
                    check("D1.1 oluştur → audience=super_admin + status=Açık + 1 mesaj",
                          d["audience"] == "super_admin" and d["status"] == "open"
                          and d["message_count"] == 1 and d["is_mine"] is True, f"{d}")
        check("D1.2 5 koç talebi oluşturuldu (200)", ok_create and len(coach_reqs) == 5, f"{len(coach_reqs)}")

        inbox = sa.get("/api/v2/support/inbox").json()
        check("D1.3 süper admin gelen kutusu 5 koç talebini içerir",
              set(coach_reqs).issubset(_ids_in(inbox["items"])), f"inbox={len(inbox['items'])}")

        rid = coach_reqs[0]
        r = sa.post(f"/api/v2/support/requests/{rid}/review")
        check("D1.4 süper admin incele → Değerlendiriliyor",
              r.status_code == 200 and r.json()["data"]["status"] == "under_review", f"{r.text[:120]}")
        r = sa.post(f"/api/v2/support/requests/{rid}/reply", json={"body": "Süper admin cevabı"})
        check("D1.5 süper admin cevapla → Cevaplandı + handled_by atandı",
              r.status_code == 200 and r.json()["data"]["status"] == "answered"
              and r.json()["data"]["handled_by_name"], f"{r.text[:120]}")
        d = coach_clis[0].get(f"/api/v2/support/requests/{rid}").json()
        check("D1.6 koç detayda admin cevabını görür (2 mesaj)",
              d["message_count"] == 2 and any(not m["is_me"] for m in d["messages"]), f"{d.get('message_count')}")
        r = coach_clis[0].post(f"/api/v2/support/requests/{rid}/reply", json={"body": "Koç ek soru"})
        check("D1.7 koç tekrar yazdı → yeniden Değerlendiriliyor",
              r.status_code == 200 and r.json()["data"]["status"] == "under_review", f"{r.text[:120]}")
        r = sa.post(f"/api/v2/support/requests/{rid}/resolve")
        check("D1.8 süper admin çözümle → Çözümlendi + resolved_at",
              r.status_code == 200 and r.json()["data"]["status"] == "resolved"
              and r.json()["data"]["resolved_at"], f"{r.text[:120]}")
        r = coach_clis[0].post(f"/api/v2/support/requests/{rid}/reply", json={"body": "kapanmışa yazma"})
        check("D1.9 kapanan talebe mesaj → 400 request_closed",
              r.status_code == 400 and _code(r) == "request_closed", f"{r.status_code} {r.text[:100]}")

        # geri çekme
        r = coach_clis[1].post(f"/api/v2/support/requests/{coach_reqs[1]}/withdraw")
        check("D1.10 koç talebi geri çek → Geri çekildi",
              r.status_code == 200 and r.json()["data"]["status"] == "withdrawn", f"{r.text[:120]}")

        # ── D2: Kurum yöneticisi → Süper Admin ──
        print("\nD2 — Kurum yöneticisi → Süper Admin:")
        admin_clis = [login(f"adm{i}") for i in range(5)]
        admin_reqs = []
        for i, ac in enumerate(admin_clis):
            r = _create(ac, f"Kurum talebi {i}", f"Yönetici {i} mesajı", "billing")
            if r.status_code == 200:
                d = r.json()["data"]
                admin_reqs.append(d["id"])
                if i == 0:
                    check("D2.1 yönetici talebi → audience=super_admin + kurum bağlamı dolu",
                          d["audience"] == "super_admin" and d["institution_id"] is not None, f"{d}")
        check("D2.2 5 yönetici talebi oluşturuldu", len(admin_reqs) == 5, f"{len(admin_reqs)}")
        inbox = sa.get("/api/v2/support/inbox").json()
        check("D2.3 süper admin gelen kutusu koç+yönetici taleplerini içerir (≥10)",
              set(coach_reqs).issubset(_ids_in(inbox["items"]))
              and set(admin_reqs).issubset(_ids_in(inbox["items"])), f"inbox={len(inbox['items'])}")
        rid = admin_reqs[0]
        sa.post(f"/api/v2/support/requests/{rid}/review")
        r = sa.post(f"/api/v2/support/requests/{rid}/reply", json={"body": "Yöneticiye cevap"})
        r2 = sa.post(f"/api/v2/support/requests/{rid}/resolve")
        check("D2.4 yönetici talebi tam döngü (cevapla→çözümle)",
              r.json()["data"]["status"] == "answered" and r2.json()["data"]["status"] == "resolved",
              f"{r.text[:80]} | {r2.text[:80]}")

        # ── D3: Kuruma bağlı öğretmen → Kurum yöneticisi ──
        print("\nD3 — Kuruma bağlı öğretmen → Kurum yöneticisi:")
        teacher_clis = [login(f"tch{i}") for i in range(5)]
        teacher_reqs = []
        for i, tc in enumerate(teacher_clis):
            r = _create(tc, f"Öğretmen talebi {i}", f"Öğretmen {i} mesajı", "account")
            if r.status_code == 200:
                d = r.json()["data"]
                teacher_reqs.append(d["id"])
                if i == 0:
                    check("D3.1 öğretmen talebi → audience=institution_admin + kurum dolu",
                          d["audience"] == "institution_admin"
                          and d["institution_id"] == ctx["inst_ids"][0], f"{d}")
        check("D3.2 5 öğretmen talebi oluşturuldu", len(teacher_reqs) == 5, f"{len(teacher_reqs)}")

        # her kurum yöneticisi KENDİ öğretmeninin talebini görür
        adm0_inbox = admin_clis[0].get("/api/v2/support/inbox").json()
        check("D3.3 kurum yöneticisi[0] gelen kutusunda kendi öğretmeninin talebi var",
              teacher_reqs[0] in _ids_in(adm0_inbox["items"]), f"{_ids_in(adm0_inbox['items'])}")

        # ── TENANT İZOLASYONU ──
        print("\nTenant izolasyonu:")
        check("İZO.1 yönetici[0] gelen kutusunda BAŞKA kurumun öğretmen talebi YOK",
              teacher_reqs[1] not in _ids_in(adm0_inbox["items"]), f"{teacher_reqs[1]} in inbox!")
        r = admin_clis[1].get(f"/api/v2/support/requests/{teacher_reqs[0]}")
        check("İZO.2 yönetici[1] başka kurumun talebini AÇAMAZ → 404",
              r.status_code == 404, f"{r.status_code}")
        r = admin_clis[1].post(f"/api/v2/support/requests/{teacher_reqs[0]}/review")
        check("İZO.3 yönetici[1] başka kurumun talebini inceleyemez → 404",
              r.status_code == 404, f"{r.status_code}")
        # yöneticinin kendi (süper admin'e) talebi gelen kutusunda görünmez
        adm0_mine = admin_clis[0].get("/api/v2/support/requests").json()
        check("İZO.4 yönetici kendi (süper admin'e) talebini 'Taleplerim'de görür",
              admin_reqs[0] in _ids_in(adm0_mine["items"]), f"{_ids_in(adm0_mine['items'])}")
        check("İZO.5 yöneticinin kendi talebi 'Gelen kutusu'nda görünmez",
              admin_reqs[0] not in _ids_in(adm0_inbox["items"]), "kendi talebi inbox'ta!")

        # öğretmen talebinin tam döngüsü (yönetici muhatap)
        rid = teacher_reqs[0]
        admin_clis[0].post(f"/api/v2/support/requests/{rid}/review")
        r = admin_clis[0].post(f"/api/v2/support/requests/{rid}/reply", json={"body": "Yönetici cevabı"})
        teacher_clis[0].post(f"/api/v2/support/requests/{rid}/reply", json={"body": "Öğretmen yanıtı"})
        r2 = admin_clis[0].post(f"/api/v2/support/requests/{rid}/resolve")
        check("D3.4 öğretmen↔yönetici tam döngü (cevapla→yanıtla→çözümle)",
              r.json()["data"]["status"] == "answered" and r2.json()["data"]["status"] == "resolved",
              f"{r.text[:80]} | {r2.text[:80]}")

        # ── ESC: Kurum yöneticisi → Süper Admin yönlendirme ──
        print("\nYönlendirme (kurum yöneticisi → süper admin):")
        d = admin_clis[2].get(f"/api/v2/support/requests/{teacher_reqs[2]}").json()
        check("ESC.0 kurum yöneticisi can_escalate=True", d.get("can_escalate") is True, f"{d.get('can_escalate')}")
        r = admin_clis[2].post(f"/api/v2/support/requests/{teacher_reqs[2]}/escalate",
                               json={"note": "Teknik/şifre konusu, sizde çözülür"})
        ok = r.status_code == 200 and r.json()["data"]["audience"] == "super_admin" and r.json()["data"]["status"] == "open"
        check("ESC.1 yönlendir → 200 + audience=super_admin + status=Açık", ok, f"{r.text[:140]}")
        d = r.json()["data"] if r.status_code == 200 else {"messages": []}
        check("ESC.2 thread'e yönlendirme notu eklendi",
              any("Yönlendirme" in m["body"] for m in d["messages"]), "not yok")
        inbox = sa.get("/api/v2/support/inbox").json()
        check("ESC.3 süper admin gelen kutusunda yönlendirilen var",
              teacher_reqs[2] in _ids_in(inbox["items"]), "yok")
        adm2_inbox = admin_clis[2].get("/api/v2/support/inbox").json()
        check("ESC.4 yönlendirilen, kurum yöneticisi kutusundan çıktı",
              teacher_reqs[2] not in _ids_in(adm2_inbox["items"]), "hâlâ var")
        r = admin_clis[2].post(f"/api/v2/support/requests/{teacher_reqs[2]}/resolve")
        check("ESC.5 yönlendiren kurum yöneticisi artık çözümleyemez → 404", r.status_code == 404, f"{r.status_code}")
        sa.post(f"/api/v2/support/requests/{teacher_reqs[2]}/review")
        r = sa.post(f"/api/v2/support/requests/{teacher_reqs[2]}/resolve")
        check("ESC.6 süper admin yönlendcileni çözümler → Çözümlendi",
              r.status_code == 200 and r.json()["data"]["status"] == "resolved", f"{r.text[:100]}")
        r = sa.post(f"/api/v2/support/requests/{coach_reqs[2]}/escalate", json={})
        check("ESC.7 süper admin yönlendiremez → 403", r.status_code == 403, f"{r.status_code}")
        r = teacher_clis[3].post(f"/api/v2/support/requests/{teacher_reqs[3]}/escalate", json={})
        check("ESC.8 öğretmen yönlendiremez → 403", r.status_code == 403, f"{r.status_code}")
        r = admin_clis[0].post(f"/api/v2/support/requests/{teacher_reqs[3]}/escalate", json={})
        check("ESC.9 başka kurum yöneticisi yönlendiremez → 404", r.status_code == 404, f"{r.status_code}")

        # ── YETKİ ──
        print("\nYetki kontrolleri:")
        r = coach_clis[2].get("/api/v2/support/inbox")
        check("YET.1 bağımsız koçun gelen kutusu YOK → 403",
              r.status_code == 403, f"{r.status_code}")
        r = coach_clis[2].get(f"/api/v2/support/requests/{coach_reqs[0]}")
        check("YET.2 koç BAŞKA koçun talebini açamaz → 404", r.status_code == 404, f"{r.status_code}")
        r = teacher_clis[1].post(f"/api/v2/support/requests/{teacher_reqs[1]}/review")
        check("YET.3 öğretmen KENDİ talebini incele/çözümle yapamaz → 403 (muhatap değil)",
              r.status_code == 403, f"{r.status_code}")
        r = teacher_clis[1].post(f"/api/v2/support/requests/{teacher_reqs[1]}/resolve")
        check("YET.4 öğretmen kendi talebini çözümleyemez → 403", r.status_code == 403, f"{r.status_code}")

        # ── SAYIMLAR ──
        print("\nSayımlar:")
        # süper admin pending = open+under_review olan super_admin talepleri
        with SessionLocal() as db:
            from app.models import SUPPORT_RECIPIENT_PENDING_STATUSES
            exp = db.query(SupportRequest).filter(
                SupportRequest.audience == "super_admin",
                SupportRequest.status.in_(SUPPORT_RECIPIENT_PENDING_STATUSES)).count()
        inbox = sa.get("/api/v2/support/inbox").json()
        check("SAY.1 süper admin pending_count DB ile tutarlı",
              inbox["pending_count"] == exp, f"api={inbox['pending_count']} db={exp}")
        mine = coach_clis[2].get("/api/v2/support/requests").json()
        check("SAY.2 koç 'Taleplerim' pending_count = açık talepleri",
              mine["pending_count"] == 1 and len(mine["items"]) == 1, f"{mine['pending_count']}/{len(mine['items'])}")
        # kategori seçenekleri dönüyor
        check("SAY.3 kategori seçenekleri dönüyor (≥3)", len(inbox["categories"]) >= 3, f"{len(inbox['categories'])}")

        # ── DOĞRULAMA: validasyon ──
        print("\nValidasyon:")
        r = coach_clis[3].post("/api/v2/support/requests", json={"subject": "", "body": "x"})
        check("VAL.1 boş konu → 400 subject_required", r.status_code == 400 and _code(r) == "subject_required", f"{r.status_code}")
        r = coach_clis[3].post("/api/v2/support/requests", json={"subject": "konu", "body": ""})
        check("VAL.2 boş gövde → 400 body_required", r.status_code == 400 and _code(r) == "body_required", f"{r.status_code}")

    finally:
        with SessionLocal() as db:
            ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if ids:
                reqids = [r[0] for r in db.query(SupportRequest.id).filter(
                    SupportRequest.requester_id.in_(ids)).all()]
                if reqids:
                    db.execute(sa_delete(SupportRequestMessage).where(SupportRequestMessage.request_id.in_(reqids)))
                    db.execute(sa_delete(SupportRequest).where(SupportRequest.id.in_(reqids)))
                db.execute(sa_delete(User).where(User.id.in_(ids)))
            if ctx.get("inst_ids"):
                db.execute(sa_delete(Institution).where(Institution.id.in_(ctx["inst_ids"])))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
