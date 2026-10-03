"""Site asistanı "Rota" smoke (2026-10-03) — ziyaretçi + roller + aktarım + sınır."""
import json
import secrets
import sys
from datetime import datetime

sys.path.insert(0, ".")
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import delete as sa_delete  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AssistantMessage, Institution, SuspiciousIp, User, UserRole  # noqa: E402
from app.models.contact_request import ContactRequest  # noqa: E402
from app.models.sales_prospect import SalesProspect  # noqa: E402
from app.models.support_request import SupportRequest, SupportRequestMessage  # noqa: E402
from app.routes.api_v2 import site_assistant as route  # noqa: E402
from app.services import gemini, site_assistant as sa  # noqa: E402
from app.services.rate_limit import get_login_limiter  # noqa: E402
from app.services.security import hash_password  # noqa: E402

PFX = f"sas_{secrets.token_hex(3)}"
PW = "SiteAsist2026!x"
KEY = f"test{secrets.token_hex(8)}"
PHONE = "0532" + str(secrets.randbelow(10**7)).zfill(7)
passed = 0
failed: list[str] = []


def check(label, cond, extra=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  {extra}")


def mk(db, tag, **kw):
    u = User(email=f"{PFX}_{tag}@test.invalid", password_hash=hash_password(PW), full_name=f"Ada {tag}",
             role=kw.pop("role", UserRole.TEACHER), is_active=True, must_change_password=False,
             password_changed_at=datetime.utcnow(), **kw)
    db.add(u)
    db.flush()
    return u


def login(tag) -> TestClient:
    c = TestClient(app)
    r = c.post("/api/v2/auth/login", json={"email": f"{PFX}_{tag}@test.invalid", "password": PW})
    assert r.status_code == 200, r.text
    return c


orig_generate = gemini.generate
orig_send = route._send_mails
orig_anon = sa.AI_DAILY_ANON
sent: list = []
ids: list[int] = []
inst_id = None
try:
    with SessionLocal() as db:
        t = mk(db, "koc", plan="solo_free")
        mk(db, "ogr", role=UserRole.STUDENT, teacher_id=t.id, grade_level=8)
        inst = Institution(name=f"{PFX} kurum", slug=f"{PFX}-kurum", plan="etut_standart", is_active=True)
        db.add(inst)
        db.flush()
        inst_id = inst.id
        mk(db, "yon", role=UserRole.INSTITUTION_ADMIN, institution_id=inst.id)
        mk(db, "sa", role=UserRole.SUPER_ADMIN)
        db.commit()
        ids = [u.id for u in db.query(User).filter(User.email.like(f"{PFX}_%")).all()]
    route._send_mails = lambda *a, **k: sent.append(a)
    route._ASK_LIMIT.reset()
    route._HANDOFF_LIMIT.reset()

    anon = TestClient(app)

    # 0 — bilgi tabanı + arama
    kb = sa.load_kb()
    check("0a bilgi tabanı yüklendi (elle + rehber)", len(kb) > 80 and any(s["file"].startswith("guide_") for s in kb),
          str(len(kb)))
    top = sa.retrieve("öğrencime kitap nasıl atarım", "teacher", "/teacher/students")
    check("0b koç arama: kitap atama bölümü ilk sırada", top and "atama" in top[0]["title"].lower(),
          str([s["title"] for s in top]))
    check("0c öğrenci kapsamında koç bölümü çıkmaz",
          all("student" in s["audiences"] for s in sa.retrieve("kitap ekle müfredat", "student", None)))
    check("0d sayfa eşleşmesi", sa.page_matches("/teacher/students", "/teacher/students/5/week")
          and not sa.page_matches("/", "/pricing") and sa.page_matches("/", "/"))

    # 1 — ziyaretçi durumu
    r = anon.get("/api/v2/assistant?page=/pricing")
    check("1a oturum anahtarsız ziyaretçi → 422", r.status_code == 422, r.text[:120])
    s = anon.get(f"/api/v2/assistant?page=/pricing&session_key={KEY}").json()
    cids = [c["id"] for c in s["chips"]]
    check("1b ziyaretçi: audience public + paket çipleri + insan çipi",
          s["audience"] == "public" and "human" in cids and any("paket" in c["label"].lower() for c in s["chips"]),
          str(s)[:300])
    check("1c WhatsApp hattı numarası", s["whatsapp"].endswith("5056738561") or len(s["whatsapp"]) >= 11, s["whatsapp"])
    check("1d fiyat sayfası karşılaması paket seçimine yönelik", "paket" in s["greeting"].lower(), s["greeting"])

    # 2 — hazır soru (kredisiz, kural)
    chip = next(c for c in s["chips"] if c["id"] != "human")
    r = anon.post("/api/v2/assistant/ask", json={"session_key": KEY, "page": "/pricing", "chip": chip["id"],
                                                 "label": chip["label"]}).json()
    check("2 ziyaretçi hazır soru → bilgi metni, source=rule", r["source"] == "rule" and len(r["answer"]) > 40, str(r)[:200])

    # 3 — serbest soru (Gemini taklit): bağlantı listeden doğrulanır
    captured = {}

    def fake_ok(parts, **kw):
        captured["prompt"] = parts[0]["text"]
        captured["kw"] = kw
        return json.dumps({"answer": "Rota paketi 25 öğrenciye kadar, aylık 5.000 ₺.", "link": "/pricing",
                           "handoff": False})
    gemini.generate = fake_ok
    r = anon.post("/api/v2/assistant/ask", json={"session_key": KEY, "page": "/pricing",
                                                 "question": "25 öğrencim var hangi paket ve fiyatı ne"}).json()
    check("3a serbest soru → ai + izinli bağlantı", r["source"] == "ai" and (r.get("action") or {}).get("href") == "/pricing",
          str(r))
    check("3b ücretsiz anahtar + hızlı model (kişisel veri yok)",
          captured["kw"].get("personal_data") is False and captured["kw"].get("prefer_fast") is True, str(captured["kw"]))
    check("3c bilgi paketinde fiyatlar ve paket bölümleri var",
          "Patika" in captured["prompt"] and "Paketler ve fiyatlar" in captured["prompt"])
    check("3d kalan hak azaldı", r["ai_left"] == sa.AI_DAILY_ANON - 1, str(r["ai_left"]))
    gemini.generate = lambda parts, **kw: json.dumps({"answer": "Şuraya bak.", "link": "https://kotu.example"})
    r = anon.post("/api/v2/assistant/ask", json={"session_key": KEY, "page": "/", "question": "nasıl üye olurum"}).json()
    check("3e bilgi tabanında olmayan bağlantı düşürülür", r.get("action") is None, str(r))

    # 4 — Gemini çökerse en yakın bölüm
    def boom(*a, **k):
        raise RuntimeError("down")
    gemini.generate = boom
    r = anon.post("/api/v2/assistant/ask", json={"session_key": KEY, "page": "/", "question": "ücretsiz deneme kaç gün"}).json()
    check("4 yapay zekâ yoksa fallback bölüm cevabı", r["source"] == "fallback" and "14" in r["answer"], str(r)[:200])

    # 5 — günlük sınır
    sa.AI_DAILY_ANON = 2
    gemini.generate = fake_ok
    r = anon.post("/api/v2/assistant/ask", json={"session_key": KEY, "question": "paketler ne kadar"}).json()
    check("5 ziyaretçi sınırı dolunca source=limit (yapay zekâ çağrılmaz)", r["source"] == "limit" and r["ai_left"] == 0,
          str(r)[:200])
    sa.AI_DAILY_ANON = orig_anon

    # 6 — ziyaretçi aktarımı: aday + iletişim talebi + e-posta/WhatsApp
    r = anon.post("/api/v2/assistant/handoff", json={"session_key": KEY, "message": "Kurumum için teklif istiyorum",
                                                     "name": "Ayşe"})
    check("6a iletişim bilgisi yoksa 422", r.status_code == 422 and "contact_required" in r.text, r.text[:150])
    r = anon.post("/api/v2/assistant/handoff", json={
        "session_key": KEY, "page": "/pricing", "message": "Kurumum için teklif istiyorum, 15 koçumuz var",
        "name": "Ayşe Deneme", "phone": PHONE,
        "transcript": [{"role": "user", "text": "kurum fiyatı"}, {"role": "assistant", "text": "Etüt Standart..."}]})
    j = r.json()
    check("6b ziyaretçi aktarımı 200 + WhatsApp bağlantısı", r.status_code == 200 and j["whatsapp_url"].startswith("https://wa.me/"),
          r.text[:200])
    with SessionLocal() as db:
        cr = db.query(ContactRequest).filter(ContactRequest.source == "assistant",
                                             ContactRequest.name == "Ayşe Deneme").order_by(ContactRequest.id.desc()).first()
        pr = db.query(SalesProspect).filter(SalesProspect.name == "Ayşe Deneme").first()
    check("6c iletişim talebi (kaynak: asistan) + konuşma dökümü", cr is not None and "kurum fiyatı" in (cr.message or ""),
          str(cr and cr.message)[:200])
    check("6d satış adayı (kurum) oluştu", pr is not None and pr.kind == "institution" and "aday_id" in (cr.message or ""),
          str(pr and pr.kind))
    check("6e e-posta işi: üyelik konusu + iletişim talepleri kutusu",
          sent and sent[-1][1]["topic_label"] == "Üyelik talebi" and sent[-1][1]["inbox_path"] == "/admin/contact-requests",
          str(sent[-1][1] if sent else None)[:200])
    n_before = len(sent)
    r = anon.post("/api/v2/assistant/handoff", json={"session_key": KEY, "message": "spam spam", "name": "Bot",
                                                     "email": "bot@example.com", "website": "http://x"})
    check("6f bal küpü: bot sessizce kabul, kayıt/e-posta yok", r.status_code == 200 and len(sent) == n_before)

    # 7 — koç
    get_login_limiter().reset()
    ck, co, cy, cs = (login(x) for x in ("koc", "ogr", "yon", "sa"))
    s = ck.get(f"/api/v2/assistant?page=/teacher/plan&session_key={KEY}k").json()
    check("7a koç /teacher/plan: hesaba özel paket çipleri", s["audience"] == "teacher"
          and any(c["id"].startswith("pa:") for c in s["chips"]), str(s["chips"]))
    r = ck.post("/api/v2/assistant/ask", json={"session_key": f"{KEY}k", "page": "/teacher/plan", "chip": "pa:which"}).json()
    check("7b koç 'Hangi paket?' hesaptan cevap", r["source"] == "rule" and "öğrenci" in r["answer"], str(r)[:200])
    s2 = ck.get(f"/api/v2/assistant?page=/teacher/library&session_key={KEY}k").json()
    check("7c koç kütüphane sayfasında kitap çipi önde", "kitap" in s2["chips"][0]["label"].lower(), str(s2["chips"]))
    r = ck.post("/api/v2/assistant/handoff", json={"page": "/teacher/plan", "message": "Ödemem geçmiyor yardım"})
    with SessionLocal() as db:
        sr = db.query(SupportRequest).filter(SupportRequest.requester_id == ids[0]).first()
    check("7d koç aktarımı → destek talebi (üyelik)", r.status_code == 200 and sr is not None and sr.category == "billing",
          r.text[:200])

    # 8 — öğrenci
    s = co.get("/api/v2/assistant?page=/student/day").json()
    check("8a öğrenci: anahtarsız da çalışır + öğrenci çipleri", s["audience"] == "student"
          and any("işaret" in c["label"].lower() for c in s["chips"]), str(s)[:200])
    r = co.post("/api/v2/assistant/handoff", json={"page": "/student/day", "message": "Giriş sorunu yaşıyorum"})
    check("8b öğrenci aktarımı → iletişim talebi", r.status_code == 200, r.text[:200])

    # 9 — kurum yöneticisi
    r = cy.post("/api/v2/assistant/handoff", json={"page": "/institution", "message": "Paketimizi yükseltmek istiyoruz"})
    with SessionLocal() as db:
        yid = db.query(User.id).filter(User.email == f"{PFX}_yon@test.invalid").scalar()
        sr2 = db.query(SupportRequest).filter(SupportRequest.requester_id == yid).first()
    check("9a kurum yöneticisi → süper yöneticiye destek talebi", r.status_code == 200 and sr2 is not None
          and sr2.audience == "super_admin", r.text[:200])
    check("9b kurum yöneticisi e-postası süper yönetici kutusuna", sent[-1][1]["inbox_path"] == "/admin/support",
          str(sent[-1][1])[:150])

    # 11 — mobil uygulama kanalı (App Store 3.1.1): kart/web ödemesi ve fiyat yok
    gemini.generate = fake_ok
    banned = ("iyzico", "kartla", "havale", "₺", "web sitesi")
    s = anon.get(f"/api/v2/assistant?page=/&session_key={KEY}m&channel=ios").json()
    texts = [s["greeting"]]
    for c in s["chips"]:
        if c["id"] == "human":
            continue
        texts.append(anon.post("/api/v2/assistant/ask", json={"session_key": f"{KEY}m", "chip": c["id"],
                                                              "channel": "ios"}).json()["answer"])
    leak = [t[:80] for t in texts if any(b in t.lower() for b in banned)]
    check("11a iOS ziyaretçi: hazır cevaplarda ödeme/fiyat geçmiyor", not leak and len(texts) > 3, str(leak))
    anon.post("/api/v2/assistant/ask", json={"session_key": f"{KEY}m", "channel": "ios",
                                            "question": "paketler ne kadar"})
    pr = captured["prompt"]
    check("11b iOS yapay zekâ isteminde fiyat bölümü/özeti yok + uygulama kuralı var",
          "Paketler ve fiyatlar" not in pr and "aylik_tl" not in pr and "iPhone UYGULAMASINDA" in pr, pr[-600:])
    s = ck.get(f"/api/v2/assistant?page=/teacher/plan&session_key={KEY}k&channel=android").json()
    check("11c Android koç Paketim: ödeme çipi yok", all(c["id"] not in ("pa:pay_safe", "pa:payment_failed")
                                                         for c in s["chips"]), str(s["chips"]))
    w = anon.get(f"/api/v2/assistant?page=/&session_key={KEY}m").json()
    check("11d web'de uygulama bölümleri görünmez", all("uygulamada" not in c["label"] for c in w["chips"])
          and not any("(uygulamada)" in x["title"] for x in sa._visible("public", search=True)))

    # 10 — süper yönetici görünümü
    a = cs.get("/api/v2/admin/assistant/messages?days=1").json()
    check("10a süper yönetici: sorular + en çok sorulanlar + aktarım sayısı",
          a["total"] >= 5 and a["handoff_count"] >= 3 and a["top_questions"], str(a)[:200])
    check("10b koç süper yönetici görünümüne giremez", ck.get("/api/v2/admin/assistant/messages").status_code == 403)
    check("10c ziyaretçi giremez", anon.get("/api/v2/admin/assistant/messages").status_code == 401)
finally:
    gemini.generate = orig_generate
    route._send_mails = orig_send
    sa.AI_DAILY_ANON = orig_anon
    with SessionLocal() as db:
        db.execute(sa_delete(AssistantMessage).where(AssistantMessage.session_key.like(f"{KEY}%")))
        if ids:
            db.execute(sa_delete(AssistantMessage).where(AssistantMessage.user_id.in_(ids)))
            rq = [r[0] for r in db.query(SupportRequest.id).filter(SupportRequest.requester_id.in_(ids)).all()]
            if rq:
                db.execute(sa_delete(SupportRequestMessage).where(SupportRequestMessage.request_id.in_(rq)))
                db.execute(sa_delete(SupportRequest).where(SupportRequest.id.in_(rq)))
            emails = [e for (e,) in db.query(User.email).filter(User.id.in_(ids)).all()]
            db.execute(sa_delete(ContactRequest).where(ContactRequest.email.in_(emails)))
            db.execute(sa_delete(User).where(User.id.in_(ids)))
        db.execute(sa_delete(ContactRequest).where(ContactRequest.name.in_(["Ayşe Deneme", "Bot"])))
        db.execute(sa_delete(SalesProspect).where(SalesProspect.name == "Ayşe Deneme"))
        if inst_id:
            db.execute(sa_delete(Institution).where(Institution.id == inst_id))
        db.execute(sa_delete(SuspiciousIp).where(SuspiciousIp.ip == "testclient"))
        db.commit()

print(f"\n=== {passed} passed, {len(failed)} failed ===")
sys.exit(0 if not failed else 1)
