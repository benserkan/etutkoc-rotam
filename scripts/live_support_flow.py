"""CANLI talep akışı testi — gerçek çalışan sunuculara HTTP + cookie jar ile.

Tarayıcının kullandığı birebir yolu sürer: POST /api/v2/auth/login → cookie →
/api/v2/support/* (vars. Next.js :3000 → rewrite → FastAPI). Her kullanıcı için
ayrı httpx.Client (ayrı cookie jar = ayrı tarayıcı oturumu).

Kullanım:  python scripts/live_support_flow.py [BASE_URL]
  varsayılan BASE_URL = http://127.0.0.1:3000  (Next.js dev → rewrite → 8081)

3 akış (trafik izlenir — kim gönderir / kim görür / ne yanıt):
  A) Bağımsız koç → Süper Admin (cevap koça geri döner)
  B) Kuruma bağlı öğretmen → Kurum yöneticisi (kurum içi çözüm)
  C) Öğretmen → Kurum yöneticisi → YÖNLENDİR → Süper Admin
     (yönlendiren talebi görmeye DEVAM eder + süper admin cevabını görür)
"""
from __future__ import annotations

import sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import secrets
from datetime import datetime, timezone

import httpx
from sqlalchemy import delete as sa_delete

from app.database import SessionLocal
from app.models import (
    Institution,
    SupportAttachment,
    SupportRequest,
    SupportRequestMessage,
    User,
    UserRole,
)
from app.models.suspicious_ip import SuspiciousIp
from app.services.rate_limit import get_login_limiter
from app.services.security import hash_password

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:3000"
PFX = f"live_{secrets.token_hex(3)}"
PWD = hash_password("LiveSupport!23")
PWDH = "LiveSupport!23"
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


def traffic(line: str):
    print(f"     ↪ {line}")


def setup():
    get_login_limiter().reset()
    with SessionLocal() as db:
        sa = User(email=f"{PFX}_sa@test.invalid", password_hash=PWD, full_name=f"{PFX} SüperAdmin",
                  role=UserRole.SUPER_ADMIN, institution_id=None, is_active=True,
                  password_changed_at=now, must_change_password=False)
        db.add(sa); db.flush()
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-k", plan="etut_standart", is_active=True)
        db.add(inst); db.flush()
        adm = User(email=f"{PFX}_adm@test.invalid", password_hash=PWD, full_name=f"{PFX} Yönetici",
                   role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id, is_active=True,
                   password_changed_at=now, must_change_password=False)
        tch = User(email=f"{PFX}_tch@test.invalid", password_hash=PWD, full_name=f"{PFX} Öğretmen",
                   role=UserRole.TEACHER, institution_id=inst.id, is_active=True,
                   password_changed_at=now, must_change_password=False)
        coach = User(email=f"{PFX}_coach@test.invalid", password_hash=PWD, full_name=f"{PFX} Koç",
                     role=UserRole.TEACHER, institution_id=None, is_active=True, plan="solo_pro",
                     password_changed_at=now, must_change_password=False)
        db.add_all([adm, tch, coach]); db.commit()
        ctx.update(inst_id=inst.id)


def login(local) -> httpx.Client:
    get_login_limiter().reset()
    c = httpx.Client(base_url=BASE, timeout=30.0, follow_redirects=False)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{local}@test.invalid", "password": PWDH})
    if r.status_code != 200:
        raise RuntimeError(f"login {local} @ {BASE}: {r.status_code} {r.text[:200]}")
    return c


def create(cli, subject, body, category="other"):
    return cli.post("/api/v2/support/requests", json={"subject": subject, "body": body, "category": category})


def ids(items):
    return {it["id"] for it in items}


def msgs_text(cli, rid):
    d = cli.get(f"/api/v2/support/requests/{rid}").json()
    return [m["body"] for m in d.get("messages", [])], d


def main() -> int:
    print(f"\n=== CANLI TALEP AKIŞI — BASE={BASE} — {PFX} ===\n")
    setup()
    try:
        sa = login("sa"); adm = login("adm"); tch = login("tch"); coach = login("coach")

        # Tazelik kontrolü: yeni alanlar var mı (stale backend tespiti)
        r = create(coach, "Tazelik kontrolü", "alan kontrolü")
        fresh = r.status_code == 200 and "can_manage" in (r.json().get("data") or {})
        check("0. backend güncel kod (can_manage alanı mevcut)", fresh,
              f"status={r.status_code} — :8081 STALE olabilir, sunucuyu yeniden başlatın")
        if r.status_code == 200:
            coach.post(f"/api/v2/support/requests/{r.json()['data']['id']}/withdraw")

        # ── AKIŞ A: Bağımsız koç → Süper Admin ──
        print("\nAKIŞ A — Bağımsız koç → Süper Admin:")
        r = create(coach, "Giriş yapamıyorum", "Şifremi sıfırlayın lütfen", "account")
        A = r.json()["data"]["id"]
        traffic(f"KOÇ → SüperAdmin talep #{A} gönderdi (Açık)")
        inbox = sa.get("/api/v2/support/inbox").json()
        check("A1 süper admin koç talebini görür", A in ids(inbox["items"]), "görmüyor")
        traffic("SüperAdmin gelen kutusunda görüyor")
        sa.post(f"/api/v2/support/requests/{A}/review")
        sa.post(f"/api/v2/support/requests/{A}/reply", json={"body": "Şifreniz sıfırlandı, e-postanıza bakın."})
        traffic("SüperAdmin → KOÇ cevap yazdı (Cevaplandı)")
        bodies, _ = msgs_text(coach, A)
        check("A2 KOÇ süper admin cevabını GÖRÜR (cevap geri döndü)",
              any("Şifreniz sıfırlandı" in b for b in bodies), "cevap koça düşmedi")
        traffic("KOÇ cevabı gördü ✓")
        coach.post(f"/api/v2/support/requests/{A}/reply", json={"body": "Teşekkürler, oldu."})
        r = sa.post(f"/api/v2/support/requests/{A}/resolve")
        check("A3 süper admin çözümledi → Çözümlendi", r.json()["data"]["status"] == "resolved", "")

        # ── AKIŞ B: Öğretmen → Kurum yöneticisi (kurum içi) ──
        print("\nAKIŞ B — Kuruma bağlı öğretmen → Kurum yöneticisi:")
        r = create(tch, "Sınıf listem eksik", "3 öğrenci görünmüyor", "technical")
        B = r.json()["data"]["id"]
        traffic(f"ÖĞRETMEN → KurumYöneticisi talep #{B} (Açık)")
        adm_inbox = adm.get("/api/v2/support/inbox").json()
        sa_inbox = sa.get("/api/v2/support/inbox").json()
        check("B1 kurum yöneticisi görür, süper admin GÖRMEZ (tenant)",
              B in ids(adm_inbox["items"]) and B not in ids(sa_inbox["items"]), "yönlendirme hatası")
        traffic("KurumYöneticisi görüyor; SüperAdmin görmüyor (doğru)")
        adm.post(f"/api/v2/support/requests/{B}/review")
        adm.post(f"/api/v2/support/requests/{B}/reply", json={"body": "Liste düzeltildi, kontrol edin."})
        traffic("KurumYöneticisi → ÖĞRETMEN cevap")
        bodies, _ = msgs_text(tch, B)
        check("B2 ÖĞRETMEN kurum yöneticisi cevabını görür",
              any("Liste düzeltildi" in b for b in bodies), "cevap öğretmene düşmedi")
        adm.post(f"/api/v2/support/requests/{B}/resolve")
        traffic("KurumYöneticisi çözümledi")

        # ── AKIŞ C: Öğretmen → Kurum yöneticisi → YÖNLENDİR → Süper Admin ──
        print("\nAKIŞ C — Öğretmen → Kurum yöneticisi → YÖNLENDİR → Süper Admin:")
        r = create(tch, "Sisteme hiç giremiyorum", "Hesabım kilitli, teknik konu", "technical")
        C = r.json()["data"]["id"]
        traffic(f"ÖĞRETMEN → KurumYöneticisi talep #{C} (Açık)")
        r = adm.post(f"/api/v2/support/requests/{C}/escalate",
                     json={"note": "Teknik/şifre konusu, sizde çözülür"})
        check("C1 kurum yöneticisi yönlendirdi → audience super_admin",
              r.status_code == 200 and r.json()["data"]["audience"] == "super_admin", f"{r.text[:120]}")
        traffic("KurumYöneticisi → SüperAdmin YÖNLENDİRDİ (not ekledi)")
        adm_inbox = adm.get("/api/v2/support/inbox").json()
        check("C2 YÖNLENDİREN kurum yöneticisinin kutusunda KALIR (boşalmaz!)",
              C in ids(adm_inbox["items"]), "kutudan kayboldu — ESKİ BUG")
        traffic("KurumYöneticisi yönlendirdiğini hâlâ görüyor (izleme) ✓")
        sa_inbox = sa.get("/api/v2/support/inbox").json()
        check("C3 süper admin yönlendirileni görür", C in ids(sa_inbox["items"]), "süper admin görmüyor")
        r = adm.post(f"/api/v2/support/requests/{C}/resolve")
        check("C4 yönlendiren artık çözümleyemez → 404", r.status_code == 404, f"{r.status_code}")
        sa.post(f"/api/v2/support/requests/{C}/review")
        sa.post(f"/api/v2/support/requests/{C}/reply", json={"body": "Hesap kilidi açıldı, tekrar deneyin."})
        traffic("SüperAdmin → cevap yazdı")
        bodies, _ = msgs_text(adm, C)
        check("C5 YÖNLENDİREN kurum yöneticisi süper admin cevabını GÖRÜR (cevap geri düştü!)",
              any("Hesap kilidi açıldı" in b for b in bodies), "cevap yönlendirene düşmedi — ESKİ BUG")
        traffic("KurumYöneticisi süper admin cevabını gördü ✓")
        bodies, _ = msgs_text(tch, C)
        check("C6 TALEP EDEN öğretmen de süper admin cevabını görür",
              any("Hesap kilidi açıldı" in b for b in bodies), "cevap öğretmene düşmedi")
        traffic("ÖĞRETMEN süper admin cevabını gördü ✓")
        r = sa.post(f"/api/v2/support/requests/{C}/resolve")
        check("C7 süper admin çözümledi → Çözümlendi", r.json()["data"]["status"] == "resolved", "")

        # ── AKIŞ D: Dosya eki + profil linki + rol rengi ──
        print("\nAKIŞ D — Dosya eki + profil linki + rol(renk):")
        r = create(coach, "Faturamda hata var", "Ekteki faturayı inceleyin", "billing")
        D = r.json()["data"]["id"]
        PNG = b"\x89PNG\r\n\x1a\nLIVE-FATURA-PNG"
        r = coach.post(f"/api/v2/support/requests/{D}/attachments",
                       files={"file": ("fatura.png", PNG, "image/png")})
        det = r.json().get("data", {}) if r.status_code == 200 else {}
        atts = det.get("attachments", [])
        check("D1 koç dosya ekledi → 200 + ek listede (is_image)",
              r.status_code == 200 and len(atts) == 1 and atts[0]["is_image"], f"status={r.status_code} {r.text[:120]}")
        traffic("KOÇ talebe fatura.png ekledi")
        if atts:
            url = atts[0]["download_url"]
            rr = coach.get(url)
            check("D2 yükleyen dosyayı indirir → içerik birebir",
                  rr.status_code == 200 and rr.content == PNG, f"{rr.status_code}")
            rr = tch.get(url)
            check("D3 yetkisiz (taraf olmayan) indiremez → 404", rr.status_code == 404, f"{rr.status_code}")
            rr = sa.get(url)
            check("D4 muhatap süper admin indirir → 200", rr.status_code == 200, f"{rr.status_code}")
        dd = sa.get(f"/api/v2/support/requests/{D}").json()
        m0 = dd["messages"][0]
        check("D5 gönderen rol(renk) + tıklanabilir profil linki (süper admin görünümü)",
              m0.get("sender_role") == "teacher" and (m0.get("sender_profile_url") or "").startswith("/admin/users/"),
              f"role={m0.get('sender_role')} url={m0.get('sender_profile_url')}")
        traffic("SüperAdmin: koç mesajı 'teacher' renginde + isim → /admin/users/ profil linki")

        # ── Sayfa render kontrolü (yalnız :3000'e karşı anlamlı) ──
        if BASE.endswith(":3000"):
            print("\nSayfa render (Next.js :3000):")
            for path, who in [("/teacher/support", coach), ("/institution/support", adm),
                              ("/institution/support-inbox", adm), ("/admin/support", sa)]:
                rr = who.get(path, follow_redirects=True)
                check(f"PAGE {path} → 200 (render)", rr.status_code == 200, f"{rr.status_code}")

        for c in (sa, adm, tch, coach):
            c.close()

    finally:
        with SessionLocal() as db:
            uids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
            if uids:
                rids = [r[0] for r in db.query(SupportRequest.id).filter(SupportRequest.requester_id.in_(uids)).all()]
                if rids:
                    db.execute(sa_delete(SupportAttachment).where(SupportAttachment.request_id.in_(rids)))
                    db.execute(sa_delete(SupportRequestMessage).where(SupportRequestMessage.request_id.in_(rids)))
                    db.execute(sa_delete(SupportRequest).where(SupportRequest.id.in_(rids)))
                db.execute(sa_delete(User).where(User.id.in_(uids)))
            if ctx.get("inst_id"):
                db.execute(sa_delete(Institution).where(Institution.id == ctx["inst_id"]))
            db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip.in_(["testclient", "127.0.0.1"])))
            db.commit()

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
