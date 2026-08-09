"""Katman 11.F — Alarm motoru.

Her kuralın "şu anki değerini" hesaplar, eşik aşılırsa AlarmEvent yazıp
kanallara (email süper admin, in-app) gönderim yapar. Cooldown ile
yorgunluğu önler.

İki giriş noktası:
  - evaluate_all(db): cron ya da admin "Şimdi tara" → tüm enabled kuralları çalıştır
  - acknowledge(db, event_id, user_id): admin alarmı gördü → acknowledged_at

Kural değer hesaplamaları:
  - high_failed_logins   = AuditLog 24h LOGIN_FAILED + LOGIN_LOCKED count
  - oldest_queued_long   = oldest_queued_minutes(db)
  - error_groups_open    = ErrorEvent count where resolved_at IS NULL
  - abuse_open           = AbuseSignal count where resolved_at IS NULL
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import (
    AbuseSignal,
    AlarmEvent,
    AlarmRule,
    AuditAction,
    AuditLog,
    ErrorEvent,
    User,
    UserRole,
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


# ---------------------------- Kural değer hesaplama ----------------------------


def _val_high_failed_logins(db: Session) -> int:
    cutoff = _now() - timedelta(hours=24)
    return int(
        (db.query(func.count(AuditLog.id))
         .filter(
             AuditLog.action.in_([AuditAction.LOGIN_FAILED, AuditAction.LOGIN_LOCKED]),
             AuditLog.created_at >= cutoff,
         )
         .scalar()) or 0
    )


def _val_oldest_queued_long(db: Session) -> int:
    """En eski queued bildirimin yaşı (dakika)."""
    from app.services.notification_health import oldest_queued_minutes
    return oldest_queued_minutes(db) or 0


def _val_error_groups_open(db: Session) -> int:
    # Yalnız SON 3 GÜNDE görülmüş (aktif) açık hata grupları alarmlar. Bayat
    # gruplar (3+ gün önce görülmüş — muhtemelen düzeltilmiş, artık tekrar
    # etmeyen) saatlik yanlış-alarm yaratmasın; panelde + "stale" rozetiyle yine
    # görünür, sadece email tetiklemez. (Süper admine bayat hata spam'i önlenir.)
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=3)
    return int(
        (db.query(func.count(ErrorEvent.id))
         .filter(ErrorEvent.resolved_at.is_(None),
                 ErrorEvent.last_seen_at >= cutoff)
         .scalar()) or 0
    )


def _val_abuse_open(db: Session) -> int:
    # Yalnız warn/critical açık sinyaller alarmlar. "info" (düşük güven —
    # örn. aynı IP'den birkaç test girişi) email gürültüsü yaratmasın; tespit
    # yine kaydedilir + Suistimal panelinde görünür, sadece email atmaz.
    return int(
        (db.query(func.count(AbuseSignal.id))
         .filter(
             AbuseSignal.resolved_at.is_(None),
             AbuseSignal.severity != "info",
         )
         .scalar()) or 0
    )


def _val_payment_problem_recent(db: Session) -> int:
    """Son 24 saatte ödeme sorunu sayısı (2026-07-24 üyelik revizyonu).

    Sayılanlar: FAILED işlem + 30 dakikadan eski hâlâ pending/3ds_pending
    (yarım kalmış 3DS — müşteri ödeme adımında takıldı ya da callback
    ulaşmadı). Ödeme hacmi düşükken HER sorun süper admin görmeli.
    """
    from app.models import PaymentTransaction

    now = _now()
    cutoff_24h = now - timedelta(hours=24)
    stuck_cutoff = now - timedelta(minutes=30)
    failed = int(
        (db.query(func.count(PaymentTransaction.id))
         .filter(
             PaymentTransaction.status == "failed",
             PaymentTransaction.created_at >= cutoff_24h,
         )
         .scalar()) or 0
    )
    stuck = int(
        (db.query(func.count(PaymentTransaction.id))
         .filter(
             PaymentTransaction.status.in_(["pending", "3ds_pending"]),
             PaymentTransaction.created_at >= cutoff_24h,
             PaymentTransaction.created_at < stuck_cutoff,
         )
         .scalar()) or 0
    )
    return failed + stuck


# E-posta sağlığı alarmı için en az kaç deneme birikmeli (düşük hacimde tek bir
# hard-bounce %100 başarısızlık gibi görünür → yanlış alarm).
EMAIL_HEALTH_MIN_SAMPLE = 5
EMAIL_HEALTH_WINDOW_HOURS = 24


def _val_email_delivery_failing(db: Session) -> int:
    """Son 24 saatte BAŞARISIZ e-posta yüzdesi (0-100).

    2026-07-30: ZeptoMail deneme süresi dolunca SMTP 535 vermeye başladı ve
    e-posta gönderimi 10 GÜN boyunca tamamen durdu — kimse fark etmedi, çünkü
    (a) bu durumu ölçen bir kural yoktu, (b) var olan alarmlar da e-postayla
    gönderiliyordu. Bu kural İletişim Sağlığı sayfasıyla AYNI veriyi
    (communication_logs) ve AYNI başarı/başarısızlık tanımını kullanır — panel
    ne gösteriyorsa alarm da onu ölçer.

    Örnek kayıp: şifre sıfırlama e-postası ulaşmayan koç hesabını açamaz.
    """
    from app.models.communication_log import (
        CHANNEL_EMAIL,
        FAILURE_STATUSES,
        SUCCESS_STATUSES,
    )
    from app.models import CommunicationLog

    cutoff = _now() - timedelta(hours=EMAIL_HEALTH_WINDOW_HOURS)
    rows = (
        db.query(CommunicationLog.status, func.count(CommunicationLog.id))
        .filter(
            CommunicationLog.channel == CHANNEL_EMAIL,
            CommunicationLog.created_at >= cutoff,
        )
        .group_by(CommunicationLog.status)
        .all()
    )
    counts = {str(s): int(c) for s, c in rows}
    success = sum(counts.get(s, 0) for s in SUCCESS_STATUSES)
    failure = sum(counts.get(s, 0) for s in FAILURE_STATUSES)
    attempts = success + failure
    # queued/suppressed sayılmaz: henüz denenmedi ya da bilinçli gönderilmedi.
    if attempts < EMAIL_HEALTH_MIN_SAMPLE:
        return 0
    return int(round(failure * 100.0 / attempts))


def _val_moment_silent(db: Session) -> int:
    """Sessiz kalan bağlamsal uyarı (moment) sayısı — Faz C (2026-08-04).

    moments.silent_moment_report: koşulu sağlayan + panelde gerçekten gezinen
    (login / ilgili sayfa ziyareti) ama son 48 saatte sinyali ALMAYAN kullanıcı
    sayısı. 0'dan büyükse bir bağlamsal uyarı yüzeyi kırılmış demektir
    (koşul kodu, endpoint kancası veya kayıt zinciri). E-posta kesintisi
    dersinin bağlamsal uyarılara uygulanması: ölçülmeyen kırılma sessiz kalır.
    """
    from app.services import moments

    try:
        # 90 günden eski gösterim izlerini fırsatçı temizle (ayrı cron yok)
        moments.purge_old_events(db)
    except Exception:
        logger.warning("moment purge fail (non-fatal)")
    return moments.silent_total(db)


# Kural key → değer hesaplayıcı + severity hesaplayıcı
EVALUATORS = {
    "high_failed_logins": _val_high_failed_logins,
    "oldest_queued_long": _val_oldest_queued_long,
    "error_groups_open": _val_error_groups_open,
    "abuse_open": _val_abuse_open,
    "payment_problem_recent": _val_payment_problem_recent,
    "email_delivery_failing": _val_email_delivery_failing,
    "moment_silent": _val_moment_silent,
}


# Kod-tanımlı yerleşik kurallar — DB'de yoksa İLK değerlendirmede/listelemede
# idempotent eklenir (migration'sız rollout; "seed'le dolan tablo" kuralının
# lazy karşılığı — cron saatlik evaluate_all çağırdığı için prod'da kendiliğinden
# oluşur).
_BUILTIN_RULES = [
    {
        "key": "payment_problem_recent",
        "name": "Ödeme sorunu (son 24 saat)",
        "description": (
            "Başarısız kart ödemesi VEYA 30 dakikadan uzun süredir yarım kalmış "
            "3D Secure işlemi. Müşteri ödeme adımında hata yaşıyor olabilir — "
            "iyzico paneli + /admin/security-monitor'dan işlem detayına bak."
        ),
        "threshold": 0,          # tek sorun bile alarmlar (hacim düşük)
        "cooldown_minutes": 360,
        "channels": "email,in_app",
    },
    {
        "key": "email_delivery_failing",
        "name": "E-posta gönderimi başarısız",
        "description": (
            "Son 24 saatte denenen e-postaların büyük kısmı ulaşmadı. Sağlayıcı "
            "(ZeptoMail) reddediyor olabilir — abonelik/kota bitmiş, API anahtarı "
            "değişmiş ya da alan adı doğrulaması düşmüş olabilir. Şifre sıfırlama "
            "ve veli bildirimleri bu süre boyunca ULAŞMAZ. "
            "/admin/communication-health sayfasından hata mesajına bak."
        ),
        # %40 üstü başarısızlık → uyarı, %80 üstü → kritik (severity 2x kuralı).
        # Tam kesinti (%100) daima kritik.
        "threshold": 40,
        "cooldown_minutes": 360,
        # push ÖNCE: e-posta çöktüğünde e-posta kanalı bu alarmı taşıyamaz.
        "channels": "push,in_app,email",
    },
    {
        "key": "moment_silent",
        "name": "Bağlamsal uyarı gösterilmedi (moment sessiz)",
        "description": (
            "Koşulu sağlayan ve panelde gezinen bir kullanıcıya beklenen "
            "bağlamsal uyarı (deneme bitiyor bandı, ödeme duvarı, kredi azaldı "
            "kartı...) son 48 saatte hiç sunulmadı. Uyarı yüzeyi kırılmış "
            "olabilir — koşul kodu, API kancası veya banner. Detay: alarm "
            "kaydındaki özet + scripts/run_moment_checks.py ile yerinde test."
        ),
        "threshold": 0,           # tek sessiz kullanıcı bile alarmlar
        "cooldown_minutes": 720,  # günde en çok 2 kez
        "channels": "push,in_app,email",
    },
]


def _ensure_builtin_rules(db: Session) -> None:
    """Eksik yerleşik kuralları ekle (idempotent, best-effort)."""
    try:
        existing = {k for (k,) in db.query(AlarmRule.key).all()}
        added = False
        for spec in _BUILTIN_RULES:
            if spec["key"] in existing:
                continue
            db.add(AlarmRule(
                key=spec["key"], name=spec["name"],
                description=spec["description"], threshold=spec["threshold"],
                cooldown_minutes=spec["cooldown_minutes"], enabled=True,
                channels=spec["channels"],
                created_at=_now(), updated_at=_now(),
            ))
            added = True
        if added:
            db.commit()
    except Exception:
        db.rollback()
        logger.exception("ensure_builtin_rules fail")


def _severity_for(rule_key: str, value: int, threshold: int) -> str:
    """Eşiği ne kadar aşmış? 2x → critical, ortası → warn."""
    if threshold <= 0:
        return "warn" if value > 0 else "info"
    ratio = value / threshold
    if ratio >= 2.0:
        return "critical"
    if ratio >= 1.0:
        return "warn"
    return "info"


# ---------------------------- Engine ----------------------------


@dataclass
class EvaluationResult:
    rule_key: str
    value: int
    threshold: int
    triggered: bool
    skipped_reason: str | None  # cooldown, disabled, ya da None


def _in_cooldown(rule: AlarmRule, *, now: datetime) -> bool:
    if rule.last_triggered_at is None or rule.cooldown_minutes <= 0:
        return False
    last = _aware(rule.last_triggered_at)
    if last is None:
        return False
    return (now - last).total_seconds() < rule.cooldown_minutes * 60


def _event_details(
    db: Session, *, rule_key: str, value: int, threshold: int,
) -> dict:
    """AlarmEvent.details_json — kurala özgü okunur özet (best-effort)."""
    d: dict = {"value": value, "threshold": threshold}
    if rule_key == "moment_silent":
        try:
            from app.services import moments
            d["summary"] = moments.silent_summary_text(db)
        except Exception:
            logger.warning("moment_silent summary fail")
    elif rule_key == "payment_problem_recent":
        # Alarm kendini açıklasın (2026-08-04 kullanıcı isteği): hangi işlem,
        # kim, ne durumda + müdahale ipucu — panelde alarm satırının altında.
        try:
            d["summary"] = _payment_problem_summary(db)
        except Exception:
            logger.warning("payment_problem summary fail")
    return d


def _payment_problem_summary(db: Session) -> str:
    """Son 24 saatin sorunlu ödeme işlemleri — okunur tek satır/işlem."""
    from app.models import PaymentTransaction, User as UserModel

    now = _now()
    cutoff_24h = now - timedelta(hours=24)
    stuck_cutoff = now - timedelta(minutes=30)
    txs = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.created_at >= cutoff_24h,
            (
                (PaymentTransaction.status == "failed")
                | (
                    PaymentTransaction.status.in_(["pending", "3ds_pending"])
                    & (PaymentTransaction.created_at < stuck_cutoff)
                )
            ),
        )
        .order_by(PaymentTransaction.id.desc())
        .limit(10)
        .all()
    )
    if not txs:
        return "Sorunlu işlem kalmadı (pencere içinde çözülmüş)."
    parts = []
    for t in txs:
        u = db.get(UserModel, t.user_id)
        email = "?"
        if u and u.email and "@" in u.email:
            email = u.email[:3] + "***" + u.email[u.email.find("@"):]
        if t.status == "failed":
            durum = f"BAŞARISIZ ({(t.status_reason or 'sebep yok')[:60]})"
            ipucu = "kart reddedildi — gerekirse müşteriyle iletişime geç"
        else:
            durum = "YARIM 3DS (müşteri ödeme sayfasını yarıda bıraktı ya da callback ulaşmadı)"
            ipucu = "iyzico panelinde tahsilat VARSA manuel aktive et; yoksa satış fırsatı"
        ts = t.created_at.strftime("%d/%m %H:%M") if t.created_at else "?"
        parts.append(
            f"işlem #{t.id} · {email} · {t.plan_code} {t.amount} TL · {durum} · {ts} UTC → {ipucu}"
        )
    return " || ".join(parts)


def evaluate_all(db: Session) -> list[EvaluationResult]:
    """Tüm enabled kuralları çalıştır. Tetiklenenler için AlarmEvent yaz + bildir."""
    now = _now()
    _ensure_builtin_rules(db)
    rules = db.query(AlarmRule).all()
    results: list[EvaluationResult] = []

    for rule in rules:
        if not rule.enabled:
            results.append(EvaluationResult(
                rule_key=rule.key, value=0, threshold=rule.threshold,
                triggered=False, skipped_reason="disabled",
            ))
            continue
        evaluator = EVALUATORS.get(rule.key)
        if evaluator is None:
            results.append(EvaluationResult(
                rule_key=rule.key, value=0, threshold=rule.threshold,
                triggered=False, skipped_reason="no_evaluator",
            ))
            continue
        try:
            value = evaluator(db)
        except Exception:
            logger.exception("alarm evaluator fail rule=%s", rule.key)
            results.append(EvaluationResult(
                rule_key=rule.key, value=0, threshold=rule.threshold,
                triggered=False, skipped_reason="evaluator_error",
            ))
            continue

        rule.last_value = value
        rule.updated_at = now

        should_trigger = value > rule.threshold
        # abuse_open: threshold=0 ise her tek sinyal alarmlar
        if rule.key == "abuse_open" and rule.threshold == 0:
            should_trigger = value > 0

        if not should_trigger:
            results.append(EvaluationResult(
                rule_key=rule.key, value=value, threshold=rule.threshold,
                triggered=False, skipped_reason=None,
            ))
            continue

        if _in_cooldown(rule, now=now):
            results.append(EvaluationResult(
                rule_key=rule.key, value=value, threshold=rule.threshold,
                triggered=False, skipped_reason="cooldown",
            ))
            continue

        # TETİK
        severity = _severity_for(rule.key, value, rule.threshold)
        channels = [c.strip() for c in (rule.channels or "").split(",") if c.strip()]
        event = AlarmEvent(
            rule_key=rule.key,
            rule_name=rule.name,
            value=value,
            threshold=rule.threshold,
            severity=severity,
            channels_attempted=",".join(channels),
            delivery_status="pending",
            details_json=json.dumps(
                _event_details(db, rule_key=rule.key, value=value,
                               threshold=rule.threshold),
                ensure_ascii=False,
            ),
            triggered_at=now,
        )
        db.add(event)
        rule.last_triggered_at = now

        # Kanallara gönder (defansif)
        delivery_parts: list[str] = []
        if "email" in channels:
            try:
                ok, total = _send_email_to_super_admins(db, rule=rule, event=event)
                delivery_parts.append(f"email:{ok}/{total}")
            except Exception:
                logger.exception("alarm email fail rule=%s", rule.key)
                delivery_parts.append("email:fail")
        if "push" in channels:
            # E-postadan BAĞIMSIZ kanal — e-posta çöktüğünde alarmı taşıyan tek
            # yol budur (2026-07-30 dersi: 10 günlük e-posta kesintisi fark
            # edilmedi çünkü uyarı da e-postayla gönderiliyordu).
            try:
                sent = _send_push_to_super_admins(db, rule=rule, event=event)
                delivery_parts.append(f"push:{sent}")
            except Exception:
                logger.exception("alarm push fail rule=%s", rule.key)
                delivery_parts.append("push:fail")
        if "in_app" in channels:
            # In-app şu an: AlarmEvent satırı zaten yazılı → /admin/security-monitor/alarms görür
            delivery_parts.append("in_app:ok")
        event.delivery_status = "|".join(delivery_parts) or "noop"

        results.append(EvaluationResult(
            rule_key=rule.key, value=value, threshold=rule.threshold,
            triggered=True, skipped_reason=None,
        ))

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("alarm evaluate_all commit fail")

    return results


def _active_super_admins(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == UserRole.SUPER_ADMIN, User.is_active.is_(True))
        .all()
    )


def _send_push_to_super_admins(
    db: Session, *, rule: AlarmRule, event: AlarmEvent
) -> int:
    """Mobil push — GERÇEKTEN gönderilen mesaj sayısını döner. ASLA raise etmez.

    Kayıtlı cihaz yoksa 0 döner: "push:0" teslimat kaydında görünür. Bunu
    "push:N" gibi göstermek yanlış güven verirdi — bu alarmın var olma sebebi
    tam olarak sessiz başarısızlıktı.
    """
    from app.services.push_notifications import send_push_to_user

    sent = 0
    for a in _active_super_admins(db):
        try:
            sent += send_push_to_user(
                db,
                user_id=a.id,
                title=f"[{event.severity.upper()}] {rule.name}",
                body=f"Değer: {event.value} (eşik: {event.threshold}). Panelden kontrol et.",
                data={"type": "admin_alarm", "rule_key": rule.key, "screen": "alarms"},
            )
        except Exception:  # noqa: BLE001
            logger.warning("alarm push fail user=%s", a.id, exc_info=True)
    return sent


def _alarm_email_recipients(db: Session) -> list[str]:
    """Süper admin e-postaları + config'teki ek alıcılar (tekilleştirilmiş).

    Ek alıcı gerekçesi: kurumsal alan adı/posta kutusu sorunlu olduğunda bile
    ulaşılabilir bir adres (örn. kişisel Gmail) kalsın.
    """
    from app.config import settings

    out: list[str] = []
    seen: set[str] = set()
    for a in _active_super_admins(db):
        if a.email and a.email.lower() not in seen:
            seen.add(a.email.lower())
            out.append(a.email)
    for raw in (settings.alarm_extra_emails or "").split(","):
        addr = raw.strip()
        if addr and "@" in addr and addr.lower() not in seen:
            seen.add(addr.lower())
            out.append(addr)
    return out


def _send_email_to_super_admins(
    db: Session, *, rule: AlarmRule, event: AlarmEvent
) -> tuple[int, int]:
    """E-posta süper adminlere + ek alıcılara. (başarılı, toplam) döner.

    send_email bool döndürür; onu OLDUĞU GİBİ raporlarız. Eskiden istisna
    fırlamadığı sürece "email:ok" yazılıyordu — sağlayıcı reddetse bile başarılı
    görünüyordu. E-posta kesintisini 10 gün gizleyen körlük tam olarak buydu.
    """
    try:
        from app.services.email_service import send_email
    except Exception:
        logger.warning("email_service unavailable — alarm log only")
        return (0, 0)
    recipients = _alarm_email_recipients(db)
    if not recipients:
        return (0, 0)
    ctx = {
        "rule_name": rule.name,
        "rule_key": rule.key,
        "rule_description": rule.description or "",
        "value": event.value,
        "threshold": event.threshold,
        "severity": event.severity,
        "triggered_at_display": event.triggered_at.strftime("%d %B %Y, %H:%M UTC"),
    }
    ok = 0
    for addr in recipients:
        try:
            if send_email(addr, "security_alarm_triggered", ctx):
                ok += 1
        except Exception:
            logger.exception("alarm email send fail to=%s", addr)
    return (ok, len(recipients))


# ---------------------------- Listing + ack ----------------------------


def _details_summary(details_json: str | None) -> str | None:
    """AlarmEvent.details_json icindeki 'summary' alani (varsa)."""
    if not details_json:
        return None
    try:
        d = json.loads(details_json)
        v = d.get("summary")
        return str(v) if v else None
    except Exception:
        return None


def list_recent_events(
    db: Session, *, hours: int = 72, only_unacknowledged: bool = False, limit: int = 50
) -> list[dict]:
    cutoff = _now() - timedelta(hours=hours)
    q = db.query(AlarmEvent).filter(AlarmEvent.triggered_at >= cutoff)
    if only_unacknowledged:
        q = q.filter(AlarmEvent.acknowledged_at.is_(None))
    rows = q.order_by(desc(AlarmEvent.triggered_at)).limit(limit).all()
    now = _now()
    out: list[dict] = []
    for r in rows:
        tr = _aware(r.triggered_at) or now
        out.append({
            "id": r.id,
            "rule_key": r.rule_key,
            "rule_name": r.rule_name,
            "value": r.value,
            "threshold": r.threshold,
            "severity": r.severity,
            "delivery_status": r.delivery_status,
            "triggered_at": tr,
            "acknowledged_at": _aware(r.acknowledged_at),
            "age_seconds": int((now - tr).total_seconds()),
            # Kurala ozgu okunur ozet (moment_silent: hangi uyari kimde sessiz)
            "summary": _details_summary(r.details_json),
            # Çözümleme durumu (2026-08-09) — "Gördüm" ile "çözüldü" ayrı.
            "resolved_at": _aware(r.resolved_at),
            "resolution_note": r.resolution_note,
            "false_positive": bool(r.false_positive),
        })
    return out


def acknowledge(
    db: Session, *, event_id: int, user_id: int, autocommit: bool = True
) -> AlarmEvent | None:
    row = db.get(AlarmEvent, event_id)
    if row is None or row.acknowledged_at is not None:
        return row
    row.acknowledged_at = _now()
    row.acknowledged_by_user_id = user_id
    if autocommit:
        db.commit()
    return row


def acknowledge_older_than(
    db: Session, *, user_id: int, hours: int, autocommit: bool = True
) -> int:
    """Belirtilen saatten ESKİ görülmemiş alarmları toplu "gördüm" işaretle.

    2026-07-31: prod'da 2308 onaysız alarm birikmişti (çoğu Haziran'dan,
    kuralları o zamandan beri düzeltilmiş). Tek tek kapatmak imkânsız olduğu
    için Dikkat Odası aylardır geçersiz uyarılarla doluydu ve gerçek bir sorun
    aradan seçilemiyordu. Kayıt SİLİNMEZ — yalnızca "görüldü" damgası basılır.

    Kaç kayıt işaretlendiğini döner.
    """
    cutoff = _now() - timedelta(hours=hours)
    rows = (
        db.query(AlarmEvent)
        .filter(
            AlarmEvent.acknowledged_at.is_(None),
            AlarmEvent.triggered_at < cutoff,
        )
        .all()
    )
    now = _now()
    for r in rows:
        r.acknowledged_at = now
        r.acknowledged_by_user_id = user_id
    if autocommit:
        db.commit()
    return len(rows)


def unacknowledged_count(db: Session, *, hours: int | None = None) -> int:
    """Görülmemiş alarm sayısı. hours verilirse yalnız o pencere.

    Sol menü rozeti `hours=72` kullanır: geçmişte aylarca birikmiş, artık
    geçerli olmayan alarmlar (prod'da 2300+) rozeti anlamsız bir sayıya
    çevirip alarm körlüğü yaratıyordu. Panel toplamları parametresiz çağırır.
    """
    q = db.query(func.count(AlarmEvent.id)).filter(
        AlarmEvent.acknowledged_at.is_(None)
    )
    if hours is not None:
        q = q.filter(AlarmEvent.triggered_at >= _now() - timedelta(hours=hours))
    return int(q.scalar() or 0)


def list_rules(db: Session) -> list[AlarmRule]:
    _ensure_builtin_rules(db)
    return list(
        db.query(AlarmRule).order_by(AlarmRule.key).all()
    )


def update_rule(
    db: Session,
    *,
    rule_id: int,
    threshold: int | None = None,
    cooldown_minutes: int | None = None,
    enabled: bool | None = None,
    channels: str | None = None,
    autocommit: bool = True,
) -> AlarmRule | None:
    row = db.get(AlarmRule, rule_id)
    if row is None:
        return None
    if threshold is not None:
        row.threshold = int(threshold)
    if cooldown_minutes is not None:
        row.cooldown_minutes = int(cooldown_minutes)
    if enabled is not None:
        row.enabled = bool(enabled)
    if channels is not None:
        row.channels = channels[:60]
    row.updated_at = _now()
    if autocommit:
        db.commit()
    return row


# ---------------------------- Live feed ----------------------------


def live_event_stream(db: Session, *, since_seconds: int = 300, limit: int = 50) -> list[dict]:
    """Son N saniyenin AuditLog + AlarmEvent karışık akışı (descending)."""
    cutoff = _now() - timedelta(seconds=since_seconds)
    audits = (
        db.query(AuditLog)
        .filter(AuditLog.created_at >= cutoff)
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
        .all()
    )
    alarms = (
        db.query(AlarmEvent)
        .filter(AlarmEvent.triggered_at >= cutoff)
        .order_by(desc(AlarmEvent.triggered_at))
        .limit(limit)
        .all()
    )
    # Ham "#87" süper admine hiçbir şey anlatmıyor — aktörleri tek sorguda çöz.
    actor_ids = {a.actor_id for a in audits if a.actor_id}
    kimlik: dict[int, tuple[str | None, str | None]] = {}
    if actor_ids:
        from app.models import User
        for u in db.query(User.id, User.full_name, User.email).filter(
            User.id.in_(actor_ids)
        ).all():
            kimlik[u.id] = (u.full_name, u.email)

    items: list[dict] = []
    for a in audits:
        ad, eposta = kimlik.get(a.actor_id or 0, (None, None))
        items.append({
            "type": "audit",
            "ts": _aware(a.created_at),
            "title": a.action.value if hasattr(a.action, "value") else str(a.action),
            "actor_id": a.actor_id,
            "actor_name": ad,
            "actor_email": eposta,
            "ip": a.ip_address,
            "details": a.email_attempted or "",
            "severity": "critical" if a.action.value in (
                "user_delete", "institution_delete", "impersonate_start",
                "login_locked", "permission_denied"
            ) else "info",
        })
    for e in alarms:
        items.append({
            "type": "alarm",
            "ts": _aware(e.triggered_at),
            "title": e.rule_name,
            "actor_id": None,
            "actor_name": None,
            "actor_email": None,
            "ip": None,
            "details": f"{e.value} (eşik: {e.threshold})",
            "severity": e.severity,
        })
    items.sort(key=lambda x: x["ts"] or _now(), reverse=True)
    return items[:limit]


__all__ = [
    "EvaluationResult",
    "acknowledge",
    "acknowledge_older_than",
    "evaluate_all",
    "list_recent_events",
    "list_rules",
    "live_event_stream",
    "unacknowledged_count",
    "update_rule",
]
