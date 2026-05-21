"""Katman 10 — Süper Admin Yönetim Paneli (Curator Dashboard).

Önceki 9 katmanın sayım/metrik/anomalilerini tek panelde toplar.
Yeni davranış EKLEMEZ; sadece agreguta ve okuma.

Çıktı yapısı (`get_dashboard_data` → tek dict):

  summary:        # üst sayım kartları
    total, published, landing, draft, hidden, queue_pending, active_experiment
  landing_health: # K8 ile aynı veri
    diversity_pct, learning_count, landing_count
  last_7d:        # K6 telemetri + K3 keşif + K7 bandit
    events, impressions, views, demo_clicks, cta_clicks, ctr_pct,
    new_discoveries, bandit_updates
  experiment:     # aktif deney özeti (varsa)
    None | {name, slug, started_days_ago, variants: {slug: stats}}
  anomalies:      # uyarı listesi
    [{severity, title, hint, action_url}, ...]
  recent_audit:   # son 10 feature_card_* audit kaydı
    [{action_label, target_slug, actor, when, ago}, ...]
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AUDIT_ACTION_LABELS,
    AuditAction,
    AuditLog,
    EXPERIMENT_STATUS_LABELS_TR,
    ExperimentStatus,
    FeatureBanditState,
    FeatureCard,
    FeatureCardEvent,
    FeatureEventType,
    FeatureExperiment,
    FeatureStatus,
)


_FEATURE_AUDIT_ACTIONS = {
    AuditAction.FEATURE_CARD_CREATE.value,
    AuditAction.FEATURE_CARD_UPDATE.value,
    AuditAction.FEATURE_CARD_DELETE.value,
    AuditAction.FEATURE_CARD_STATUS_CHANGE.value,
    AuditAction.FEATURE_CARD_PIN.value,
    AuditAction.FEATURE_CARD_AUTO_DISCOVERED.value,
    AuditAction.FEATURE_CARD_DISCOVERY_REJECTED.value,
}


def get_dashboard_data(db: Session, *, window_days: int = 7) -> dict[str, Any]:
    """Tüm dashboard verisini tek dict olarak döndürür."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)

    return {
        "summary": _summary(db),
        "landing_health": _landing_health(db),
        "last_7d": _last_window_metrics(db, since=window_start, window_days=window_days),
        "experiment": _active_experiment_summary(db, now=now),
        "anomalies": _anomalies(db, now=now, window_start=window_start),
        "recent_audit": _recent_audit(db, limit=10, now=now),
        "window_days": window_days,
        "generated_at": now,
    }


# ============================================================
# Sections
# ============================================================


def _summary(db: Session) -> dict[str, int]:
    """Üst sayım kartları."""
    total = db.query(FeatureCard).count()
    by_status: dict[str, int] = {}
    rows = (
        db.query(FeatureCard.status, func.count(FeatureCard.id))
        .group_by(FeatureCard.status)
        .all()
    )
    for st, n in rows:
        by_status[st] = int(n)

    hidden = db.query(FeatureCard).filter(FeatureCard.manual_hide.is_(True)).count()

    # Landing'de görünen (PUBLISHED + mockup + not hidden)
    landing = (
        db.query(FeatureCard)
        .filter(
            FeatureCard.status == FeatureStatus.PUBLISHED.value,
            FeatureCard.manual_hide.is_(False),
            FeatureCard.mockup_type.isnot(None),
            FeatureCard.mockup_type != "",
        )
        .count()
    )

    # Onay kuyruğu — kesif-* DRAFT + not hidden
    queue_pending = (
        db.query(FeatureCard)
        .filter(
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
            FeatureCard.manual_hide.is_(False),
        )
        .count()
    )

    active_exp = (
        db.query(FeatureExperiment)
        .filter(FeatureExperiment.status == ExperimentStatus.RUNNING.value)
        .count()
    )

    return {
        "total": total,
        "published": by_status.get(FeatureStatus.PUBLISHED.value, 0),
        "draft": by_status.get(FeatureStatus.DRAFT.value, 0),
        "hidden": hidden,
        "landing": landing,
        "queue_pending": queue_pending,
        "active_experiment": active_exp,
    }


def _landing_health(db: Session) -> dict[str, Any]:
    """K8 diversity + K7 learning durumu — list sayfasındaki bantla aynı."""
    from app.services import diversity as dv
    from app.services import feature_catalog as fc

    landing_cards = fc.get_for_landing(db)
    div_score = dv.diversity_score(landing_cards)
    div_pct = int(round(div_score * 100))

    # Öğrenme aktif: bu kartların kaç tanesinin bandit state'i var ve obs > 0
    landing_ids = [c.id for c in landing_cards]
    bandit_active = 0
    if landing_ids:
        bandit_active = (
            db.query(FeatureBanditState)
            .filter(
                FeatureBanditState.card_id.in_(landing_ids),
                FeatureBanditState.reward_count > 0,
            )
            .count()
        )

    return {
        "landing_count": len(landing_cards),
        "diversity_pct": div_pct,
        "diversity_score": div_score,
        "learning_count": bandit_active,
    }


def _last_window_metrics(
    db: Session, *, since: datetime, window_days: int
) -> dict[str, Any]:
    """Son N gün metrikleri — telemetri, keşif, bandit."""
    # Telemetri sayımları
    counts = {et.value: 0 for et in FeatureEventType}
    rows = (
        db.query(FeatureCardEvent.event_type, func.count(FeatureCardEvent.id))
        .filter(FeatureCardEvent.created_at >= since)
        .group_by(FeatureCardEvent.event_type)
        .all()
    )
    for et, n in rows:
        if et in counts:
            counts[et] = int(n)
    total_events = sum(counts.values())
    total_clicks = counts["demo_click"] + counts["cta_click"]
    impressions = counts["impression"]
    ctr = (total_clicks / impressions) if impressions > 0 else 0.0

    # Yeni keşfedilen kartlar (FEATURE_CARD_AUTO_DISCOVERED audit)
    new_discoveries = (
        db.query(AuditLog)
        .filter(
            AuditLog.action == AuditAction.FEATURE_CARD_AUTO_DISCOVERED,
            AuditLog.created_at >= since,
        )
        .count()
    )

    # Bandit güncellemeleri — kaç state son N günde update aldı
    bandit_updates = (
        db.query(FeatureBanditState)
        .filter(FeatureBanditState.updated_at >= since)
        .count()
    )

    return {
        "events": total_events,
        "impressions": impressions,
        "views": counts["view"],
        "demo_clicks": counts["demo_click"],
        "cta_clicks": counts["cta_click"],
        "total_clicks": total_clicks,
        "ctr_pct": round(ctr * 100, 2),
        "new_discoveries": new_discoveries,
        "bandit_updates": bandit_updates,
        "window_days": window_days,
    }


def _active_experiment_summary(
    db: Session, *, now: datetime
) -> dict[str, Any] | None:
    """Aktif deney varsa özet stats."""
    from app.services import experiments as exp_svc
    active = exp_svc.get_active_experiment(db)
    if active is None:
        return None
    stats = exp_svc.compute_stats(db, experiment_id=active.id)
    started_at = active.start_at or active.created_at
    if started_at and started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    days_running = (
        max(0, int((now - started_at).total_seconds() / 86400))
        if started_at else 0
    )
    total_impr = sum(v["impression"] for v in stats.values())
    has_significance = any(
        v.get("vs_control_significant") for v in stats.values()
    )
    return {
        "id": active.id,
        "name": active.name,
        "slug": active.slug,
        "started_days_ago": days_running,
        "variants": stats,
        "total_impressions": total_impr,
        "has_significance": has_significance,
    }


def _anomalies(
    db: Session, *, now: datetime, window_start: datetime
) -> list[dict[str, str]]:
    """Süper admin'in dikkatini hak eden durumlar."""
    out: list[dict[str, str]] = []

    summary = _summary(db)
    last7 = _last_window_metrics(db, since=window_start, window_days=7)

    # Landing'de 3'ten az kart varsa — anasayfa zayıf
    if summary["landing"] < 3:
        out.append({
            "severity": "rose",
            "title": f"Anasayfada yalnız {summary['landing']} kart var",
            "hint": "En az 3 kart gerekli — mockup_type'ı dolu PUBLISHED kart sayısını artır.",
            "action_url": "/admin/feature-catalog?status_filter=published",
            "action_label": "Yayındaki kartları gör",
        })

    # Onay kuyruğunda 10+ kart varsa — birikme
    if summary["queue_pending"] >= 10:
        out.append({
            "severity": "amber",
            "title": f"Onay kuyruğunda {summary['queue_pending']} aday bekliyor",
            "hint": "Otomatik bulunan adayları gözden geçirmeden yenisi üretilirse karışıklık olur.",
            "action_url": "/admin/feature-catalog/discovery-queue",
            "action_label": "Kuyruğu aç",
        })

    # 7 gün ziyaret yoksa — trafik yok
    if last7["impressions"] == 0:
        out.append({
            "severity": "slate",
            "title": "Son 7 günde anasayfa ziyareti kaydedilmedi",
            "hint": "Bandit'in öğrenmesi ve A/B testlerin sonuç vermesi için trafik şart.",
            "action_url": "/",
            "action_label": "Anasayfayı aç",
        })

    # Aktif deney 200+ impression aldı ama anlamlı fark yok
    active_exp = _active_experiment_summary(db, now=now)
    if active_exp is not None:
        if (
            active_exp["total_impressions"] >= 200
            and not active_exp["has_significance"]
            and active_exp["started_days_ago"] >= 7
        ):
            out.append({
                "severity": "amber",
                "title": f"'{active_exp['name']}' 7+ gündür anlamlı sonuç vermiyor",
                "hint": (
                    "Yeterli örneklem var ama varyant'lar arası fark gürültü içinde. "
                    "Daha radikal bir hipotez test etmeyi düşün."
                ),
                "action_url": f"/admin/feature-catalog/experiments/{active_exp['id']}",
                "action_label": "Deneyi aç",
            })

    # Gizli kart sayısı (manual_hide=True) yüksekse — temizlik ihtiyacı
    if summary["hidden"] >= 20:
        out.append({
            "severity": "slate",
            "title": f"{summary['hidden']} kart manuel gizlenmiş durumda",
            "hint": "Reddedilen keşif adayları DB'de birikir. Toplu silme isteğe bağlı.",
            "action_url": "/admin/feature-catalog/discovery-queue?show_rejected=1",
            "action_label": "Reddedilenleri göster",
        })

    return out


def _recent_audit(db: Session, *, limit: int, now: datetime) -> list[dict[str, Any]]:
    """Son N FeatureCard audit kaydı (görsel timeline için)."""
    rows = (
        db.query(AuditLog)
        .filter(AuditLog.action.in_(_FEATURE_AUDIT_ACTIONS))
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        ago_seconds = (now - (r.created_at.replace(tzinfo=timezone.utc)
                              if r.created_at.tzinfo is None else r.created_at)
                       ).total_seconds()
        # Action label
        try:
            action_enum = AuditAction(r.action)
            action_label = AUDIT_ACTION_LABELS.get(action_enum, r.action)
        except ValueError:
            action_label = r.action

        # Target slug — details_json'dan
        target_slug = None
        if r.details_json:
            try:
                import json as _json
                d = _json.loads(r.details_json)
                target_slug = d.get("slug")
            except (ValueError, TypeError):
                pass

        out.append({
            "action": r.action,
            "action_label": action_label,
            "target_id": r.target_id,
            "target_slug": target_slug,
            "actor_id": r.actor_id,
            "when": r.created_at,
            "ago_seconds": int(ago_seconds),
        })
    return out


def humanize_ago(seconds: int) -> str:
    """Sade Türkçe relative time: '3 dk önce', '2 saat önce', '5 gün önce'."""
    if seconds < 60:
        return "az önce"
    if seconds < 3600:
        return f"{seconds // 60} dk önce"
    if seconds < 86400:
        return f"{seconds // 3600} saat önce"
    if seconds < 86400 * 7:
        return f"{seconds // 86400} gün önce"
    return f"{seconds // (86400 * 7)} hafta önce"
