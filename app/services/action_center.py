"""Sprint C (Roadmap Faz D) — Aksiyon Merkezi (Bugünün arama listesi).

Admin sabahı açıp "bugün hangi kuruma ne yapmalıyım?" sorusunun cevabını
veren akıllı liste. Tüm sinyalleri puan tabanlı önceliklendirir:

  - Kritik sağlık: 100 puan (acil müdahale)
  - Ödeme 7+ gün gecikti: 90 puan
  - Trial 1-2 gün kaldı: 85 puan
  - Risk seviye sağlık: 70 puan
  - Trial 3-7 gün: 60 puan
  - Ödeme 1-6 gün gecikti: 65 puan
  - Aktif öğretmen %30+ düştü (ileride): 55 puan
  - Watch seviye sağlık: 40 puan
  - Champion (referans aday): 20 puan (pozitif aksiyon)

Aynı kurum birden çok sinyal vermişse en yüksek puanlı sinyal başlık olur,
diğerleri "+ X başka uyarı" olarak görünür.

Önerilen aksiyon her sinyal türüne göre değişir:
  - Kritik → memnuniyet anketi + onboarding
  - Ödeme gecikti → hatırlatma + ödeme linki
  - Trial bitiyor → arama + uzatma teklifi
  - Champion → referans iste

UI ham veriyi render eder; aksiyon butonları CrmAction oluşturur veya
şablon penceresi açar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models import (
    Institution,
    Invoice,
    InvoiceStatus,
)


logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------- Aksiyon önerileri ----------------------------


@dataclass
class SuggestedAction:
    """Bir kuruma önerilen aksiyon — UI butonu için."""
    kind: str                       # CrmActionKind value (call, email, ...)
    summary: str                    # Önerilen özet metni (form'a hazır gelir)
    label: str                      # Buton üzerindeki kısa etiket
    icon: str                       # Emoji
    color: str = "indigo"           # Tailwind paleti


# Sinyal türü → önerilen aksiyon eşlemesi
ACTION_SUGGESTIONS: dict[str, list[SuggestedAction]] = {
    "health_critical": [
        SuggestedAction(
            kind="call", icon="📞", label="Hemen ara",
            summary="Kritik sağlık seviyesi — memnuniyet ve sorun tespit görüşmesi",
            color="rose",
        ),
        SuggestedAction(
            kind="onboarding", icon="🎓", label="Onboarding tekrar",
            summary="Kullanım düştü, ekibi yeniden eğit",
            color="indigo",
        ),
    ],
    "billing_overdue_severe": [
        SuggestedAction(
            kind="call", icon="📞", label="Ödeme hatırlatma",
            summary="Ödeme 7+ gündür gecikti — telefonla nazik hatırlatma",
            color="rose",
        ),
        SuggestedAction(
            kind="email", icon="✉️", label="Son uyarı e-postası",
            summary="Resmi son uyarı — 7 gün sonrası hesap kısıtlanacak",
            color="rose",
        ),
    ],
    "trial_ending_imminent": [
        SuggestedAction(
            kind="call", icon="📞", label="Trial dönüşüm görüşmesi",
            summary="Trial 1-2 gün içinde bitiyor — ödemeli plana geçiş için ara",
            color="amber",
        ),
        SuggestedAction(
            kind="offer_sent", icon="🎁", label="Uzatma teklifi sun",
            summary="14 günlük ek deneme veya %20 indirim teklifi",
            color="amber",
        ),
    ],
    "health_risk": [
        SuggestedAction(
            kind="call", icon="📞", label="İhtiyaç görüşmesi",
            summary="Risk seviyesi — kullanımı arttırmak için ihtiyaç tespit",
            color="amber",
        ),
        SuggestedAction(
            kind="email", icon="✉️", label="Kullanım ipuçları",
            summary="Öğretmenlere yönelik kullanım ipuçları e-postası gönder",
            color="amber",
        ),
    ],
    "billing_overdue_mild": [
        SuggestedAction(
            kind="email", icon="✉️", label="Nazik hatırlatma",
            summary="Ödeme birkaç gün gecikti — nazik hatırlatma e-postası",
            color="amber",
        ),
        SuggestedAction(
            kind="whatsapp", icon="💬", label="WhatsApp",
            summary="Hızlı WhatsApp hatırlatma",
            color="emerald",
        ),
    ],
    "trial_ending_week": [
        SuggestedAction(
            kind="email", icon="✉️", label="Geri sayım e-postası",
            summary="Trial 3-7 gün içinde bitiyor — değer iletisi",
            color="amber",
        ),
    ],
    "health_watch": [
        SuggestedAction(
            kind="email", icon="✉️", label="İzleme e-postası",
            summary="İzleme seviyesi — proaktif kontrol e-postası",
            color="slate",
        ),
    ],
    "champion": [
        SuggestedAction(
            kind="email", icon="✉️", label="Memnuniyet anketi",
            summary="Yüksek sağlıklı kurum — NPS anketi + referans isteği",
            color="emerald",
        ),
        SuggestedAction(
            kind="offer_sent", icon="🎁", label="Yıllığa geçiş teklifi",
            summary="Yıllık plana geçiş için %15 indirim teklifi (LTV artar)",
            color="emerald",
        ),
    ],
}


# ---------------------------- Sinyaller ----------------------------


@dataclass
class ActionSignal:
    """Bir kurum için tek bir aciliyet sinyali."""
    kind: str                       # health_critical, billing_overdue, trial_ending vb.
    severity: Literal["critical", "high", "medium", "low", "positive"]
    score: int                      # 0-100, yüksek = daha öncelikli
    title: str                      # "Ödeme 8 gün gecikti"
    description: str                # Daha detaylı açıklama


@dataclass
class ActionItem:
    """Aksiyon merkezinde bir satır — bir owner (kurum VEYA bağımsız koç) +
    tüm sinyalleri + öneriler. Owner-pattern: owner_type/owner_id + detail_url."""
    institution_id: int             # owner=user ise 0 (geriye uyum)
    institution_name: str           # owner adı (kurum adı veya koç ad/e-posta)
    plan: str
    plan_label: str
    monthly_price_try: int
    primary_signal: ActionSignal
    other_signals: list[ActionSignal] = field(default_factory=list)
    suggested_actions: list[SuggestedAction] = field(default_factory=list)
    last_action_at: datetime | None = None
    last_action_summary: str | None = None
    owner_type: str = "institution"     # institution | user
    owner_id: int = 0                   # kurum id veya koç user id
    detail_url: str = ""                # 360 detay sayfası

    @property
    def total_score(self) -> int:
        """Tüm sinyallerin toplam puanı (üstte gösterim sırası)."""
        s = self.primary_signal.score
        for o in self.other_signals:
            s += o.score // 4  # ikincil sinyaller %25 ağırlıkta
        return s

    @property
    def severity(self) -> str:
        return self.primary_signal.severity


# ---------------------------- Sinyal toplama ----------------------------


def _collect_health_signals(db: Session) -> dict[int, list[ActionSignal]]:
    """Tenant_health'ten kritik/risk/watch kurumları topla."""
    from app.services.tenant_health import bulk_health_assessment
    insts = db.query(Institution).filter(Institution.is_active.is_(True)).all()
    signals: dict[int, list[ActionSignal]] = {}
    try:
        assessments = bulk_health_assessment(db, institutions=insts)
    except Exception:
        logger.exception("health bulk fail")
        return signals

    for a in assessments:
        kind, severity, score, title = None, None, 0, ""
        if a.level == "critical":
            kind, severity, score = "health_critical", "critical", 100
            title = f"Kritik sağlık seviyesi (skor {100 - a.score}/100)"
        elif a.level == "risk":
            kind, severity, score = "health_risk", "high", 70
            title = f"Risk seviyesi (skor {100 - a.score}/100)"
        elif a.level == "watch":
            kind, severity, score = "health_watch", "medium", 40
            title = f"İzleme seviyesi (skor {100 - a.score}/100)"
        else:
            # healthy → champion eligibility kontrolü
            from app.services.revenue_panel import _plan_label_and_price
            _, price = _plan_label_and_price(a.institution.plan)
            if price > 0:
                kind, severity, score = "champion", "positive", 20
                title = "Sağlıklı + ödeyen kurum — referans/upsell adayı"
        if kind is None:
            continue
        # En tepedeki indicator açıklama
        desc_text = ""
        if a.indicators:
            top = a.indicators[0]
            desc_text = getattr(top, "message", None) or getattr(top, "name", "")
        signals.setdefault(a.institution.id, []).append(
            ActionSignal(
                kind=kind, severity=severity, score=score,
                title=title, description=desc_text,
            )
        )
    return signals


def _collect_billing_signals(db: Session) -> dict[int, list[ActionSignal]]:
    """Ödeme gecikmesi sinyalleri."""
    now = _now()
    signals: dict[int, list[ActionSignal]] = {}
    overdue = (
        db.query(Invoice)
        .filter(
            Invoice.status.in_([InvoiceStatus.OVERDUE, InvoiceStatus.PENDING]),
            Invoice.due_at < now,
        )
        .all()
    )
    # Kurum başına gecikme topla (en eski)
    per_inst: dict[int, list[Invoice]] = {}
    for inv in overdue:
        per_inst.setdefault(inv.institution_id, []).append(inv)
    for inst_id, invs in per_inst.items():
        # En eski geciken
        invs_sorted = sorted(invs, key=lambda i: i.due_at)
        oldest = invs_sorted[0]
        days_overdue = (now - _aware(oldest.due_at)).days
        total_overdue_try = sum(i.amount_try for i in invs)
        if days_overdue >= 7:
            kind, severity, score = "billing_overdue_severe", "critical", 90
            title = f"Ödeme {days_overdue} gündür gecikti"
        else:
            kind, severity, score = "billing_overdue_mild", "high", 65
            title = f"Ödeme {days_overdue} gün gecikti"
        signals.setdefault(inst_id, []).append(
            ActionSignal(
                kind=kind, severity=severity, score=score,
                title=title,
                description=f"{len(invs)} adet fatura · toplam {total_overdue_try:,} ₺",
            )
        )
    return signals


def _collect_trial_signals(db: Session) -> dict[int, list[ActionSignal]]:
    """Trial bitiş yaklaşan kurumlar."""
    now = _now()
    signals: dict[int, list[ActionSignal]] = {}
    rows = (
        db.query(Institution)
        .filter(
            Institution.is_active.is_(True),
            Institution.trial_ends_at.isnot(None),
            Institution.trial_ends_at >= now,
            Institution.trial_ends_at <= now + timedelta(days=7),
        )
        .all()
    )
    for inst in rows:
        te = _aware(inst.trial_ends_at)
        days_left = (te - now).days
        if days_left <= 2:
            kind, severity, score = "trial_ending_imminent", "critical", 85
            title = f"Trial {days_left} gün içinde bitiyor"
        else:
            kind, severity, score = "trial_ending_week", "medium", 60
            title = f"Trial {days_left} gün içinde bitiyor"
        signals.setdefault(inst.id, []).append(
            ActionSignal(
                kind=kind, severity=severity, score=score,
                title=title,
                description=f"Sonraki plan: {inst.post_trial_plan or 'belirsiz'}",
            )
        )
    return signals


# ---------------------------- Aggregator ----------------------------


def _last_action_for(db: Session, *, institution_id: int) -> tuple[datetime | None, str | None]:
    """Son yapılan CRM aksiyonu — 'kurum 7 gündür temas almamış' uyarısı için."""
    from app.models import CrmAction
    row = (
        db.query(CrmAction)
        .filter(CrmAction.institution_id == institution_id)
        .order_by(desc(CrmAction.created_at))
        .first()
    )
    if row is None:
        return (None, None)
    return (_aware(row.created_at), row.summary)


def build_action_list(
    db: Session, *, limit: int = 50,
) -> list[ActionItem]:
    """Aksiyon merkezi için tüm kurumları puana göre sırala."""
    all_signals: dict[int, list[ActionSignal]] = {}

    # Her sinyal kaynağından topla
    for fn in (_collect_health_signals, _collect_billing_signals,
               _collect_trial_signals):
        try:
            for inst_id, sigs in fn(db).items():
                all_signals.setdefault(inst_id, []).extend(sigs)
        except Exception:
            logger.exception("signal collector fail: %s", fn.__name__)

    if not all_signals:
        return []

    # Kurum dict
    insts_map = {
        i.id: i for i in
        db.query(Institution).filter(
            Institution.id.in_(list(all_signals.keys()))
        ).all()
    }

    # Plan etiket helper
    from app.services.revenue_panel import _plan_label_and_price

    items: list[ActionItem] = []
    for inst_id, signals in all_signals.items():
        inst = insts_map.get(inst_id)
        if inst is None:
            continue
        # En yüksek puan birincil
        signals_sorted = sorted(signals, key=lambda s: -s.score)
        primary = signals_sorted[0]
        others = signals_sorted[1:]
        # Önerilen aksiyonlar — birincilden, yoksa "diğer" tipinden
        suggestions = ACTION_SUGGESTIONS.get(primary.kind, [
            SuggestedAction(
                kind="call", icon="📞", label="Ara",
                summary="Genel kontrol görüşmesi", color="indigo",
            )
        ])
        last_at, last_summary = _last_action_for(db, institution_id=inst_id)
        plan_label, price = _plan_label_and_price(inst.plan)
        items.append(ActionItem(
            institution_id=inst.id,
            institution_name=inst.name,
            plan=inst.plan,
            plan_label=plan_label,
            monthly_price_try=price,
            primary_signal=primary,
            other_signals=others,
            suggested_actions=suggestions,
            last_action_at=last_at,
            last_action_summary=last_summary,
            owner_type="institution",
            owner_id=inst.id,
            detail_url=f"/admin/revenue/institutions/{inst.id}",
        ))

    # Bağımsız koç (solo) sinyalleri — owner-pattern (kurum-merkezli boşluk kapatıldı)
    try:
        items.extend(_build_solo_items(db))
    except Exception:
        logger.exception("solo action items fail")

    # Total skor azalan sıraya göre sırala
    items.sort(key=lambda x: -x.total_score)
    return items[:limit]


# Solo sinyallere özel öneriler (kurum ACTION_SUGGESTIONS'a ek)
_SOLO_SUGGESTIONS: dict[str, list[SuggestedAction]] = {
    "subscription_past_due": [
        SuggestedAction(kind="call", icon="📞", label="Yenileme görüşmesi",
                        summary="Abonelik yenilenmedi — ödeme/yenileme için ara", color="rose"),
        SuggestedAction(kind="email", icon="✉️", label="Yenileme e-postası",
                        summary="Ödeme bağlantısı + yenileme hatırlatması gönder", color="amber"),
    ],
    "over_student_limit": [
        SuggestedAction(kind="call", icon="📞", label="Yükseltme görüşmesi",
                        summary="Deneme bitti, limit aşıldı — Solo'ya geçiş için ara", color="indigo"),
        SuggestedAction(kind="offer_sent", icon="🎁", label="Yükseltme teklifi",
                        summary="Solo Pro yükseltme teklifi sun", color="emerald"),
    ],
}


def _build_solo_items(db: Session) -> list["ActionItem"]:
    """Bağımsız koç (institution_id NULL) için aksiyon sinyalleri:
    deneme bitiyor / abonelik past_due / ücretsiz limit aşımı."""
    from app.models import User, UserRole
    from app.services import pricing
    from app.services.plans import (
        SOLO_FREE, SOLO_TRIAL, count_solo_students, get_plan_info,
        is_trial_active, trial_days_left,
    )

    now = _now()
    coaches = (
        db.query(User)
        .filter(
            User.role == UserRole.TEACHER,
            User.institution_id.is_(None),
            User.is_active.is_(True),
        )
        .all()
    )
    items: list[ActionItem] = []
    for c in coaches:
        plan = c.plan or SOLO_FREE
        signals: list[ActionSignal] = []
        if plan == SOLO_TRIAL and is_trial_active(c, now):
            dl = trial_days_left(owner=c, now=now) or 0
            if dl <= 7:
                if dl <= 2:
                    kind, sev, score = "trial_ending_imminent", "critical", 85
                else:
                    kind, sev, score = "trial_ending_week", "medium", 60
                signals.append(ActionSignal(
                    kind=kind, severity=sev, score=score,
                    title=f"Deneme {dl} gün içinde bitiyor",
                    description="Bağımsız koç — ödemeli plana dönüşüm fırsatı"))
        if getattr(c, "subscription_status", None) == "past_due":
            signals.append(ActionSignal(
                kind="subscription_past_due", severity="critical", score=90,
                title="Abonelik yenilenmedi (ödeme gecikti)",
                description="Aktif koçluk kilitli — yenileme görüşmesi"))
        if plan == SOLO_FREE:
            cnt = count_solo_students(db, teacher_id=c.id)
            if cnt > 3:
                signals.append(ActionSignal(
                    kind="over_student_limit", severity="high", score=70,
                    title=f"Deneme bitti, {cnt} öğrenci (limit 3 aşıldı)",
                    description="Yükseltme veya öğrenci azaltma gerek"))
        if not signals:
            continue
        signals.sort(key=lambda s: -s.score)
        primary, others = signals[0], signals[1:]
        suggestions = (ACTION_SUGGESTIONS.get(primary.kind)
                       or _SOLO_SUGGESTIONS.get(primary.kind)
                       or [SuggestedAction(kind="call", icon="📞", label="Ara",
                                           summary="Koçla görüşme", color="indigo")])
        info = get_plan_info(plan)
        monthly = pricing.compute_solo_monthly(count_solo_students(db, teacher_id=c.id))
        items.append(ActionItem(
            institution_id=0,
            institution_name=(c.full_name or c.email),
            plan=plan,
            plan_label=info.label if info else plan,
            monthly_price_try=monthly,
            primary_signal=primary,
            other_signals=others,
            suggested_actions=suggestions,
            owner_type="user",
            owner_id=c.id,
            detail_url=f"/admin/revenue/users/{c.id}",
        ))
    return items


def action_center_data(db: Session) -> dict:
    """Aksiyon merkezi sayfası için aggregator."""
    items = build_action_list(db, limit=50)
    severity_counts: dict[str, int] = {
        "critical": 0, "high": 0, "medium": 0, "low": 0, "positive": 0,
    }
    for it in items:
        severity_counts[it.severity] = severity_counts.get(it.severity, 0) + 1
    return {
        "generated_at": _now(),
        "items": items,
        "total_count": len(items),
        "severity_counts": severity_counts,
    }


__all__ = [
    "ACTION_SUGGESTIONS",
    "ActionItem",
    "ActionSignal",
    "SuggestedAction",
    "action_center_data",
    "build_action_list",
]
