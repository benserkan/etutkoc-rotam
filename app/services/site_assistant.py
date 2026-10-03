"""Site asistanı "Rota" — sitenin her yerinde TEK yapay zekâ asistanı (2026-10-03).

Kim sorarsa sorsun (ziyaretçi, koç, öğrenci, veli, kurum yöneticisi, süper
yönetici) aynı balon; bilgisi role ve bulunulan sayfaya göre değişir.

Katmanlar:
  1. BİLGİ TABANI — app/assistant_kb/*.md (elle yazılmış, rol başına) +
     guide_*.json (Rota rehber anlatımlarından üretilir: scripts/build_assistant_kb.py).
     Asistan YALNIZ bu metinlere + kullanıcının kendi hesap özetine dayanır.
  2. HAZIR SORULAR (çip) — bilgi bölümünden ya da (koçta) paket asistanının
     hesaba özel kurallarından; yapay zekâsız, anında, sınırsız.
  3. SERBEST SORU — soruya en yakın bölümler seçilir (anahtar kelime eşleşmesi),
     Gemini (ücretsiz anahtar, hızlı model) cevaplar. Kredi DÜŞMEZ. Günlük sınır:
     giriş yapan kullanıcı AI_DAILY_USER, ziyaretçi oturumu AI_DAILY_ANON
     (+ aynı IP özeti için AI_DAILY_IP). Gemini yoksa en yakın bölüme düşer.
  4. İNSANA AKTAR — koç ve kurum yöneticisi → destek talebi (+ muhataba e-posta);
     ziyaretçi/öğrenci/veli → iletişim talebi (+ ziyaretçide satış adayı) +
     ekibe e-posta + süper yöneticiye mobil bildirim. WhatsApp hattı her zaman
     ikinci seçenek olarak sunulur.

Kişisel öğrenci verisi (ad vb.) yapay zekâya GİTMEZ — yalnız sayılar.
"""
from __future__ import annotations

import fnmatch
import functools
import hashlib
import json
import logging
import pathlib
import re
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import User, UserRole

logger = logging.getLogger(__name__)

KB_DIR = pathlib.Path(__file__).resolve().parents[1] / "assistant_kb"

AI_DAILY_USER = 40
AI_DAILY_ANON = 15
AI_DAILY_IP = 60
DEFAULT_WHATSAPP = "905056738561"

AUDIENCES = ("public", "teacher", "student", "parent", "institution_admin", "super_admin")

# Dosya → hangi kitleye ait
_FILE_AUD = {
    "public.md": {"public"},
    "teacher.md": {"teacher"},
    "student.md": {"student"},
    "parent.md": {"parent"},
    "institution.md": {"institution_admin"},
    "common.md": {"teacher", "student", "parent", "institution_admin", "super_admin"},
    "guide_teacher.json": {"teacher"},
    "guide_student.json": {"student"},
    "guide_parent.json": {"parent"},
}
# Ek arama kapsamı (çip olarak değil, yalnız bilgi olarak): koç ve yöneticiler
# fiyat/paket sorabilir.
_EXTRA_SEARCH = {
    "teacher": {"public"},
    "institution_admin": {"public"},
    "super_admin": {"public", "teacher", "institution_admin", "student", "parent"},
}

HUMAN_CHIP = {"id": "human", "label": "Bir insanla görüşmek istiyorum"}


def audience_for(user: User | None) -> str:
    if user is None:
        return "public"
    return {
        UserRole.TEACHER: "teacher",
        UserRole.STUDENT: "student",
        UserRole.PARENT: "parent",
        UserRole.INSTITUTION_ADMIN: "institution_admin",
        UserRole.SUPER_ADMIN: "super_admin",
    }.get(user.role, "public")


# =============================================================================
# Bilgi tabanı
# =============================================================================

_META_KEYS = ("chip", "rule", "pages", "link")


def _slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _norm(t)).strip("-")[:50]


def _parse_md(text: str, fname: str) -> list[dict]:
    out: list[dict] = []
    cur: dict | None = None
    in_meta = False
    for line in text.splitlines():
        if line.startswith("## "):
            if cur:
                out.append(cur)
            title = line[3:].strip()
            cur = {"id": f"{fname.split('.')[0]}-{_slug(title)}", "title": title, "body": "",
                   "chip": None, "rule": None, "pages": [], "link": None}
            in_meta = True
            continue
        if cur is None:
            continue
        if in_meta:
            m = re.match(r"^(chip|rule|pages|link):\s*(.+)$", line.strip())
            if m:
                k, v = m.group(1), m.group(2).strip()
                if k == "pages":
                    cur["pages"] = [p.strip() for p in v.split(",") if p.strip()]
                elif k == "link":
                    href, _, label = v.partition("|")
                    cur["link"] = {"href": href.strip(), "label": label.strip() or "Sayfaya git"}
                else:
                    cur[k] = v
                continue
            if not line.strip():
                in_meta = False
                continue
            in_meta = False
        cur["body"] = (cur["body"] + " " + line.strip()).strip()
    if cur:
        out.append(cur)
    return out


@functools.lru_cache(maxsize=1)
def load_kb() -> tuple[dict, ...]:
    sections: list[dict] = []
    for fname, auds in _FILE_AUD.items():
        p = KB_DIR / fname
        if not p.exists():
            continue
        if fname.endswith(".md"):
            items = _parse_md(p.read_text(encoding="utf-8"), fname)
        else:
            items = [{"id": s["id"], "title": s["title"], "body": s["body"], "chip": None,
                      "rule": None, "pages": [], "link": None}
                     for s in json.loads(p.read_text(encoding="utf-8"))]
        for s in items:
            s["audiences"] = set(auds)
            s["file"] = fname
            s["stems_title"] = _stems(s["title"])
            s["stems_body"] = _stems(s["body"])
            sections.append(s)
    return tuple(sections)


# =============================================================================
# Arama (anahtar kelime — Türkçe sadeleştirme + 5 harflik kök)
# =============================================================================

_TR = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
_FOLD = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c", "â": "a", "î": "i", "û": "u"})
_STOP = {
    "ve", "ile", "bir", "bu", "su", "da", "de", "mi", "mu", "ne", "nasil", "icin", "gibi", "var",
    "yok", "ben", "sen", "biz", "siz", "o", "ki", "en", "daha", "cok", "ama", "veya", "ya",
    "neden", "nedir", "nerede", "hangi", "kac", "olur", "olarak", "olan", "her", "tum", "benim",
    "bana", "sana", "yapabilir", "miyim", "musun", "mi", "istiyorum", "lazim", "gerek",
}


def _norm(t: str) -> str:
    return (t or "").translate(_TR).lower().translate(_FOLD)


def _stems(t: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", _norm(t))
    return {w[:5] for w in words if len(w) >= 3 and w not in _STOP}


def page_matches(pattern: str, path: str) -> bool:
    if not path:
        return False
    if pattern == "/":
        return path == "/"
    if "*" in pattern:
        return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern + "/*")
    return path == pattern or path.startswith(pattern.rstrip("/") + "/")


def _visible(audience: str, *, search: bool) -> list[dict]:
    auds = {audience} | (_EXTRA_SEARCH.get(audience, set()) if search else set())
    return [s for s in load_kb() if s["audiences"] & auds]


def retrieve(question: str, audience: str, page: str | None, k: int = 6) -> list[dict]:
    q = _stems(question)
    scored: list[tuple[float, int, dict]] = []
    for i, s in enumerate(_visible(audience, search=True)):
        sc = 0.0
        for w in q:
            if w in s["stems_title"]:
                sc += 3
            elif w in s["stems_body"]:
                sc += 1
        on_page = any(page_matches(p, page or "") for p in s["pages"])
        if on_page:
            sc += 1.5
        if audience not in s["audiences"]:   # ek kapsam (ör. koçta ziyaretçi bölümleri)
            sc *= 0.8
        if sc > 0:
            scored.append((sc, -i, s))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    picked = [s for _, _, s in scored[:k]]
    if not picked:   # hiç eşleşme yoksa sayfanın bölümleri
        picked = [s for s in _visible(audience, search=False)
                  if any(page_matches(p, page or "") for p in s["pages"])][:3]
    return picked


# =============================================================================
# Hesap özeti (yapay zekâya giden kişisel-olmayan sayılar)
# =============================================================================

def _pricing_facts() -> dict:
    from app.services import pricing
    cat = pricing.get_pricing_catalog()
    return {
        "bagimsiz_koc_paketleri": [
            {"ad": t.get("label"), "ogrenci_siniri": t.get("max_students") or "sınırsız",
             "aylik_tl": t.get("monthly"), "akademik_yil_aylik_tl": t.get("annual_monthly"),
             "akademik_yil_toplam_tl": t.get("annual_total")}
            for t in cat["solo"]["tiers"]
        ],
        "ucretsiz_paket": {"ad": "Keşif", "ogrenci_siniri": cat["solo"]["free"]["students"],
                           "yapay_zeka": "kapalı"},
        "deneme_gun": cat["solo"]["trial_days"],
        "akademik_yil_ay": cat.get("annual_paid_months"),
        "akademik_yil_indirim_yuzde": cat.get("annual_discount_pct"),
        "kurum_kademeleri": [
            {"ad": t.get("label"), "koc": f"{t.get('min_coaches')}-{t.get('max_coaches') or 've üstü'}",
             "aylik_toplam_tl": None if t.get("price_hidden") else t.get("monthly_total")}
            for t in cat["institution"]["tiers"]
        ] if cat.get("institution") else [],
        "kredi_maliyetleri": cat.get("credit_costs") or [],
    }


def account_facts(db: Session, user: User | None, audience: str) -> dict:
    try:
        if audience == "public":
            return {"fiyatlar": _pricing_facts()}
        if audience == "teacher":
            from app.services import plan_assistant as pa
            return pa._facts_for_ai(pa.build_state(db, user))
        if audience == "student":
            from app.models import Task, TaskStatus
            today = date.today()
            q = db.query(Task).filter(Task.student_id == user.id, Task.date == today,
                                      Task.is_draft.is_(False))
            total = q.count()
            done = q.filter(Task.status == TaskStatus.COMPLETED).count()
            return {"bugun_gorev": total, "bugun_tamamlanan": done,
                    "koc_var": bool(user.teacher_id)}
        if audience == "parent":
            from app.models import ParentStudentLink
            n = db.query(ParentStudentLink).filter(ParentStudentLink.parent_id == user.id).count()
            return {"bagli_cocuk_sayisi": n}
        if audience == "institution_admin":
            from app.services.plans import PLAN_CATALOG
            inst = user.institution
            teachers = db.query(func.count(User.id)).filter(
                User.institution_id == user.institution_id, User.role == UserRole.TEACHER,
                User.is_active.is_(True)).scalar()
            pi = PLAN_CATALOG.get(getattr(inst, "plan", None) or "")
            return {"kurum_paketi": pi.label if pi else getattr(inst, "plan", None),
                    "aktif_ogretmen": int(teachers or 0), "fiyatlar": _pricing_facts()}
    except Exception:  # noqa: BLE001 — özet yoksa asistan yine çalışır
        logger.warning("assistant facts failed", exc_info=True)
    return {}


# =============================================================================
# Karşılama + hazır sorular
# =============================================================================

def _first_name(user: User | None) -> str:
    n = ((user.full_name or "") if user else "").strip().split(" ")
    return n[0] if n and n[0] else ""


def _teacher_state(db: Session, user: User) -> dict | None:
    try:
        from app.services import plan_assistant as pa
        return pa.build_state(db, user)
    except Exception:  # noqa: BLE001
        logger.warning("plan state failed", exc_info=True)
        return None


def greeting(db: Session, user: User | None, audience: str, page: str | None,
             tstate: dict | None = None) -> str:
    name = _first_name(user)
    hi = f"Merhaba {name}!" if name else "Merhaba!"
    if audience == "public":
        if page and page.startswith("/pricing"):
            return ("Merhaba! Ben Rota, ETÜTKOÇ Rotam'ın asistanıyım. Paket seçmene yardım "
                    "edeyim: kaç öğrencinle çalışıyorsun? Fiyat, deneme ya da ödeme hakkında "
                    "da sorabilirsin; istersen ekibimize bağlarım.")
        return ("Merhaba! Ben Rota, ETÜTKOÇ Rotam'ın asistanıyım. Sistemin nasıl çalıştığını, "
                "paketleri ve ücretsiz denemeyi anlatabilirim; istersen ekibimize de bağlarım.")
    if audience == "teacher" and tstate and page and page.startswith("/teacher/plan"):
        from app.services import plan_assistant as pa
        return pa.greeting_for(tstate)
    if audience == "student":
        return f"{hi} Görevlerini işaretlemekten deneme yüklemeye kadar sistemle ilgili her şeyi sorabilirsin."
    if audience == "parent":
        return (f"{hi} Paneli, raporları ve bildirim ayarlarını anlatabilirim. Çocuğunuzun "
                "çalışmasıyla ilgili sorular için çocuğunuzun sayfasındaki Rota kartını kullanın.")
    if audience == "institution_admin":
        return f"{hi} Kurum panelindeki sayıları, öğretmen eklemeyi ya da paketinizi sorabilirsiniz."
    return f"{hi} Sistemle ilgili ne sormak istersin?"


def chips(db: Session, user: User | None, audience: str, page: str | None,
          tstate: dict | None = None, limit: int = 5) -> list[dict]:
    allowed_rules: set[str] = set()
    if audience == "teacher" and tstate:
        from app.services import plan_assistant as pa
        allowed_rules = {c["id"] for c in pa.chips_for(tstate)}
        if page and page.startswith("/teacher/plan"):
            return [{"id": f"pa:{c['id']}", "label": c["label"]} for c in pa.chips_for(tstate)
                    if c["id"] != "human"][:limit] + [HUMAN_CHIP]
    on_page: list[dict] = []
    rest: list[dict] = []
    for s in _visible(audience, search=False):
        if not s["chip"]:
            continue
        if s["rule"] and s["rule"] not in allowed_rules:
            continue
        item = {"id": f"pa:{s['rule']}" if s["rule"] else s["id"], "label": s["chip"]}
        (on_page if any(page_matches(p, page or "") for p in s["pages"]) else rest).append(item)
    seen: set[str] = set()
    out = []
    for c in on_page + rest:
        if c["id"] in seen:
            continue
        seen.add(c["id"])
        out.append(c)
    return out[:limit] + [HUMAN_CHIP]


def _section_by_id(sid: str) -> dict | None:
    return next((s for s in load_kb() if s["id"] == sid), None)


def _link_action(link: dict | None) -> dict | None:
    return {"type": "link", "href": link["href"], "label": link["label"]} if link else None


def rule_answer(db: Session, user: User | None, audience: str, chip: str,
                tstate: dict | None = None) -> dict:
    if chip == "human":
        return {"answer": ("Tabii. Aşağıdan mesajını bırakırsan bu konuşmayla birlikte ekibimize "
                           "iletilir; istersen WhatsApp'tan da yazabilirsin."),
                "action": {"type": "handoff", "label": "Ekibe yaz"}}
    if chip.startswith("pa:"):
        if audience == "teacher" and tstate:
            from app.services import plan_assistant as pa
            res = pa.rule_answer(chip[3:], tstate)
            act = res.get("action")
            if act and act.get("type") == "handoff":
                act = {"type": "handoff", "label": "Ekibe yaz"}
            return {"answer": res["answer"], "action": act}
        return {"answer": "Bu soru giriş yapmış koçlar içindir.", "action": None}
    s = _section_by_id(chip)
    vis = _visible(audience, search=True)
    if not s or s not in vis:
        return {"answer": "Bunu bulamadım; kendi cümlenle sorabilirsin.", "action": None}
    return {"answer": s["body"], "action": _link_action(s["link"])}


# =============================================================================
# Serbest soru (Gemini)
# =============================================================================

_ROLE_TR = {
    "public": "siteyi inceleyen bir ziyaretçi (henüz üye değil; büyük olasılıkla eğitim koçu ya da kurum yetkilisi)",
    "teacher": "bir eğitim koçu (öğretmen)",
    "student": "bir öğrenci (ortaokul ya da lise, LGS/YKS hazırlığı)",
    "parent": "bir veli",
    "institution_admin": "bir kurum yöneticisi (etüt merkezi, dershane ya da okul)",
    "super_admin": "platformun süper yöneticisi",
}
_HITAP = {"parent": "siz", "institution_admin": "siz"}

_PROMPT = """Sen "Rota"sın: ETÜTKOÇ Rotam adlı eğitim koçluğu platformunun yardım asistanı.
Şu an seninle konuşan: {role}. Bulunduğu sayfa: {page}.

KURALLAR:
- YALNIZ aşağıdaki BİLGİ BÖLÜMLERİ ve HESAP ÖZETİ'ni kullan. Orada olmayan özellik,
  fiyat, indirim, tarih, kampanya ya da kural UYDURMA. Bilmiyorsan dürüstçe söyle ve
  ekibe bağlanmayı (handoff) öner.
- Türkçe, sıcak, sade yaz; 2-6 kısa cümle. Kullanıcıya "{hitap}" diye hitap et.
  "Merhaba" ile başlama. Teknik kod/alan adı yazma.
- "Nasıl yapılır" sorularında adımları menü adlarıyla anlat; uygun bir sayfa varsa
  "link" alanına O BÖLÜMLERDEKİ bağlantılardan birini koy (başka adres yazma).
- Fiyatları "2.500 ₺" biçiminde yaz. Kişisel tavsiye verirken hesap özetindeki sayıları kullan.
- Konu bu platformla ilgisizse kibarca yalnız platform hakkında yardım edebildiğini söyle.
- Üyelik satın alma, özel fiyat, kurum teklifi, ödeme sorunu, hesap erişim sorunu gibi
  insan gerektiren durumlarda handoff=true yap.
{extra}
Sadece şu JSON'u döndür:
{{"answer": "<cevap>", "link": null | "<bağlantı>", "handoff": true | false{plan_field}}}

BİLGİ BÖLÜMLERİ:
{sections}

HESAP ÖZETİ:
{facts}

ÖNCEKİ KONUŞMA (eskiden yeniye):
{history}

SORU: {question}
"""


def ai_answer(question: str, history: list[dict], *, audience: str, page: str | None,
              sections: list[dict], facts: dict, tstate: dict | None = None) -> dict:
    """Gemini cevabı — DB'siz saf fonksiyon (çağıran işlemi önce kapatır)."""
    from app.services import gemini

    links = {s["link"]["href"]: s["link"]["label"] for s in sections if s.get("link")}
    sec_txt = "\n\n".join(
        f"### {s['title']}\n{s['body'][:1800]}"
        + (f"\nBağlantı: {s['link']['href']} ({s['link']['label']})" if s.get("link") else "")
        for s in sections
    ) or "(bu soruya uygun bölüm bulunamadı)"
    hist = "\n".join(
        f"{'Kullanıcı' if h.get('role') == 'user' else 'Rota'}: {str(h.get('text', ''))[:500]}"
        for h in history[-8:]
    ) or "(yok)"
    teacher_plan = audience == "teacher" and tstate is not None
    prompt = _PROMPT.format(
        role=_ROLE_TR.get(audience, "bir kullanıcı"), page=page or "-",
        hitap=_HITAP.get(audience, "sen"),
        extra=("- Koç paket önermek istersen yalnız öğrenci sayısına YETEN paketin kodunu 'plan' alanına koy.\n"
               if teacher_plan else ""),
        plan_field=(', "plan": null | "<paket kodu>"' if teacher_plan else ""),
        sections=sec_txt, facts=json.dumps(facts, ensure_ascii=False, default=str)[:6000],
        history=hist, question=question[:800],
    )
    raw = gemini.generate([{"text": prompt}], personal_data=False, json_mode=True,
                          max_output_tokens=8192, prefer_fast=True, timeout=30.0)
    data = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(data, list):
        data = data[0] if data else {}
    data = data or {}
    answer = str(data.get("answer") or "").strip()
    if not answer:
        raise ValueError("empty answer")
    action = None
    if teacher_plan and data.get("plan"):
        from app.services import plan_assistant as pa
        action = pa._clean_action({"type": "select_plan", "plan": data.get("plan")}, tstate)
    link = data.get("link")
    if action is None and isinstance(link, str) and link in links:
        action = {"type": "link", "href": link, "label": links[link]}
    if action is None and data.get("handoff") is True:
        action = {"type": "handoff", "label": "Ekibe yaz"}
    return {"answer": answer[:1800], "action": action}


def fallback_answer(question: str, audience: str, page: str | None) -> dict:
    hits = retrieve(question, audience, page, k=1)
    if hits:
        s = hits[0]
        return {"answer": s["body"][:900], "action": _link_action(s["link"])}
    return {"answer": ("Bunu şu an yanıtlayamadım. Hazır sorulardan birini seçebilir ya da "
                       "ekibimize yazabilirsin."),
            "action": {"type": "handoff", "label": "Ekibe yaz"}}


# =============================================================================
# Kayıt + günlük sınır
# =============================================================================

def ip_hash(ip: str | None) -> str | None:
    if not ip:
        return None
    from app.config import settings
    return hashlib.sha256(f"{settings.session_secret}:{ip}".encode()).hexdigest()


def _day_start() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def ai_left(db: Session, *, user: User | None, session_key: str, iph: str | None) -> int:
    from app.models import AssistantMessage as AM
    base = db.query(func.count(AM.id)).filter(AM.source == "ai", AM.created_at >= _day_start())
    if user is not None:
        used = base.filter(AM.user_id == user.id).scalar() or 0
        return max(0, AI_DAILY_USER - int(used))
    used_s = base.filter(AM.session_key == session_key, AM.user_id.is_(None)).scalar() or 0
    left = AI_DAILY_ANON - int(used_s)
    if iph:
        used_ip = base.filter(AM.ip_hash == iph, AM.user_id.is_(None)).scalar() or 0
        left = min(left, AI_DAILY_IP - int(used_ip))
    return max(0, left)


def log_message(db: Session, *, user: User | None, session_key: str, iph: str | None,
                audience: str, page: str | None, chip: str | None, question: str,
                answer: str | None, source: str, handoff: bool = False) -> None:
    from app.models import AssistantMessage
    db.add(AssistantMessage(
        session_key=session_key[:64], user_id=user.id if user else None, ip_hash=iph,
        audience=audience, page=(page or "")[:200] or None, chip=(chip or None),
        question=question[:800], answer=(answer or "")[:1800] or None, source=source,
        handoff=handoff,
    ))


def purge_old(db: Session, *, now: datetime, days: int = 180) -> int:
    from datetime import timedelta
    from app.models import AssistantMessage
    n = db.query(AssistantMessage).filter(
        AssistantMessage.created_at < now - timedelta(days=days)).delete(synchronize_session=False)
    return int(n or 0)


def whatsapp_number() -> str:
    try:
        from app.services import pricing
        w = str(pricing.get_pricing_catalog().get("contact", {}).get("whatsapp") or "")
        digits = re.sub(r"\D", "", w)
        if len(digits) >= 10:
            return digits if digits.startswith("90") else "90" + digits.lstrip("0")
    except Exception:  # noqa: BLE001
        pass
    return DEFAULT_WHATSAPP


# =============================================================================
# Ekibe aktarım alıcıları
# =============================================================================

def super_admin_recipients(db: Session) -> tuple[list[str], list[int]]:
    rows = db.query(User.id, User.email).filter(
        User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True)).all()
    emails = {e for (_, e) in rows if e}
    try:
        from app.services import pricing
        sales = str(pricing.get_pricing_catalog().get("contact", {}).get("sales_email") or "")
        if "@" in sales:
            emails.add(sales)
    except Exception:  # noqa: BLE001
        pass
    return sorted(emails), [i for (i, _) in rows]


def topic_is_membership(texts: list[str]) -> bool:
    blob = _norm(" ".join(texts))
    return any(k in blob for k in ("paket", "odeme", "uyelik", "abonelik", "fiyat", "kredi",
                                   "fatura", "kart", "iptal", "yenile", "teklif", "deneme sur"))
