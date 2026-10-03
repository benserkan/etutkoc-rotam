"""Paket asistanı — /teacher/plan için canlı yardım (2026-10-03).

İki katman:
  1. HAZIR SORULAR (çip) — koçun GERÇEK hesap durumundan kurulan, yapay
     zekâsız, anında ve her zaman doğru cevaplar ("Hangi paket bana uygun?",
     "Deneme bitince ne olur?", "Ödemem neden geçmedi?" …). Kredi/limit yok.
  2. SERBEST SORU — Gemini; YALNIZ sunucunun topladığı bilgi paketini görür
     (fiyatlar katalogdan, durum hesaptan). Uydurma fiyat/kural yasak; emin
     değilse insana yönlendirir. Koç başına günde PA_DAILY_LIMIT soru, kredi
     DÜŞMEZ (0 kredilik ölçüm satırı). Gemini yoksa en yakın hazır cevaba düşer.
  + İNSANA AKTAR — konuşma dökümüyle süper admine "Üyelik / ödeme" destek
     talebi açılır (mevcut destek sistemi).

Kişisel öğrenci verisi pakete GİRMEZ (yalnız sayılar + plan durumu).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import User

PA_DAILY_LIMIT = 30
_ABANDON_AFTER = timedelta(minutes=15)
_ISSUE_WINDOW = timedelta(days=7)


def _now() -> datetime:
    return datetime.utcnow()


def _fmt_tl(n: int | float) -> str:
    return f"{int(round(n)):,}".replace(",", ".") + " ₺"


def _fmt_int(n: int | float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def _fmt_date(d: datetime | None) -> str:
    return d.strftime("%d.%m.%Y") if d else ""


# =============================================================================
# Ödeme sorunu + yenileme günü (plan sayfası da kullanır)
# =============================================================================

_REASON_RULES: list[tuple[tuple[str, ...], str, str]] = [
    (("limit", "bakiye", "insufficient", "funds"),
     "Kartının limiti ya da bakiyesi yetersiz görünüyor",
     "Başka bir kartla dene ya da bankandan kart limitini kontrol et."),
    (("3d", "mdstatus", "doğrulama", "dogrulama", "authentication", "sms"),
     "3D Secure doğrulaması tamamlanmadı",
     "Bankanın gönderdiği SMS kodunu girerek tekrar dene. Kod gelmiyorsa bankanı ara."),
    (("fraud", "şüpheli", "supheli", "güvenlik", "guvenlik", "risk"),
     "Bankan ödemeyi güvenlik nedeniyle durdurdu",
     "Bankanı arayıp internet alışverişine izin verdiğini söyle, sonra tekrar dene."),
    (("internet", "e-ticaret", "eticaret", "online", "sanal"),
     "Kartın internet alışverişine kapalı",
     "Mobil bankacılıktan internet alışverişini açıp tekrar dene."),
    (("expire", "son kullanma", "geçersiz", "gecersiz", "invalid", "kart numara", "cvc", "cvv"),
     "Kart bilgisi kabul edilmedi",
     "Kart numarasını, son kullanma tarihini ve güvenlik kodunu kontrol ederek tekrar dene."),
]


def humanize_payment_reason(raw: str | None) -> tuple[str, str]:
    t = (raw or "").lower()
    for keys, title, detail in _REASON_RULES:
        if any(k in t for k in keys):
            return title, detail
    return ("Ödeme bankan tarafından onaylanmadı",
            "Tekrar dene. Aynı hata sürerse başka bir kart kullan ya da asistandan bize yaz.")


def _plan_label(code: str | None) -> str | None:
    if not code:
        return None
    from app.services.plans import PLAN_CATALOG
    pi = PLAN_CATALOG.get(code)
    if pi:
        return pi.label
    if code.startswith(("credit_", "pack_")):
        return "Ek yapay zekâ kredisi"
    return code


def payment_issue_for(db: Session, user: User) -> dict | None:
    """Son 7 gündeki EN SON ödeme denemesi sorunluysa sade dille anlat."""
    from app.models.payment_transaction import (
        CYCLE_ANNUAL, CYCLE_ONE_TIME, STATUS_3DS_PENDING, STATUS_FAILED,
        STATUS_PENDING, PaymentTransaction,
    )
    tx = (
        db.query(PaymentTransaction)
        .filter(PaymentTransaction.user_id == user.id,
                PaymentTransaction.created_at >= _now() - _ISSUE_WINDOW)
        .order_by(PaymentTransaction.created_at.desc(), PaymentTransaction.id.desc())
        .first()
    )
    if tx is None:
        return None
    created = tx.created_at.replace(tzinfo=None) if tx.created_at else _now()
    if tx.status == STATUS_FAILED:
        kind = "failed"
        title, detail = humanize_payment_reason(tx.status_reason)
    elif tx.status in (STATUS_PENDING, STATUS_3DS_PENDING) and created < _now() - _ABANDON_AFTER:
        kind = "abandoned"
        title = "Ödeme yarım kaldı"
        detail = ("Ödeme sayfası kapatılmış ya da yarıda kalmış; kartından para çekilmedi. "
                  "Paketi seçip tekrar ödeyebilirsin.")
    else:
        return None
    cycle = ("academic_year" if tx.cycle == CYCLE_ANNUAL
             else "one_time" if tx.cycle == CYCLE_ONE_TIME else "monthly")
    return {
        "kind": kind,
        "title": title,
        "detail": detail,
        "plan_code": tx.plan_code,
        "plan_label": _plan_label(tx.plan_code),
        "cycle": cycle,
        "occurred_at": created.isoformat(),
    }


def renewal_days_left(user: User) -> int | None:
    """Aktif (iptal edilmemiş) web aboneliğinin bitişine kalan gün."""
    if getattr(user, "subscription_status", None) != "active":
        return None
    if getattr(user, "subscription_platform", None) == "app_store":
        return None
    end = getattr(user, "subscription_period_end", None)
    if end is None:
        return None
    secs = (end.replace(tzinfo=None) - _now()).total_seconds()
    return max(0, math.ceil(secs / 86400))


# =============================================================================
# Durum paketi (hazır cevaplar + yapay zekâ ortak)
# =============================================================================

def build_state(db: Session, user: User) -> dict[str, Any]:
    from app.routes.api_v2.teacher import _build_plan_response
    from app.services import pricing

    plan = _build_plan_response(db, user).model_dump()
    cat = pricing.get_pricing_catalog()
    cards = {c.get("plan"): c for c in cat.get("cards", [])}
    tiers = []
    for t in cat["solo"]["tiers"]:
        c = cards.get(t["code"]) or {}
        tiers.append({
            "code": t["code"],
            "label": t.get("label") or _plan_label(t["code"]),
            "max_students": t.get("max_students"),
            "monthly_try": t.get("monthly"),
            "ai_credits_monthly": c.get("credits_monthly"),
            "badge": c.get("badge"),
        })
    return {
        "plan": plan,
        "tiers": tiers,
        "annual_paid_months": int(cat.get("annual_paid_months") or 10),
        "trial_days": int(cat["solo"]["trial_days"]),
        "free_students": int(cat["solo"]["free"]["students"]),
        "credit_costs": cat.get("credit_costs") or [],
        "credit_packs": cat.get("credit_packs") or [],
    }


def _tier(state: dict, code: str | None) -> dict | None:
    return next((t for t in state["tiers"] if t["code"] == code), None)


def _fits(t: dict, n: int) -> bool:
    return t["max_students"] is None or n <= int(t["max_students"])


def _cap(t: dict) -> str:
    return "sınırsız öğrenci" if t["max_students"] is None else f"{t['max_students']} öğrenciye kadar"


def suggested_plan(state: dict) -> dict | None:
    """Önerilen paket: (ödeme bekleyen/yenilenecek) mevcut ya da kayıtta seçilen
    paket öğrenci sayısına yetiyorsa o; yetmiyorsa yeten en küçük paket."""
    p = state["plan"]
    n = int(p["student_count"])
    pref = None
    if p["status"] in ("active", "past_due", "payment_required") and _tier(state, p["plan_code"]):
        pref = p["plan_code"]
    elif p.get("post_trial_plan") and _tier(state, p["post_trial_plan"]):
        pref = p["post_trial_plan"]
    t = _tier(state, pref) if pref else None
    if t and _fits(t, n):
        return t
    return next((x for x in state["tiers"] if _fits(x, n)), None)


# =============================================================================
# Hazır sorular (çipler)
# =============================================================================

CHANNELS = ("web", "ios", "android")


def _is_app(channel: str) -> bool:
    return channel in ("ios", "android")


def chips_for(state: dict, channel: str = "web") -> list[dict[str, str]]:
    p = state["plan"]
    st = p["status"]
    app = _is_app(channel)
    out: list[dict[str, str]] = []
    if p.get("last_payment_issue") and not app:
        out.append({"id": "payment_failed", "label": "Ödemem neden geçmedi?"})
    if not p["is_solo"]:
        return [{"id": "managed", "label": "Paketimi kim yönetiyor?"},
                {"id": "human", "label": "Bir insanla konuşmak istiyorum"}]
    out.append({"id": "which", "label": "Hangi paket bana uygun?"})
    if st == "trialing":
        out.append({"id": "trial_end", "label": "Deneme bitince ne olur?"})
    if st in ("free", "payment_required"):
        out.append({"id": "free_limits", "label": "Ücretsizde neler açık?"})
    if st == "past_due":
        out.append({"id": "renew", "label": "Aboneliğimi nasıl yenilerim?"})
    if st == "active":
        out.append({"id": "renew", "label": "Aboneliğim nasıl yenilenir?"})
        out.append({"id": "cancel", "label": "Aboneliği nasıl iptal ederim?"})
    out.append({"id": "credits", "label": "Yapay zekâ kredisi nedir?"})
    if app:
        out.append({"id": "buy_app", "label": "Paketi nasıl alırım?"})
    else:
        out.append({"id": "pay_safe", "label": "Ödeme nasıl yapılır?"})
    out.append({"id": "human", "label": "Bir insanla konuşmak istiyorum"})
    return out


def greeting_for(state: dict, channel: str = "web") -> str:
    p = state["plan"]
    st = p["status"]
    issue = p.get("last_payment_issue") if not _is_app(channel) else None
    if issue:
        return (f"Merhaba! Son ödeme denemende bir sorun görüyorum: «{issue['title']}». "
                "Ne yapman gerektiğini anlatabilirim — ya da başka bir şey sor.")
    if not p["is_solo"]:
        return "Merhaba! Paketin kurumun tarafından yönetiliyor. Sorularını yanıtlayabilirim."
    if st == "trialing":
        d = p.get("trial_days_left") or 0
        return (f"Merhaba! Denemenin bitmesine {d} gün var. Hangi paketin sana uygun olduğunu "
                "ve deneme bitince ne olacağını anlatabilirim.")
    if st == "past_due":
        return ("Merhaba! Aboneliğinin süresi doldu; yenileyene kadar programlama kilitli. "
                "Nasıl yenileyeceğini adım adım anlatabilirim.")
    if st == "payment_required":
        return "Merhaba! Paketinin ödemesi tamamlanmamış görünüyor. Nasıl tamamlayacağını anlatabilirim."
    if st == "active":
        left = p.get("renewal_days_left")
        if left is not None and left <= 7 and not _is_app(channel):
            return (f"Merhaba! Aboneliğinin bitmesine {left} gün kaldı. Şimdi yenilersen kalan günlerin "
                    "yanmaz, yeni dönem bitiş tarihinin üstüne eklenir.")
        return "Merhaba! Aboneliğin aktif. Paket, kredi ya da ödeme hakkında ne sormak istersin?"
    return ("Merhaba! Şu an ücretsiz paketlesin. Öğrenci sayına uygun paketi seçmene yardım "
            "edebilirim.")


def _act_select(t: dict | None) -> dict | None:
    return {"type": "select_plan", "plan": t["code"], "label": f"{t['label']} paketini seç"} if t else None


def rule_answer(chip: str, state: dict, channel: str = "web") -> dict:
    """Hazır sorunun cevabı — durumdan kurulur, yapay zekâ yok.

    Uygulama kanalında (ios/android) web ödemesine (kart/iyzico) hiç
    değinilmez — App Store kuralı (3.1.1: uygulama-dışı ödemeye yönlendirme yok).
    """
    if _is_app(channel):
        app = _app_answer(chip, state, channel)
        if app is not None:
            return app
    p = state["plan"]
    n = int(p["student_count"])
    months = state["annual_paid_months"]
    sug = suggested_plan(state)

    if chip == "payment_failed":
        i = p.get("last_payment_issue")
        if not i:
            return {"answer": "Son 7 günde sorunlu bir ödeme denemen görünmüyor.", "action": None}
        extra = (f" Denediğin paket: {i['plan_label']}." if i.get("plan_label") else "")
        t = _tier(state, i.get("plan_code"))
        return {"answer": f"{i['title']}. {i['detail']}{extra} Kartından para çekilmedi; "
                          "tekrar denemek güvenli.",
                "action": _act_select(t) if t else {"type": "handoff", "label": "Bize yaz"}}

    if chip == "managed":
        return {"answer": "Paketin ve ödemen kurumun tarafından yönetiliyor. Paket değişikliği "
                          "için kurum yöneticine başvurabilirsin.", "action": None}

    if chip == "which":
        if not sug:
            return {"answer": "Öğrenci sayına uygun paketi bulamadım; bize yazarsan yardımcı olalım.",
                    "action": {"type": "handoff", "label": "Bize yaz"}}
        lines = [f"Şu an {n} aktif öğrencin var; {sug['label']} paketi ({_cap(sug)}) sana yeter.",
                 f"Aylık {_fmt_tl(sug['monthly_try'])}, akademik yıl peşin ödersen "
                 f"{_fmt_tl(sug['monthly_try'] * months)} ({12 - months} ay bedava)."]
        if sug.get("ai_credits_monthly"):
            lines.append(f"Her ay {_fmt_int(sug['ai_credits_monthly'])} yapay zekâ kredisi gelir.")
        idx = state["tiers"].index(sug)
        nxt = state["tiers"][idx + 1] if idx + 1 < len(state["tiers"]) else None
        if nxt and sug["max_students"] is not None:
            lines.append(f"Öğrencin {sug['max_students']} kişiyi geçerse {nxt['label']} paketine geçersin.")
        return {"answer": " ".join(lines), "action": _act_select(sug)}

    if chip == "trial_end":
        d = p.get("trial_days_left") or 0
        intended = p.get("post_trial_plan_label") if p.get("post_trial_plan") not in (None, "solo_free") else None
        base = (f"Denemen {d} gün sonra biter. Bitince ödeme yapmazsan ücretsiz pakete "
                f"(Keşif) geçersin: {state['free_students']} öğrenci, yapay zekâ kapalı. "
                "Öğrencilerin ve tüm verilerin silinmez.")
        if intended:
            base += f" Kayıtta {intended} paketini seçmiştin; bu sayfadan kartla ödeyince kesintisiz devam edersin."
        return {"answer": base, "action": _act_select(sug)}

    if chip == "free_limits":
        return {"answer": (f"Ücretsiz pakette {state['free_students']} öğrenciye kadar program, "
                           "görev takibi, deneme sonuçları ve veli bilgilendirmesi açık. Yapay zekâ "
                           f"özellikleri kapalı. {n} aktif öğrencin var"
                           + (f"; {state['free_students']} kişiyi aştığın için yeni programlama kilitli."
                              if n > state["free_students"] else ".")),
                "action": _act_select(sug)}

    if chip == "renew":
        if p["status"] == "past_due":
            return {"answer": ("Aboneliğinin süresi doldu. Bu sayfada paketin seçili geliyor; "
                               "'Kartla öde' ile ödediğin anda programlama açılır ve pasif "
                               "öğrencilerin kendiliğinden aktif olur."),
                    "action": _act_select(sug)}
        end = p.get("subscription_period_end")
        endtxt = _fmt_date(datetime.fromisoformat(end)) if end else ""
        return {"answer": ("Yenileme kendiliğinden kartından çekilmez; dönem bitmeden 3 gün önce "
                           "hatırlatma e-postası gelir ve bu sayfadan ödersin. "
                           + (f"Şu anki dönemin {endtxt} tarihinde bitiyor. " if endtxt else "")
                           + "Erken ödersen kalan günlerin yanmaz; yeni dönem bitiş tarihinin üstüne eklenir."),
                "action": _act_select(_tier(state, p["plan_code"]))}

    if chip == "cancel":
        if p.get("subscription_platform") == "app_store":
            return {"answer": ("Aboneliğin App Store üzerinden; iptal için iPhone'da Ayarlar → "
                               "Apple Kimliği → Abonelikler'e gir."), "action": None}
        return {"answer": ("Sayfanın altındaki 'Aboneliği iptal et' bağlantısıyla iptal edebilirsin. "
                           "Dönem sonuna kadar her şey açık kalır, sonra ücretsiz pakete geçersin. "
                           "Öğrencilerin ve verilerin silinmez; istersen iptali geri alabilirsin."),
                "action": {"type": "open", "section": "cancel", "label": "İptal bölümüne git"}}

    if chip == "credits":
        costs = state["credit_costs"][:4]
        parts = ", ".join(f"{c['label'].lower()} {c['credits']} kredi" for c in costs if c.get("credits"))
        used, alloc = p["ai_credits_used"], p["ai_credits_allocated"]
        mine = (f" Bu ay {_fmt_int(alloc)} kredinin {_fmt_int(used)} tanesini kullandın."
                if alloc and p["status"] in ("trialing", "active") else "")
        return {"answer": ("Yapay zekâ kredisi, karne okuma, veli yorumu gibi yapay zekâ işlerinde "
                           f"harcanır. Örneğin {parts}. Paket kredisi her ay başında yenilenir.{mine}"),
                "action": {"type": "open", "section": "ai", "label": "Kredi kullanımımı gör"}}

    if chip == "pay_safe":
        return {"answer": ("Ödeme yalnız kartla, iyzico üzerinden 3D Secure ile alınır; kart "
                           "bilgin bize gelmez. Paketi seçip 'Kartla öde'ye bas, bankanın SMS "
                           "kodunu gir; onaylanınca paketin hemen açılır."),
                "action": _act_select(sug)}

    if chip == "human":
        return {"answer": ("Tabii. Aşağıdaki 'Bize yaz' ile mesajını bırak; bu konuşmayla birlikte "
                           "ekibimize iletilir ve Destek sayfandan cevabı takip edersin."),
                "action": {"type": "handoff", "label": "Bize yaz"}}

    return {"answer": "Bunu tam anlayamadım. Aşağıdaki sorulardan birini seç ya da kendi cümlenle sor.",
            "action": None}


def _app_answer(chip: str, state: dict, channel: str) -> dict | None:
    """Uygulama kanalına özel cevaplar; None → ortak cevap kullanılır."""
    p = state["plan"]
    sug = suggested_plan(state)
    ios = channel == "ios"
    web_managed = p.get("subscription_platform") in ("iyzico", "manual") and p.get(
        "subscription_status") in ("active", "canceled")
    app_store = p.get("subscription_platform") == "app_store"
    buy_line = ("Paketler bölümünden paketi seçip 'Satın al'a dokunman yeterli; ödeme App Store "
                "hesabından alınır." if ios else "Paket işlemleri bu cihazda yapılamıyor.")
    if chip == "which" and sug:
        txt = (f"Şu an {p['student_count']} aktif öğrencin var; {sug['label']} paketi ({_cap(sug)}) "
               "sana yeter.")
        if sug.get("ai_credits_monthly"):
            txt += f" Her ay {_fmt_int(sug['ai_credits_monthly'])} yapay zekâ kredisi gelir."
        return {"answer": txt, "action": _act_select(sug) if ios and not web_managed else None}
    if chip == "trial_end":
        d = p.get("trial_days_left") or 0
        return {"answer": (f"Denemen {d} gün sonra biter. Bitince ücretsiz pakete (Keşif) geçersin: "
                           f"{state['free_students']} öğrenci, yapay zekâ kapalı. Öğrencilerin ve tüm "
                           "verilerin silinmez." + (f" {buy_line}" if ios else "")),
                "action": _act_select(sug) if ios and sug else None}
    if chip in ("renew", "cancel"):
        if app_store:
            return {"answer": ("Aboneliğin App Store üzerinden; dönem sonunda kendiliğinden yenilenir. "
                               "İptal ya da değişiklik için iPhone'da Ayarlar → Apple Kimliği → "
                               "Abonelikler'e gir. İptal edersen dönem sonuna kadar her şey açık kalır."),
                    "action": None}
        if web_managed:
            return {"answer": ("Aboneliğin web hesabın üzerinden yönetiliyor. Öğrencilerin ve verilerin "
                               "her durumda korunur."), "action": None}
        return {"answer": "Şu an aktif bir aboneliğin yok. " + buy_line,
                "action": _act_select(sug) if ios and sug else None}
    if chip in ("buy_app", "pay_safe", "payment_failed"):
        if web_managed:
            return {"answer": "Aboneliğin web hesabın üzerinden yönetiliyor; burada ayrıca satın alman gerekmez.",
                    "action": None}
        if ios:
            return {"answer": ("Paketler bölümünden paketi seç ve 'Satın al'a dokun. Ödeme App Store "
                               "hesabından alınır, dönem sonunda kendiliğinden yenilenir; App Store → "
                               "Abonelikler'den istediğin zaman iptal edebilirsin. Telefon değiştirdiysen "
                               "'Satın alımları geri yükle'yi kullan."),
                    "action": _act_select(sug) if sug else None}
        return {"answer": ("Paket işlemleri bu cihazda yapılamıyor. Sorunu yazarsan ekibimiz sana "
                           "yardımcı olur."), "action": {"type": "handoff", "label": "Bize yaz"}}
    if chip == "free_limits":
        r = rule_answer(chip, state, "web")
        return {"answer": r["answer"], "action": _act_select(sug) if ios and sug else None}
    if chip == "credits":
        r = rule_answer(chip, state, "web")
        return {"answer": r["answer"], "action": None}
    return None


# =============================================================================
# Serbest soru (Gemini)
# =============================================================================

def ask_count_today(db: Session, user_id: int) -> int:
    from app.models import UsageEvent, UsageKind
    day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(db.query(func.count(UsageEvent.id)).filter(
        UsageEvent.kind == UsageKind.AI_PLAN_ASSISTANT,
        UsageEvent.actor_user_id == user_id,
        UsageEvent.occurred_at >= day_start,
    ).scalar() or 0)


def record_ask(db: Session, user: User, *, source: str) -> None:
    from app.models import UsageEvent, UsageKind
    from app.services.credits import CreditOwner, current_period
    owner = CreditOwner.for_user(user)
    db.add(UsageEvent(
        owner_type=owner.type, owner_id=owner.id, kind=UsageKind.AI_PLAN_ASSISTANT,
        credits=0, period_year_month=current_period(datetime.now(timezone.utc)),
        actor_user_id=user.id,
        metadata_json=json.dumps({"source": source}, ensure_ascii=False),
    ))


_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("geçmedi", "gecmedi", "reddet", "hata", "başarısız", "basarisiz", "çekilmedi", "olmadı"), "payment_failed"),
    (("iptal", "vazgeç", "vazgec", "sonlandır"), "cancel"),
    (("yenile", "uzat", "süre", "sure doldu", "bitiyor"), "renew"),
    (("deneme", "14 gün", "trial"), "trial_end"),
    (("kredi", "yapay zeka", "yapay zekâ", "ai"), "credits"),
    (("güvenli", "guvenli", "kart", "nasıl öde", "nasil ode", "taksit", "havale", "eft"), "pay_safe"),
    (("ücretsiz", "ucretsiz", "keşif", "kesif", "bedava"), "free_limits"),
    (("insan", "temsilci", "aray", "telefon", "destek"), "human"),
    (("hangi paket", "uygun", "öneri", "oneri", "fark", "fiyat", "ne kadar"), "which"),
]


def keyword_chip(question: str) -> str | None:
    q = question.lower()
    for keys, chip in _KEYWORDS:
        if any(k in q for k in keys):
            return chip
    return None


def _facts_for_ai(state: dict, channel: str = "web") -> dict:
    p = state["plan"]
    keep = ("plan_code", "plan_label", "status", "student_count", "trial_active", "trial_days_left",
            "subscription_status", "subscription_period_end", "subscription_cycle",
            "subscription_platform", "post_trial_plan_label", "ai_credits_used",
            "ai_credits_allocated", "last_payment_issue", "renewal_days_left", "is_solo")
    return {
        "hesap": {k: p.get(k) for k in keep},
        "paketler": state["tiers"],
        "akademik_yil_odenen_ay": state["annual_paid_months"],
        "deneme_gun": state["trial_days"],
        "ucretsiz_ogrenci": state["free_students"],
        "kredi_maliyetleri": state["credit_costs"],
        "ek_kredi_paketleri": state["credit_packs"],
        "kurallar": [
            "Ödeme yalnız kartla, iyzico 3D Secure. Havale/EFT yok. Kart bilgisi platforma gelmez.",
            "Web aboneliği kendiliğinden yenilenmez: bitişten 3 gün önce e-posta gelir, koç bu sayfadan öder.",
            "Erken yenileme ya da dönem içinde paket yükseltme kalan günleri yakmaz; yeni dönem mevcut bitişin üstüne eklenir.",
            "Akademik yıl peşin ödemede 12 ay yerine 'akademik_yil_odenen_ay' kadar ödenir.",
            "İptal: dönem sonuna kadar her şey açık, sonra ücretsiz pakete geçilir; veri silinmez; iptal geri alınabilir.",
            "Süresi dolan (past_due) abonelikte programlama kilitlenir; ödeyince açılır, pasif öğrenciler kendiliğinden aktif olur.",
            "Ücretsiz pakette yapay zekâ kapalı; öğrenci sınırını aşınca yeni programlama kilitlenir, veri silinmez.",
            "Paket kredisi her ay başında yenilenir; ek kredi paketleri tek seferliktir ve ay sonunda yanmaz; yalnız aktif abonelikte ve kredi %80'i geçince satın alınabilir.",
            "Paketin öğrenci sınırı aktif öğrenci sayısından küçükse o paket seçilemez.",
            "App Store'dan alınan abonelik (subscription_platform=app_store) yalnız iPhone ayarlarından yönetilir.",
            "Kurum öğretmeninin (is_solo=false) paketi kurum tarafından yönetilir.",
        ] + ([
            "KOÇ MOBİL UYGULAMADA: kart, iyzico, web sitesi ya da web'den ödeme hakkında HİÇBİR ŞEY "
            "söyleme, bağlantı verme. iPhone'da paketler yalnız uygulama içinden App Store ile alınır; "
            "Android'de paket işlemi uygulamada yapılamaz (yalnız 'bize yaz' öner).",
        ] if _is_app(channel) else []),
    }


_PROMPT = """Sen ETÜTKOÇ Rotam'ın paket asistanısın. Bir eğitim koçu (öğretmen) üyelik paketleri,
ödeme, yapay zekâ kredisi ve abonelik hakkında soru soruyor.

KURALLAR:
- YALNIZ aşağıdaki BİLGİ PAKETİNİ kullan. Pakette olmayan fiyat, indirim, kampanya, taksit,
  tarih ya da kural UYDURMA. Bilmiyorsan dürüstçe söyle ve insana aktarmayı öner.
- Türkçe, sıcak ve sade yaz; 2-5 kısa cümle. Koça "sen" diye hitap et (siz değil); "Merhaba" ile başlama. Teknik terim kullanma ("status", "plan_code" yazma).
- Fiyatları "2.500 ₺" biçiminde yaz.
- Koçun hesabına özel konuş (öğrenci sayısı, kalan gün, kredi gibi sayıları kullan).
- Bir paket önerirsen, öğrenci sayısına YETEN paketi öner.

Sadece şu JSON'u döndür:
{"answer": "<cevap>", "action": null | {"type": "select_plan", "plan": "<paket kodu>"} | {"type": "handoff"} | {"type": "open", "section": "ai" | "cancel"}}

BİLGİ PAKETİ:
{facts}

ÖNCEKİ KONUŞMA (en eski → en yeni):
{history}

KOÇUN SORUSU: {question}
"""


def ai_answer(question: str, history: list[dict], state: dict, channel: str = "web") -> dict:
    """Gemini cevabı — DB'siz saf fonksiyon (çağıran işlemi önce kapatır)."""
    from app.services import gemini

    hist = "\n".join(
        f"{'Koç' if h.get('role') == 'user' else 'Asistan'}: {str(h.get('text', ''))[:600]}"
        for h in history[-8:]
    ) or "(yok)"
    prompt = (_PROMPT
              .replace("{facts}", json.dumps(_facts_for_ai(state, channel), ensure_ascii=False, default=str))
              .replace("{history}", hist)
              .replace("{question}", question[:800]))
    raw = gemini.generate([{"text": prompt}], personal_data=False, json_mode=True,
                          max_output_tokens=8192, prefer_fast=True, timeout=30.0)
    data = json.loads(raw) if isinstance(raw, str) else raw
    if isinstance(data, list):
        data = data[0] if data else {}
    answer = str((data or {}).get("answer") or "").strip()
    if not answer:
        raise ValueError("empty answer")
    action = _clean_action((data or {}).get("action"), state)
    if channel == "android" and action and action.get("type") == "select_plan":
        action = None
    return {"answer": answer[:1500], "action": action}


def _clean_action(a: Any, state: dict) -> dict | None:
    if not isinstance(a, dict):
        return None
    t = a.get("type")
    if t == "select_plan":
        tier = _tier(state, a.get("plan"))
        if tier and _fits(tier, int(state["plan"]["student_count"])) and state["plan"]["is_solo"]:
            return _act_select(tier)
        return None
    if t == "handoff":
        return {"type": "handoff", "label": "Bize yaz"}
    if t == "open" and a.get("section") in ("ai", "cancel"):
        lbl = "Kredi kullanımımı gör" if a["section"] == "ai" else "İptal bölümüne git"
        return {"type": "open", "section": a["section"], "label": lbl}
    return None
