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
    """Aksiyon merkezinde bir satır — bir kurum + tüm sinyalleri + öneriler."""
    institution_id: int
    institution_name: str
    plan: str
    plan_label: str
    monthly_price_try: int
    primary_signal: ActionSignal
    other_signals: list[ActionSignal] = field(default_factory=list)
    suggested_actions: list[SuggestedAction] = field(default_factory=list)
    last_action_at: datetime | None = None
    last_action_summary: str | None = None

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
        ))

    # Total skor azalan sıraya göre sırala
    items.sort(key=lambda x: -x.total_score)
    return items[:limit]


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
