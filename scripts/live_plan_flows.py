"""/teacher/plan uçtan uca canlı test — 9 koç durumu, gerçek tarayıcı (2026-10-03).

Kullanım (dev sunucuları açıkken: :8081 backend, :3000 Next):
    python scripts/live_plan_flows.py [--keep]

Her durum için: sayfa açılır (390px telefon + 1280px masaüstü), durum etiketi,
ana eylem, paket kartları, ödeme penceresi, asistan, yatay taşma ve kırpılmış
metin denetlenir; ekran görüntüleri .shots/plan_*.png. Ödeme penceresinde
"öde" iyzico SANDBOX sayfasına yönlendirmeli (gerçek para yok).
"""
from __future__ import annotations

import os
import secrets
import sys
import time
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, ".")
from playwright.sync_api import sync_playwright  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import Institution, UsageEvent, User, UserRole  # noqa: E402
from app.models.usage import CreditAccount  # noqa: E402
from app.models.payment_transaction import PaymentTransaction  # noqa: E402
from app.models.support_request import SupportRequest, SupportRequestMessage  # noqa: E402
from app.services.security import hash_password  # noqa: E402

BASE = "http://localhost:3000"
PFX = f"lpf{secrets.token_hex(2)}"
PW = "PlanAkis2026!x"
SHOTS = os.path.join(".shots")
os.makedirs(SHOTS, exist_ok=True)
ok: list[bool] = []


def chk(label, cond, extra=""):
    ok.append(bool(cond))
    print(("  OK   " if cond else "  FAIL ") + label + (f"  [{extra}]" if not cond and extra else ""), flush=True)


def mk(db, tag, n_students=0, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PW), full_name=f"Koç {tag}",
             role=kw.pop("role", UserRole.TEACHER), is_active=True, must_change_password=False,
             email_verified_at=datetime.utcnow(), password_changed_at=datetime.utcnow(), **kw)
    db.add(u)
    db.flush()
    for i in range(n_students):
        db.add(User(email=f"{PFX}_{tag}_s{i}@test.invalid", password_hash="x", full_name=f"Öğr {i}",
                    role=UserRole.STUDENT, is_active=True, teacher_id=u.id, grade_level=12,
                    must_change_password=False))
    return u


def setup() -> dict:
    now = datetime.utcnow()
    with SessionLocal() as db:
        inst = Institution(name=f"{PFX} Kurum", slug=f"{PFX}-kurum", plan="etut_standart", is_active=True)
        db.add(inst)
        db.flush()
        mk(db, "trial", 4, plan="solo_trial", trial_ends_at=now + timedelta(days=6), post_trial_plan="solo_elite")
        mk(db, "free", 2, plan="solo_free")
        mk(db, "pend", 5, plan="solo_free", post_trial_plan="solo_pro",
           trial_ends_at=now - timedelta(days=2))
        mk(db, "active", 6, plan="solo_pro", subscription_status="active",
           subscription_period_end=now + timedelta(days=5), subscription_cycle="monthly",
           subscription_platform="iyzico")
        mk(db, "cancel", 3, plan="solo_elite", subscription_status="canceled",
           subscription_period_end=now + timedelta(days=12), subscription_cycle="monthly",
           subscription_platform="iyzico")
        mk(db, "pastdue", 12, plan="solo_elite", subscription_status="past_due",
           subscription_period_end=now - timedelta(days=2), subscription_cycle="monthly",
           subscription_platform="iyzico")
        fail = mk(db, "fail", 2, plan="solo_free")
        mk(db, "over", 7, plan="solo_free")
        mk(db, "inst", 0, institution_id=inst.id)
        db.flush()
        db.add(PaymentTransaction(user_id=fail.id, provider="iyzico", amount=Decimal("2500"),
                                  plan_code="solo_pro", cycle="monthly", status="failed",
                                  status_reason="3D Secure doğrulaması başarısız (mdStatus=0)",
                                  created_at=now - timedelta(minutes=40)))
        db.commit()
        return {"inst": inst.id}


def cleanup(inst_id):
    with SessionLocal() as db:
        ids = [r[0] for r in db.query(User.id).filter(User.email.like(f"{PFX}_%")).all()]
        if ids:
            rq = [r[0] for r in db.query(SupportRequest.id).filter(SupportRequest.requester_id.in_(ids)).all()]
            if rq:
                db.execute(sa_delete(SupportRequestMessage).where(SupportRequestMessage.request_id.in_(rq)))
                db.execute(sa_delete(SupportRequest).where(SupportRequest.id.in_(rq)))
            db.execute(sa_delete(UsageEvent).where(UsageEvent.actor_user_id.in_(ids)))
            db.execute(sa_delete(PaymentTransaction).where(PaymentTransaction.user_id.in_(ids)))
            db.execute(sa_delete(CreditAccount).where(CreditAccount.owner_id.in_(ids)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(Institution).where(Institution.id == inst_id))
        db.commit()


LAYOUT_JS = """() => {
  const sw = document.documentElement.scrollWidth, vw = window.innerWidth;
  const bad = [];
  for (const el of document.querySelectorAll('main *, section *, [role=dialog] *')) {
    const cs = getComputedStyle(el);
    if (cs.textOverflow === 'ellipsis' && el.scrollWidth > el.clientWidth + 1 && el.textContent.trim())
      bad.push(el.textContent.trim().slice(0, 40));
  }
  return {overflow: sw - vw, truncated: bad.slice(0, 5)};
}"""


def login(page, tag):
    page.context.clear_cookies()
    page.goto(f"{BASE}/login")
    page.wait_for_selector("input[type=email]")
    time.sleep(1.5)
    page.fill("input[type=email]", f"{PFX}_{tag}@test.invalid")
    page.fill("input[type=password]", PW)
    page.click("button[type=submit]")
    try:
        page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
    except Exception:  # giriş hız sınırı (dakikada 10) — bekle, yeniden dene
        time.sleep(62)
        page.reload()
        page.wait_for_selector("input[type=email]")
        time.sleep(1.5)
        page.fill("input[type=email]", f"{PFX}_{tag}@test.invalid")
        page.fill("input[type=password]", PW)
        page.click("button[type=submit]")
        page.wait_for_url(lambda u: "/login" not in u, timeout=20000)
    page.goto(f"{BASE}/teacher/plan")
    page.wait_for_selector("text=Paketim", timeout=30000)
    time.sleep(2.5)
    later = page.get_by_role("button", name="Daha sonra")
    if later.count():  # yeni koç hesabında rehber karşılama penceresi
        later.first.click()
        time.sleep(1)


def hero_text(page) -> str:
    return page.locator("section[aria-label='Paket durumu']").inner_text()


def main():
    keep = "--keep" in sys.argv
    meta = setup()
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome")
            mob = b.new_context(viewport={"width": 390, "height": 860}, is_mobile=True, has_touch=True)
            desk = b.new_context(viewport={"width": 1280, "height": 900})
            pm, pd = mob.new_page(), desk.new_page()

            def both(tag, fn):
                for name, page in (("mobil", pm), ("masaüstü", pd)):
                    login(page, tag)
                    lay = page.evaluate(LAYOUT_JS)
                    chk(f"[{tag}/{name}] yatay taşma yok, kırpılmış metin yok",
                        lay["overflow"] <= 0 and not lay["truncated"], str(lay))
                    page.screenshot(path=os.path.join(SHOTS, f"plan_{tag}_{'m' if name == 'mobil' else 'd'}.png"),
                                    full_page=True)
                    fn(page, name)

            # 1 — deneme
            def trial(page, name):
                h = hero_text(page)
                chk(f"[trial/{name}] durum 'Deneme · 6 gün' + 'Rota denemesi' + ana eylem Rota",
                    "Deneme" in h and "Rota denemesi" in h and "Rota ile devam et" in h, h[:200])
                if name == "masaüstü":
                    page.get_by_role("button", name="Rota ile devam et").first.click()
                    page.wait_for_selector("text=Ödemeyi onayla")
                    dlg = page.get_by_role("dialog").inner_text()
                    chk("[trial] ödeme penceresi: Rota · 5.000 ₺ · hemen başlar",
                        "Rota" in dlg and "5.000 ₺" in dlg and "hemen" in dlg, dlg[:200])
                    page.get_by_role("button", name="5.000 ₺ öde").click()
                    page.wait_for_url(lambda u: "localhost" not in u, timeout=30000)
                    chk("[trial] öde → iyzico sandbox ödeme sayfası", "iyzipay" in page.url or "iyzico" in page.url,
                        page.url)
            both("trial", trial)

            # 2 — ücretsiz (2 öğrenci): Patika önerilir
            def free(page, name):
                h = hero_text(page)
                chk(f"[free/{name}] 'Ücretsiz' + 'Yapay zekâ Kapalı' + Patika ile devam et",
                    "Ücretsiz" in h and "Kapalı" in h and "Patika ile devam et" in h, h[:200])
                if name == "masaüstü":
                    page.get_by_role("radio", name="Zirve").first.click()
                    page.wait_for_timeout(300)
                    t = page.locator("#paketler").inner_text()
                    chk("[free] Zirve seçilince içerik + 'Zirve — kartla öde'",
                        "Zirve paketinde neler var?" in t and "Zirve — kartla öde" in t, t[-300:])
                    page.get_by_role("radio", name="Akademik yıl").click()
                    t = page.locator("#paketler").inner_text()
                    chk("[free] akademik yıl: toplam 75.000 ₺", "75.000 ₺" in t, t[-200:])
            both("free", free)

            # 3 — deneme bitti, Patika ödemesi bekleniyor
            def pend(page, name):
                h = hero_text(page)
                chk(f"[pend/{name}] 'Kayıtta Patika paketini seçmiştin' + Patika eylemi",
                    "Patika paketini seçmiştin" in h and "Patika ile devam et" in h, h[:250])
                if name == "masaüstü":
                    tag = page.locator("[role=radio]", has_text="Patika").inner_text()
                    chk("[pend] Patika kartında 'Kayıtta seçtiğin'", "Kayıtta seçtiğin" in tag, tag)
            both("pend", pend)

            # 4 — aktif, 5 gün kaldı → Şimdi yenile; alt paket yok
            def active(page, name):
                h = hero_text(page)
                chk(f"[active/{name}] 'Aktif' + 'Şimdi yenile · 5 gün kaldı'",
                    "Aktif" in h and "Şimdi yenile" in h and "5 gün" in h, h[:250])
                if name == "masaüstü":
                    radios = page.locator("[role=radiogroup][aria-label='Paket seçimi'] [role=radio]").all_inner_texts()
                    chk("[active] Patika (mevcut) + üst paketler; 'Mevcut paketin' etiketi",
                        len(radios) == 3 and "Mevcut paketin" in radios[0], str(radios)[:200])
                    page.get_by_role("button", name="Şimdi yenile").first.click()
                    page.wait_for_selector("text=Ödemeyi onayla")
                    dlg = page.get_by_role("dialog").inner_text()
                    chk("[active] yenileme penceresi: 'Mevcut dönemin bitişinden sonra'",
                        "bitişinden sonra" in dlg, dlg[:250])
                    page.keyboard.press("Escape")
                    page.get_by_role("button", name="Diğer işlemler").click()
                    page.get_by_role("button", name="İptal et").first.click()
                    page.get_by_text("Fiyat yüksek geldi").click()
                    page.get_by_role("dialog").get_by_role("button", name="İptal et").click()
                    page.wait_for_timeout(2500)
                    h = hero_text(page)
                    chk("[active] iptal → 'İptal edildi' + 'İptali geri al'", "İptal edildi" in h and "İptali geri al" in h,
                        h[:200])
                    page.get_by_role("button", name="İptali geri al").click()
                    page.wait_for_timeout(2500)
                    chk("[active] iptali geri al → tekrar 'Aktif'", "Aktif" in hero_text(page))
            both("active", active)

            # 5 — iptal edilmiş
            def cancel(page, name):
                h = hero_text(page)
                chk(f"[cancel/{name}] 'İptal edildi' + bitiş tarihi + 'İptali geri al'",
                    "İptal edildi" in h and "İptali geri al" in h, h[:200])
            both("cancel", cancel)

            # 6 — süresi dolmuş Rota, 12 öğrenci: Rota yenilenir (Patika DEĞİL)
            def pastdue(page, name):
                h = hero_text(page)
                chk(f"[pastdue/{name}] 'Süresi doldu' + 'Rota paketini yenile' (ucuz pakete düşürmez)",
                    "Süresi doldu" in h and "Rota paketini yenile" in h, h[:250])
                if name == "masaüstü":
                    pat = page.locator("[role=radio]", has_text="Patika")
                    chk("[pastdue] Patika 12 öğrenciye yetmiyor → seçilemez",
                        pat.is_disabled() and "yetmiyor" in pat.inner_text(), pat.inner_text())
            both("pastdue", pastdue)

            # 7 — ödemesi geçmemiş: kırmızı kart + tekrar dene + asistan
            def fail(page, name):
                t = page.locator("section[role=alert]").first.inner_text()
                chk(f"[fail/{name}] kırmızı kart '3D Secure doğrulaması tamamlanmadı' + Tekrar dene",
                    "3D Secure" in t and "Tekrar dene" in t, t[:200])
                if name == "mobil":
                    page.get_by_role("button", name="Asistana sor").click()
                    page.wait_for_selector("[role=dialog][aria-label='Paket asistanı']")
                    page.wait_for_timeout(1500)
                    d = page.locator("[role=dialog][aria-label='Paket asistanı']")
                    chk("[fail] asistan açılınca ödeme sorununu söylüyor", "sorun" in d.inner_text(), d.inner_text()[:200])
                    d.get_by_role("button", name="Ödemem neden geçmedi?").click()
                    page.wait_for_timeout(2500)
                    chk("[fail] hazır cevap: SMS kodu + Patika paketini seç eylemi",
                        "SMS" in d.inner_text() and d.get_by_role("button", name="Patika paketini seç").count() == 1,
                        d.inner_text()[-300:])
                    page.screenshot(path=os.path.join(SHOTS, "plan_assistant_m.png"))
                    d.get_by_role("button", name="Bir insanla konuşmak istiyorum").click()
                    d.locator("textarea").fill("Kartım 3D adımında takılıyor, yardım eder misiniz?")
                    d.get_by_role("button", name="Gönder", exact=True).click()
                    page.wait_for_timeout(2500)
                    chk("[fail] 'Bize yaz' → iletildi mesajı", "iletildi" in d.inner_text(), d.inner_text()[-200:])
                    with SessionLocal() as db:
                        u = db.query(User).filter(User.email == f"{PFX}_fail@test.invalid").one()
                        n = db.query(SupportRequest).filter(SupportRequest.requester_id == u.id).count()
                    chk("[fail] destek talebi açıldı (üyelik/ödeme)", n == 1, str(n))
                    page.get_by_role("button", name="Asistanı kapat").click()
                else:
                    page.get_by_role("button", name="Tekrar dene").click()
                    page.wait_for_selector("text=Ödemeyi onayla")
                    dlg = page.get_by_role("dialog").inner_text()
                    chk("[fail] Tekrar dene → aynı paket (Patika · 2.500 ₺)", "Patika" in dlg and "2.500 ₺" in dlg,
                        dlg[:200])
                    page.keyboard.press("Escape")
            both("fail", fail)

            # 8 — ücretsiz ama 7 öğrenci (sınır aşımı)
            def over(page, name):
                h = hero_text(page)
                chk(f"[over/{name}] 'yeni programlama kilitli' + öğrenci sayısı kırmızı",
                    "kilitli" in h and "7 aktif" in h, h[:250])
            both("over", over)

            # 9 — kurum öğretmeni
            def inst(page, name):
                h = hero_text(page)
                chk(f"[inst/{name}] 'Kurum yönetiyor' + paket kartı yok + ödeme eylemi yok",
                    "Kurum yönetiyor" in h and page.locator("#paketler").count() == 0
                    and page.get_by_role("button", name="kartla öde").count() == 0, h[:200])
            both("inst", inst)

            # koyu tema ekran görüntüsü
            dark = b.new_context(viewport={"width": 390, "height": 860}, color_scheme="dark")
            pdk = dark.new_page()
            login(pdk, "trial")
            pdk.screenshot(path=os.path.join(SHOTS, "plan_trial_dark_m.png"), full_page=True)
            login(pdk, "fail")
            pdk.screenshot(path=os.path.join(SHOTS, "plan_fail_dark_m.png"), full_page=True)
            b.close()
    finally:
        if not keep:
            cleanup(meta["inst"])
    print(f"\n{sum(ok)}/{len(ok)} passed")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
