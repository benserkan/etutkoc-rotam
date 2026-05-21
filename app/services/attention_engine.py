"""Katman 11.K.1 — Dikkat Odası (Attention Engine).

Tüm güvenlik kamerası kaynaklarını tarar; "şu an süper admin'in dikkat etmesi
gereken" sıra dışı durumları **bir liste halinde** birleştirir.

Felsefe: 100 kameralı bir odada güvenlik görevlisi her ekrana sürekli bakmaz —
sadece **alarm yanan ekrana** bakar. Bu motor "alarm yanan ekranları" üretir.

11 dedektör (her biri 0..N AttentionItem üretir):
  1. active_impersonations          → CRITICAL — her aktif sahte oturum
  2. super_admin_long_idle          → WARN — 60dk+ idle süper admin oturumu
  3. recent_blocked_ips             → WARN — son 1 saatte oto-bloklu IP
  4. recent_critical_audits         → WARN — son 1 saat içinde X+ kritik aksiyon
  5. unack_alarms                   → severity AlarmEvent'inin kendi şiddetidir
  6. open_abuse_signals             → WARN — açık abuse sinyali
  7. open_critical_errors           → CRITICAL — open hata grubu (resolve yok)
  8. notification_low_success       → WARN — son 24h başarı < %80 ve >50 toplam
  9. trial_imminent                 → INFO/WARN — 1-3 gün kala biten trial
 10. kvkk_sla_breach                → WARN — 30g+ açık KVKK talebi
 11. cron_drift                     → severity drift seviyesine bağlı

Hepsi tek `AttentionItem` listesi, severity descending sıralı.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.models import (
    AbuseSignal,
    ActiveSession,
    AlarmEvent,
    AuditAction,
    AuditLog,
    ErrorEvent,
    ImpersonationSession,
    Institution,
    SuspiciousIp,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# Severity sıralama anahtarları
SEVERITY_RANK = {"critical": 3, "warn": 2, "info": 1}


@dataclass
class AttentionItem:
    """Süper admin panosundaki 'şu an dikkat' kartı."""
    severity: str       # critical / warn / info
    icon: str           # tek emoji (🚨, ⚠️, 🎭, ...)
    title: str          # kısa başlık (max ~60 char)
    description: str    # 1 cümle olay özeti
    action_url: str     # tıklayınca gidilecek alt sayfa
    action_label: str   # "Detay", "İncele", "Kapat"
    category: str       # session / auth / alarm / error / abuse / revenue / integrity
    ts: datetime | None = None  # ilgili olayın zamanı (None = anlık durum)
    score: int = 0      # sıralama için (severity_rank * 100 + custom)
    explainer: str = ""  # 11.K.1+: 'Bu ne demek?' — 3 paragraflı eğitici açıklama

    def sort_key(self) -> tuple[int, int]:
        return (-SEVERITY_RANK.get(self.severity, 0), -self.score)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------- Dedektörler ----------------------------


def _detect_active_impersonations(db: Session) -> list[AttentionItem]:
    """Her aktif sahte oturum bir CRITICAL kart."""
    now = _now()
    rows = (
        db.query(ImpersonationSession)
        .filter(ImpersonationSession.ended_at.is_(None))
        .all()
    )
    items: list[AttentionItem] = []
    # Toplu user lookup
    ids = set()
    for r in rows:
        ids.add(r.actor_user_id)
        ids.add(r.target_user_id)
    users_map: dict[int, User] = {}
    if ids:
        for u in db.query(User).filter(User.id.in_(ids)).all():
            users_map[u.id] = u
    for r in rows:
        actor = users_map.get(r.actor_user_id)
        target = users_map.get(r.target_user_id)
        started = _aware(r.started_at) or now
        expires = _aware(r.expires_at) or now
        mins_left = max(0, int((expires - now).total_seconds() / 60))
        items.append(AttentionItem(
            severity="critical",
            icon="🎭",
            title=(
                f"Sahte oturum: "
                f"{actor.full_name if actor else '#'+str(r.actor_user_id)} → "
                f"{target.full_name if target else '#'+str(r.target_user_id)}"
            ),
            description=(
                f"Gerekçe: \"{r.reason[:120]}\". "
                f"{mins_left} dk sonra otomatik kapanır."
            ),
            action_url="/admin/security-monitor/sessions",
            action_label="Oturumları aç",
            category="session",
            ts=started,
            score=80,
            explainer=(
                "Bir süper admin başka bir kullanıcının (öğretmen/öğrenci/veli/kurum yöneticisi) "
                "hesabına 'geçici olarak girmiş' gibi sistem kullanıyor. Buna 'sahte oturum' "
                "(impersonate) denir. Destek talebi gelen bir öğretmenin gördüğü sorunu yerinde "
                "incelemek için kullanılır. Bu işlem audit log'a kaydedilir; gerekçe zorunlu, "
                "süre en fazla 30 dakika.\n\n"
                "Neden önemli: Bu oturum tanımadığın bir admin tarafından açıldıysa veya "
                "gerekçesi tutarsız görünüyorsa, içeriden bir yetki kötüye kullanımı olabilir. "
                "Kullanıcının kişisel verisine erişim KVKK ihlali doğurur.\n\n"
                "Ne yapmalısın: Gerekçeyi oku. Tanıdığın bir admin değilse veya gerekçe yetersizse "
                "yandaki 'Sonlandır' butonuyla uzaktan kapat — admin otomatik olarak kendi "
                "oturumuna geri döner."
            ),
        ))
    return items


def _detect_super_admin_long_idle(
    db: Session, *, idle_minutes: int = 60
) -> list[AttentionItem]:
    """60dk+ idle süper admin oturumu — unutulmuş oturum riski."""
    now = _now()
    cutoff = now - timedelta(minutes=idle_minutes)
    rows = (
        db.query(ActiveSession, User)
        .join(User, User.id == ActiveSession.user_id)
        .filter(
            ActiveSession.terminated_at.is_(None),
            User.role == UserRole.SUPER_ADMIN,
            ActiveSession.last_seen_at < cutoff,
        )
        .all()
    )
    items: list[AttentionItem] = []
    for sess, user in rows:
        last_seen = _aware(sess.last_seen_at) or now
        idle_min = int((now - last_seen).total_seconds() / 60)
        items.append(AttentionItem(
            severity="warn",
            icon="⏱",
            title=f"Idle süper admin oturumu: {user.full_name or user.email}",
            description=(
                f"{idle_min} dk hareketsiz · IP: {sess.ip or '—'}. "
                f"Tanımadığın bir oturumsa uzaktan kapat."
            ),
            action_url="/admin/security-monitor/sessions",
            action_label="Oturumları aç",
            category="session",
            ts=last_seen,
            score=60 + min(idle_min // 30, 20),
            explainer=(
                "Süper admin yetkisine sahip bir hesabın oturumu açık ama uzun süredir hareket "
                "yok. Süper admin tüm sistemi yönetebilir — kullanıcı silebilir, plan "
                "değiştirebilir, başkasının hesabına girebilir.\n\n"
                "Neden önemli: Açık bilgisayar başında bırakılmış bir süper admin oturumu, "
                "yanından geçen biri için 'parolayı bilmeden tam yetki' demektir. Halka açık "
                "bir cihazdan veya kafede unutulan bir oturum ciddi risktir.\n\n"
                "Ne yapmalısın: Bu senin oturumun değilse 'Sonlandır' butonuyla uzaktan kapat. "
                "Seninse, çıkış yap ve yeniden giriş — sliding session zaten 4 saatte bir "
                "yenilenir, ama proaktif çıkış güvenli alışkanlık."
            ),
        ))
    return items


def _detect_recent_blocked_ips(
    db: Session, *, hours: int = 1
) -> list[AttentionItem]:
    """Son N saatte blok'a giren IP (otomatik veya manuel)."""
    now = _now()
    cutoff = now - timedelta(hours=hours)
    rows = (
        db.query(SuspiciousIp)
        .filter(
            SuspiciousIp.blocked_until.isnot(None),
            SuspiciousIp.blocked_until > now,
            SuspiciousIp.last_seen_at >= cutoff,
        )
        .order_by(desc(SuspiciousIp.last_seen_at))
        .limit(5)
        .all()
    )
    items: list[AttentionItem] = []
    for r in rows:
        items.append(AttentionItem(
            severity="warn",
            icon="🚫",
            title=f"IP bloklandı: {r.ip}",
            description=(
                f"{r.fail_count} başarısız giriş, {r.distinct_email_count} "
                f"farklı e-posta denedi. Sebep: {r.block_reason or 'manual'}."
            ),
            action_url="/admin/security-monitor/sessions",
            action_label="IP listesi",
            category="auth",
            ts=_aware(r.last_seen_at),
            score=55,
            explainer=(
                "Bir bilgisayardan (IP adresi: internet üzerindeki adres) çok kısa sürede "
                "defalarca yanlış şifre denendi. Sistem bunu otomatik fark etti ve o IP'yi "
                "1 saat boyunca login sayfasına almamak için engelledi. Bu davranış "
                "'brute force' (kaba kuvvet) saldırısının tipik işaretidir: saldırgan, "
                "bir kullanıcının şifresini tahmin etmeye çalışır.\n\n"
                "Neden önemli: Otomatik blok 1 saatlik bir savunma. Aynı IP süre sonunda "
                "tekrar deneyebilir. Eğer hâlâ saldırıyorsa daha kalıcı engel gerekir.\n\n"
                "Ne yapmalısın: Süre dolduktan sonra IP yine fail giriş üretirse 'Manuel "
                "blok' formundan 24-720 saat aralığında manuel engel ekle. Şüphelendiğin "
                "kullanıcı hesabını da kontrol et — gerekirse şifresini sıfırla."
            ),
        ))
    return items


def _detect_recent_critical_audits(
    db: Session, *, hours: int = 1, threshold: int = 3
) -> list[AttentionItem]:
    """Son 1 saatte 3+ kritik aksiyon = yoğun dönem."""
    from app.services.security_monitor import CRITICAL_AUDIT_ACTIONS
    now = _now()
    cutoff = now - timedelta(hours=hours)
    count = (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.action.in_(list(CRITICAL_AUDIT_ACTIONS)),
            AuditLog.created_at >= cutoff,
        )
        .scalar()
    ) or 0
    if count < threshold:
        return []
    return [AttentionItem(
        severity="warn",
        icon="📍",
        title=f"Son 1 saatte {count} kritik aksiyon",
        description=(
            f"Silme/rol değişimi/şifre sıfırlama gibi kritik işlemler "
            f"yoğunlaşmış — beklenmedik bir paterm varsa incele."
        ),
        action_url="/admin/audit",
        action_label="Audit log'a git",
        category="auth",
        ts=now,
        score=50,
        explainer=(
            "Sistemde 'kritik aksiyon' diye işaretlenen işlemler şunlar: kullanıcı silme, "
            "rol değişimi (örn. öğretmeni admin yapma), şifre sıfırlama (admin tarafından), "
            "sahte oturum açma, kurum silme, hesap kilitleme. Bu işlemler tek tek normaldir "
            "ama 1 saat içinde 3'ten fazla yoğunlaşırsa dikkat çeker.\n\n"
            "Neden önemli: Kötü niyetli bir senaryoda saldırgan ele geçirdiği admin "
            "hesabıyla peş peşe rol değişimi/silme yapabilir. Bu pattern 'içeriden saldırı' "
            "veya 'sistem ele geçirilmiş' işaretidir.\n\n"
            "Ne yapmalısın: Audit log sayfasına git, son 1 saatin kayıtlarını filtrele. "
            "Kim hangi işlemi yapmış? Bilinen bir admin'in toplu temizlik mi yapıyor yoksa "
            "şüpheli bir aktör mü? Şüphe varsa admin hesabını geçici devre dışı bırak."
        ),
    )]


def _detect_unack_alarms(db: Session) -> list[AttentionItem]:
    """Onaylanmamış AlarmEvent'ler — severity'lerine göre."""
    rows = (
        db.query(AlarmEvent)
        .filter(AlarmEvent.acknowledged_at.is_(None))
        .order_by(desc(AlarmEvent.triggered_at))
        .limit(8)
        .all()
    )
    items: list[AttentionItem] = []
    icons = {"critical": "🚨", "warn": "⚠️", "info": "ℹ️"}
    for r in rows:
        sev = r.severity if r.severity in SEVERITY_RANK else "warn"
        items.append(AttentionItem(
            severity=sev,
            icon=icons.get(sev, "🔔"),
            title=f"Alarm: {r.rule_name}",
            description=f"Değer {r.value} (eşik {r.threshold}). Henüz görülmedi.",
            action_url="/admin/security-monitor/alarms",
            action_label="Onayla",
            category="alarm",
            ts=_aware(r.triggered_at),
            score=70 if sev == "critical" else 45,
            explainer=(
                "Sistem otomatik bir 'alarm kuralı' tetikledi. Alarm kuralı bir ölçümün "
                "(örn. başarısız login sayısı, kuyrukta bekleyen bildirim, açık hata grubu) "
                "belirlediğin eşiği aştığını gösterir. Tetiklendikten sonra süper adminlere "
                "e-posta da gönderilir.\n\n"
                "Neden önemli: 'Onaylanmamış alarm' birinin görmesini bekleyen bir bildirimdir. "
                "Eğer bu liste şişerse alarm yorgunluğu (alarm fatigue) oluşur — gerçek bir "
                "sorun olduğunda ayırt edilemez.\n\n"
                "Ne yapmalısın: Alarmlar sayfasına geç, alarmı inceledikten sonra 'Gördüm' "
                "butonuna bas. Eğer bu kural çok yanlış-pozitif tetikliyorsa kuralın eşiğini "
                "veya cooldown süresini (alarm sayfasından) yükselt."
            ),
        ))
    return items


def _detect_open_abuse_signals(db: Session) -> list[AttentionItem]:
    """Açık abuse sinyali."""
    rows = (
        db.query(AbuseSignal)
        .filter(AbuseSignal.resolved_at.is_(None))
        .order_by(desc(AbuseSignal.last_seen_at))
        .limit(5)
        .all()
    )
    items: list[AttentionItem] = []
    from app.models import ABUSE_KIND_LABELS_TR
    for r in rows:
        kind_label = ABUSE_KIND_LABELS_TR.get(r.kind, r.kind)
        sev = r.severity if r.severity in SEVERITY_RANK else "warn"
        items.append(AttentionItem(
            severity=sev,
            icon="🚨",
            title=f"Abuse: {kind_label} ({r.count})",
            description=(
                f"Pencere içinde eşik aşıldı. "
                f"Detay ve çöz işaretle: /admin/security-monitor/abuse"
            ),
            action_url="/admin/security-monitor/abuse",
            action_label="İncele",
            category="abuse",
            ts=_aware(r.last_seen_at),
            score=55 if sev == "warn" else 75,
            explainer=(
                "Sistem, normal davranış sınırlarının üstünde bir kalıp tespit etti. "
                "'Abuse' (kötüye kullanım) sinyalleri 4 tip olabilir: bir öğretmenin 1 saatte "
                "50+ veli daveti göndermesi (yanlış liste veya spam?), bir kurumun 1 saatte "
                "200+ bildirim üretmesi (taciz veya teknik döngü?), aynı cihazdan 3+ farklı "
                "hesaba giriş (şifre paylaşımı?), bir kurumdan 24h'de 10+ bildirim "
                "sessizleştirme (alıcı şikayeti?).\n\n"
                "Neden önemli: Bu tek başına suç değildir — ama 'beklenmedik yoğunluk' "
                "işaretidir. Gerçek bir teknik hata, yetkili biri tarafından yanlış kullanım, "
                "veya kötü niyet olabilir.\n\n"
                "Ne yapmalısın: 'İncele' diyerek Abuse panosunda detayı aç. Kim/hangi kurum, "
                "ne yapmış? İlgili kullanıcıyla iletişime geçilebilir; ciddiyse hesap "
                "kısıtlama veya plan değişikliği. Yanlış pozitifse 'Çöz' diyerek kapat."
            ),
        ))
    return items


def _detect_open_critical_errors(db: Session) -> list[AttentionItem]:
    """Open ErrorEvent'ler — en yüksek count'lu 3 tanesi."""
    rows = (
        db.query(ErrorEvent)
        .filter(ErrorEvent.resolved_at.is_(None))
        .order_by(desc(ErrorEvent.count))
        .limit(3)
        .all()
    )
    items: list[AttentionItem] = []
    for r in rows:
        # Çok yüksek count → critical, az → warn
        sev = "critical" if (r.count or 0) >= 10 else "warn"
        items.append(AttentionItem(
            severity=sev,
            icon="🔧",
            title=f"{r.exception_type or 'HTTPError'}: {r.endpoint}",
            description=(
                f"{r.count} kez tetiklendi. "
                f"{(r.exception_message or '')[:100]}"
            ),
            action_url="/admin/security-monitor/system",
            action_label="Hata grubunu aç",
            category="error",
            ts=_aware(r.last_seen_at),
            score=70 if sev == "critical" else 50,
            explainer=(
                "Bir kullanıcı sistemin bir sayfasını kullanırken kod düzeyinde hata oluştu "
                "(programcıların 'exception' dediği şey). Sistem hatayı yakaladı, kullanıcıya "
                "muhtemelen 'bir hata oluştu' mesajı gösterdi ama detayını programcı için "
                "buraya kaydetti. Aynı hata kod konumundan tekrar gelse sayaç artar, yeni "
                "satır açılmaz.\n\n"
                "Neden önemli: 10+ kez tekrarlamış bir hata = düzenli olarak kullanıcı "
                "etkilenmiş demektir. Şikayet gelmeden önce fark etmek değerlidir.\n\n"
                "Ne yapmalısın: 'Hata grubunu aç' diyerek stack trace (hatanın kod yolu) "
                "ve ilk/son tetiklenme zamanını gör. Geliştiriciye iletilebilir veya "
                "geçici çare bulunabilir. Çözüldüğünde 'Çöz' işaretle — aynı hata tekrar "
                "tetiklenirse otomatik tekrar açılır."
            ),
        ))
    return items


def _detect_notification_low_success(db: Session) -> list[AttentionItem]:
    """Son 24h bildirim başarı % < 80 ve toplam > 50 → kart."""
    try:
        from app.services.notification_health import window_summary
        s = window_summary(db, hours=24, label="24h")
        if s.total < 50:
            return []
        if s.success_pct is None or s.success_pct >= 80:
            return []
        sev = "critical" if s.success_pct < 50 else "warn"
        return [AttentionItem(
            severity=sev,
            icon="📨",
            title=f"Bildirim başarı düşük: %{s.success_pct}",
            description=(
                f"24h: {s.sent} gitti / {s.failed} hata. "
                f"Dispatcher veya kanal sorunu olabilir."
            ),
            action_url="/admin/security-monitor/notifications",
            action_label="Paneli aç",
            category="notification",
            ts=_now(),
            score=65 if sev == "critical" else 45,
            explainer=(
                "Veliye giden günlük özet, drop alert, sınav yaklaşıyor gibi bildirimler "
                "e-posta veya WhatsApp ile gönderilir. Normal başarı oranı %95+ olmalı. "
                "Bu rozet, son 24 saatte oranın %80'in altına düştüğünü gösterir.\n\n"
                "Neden önemli: Düşük başarı = veliler önemli bildirimleri almıyor. "
                "Çocuğunun derslerini takip eden veliler için ciddi etki; abone kaybına "
                "kadar gidebilir. Olası sebepler: SMTP (e-posta sunucusu) arızası, "
                "WhatsApp token süresi dolması, Meta API kotası aşımı, veliler şikayet "
                "edip spam işaretledi.\n\n"
                "Ne yapmalısın: 'Paneli aç' diyerek Bildirim Teslimat panosuna geç. "
                "Hangi kanal (email/whatsapp) hata aldı, neden bastırıldı (suppress reason) "
                "dağılımına bak. WhatsApp token'ı süresi dolduysa /admin altından yenile."
            ),
        )]
    except Exception:
        logger.exception("notification low_success detect fail")
        return []


def _detect_trial_imminent(db: Session) -> list[AttentionItem]:
    """1-3 gün kala biten trial → ticari fırsat kartı."""
    try:
        from app.services.revenue_panel import trial_ending_soon
        trials = trial_ending_soon(db, days_horizon=3)
        items: list[AttentionItem] = []
        # Tek özet kart (her trial için ayrı kart kalabalık olur)
        if not trials:
            return []
        urgent = [t for t in trials if t.days_left <= 1]
        sev = "warn" if urgent else "info"
        names = ", ".join(t.institution_name for t in trials[:3])
        more = f" +{len(trials) - 3} daha" if len(trials) > 3 else ""
        return [AttentionItem(
            severity=sev,
            icon="⏳",
            title=f"{len(trials)} trial 3 gün içinde bitiyor",
            description=f"Yakın bitenler: {names}{more}",
            action_url="/admin/security-monitor/revenue",
            action_label="Trial listesi",
            category="revenue",
            ts=_now(),
            score=40 if urgent else 25,
            explainer=(
                "Kurumlar Rotam'a kayıt olduğunda 30 günlük ücretsiz deneme süresi (trial) "
                "alır; bireysel öğretmenler 14 gün. Süre bittiğinde 'post_trial_plan' alanında "
                "yazılı plana (genelde ücretsiz tier'a) otomatik düşer. Bu rozet, 3 gün "
                "içinde trial'ı dolacak kurumları gösterir.\n\n"
                "Neden önemli: Trial bitmeden ödemeye geçen kurumlar gerçek müşterindir. "
                "Trial bittikten sonra ücretsiz tier'a düşen bir kurumun çoğu yeniden geri "
                "gelmez. Bu pencerede dokunuş (hatırlatma e-postası, demo görüşmesi, "
                "destek) dönüşüm oranını %30+ artırabilir.\n\n"
                "Ne yapmalısın: 'Trial listesi' diyerek Ticari panosuna geç. Liste içinde "
                "her kurumun adına tıklayıp ilgili kurum yöneticisinin iletişim bilgisini "
                "gör. Hızlı bir telefon veya WhatsApp mesajı genelde yeterli."
            ),
        )]
    except Exception:
        logger.exception("trial_imminent detect fail")
        return []


def _detect_kvkk_sla_breach(db: Session) -> list[AttentionItem]:
    """KVKK 30g SLA aşımı."""
    try:
        from app.services.data_integrity import kvkk_sla_check
        sla = kvkk_sla_check(db)
        if sla["overdue_count"] == 0:
            return []
        return [AttentionItem(
            severity="warn",
            icon="📋",
            title=f"KVKK: {sla['overdue_count']} talep 30g+",
            description=(
                f"Yasal SLA aşıldı. Hemen incelenmeli — yaptırım riski."
            ),
            action_url="/admin/kvkk",
            action_label="KVKK panosu",
            category="integrity",
            ts=_now(),
            score=60,
            explainer=(
                "Türkiye'de KVKK (Kişisel Verilerin Korunması Kanunu) gereği, bir kullanıcı "
                "'verilerimi sil' veya 'verilerimi dışa aktar' diye talep ederse sistem bu "
                "talebi 30 gün içinde işleme almak zorundadır. Yasal süre aşımı, KVKK "
                "Kurumu'na şikayet edildiğinde **idari para cezasına** yol açar (yıllık "
                "ciroya göre 6 milyon TL'ye kadar).\n\n"
                "Neden önemli: Bu sadece 'iyi olur' değil, **yasal zorunluluk**. Birden "
                "fazla talep geciktiyse risk büyür çünkü tek bir şikayet bile denetimi "
                "başlatabilir.\n\n"
                "Ne yapmalısın: 'KVKK panosu' diyerek bekleyen talepleri aç. Her birini "
                "tek tek incele: dışa aktarma talebi mi (kullanıcının kendi verisini "
                "PDF/JSON olarak yollamak), silme talebi mi (anonimleştirme). Onaylanan "
                "silme talepleri 30 günlük grace period sonra otomatik uygulanır."
            ),
        )]
    except Exception:
        logger.exception("kvkk_sla detect fail")
        return []


def _detect_cron_drift(db: Session) -> list[AttentionItem]:
    """Cron drift critical durumdaki job'lar."""
    try:
        from app.services.data_integrity import cron_drift_check
        cd = cron_drift_check(db)
        if cd["summary"]["critical"] == 0:
            return []
        crit_jobs = [j for j in cd["jobs"] if j["level"] == "critical"][:3]
        names = ", ".join(j["job_key"] for j in crit_jobs)
        more = f" +{cd['summary']['critical'] - 3}" if cd["summary"]["critical"] > 3 else ""
        return [AttentionItem(
            severity="critical",
            icon="🩺",
            title=f"{cd['summary']['critical']} cron 48 saattir çalışmıyor",
            description=f"{names}{more}",
            action_url="/admin/security-monitor/integrity",
            action_label="Bütünlük panosu",
            category="integrity",
            ts=_now(),
            score=75,
            explainer=(
                "'Cron' sistemde belirli aralıklarla otomatik çalışan iş demektir. Rotam'da "
                "çok sayıda cron var: her gece veli özetlerini yollayan, ay başı kredileri "
                "yenileyen, eski log'ları temizleyen, alarm motorunu 5 dakikada bir "
                "çalıştıran, abuse tespitini her saat yapan vb.\n\n"
                "Neden önemli: Bir cron 48 saattir çalışmıyorsa o işin yapması gereken "
                "şeyler **olmadı**. Veliye günlük özet gitmedi, alarm tetiklenmedi, "
                "eski hata kayıtları silinmedi. En olası sebep: dispatcher loop'u "
                "(arka plan işleyicisi) çökmüş veya restart sırasında başlamamış.\n\n"
                "Ne yapmalısın: 'Bütünlük panosu' diyerek hangi cron'ların hangi son hata "
                "ile durduğunu gör. Sunucuyu yeniden başlatmak çoğu zaman yeterlidir "
                "(`pkill uvicorn && python -m uvicorn ...`). Hata mesajı kod-bug "
                "gösteriyorsa geliştiriciye iletilebilir."
            ),
        )]
    except Exception:
        logger.exception("cron_drift detect fail")
        return []


def _detect_open_system_errors_count(db: Session) -> list[AttentionItem]:
    """Açık hata grubu sayısı yüksekse tek özet kart."""
    open_groups = (
        db.query(func.count(ErrorEvent.id))
        .filter(ErrorEvent.resolved_at.is_(None))
        .scalar()
    ) or 0
    if open_groups < 5:
        return []
    sev = "critical" if open_groups >= 15 else "warn"
    return [AttentionItem(
        severity=sev,
        icon="🔧",
        title=f"{open_groups} açık hata grubu",
        description="Sistem hatası birikmiş — çözüm önceliği gerekli.",
        action_url="/admin/security-monitor/system",
        action_label="Hata listesi",
        category="error",
        ts=_now(),
        score=65 if sev == "critical" else 40,
        explainer=(
            "Sistemde 5'ten fazla farklı kod hatası 'çözüldü' olarak işaretlenmemiş "
            "halde duruyor. Bu, kullanıcıların farklı yerlerde sorun yaşadığını gösterir.\n\n"
            "Neden önemli: Açık hata listesi büyüdükçe 'gerçekten kritik olan'la "
            "'önemsiz olan' karışır. 15'in üstüne çıkarsa muhtemelen kullanıcı şikayetleri "
            "başlayacaktır. Ayrıca veritabanı şişer.\n\n"
            "Ne yapmalısın: 'Hata listesi' diyerek Sistem Hataları panosuna geç. En çok "
            "tekrar eden hatalardan başla — onları çözmek en çok kullanıcıyı etkiler. "
            "30 günden eski 'çözüldü' işaretli kayıtlar zaten otomatik silinir."
        ),
    )]


# ---------------------------- Aggregator ----------------------------


DETECTORS = [
    _detect_active_impersonations,
    _detect_super_admin_long_idle,
    _detect_recent_blocked_ips,
    _detect_recent_critical_audits,
    _detect_unack_alarms,
    _detect_open_abuse_signals,
    _detect_open_critical_errors,
    _detect_open_system_errors_count,
    _detect_notification_low_success,
    _detect_trial_imminent,
    _detect_kvkk_sla_breach,
    _detect_cron_drift,
]


def get_attention_items(db: Session, *, limit: int = 12) -> list[AttentionItem]:
    """Tüm dedektörleri çalıştır, severity descending sıralı liste döndür."""
    items: list[AttentionItem] = []
    for fn in DETECTORS:
        try:
            items.extend(fn(db))
        except Exception:
            logger.exception("attention detector fail: %s", fn.__name__)
    items.sort(key=lambda it: it.sort_key())
    return items[:limit]


def get_attention_summary(db: Session) -> dict:
    """Pano için: kart listesi + kategori sayıları + en yüksek severity."""
    items = get_attention_items(db, limit=12)
    by_severity = {"critical": 0, "warn": 0, "info": 0}
    by_category: dict[str, int] = {}
    for it in items:
        by_severity[it.severity] = by_severity.get(it.severity, 0) + 1
        by_category[it.category] = by_category.get(it.category, 0) + 1
    top_sev = "info"
    if by_severity["critical"] > 0:
        top_sev = "critical"
    elif by_severity["warn"] > 0:
        top_sev = "warn"
    return {
        "items": items,
        "total": len(items),
        "by_severity": by_severity,
        "by_category": by_category,
        "top_severity": top_sev,
        "is_clean": len(items) == 0,
    }


__all__ = [
    "AttentionItem",
    "DETECTORS",
    "SEVERITY_RANK",
    "get_attention_items",
    "get_attention_summary",
]
