"""Alarm Teşhis Kartı — "bu alarm ne demek, ne yapmalıyım, kim tetikledi?"

NEDEN (2026-08-09 kullanıcı direktifi: "alarm körlüğü bu projede tekrarlayan
bir sorun, kapsamlı çözelim"):
Panel alarmı gösteriyordu ama süper admin ne olduğunu anlayamıyordu. Somut
vaka: `moment_silent` iki gün boyunca günde iki kez çaldı; kök nedene ancak
prod'da elle beş ayrı SQL sorgusu koşularak inildi ve alarmın KENDİSİNİN
hatalı olduğu görüldü. Panelde ne "hâlâ geçerli mi?", ne "kimi ilgilendiriyor",
ne de "bu yanlış alarmdı" diyecek bir yer vardı.

Bu servis, Sistem Sağlığı'ndaki `error_translator` desenini alarmlara taşır:
  1. REHBER    — ne oldu / neden tetiklenir / ne yapmalı (kural başına sabit)
  2. CANLI     — kuralı ŞU AN yeniden hesapla: sorun sürüyor mu, geçti mi?
  3. KANIT     — hangi kullanıcı/kayıt tetikledi (tıklanabilir bağlantılarla)
  4. GEÇMİŞ    — bu kural son 30 günde kaç kez çaldı, kaçı yanlış alarmdı

Yeni alarm kuralı eklerken buraya da rehber + kanıt çözücü ekle; yoksa kural
"açıklamasız" kalır ve alarm körlüğü yeniden başlar.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AlarmEvent, User

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------- Rehber ----------------------------


@dataclass(frozen=True)
class AlarmGuide:
    ne_oldu: str
    neden: str
    ne_yapmali: list[str]
    baglantilar: list[tuple[str, str]] = field(default_factory=list)
    # Kimin işi: "sen" (süper admin aksiyonu) · "kod" (geliştirme gerekir)
    # · "saglayici" (dış servis — iyzico/ZeptoMail/Google)
    sorumlu: str = "sen"
    birim: str = ""  # değerin birimi ("adet", "dakika", "%")


GUIDES: dict[str, AlarmGuide] = {
    "high_failed_logins": AlarmGuide(
        birim="başarısız giriş",
        ne_oldu="Son 24 saatte başarısız giriş denemesi normalin üzerine çıktı.",
        neden=(
            "Ya gerçek bir kullanıcı şifresini unutup üst üste deniyor, ya da "
            "birisi otomatik olarak şifre deniyor (kaba kuvvet saldırısı). "
            "Sistem zaten hesabı belirli sayıda yanlıştan sonra kilitler ve "
            "şüpheli IP'yi engeller — bu alarm sadece haber verir."
        ),
        ne_yapmali=[
            "Kanıt listesinde denemeler TEK bir e-postada mı toplanıyor bak — "
            "öyleyse muhtemelen şifresini unutmuş gerçek bir kullanıcıdır; "
            "kendisine şifre sıfırlama bağlantısı gönderebilirsin.",
            "Denemeler ÇOK sayıda farklı e-postaya yayılmışsa saldırı olabilir; "
            "Oturumlar sayfasından ilgili IP'yi engelle.",
            "Tek bir IP'den geliyorsa Oturumlar > şüpheli IP bölümünden "
            "'Bloka al' ile süreli engelle.",
        ],
        baglantilar=[
            ("Oturumlar ve IP engelleme", "/admin/security-monitor/sessions"),
            ("Audit kayıtları", "/admin/audit"),
        ],
    ),
    "oldest_queued_long": AlarmGuide(
        birim="dakika",
        ne_oldu=(
            "Gönderilmeyi bekleyen bir bildirim kuyrukta uzun süre kaldı."
        ),
        neden=(
            "Bildirimleri gönderen arka plan işçisi (worker) durmuş ya da "
            "gönderim sürekli hata alıyor olabilir. Sessiz saat kuralı "
            "nedeniyle ertelenen bildirimler bu sayıma GİRMEZ — yani burada "
            "görünen gecikme gerçek bir gecikmedir."
        ),
        ne_yapmali=[
            "Bildirim Sağlığı sayfasında son hataları oku — sağlayıcı mı "
            "reddediyor, yoksa hiç deneme mi yapılmıyor?",
            "Hiç deneme yoksa worker durmuş olabilir; sunucuda "
            "'docker compose ps' ile lgs-worker ayakta mı bak.",
            "E-posta hataları görünüyorsa İletişim Sağlığı'ndan sağlayıcı "
            "mesajına bak (kota/anahtar/doğrulama sorunu olabilir).",
        ],
        baglantilar=[
            ("Bildirim Sağlığı", "/admin/security-monitor/notifications"),
            ("İletişim Sağlığı", "/admin/communication-health"),
        ],
        sorumlu="kod",
    ),
    "error_groups_open": AlarmGuide(
        birim="açık hata grubu",
        ne_oldu="Uygulamada çözülmemiş hata grupları birikti.",
        neden=(
            "Kullanıcılar bir işlem sırasında hata alıyor olabilir. Yalnız "
            "son 3 günde tekrar etmiş hatalar sayılır; eski/çözülmüş hatalar "
            "bu alarmı tetiklemez."
        ),
        ne_yapmali=[
            "Uygulama Hataları sayfasını aç; her hatanın yanında sade dil "
            "açıklaması (ne oldu / neden / ne yapmalı) yazıyor.",
            "'Kod düzeltmesi gerekir' etiketli olanlar geliştirme işidir — "
            "not al, düzeltilince 'Çözüldü' işaretle.",
            "'Muhtemelen çözülmüş' (bayat) etiketlilerini kapatarak listeyi "
            "temizle.",
        ],
        baglantilar=[("Uygulama Hataları", "/admin/security-monitor/system")],
        sorumlu="kod",
    ),
    "abuse_open": AlarmGuide(
        birim="açık sinyal",
        ne_oldu="Kötüye kullanım şüphesi taşıyan çözülmemiş sinyal var.",
        neden=(
            "Aynı cihazdan çok sayıda hesap açılması, toplu davet gönderimi "
            "veya olağandışı bildirim hacmi gibi desenler otomatik "
            "işaretlenir. Düşük güvenli ('bilgi' seviyesi) sinyaller bu "
            "alarmı tetiklemez."
        ),
        ne_yapmali=[
            "Suistimal sayfasında sinyale bak: aktör gerçekten şüpheli mi, "
            "yoksa kendi test hesaplarımız mı?",
            "Kendi testinse 'Çöz' ile not düşerek kapat — açık bıraktığın "
            "her sinyal bu alarmı tekrar çaldırır.",
            "Gerçek suistimalse ilgili toplu aksiyonu (davetleri iptal et / "
            "bildirimleri bastır / oturumları kapat) uygula.",
        ],
        baglantilar=[("Suistimal sinyalleri", "/admin/security-monitor/abuse")],
    ),
    "payment_problem_recent": AlarmGuide(
        birim="sorunlu işlem",
        ne_oldu=(
            "Son 24 saatte başarısız kart ödemesi veya yarım kalmış 3D Secure "
            "işlemi var."
        ),
        neden=(
            "Müşteri ödeme adımında hata almış ya da 3D Secure ekranını "
            "tamamlamadan çıkmış olabilir. Ödeme hacmi düşük olduğu için "
            "tek bir sorun bile alarm üretir."
        ),
        ne_yapmali=[
            "Kanıt listesindeki işlemin sahibine bak — gerçek müşteri mi, "
            "senin test denemen mi?",
            "Gerçek müşteriyse ara: kart mı reddedildi, 3D şifresi mi "
            "gelmedi? Gerekirse yeni ödeme bağlantısı gönder.",
            "iyzico panelinden aynı işlemin sağlayıcı tarafındaki sonucunu "
            "doğrula.",
        ],
        baglantilar=[
            ("Ödeme linkleri", "/admin/payment-links"),
            ("Ticari pano", "/admin/security-monitor/revenue"),
        ],
        sorumlu="saglayici",
    ),
    "email_delivery_failing": AlarmGuide(
        birim="% başarısız",
        ne_oldu="Son 24 saatte denenen e-postaların büyük kısmı ulaşmadı.",
        neden=(
            "Sağlayıcı (ZeptoMail) reddediyor olabilir: abonelik/kota bitmiş, "
            "API anahtarı değişmiş ya da alan adı doğrulaması düşmüş. Bu "
            "durumda şifre sıfırlama ve veli bildirimleri ULAŞMAZ — yani "
            "sessiz ama ağır bir kesintidir."
        ),
        ne_yapmali=[
            "İletişim Sağlığı sayfasında sağlayıcının döndürdüğü hata "
            "mesajını oku (örn. '535 Authentication Failed' = anahtar/hesap "
            "sorunu).",
            "ZeptoMail panelinde hesabın aktif ve alan adının doğrulanmış "
            "olduğunu kontrol et.",
            "Anahtar değiştiyse sunucudaki .env dosyasında güncelle ve "
            "web + worker servislerini yeniden başlat.",
            "Bu kesinti sürerken alarm e-postaları da gitmez — panelden ve "
            "mobil bildirimden takip et.",
        ],
        baglantilar=[("İletişim Sağlığı", "/admin/communication-health")],
        sorumlu="saglayici",
    ),
    "moment_silent": AlarmGuide(
        birim="sessiz kullanıcı",
        ne_oldu=(
            "Bir kullanıcıya gösterilmesi gereken bağlamsal uyarı (deneme "
            "bitiyor bandı, ödeme duvarı, kredi azaldı kartı) gösterilmemiş "
            "görünüyor."
        ),
        neden=(
            "Uyarıyı taşıyan yüzey kırılmış olabilir: koşul kodu, API kancası "
            "veya arayüzdeki bant. Bu kural, uyarı yüzeylerinin sessizce "
            "bozulmasını yakalamak için vardır."
        ),
        ne_yapmali=[
            "Kanıttaki kullanıcıya bak: gerçekten uyarıyı görmesi gereken "
            "biri mi?",
            "Aynı kullanıcı panele girdiğinde uyarı görünüyorsa sorun "
            "geçmiştir — 'Çözüldü' ile kapat.",
            "Uyarı hâlâ görünmüyorsa yüzey kırık demektir: "
            "scripts/run_moment_checks.py çalıştırılmalı (geliştirme işi).",
            "Kullanıcı zaten panele hiç girmediyse bu YANLIŞ alarmdır — "
            "'Bu yanlış alarm' ile işaretle.",
        ],
        baglantilar=[("Kullanıcılar", "/admin/users")],
        sorumlu="kod",
    ),
}


_VARSAYILAN = AlarmGuide(
    ne_oldu="Bu kural için henüz sade dil açıklaması tanımlanmamış.",
    neden="Kural açıklamasına ve ölçülen değere bakarak değerlendir.",
    ne_yapmali=[
        "Kuralın eşiğini ve son değerini Alarm Ayarları'ndan incele.",
        "Tekrar ediyorsa bu kural için bir teşhis rehberi eklenmeli.",
    ],
)


def guide_for(rule_key: str) -> AlarmGuide:
    return GUIDES.get(rule_key, _VARSAYILAN)


# ---------------------------- Kanıt ----------------------------


@dataclass
class EvidenceRow:
    baslik: str
    detay: str = ""
    href: str | None = None
    ton: str = "slate"  # rose | amber | emerald | slate
    zaman: datetime | None = None


def _kisi_etiket(u: User | None, uid: int | None) -> str:
    if u is None:
        return f"#{uid}" if uid else "(bilinmiyor)"
    ad = (u.full_name or "").strip() or "(adsız)"
    return f"{ad} · {u.email}" if u.email else ad


def _kisiler(db: Session, ids: set[int]) -> dict[int, User]:
    if not ids:
        return {}
    return {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()}


def _ev_high_failed_logins(db: Session, limit: int) -> list[EvidenceRow]:
    from app.models import AuditAction, AuditLog

    cutoff = _now() - timedelta(hours=24)
    rows = (
        db.query(
            AuditLog.email_attempted, AuditLog.ip_address,
            func.count(AuditLog.id), func.max(AuditLog.created_at),
        )
        .filter(
            AuditLog.action.in_([AuditAction.LOGIN_FAILED, AuditAction.LOGIN_LOCKED]),
            AuditLog.created_at >= cutoff,
        )
        .group_by(AuditLog.email_attempted, AuditLog.ip_address)
        .order_by(func.count(AuditLog.id).desc())
        .limit(limit)
        .all()
    )
    return [
        EvidenceRow(
            baslik=f"{eposta or '(e-posta yok)'} — {adet} deneme",
            detay=f"IP {ip or '?'}",
            ton="rose" if adet >= 10 else "amber",
            zaman=son,
        )
        for eposta, ip, adet, son in rows
    ]


def _ev_oldest_queued_long(db: Session, limit: int) -> list[EvidenceRow]:
    from app.models import NotificationLog

    now = _now()
    q = (
        db.query(NotificationLog)
        .filter(NotificationLog.status == "queued")
        .order_by(NotificationLog.queued_at.asc())
        .limit(limit)
    )
    out: list[EvidenceRow] = []
    for n in q.all():
        yas = ""
        if n.queued_at:
            dk = int((now - _aware(n.queued_at)).total_seconds() // 60)
            yas = f"{dk} dakikadır bekliyor"
        out.append(EvidenceRow(
            baslik=f"{getattr(n, 'kind', '?')} → {getattr(n, 'channel', '?')}",
            detay=yas, ton="rose", zaman=n.queued_at,
        ))
    return out


def _ev_error_groups_open(db: Session, limit: int) -> list[EvidenceRow]:
    from app.models import ErrorEvent

    cutoff = _now() - timedelta(days=3)
    rows = (
        db.query(ErrorEvent)
        .filter(ErrorEvent.resolved_at.is_(None), ErrorEvent.last_seen_at >= cutoff)
        .order_by(ErrorEvent.last_seen_at.desc())
        .limit(limit)
        .all()
    )
    out: list[EvidenceRow] = []
    for e in rows:
        adet = getattr(e, "occurrence_count", None) or getattr(e, "count", None) or 1
        out.append(EvidenceRow(
            baslik=f"{getattr(e, 'exception_type', 'Hata')} — {adet} kez",
            detay=(getattr(e, "endpoint", "") or "")[:90],
            href="/admin/security-monitor/system",
            ton="rose", zaman=e.last_seen_at,
        ))
    return out


def _ev_abuse_open(db: Session, limit: int) -> list[EvidenceRow]:
    from app.models import AbuseSignal
    from app.services.abuse_detection import ABUSE_KIND_LABELS_TR

    rows = (
        db.query(AbuseSignal)
        .filter(AbuseSignal.resolved_at.is_(None), AbuseSignal.severity != "info")
        .order_by(AbuseSignal.detected_at.desc())
        .limit(limit)
        .all()
    )
    kisiler = _kisiler(db, {r.actor_user_id for r in rows if r.actor_user_id})
    out: list[EvidenceRow] = []
    for r in rows:
        etiket = ABUSE_KIND_LABELS_TR.get(r.kind, r.kind)
        u = kisiler.get(r.actor_user_id) if r.actor_user_id else None
        out.append(EvidenceRow(
            baslik=f"{etiket} ({r.count})",
            detay=_kisi_etiket(u, r.actor_user_id),
            href=f"/admin/users/{r.actor_user_id}" if r.actor_user_id else
                 "/admin/security-monitor/abuse",
            ton="rose" if r.severity == "critical" else "amber",
            zaman=r.detected_at,
        ))
    return out


def _ev_payment_problem_recent(db: Session, limit: int) -> list[EvidenceRow]:
    from app.models import PaymentTransaction

    now = _now()
    rows = (
        db.query(PaymentTransaction)
        .filter(
            PaymentTransaction.created_at >= now - timedelta(hours=24),
            PaymentTransaction.status.in_(["failed", "pending", "3ds_pending"]),
        )
        .order_by(PaymentTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    kisiler = _kisiler(db, {t.user_id for t in rows if t.user_id})
    out: list[EvidenceRow] = []
    for t in rows:
        u = kisiler.get(t.user_id) if t.user_id else None
        durum = {"failed": "Başarısız", "pending": "Yarım kaldı",
                 "3ds_pending": "3D Secure yarım kaldı"}.get(t.status, t.status)
        out.append(EvidenceRow(
            baslik=f"{durum} — {t.amount} ₺ ({t.plan_code or '—'})",
            detay=_kisi_etiket(u, t.user_id),
            href=f"/admin/users/{t.user_id}" if t.user_id else None,
            ton="rose" if t.status == "failed" else "amber",
            zaman=t.created_at,
        ))
    return out


def _ev_email_delivery_failing(db: Session, limit: int) -> list[EvidenceRow]:
    from app.models import CommunicationLog
    from app.models.communication_log import CHANNEL_EMAIL, FAILURE_STATUSES

    rows = (
        db.query(CommunicationLog)
        .filter(
            CommunicationLog.channel == CHANNEL_EMAIL,
            CommunicationLog.created_at >= _now() - timedelta(hours=24),
            CommunicationLog.status.in_(list(FAILURE_STATUSES)),
        )
        .order_by(CommunicationLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        EvidenceRow(
            baslik=(getattr(r, "subject", None) or getattr(r, "category", None)
                    or "E-posta"),
            detay=(f"{getattr(r, 'recipient', '') or ''} — "
                   f"{(getattr(r, 'status_reason', '') or r.status)}")[:140],
            href="/admin/communication-health",
            ton="rose", zaman=r.created_at,
        )
        for r in rows
    ]


def _ev_moment_silent(db: Session, limit: int) -> list[EvidenceRow]:
    from app.services import moments

    out: list[EvidenceRow] = []
    for satir in moments.silent_moment_report(db):
        if not satir.silent_user_ids:
            continue
        kisiler = _kisiler(db, set(satir.silent_user_ids[:limit]))
        for uid in satir.silent_user_ids[:limit]:
            out.append(EvidenceRow(
                baslik=satir.label,
                detay=_kisi_etiket(kisiler.get(uid), uid),
                href=f"/admin/users/{uid}",
                ton="amber",
            ))
    return out[:limit]


_KANIT = {
    "high_failed_logins": _ev_high_failed_logins,
    "oldest_queued_long": _ev_oldest_queued_long,
    "error_groups_open": _ev_error_groups_open,
    "abuse_open": _ev_abuse_open,
    "payment_problem_recent": _ev_payment_problem_recent,
    "email_delivery_failing": _ev_email_delivery_failing,
    "moment_silent": _ev_moment_silent,
}


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evidence_for(db: Session, rule_key: str, *, limit: int = 10) -> list[EvidenceRow]:
    """Kuralı ŞU AN tetikleyen kayıtlar. Asla patlamaz — teşhis kartı açılmalı."""
    fn = _KANIT.get(rule_key)
    if fn is None:
        return []
    try:
        return fn(db, limit)
    except Exception:
        logger.exception("alarm kanıt çözücü hata (rule=%s)", rule_key)
        return []


# ---------------------------- Teşhis ----------------------------


def diagnose(db: Session, event: AlarmEvent) -> dict:
    """Alarm kaydı → rehber + canlı durum + kanıt + geçmiş."""
    from app.services.alarm_engine import EVALUATORS

    g = guide_for(event.rule_key)

    # 1) Canlı yeniden değerlendirme — sorun sürüyor mu?
    guncel: int | None = None
    hata: str | None = None
    ev = EVALUATORS.get(event.rule_key)
    if ev is not None:
        try:
            guncel = int(ev(db))
        except Exception as exc:  # noqa: BLE001 — teşhis kartı yine açılmalı
            hata = f"{type(exc).__name__}: {exc}"
            logger.exception("alarm canlı değerlendirme hata (%s)", event.rule_key)

    hala_gecerli = (guncel is not None and guncel > event.threshold)

    # 2) Geçmiş — bu kural ne sıklıkla çalıyor, kaçı yanlış alarmdı?
    otuz = _now() - timedelta(days=30)
    toplam = int((db.query(func.count(AlarmEvent.id)).filter(
        AlarmEvent.rule_key == event.rule_key,
        AlarmEvent.triggered_at >= otuz).scalar()) or 0)
    yanlis = int((db.query(func.count(AlarmEvent.id)).filter(
        AlarmEvent.rule_key == event.rule_key,
        AlarmEvent.triggered_at >= otuz,
        AlarmEvent.false_positive.is_(True)).scalar()) or 0)

    return {
        "rule_key": event.rule_key,
        "rule_name": event.rule_name,
        "severity": event.severity,
        "triggered_at": event.triggered_at,
        "value": event.value,
        "threshold": event.threshold,
        "birim": g.birim,
        "ne_oldu": g.ne_oldu,
        "neden": g.neden,
        "ne_yapmali": list(g.ne_yapmali),
        "baglantilar": [{"etiket": e, "href": h} for e, h in g.baglantilar],
        "sorumlu": g.sorumlu,
        "guncel_deger": guncel,
        "hala_gecerli": hala_gecerli,
        "degerlendirme_hatasi": hata,
        "kanit": [
            {
                "baslik": k.baslik, "detay": k.detay, "href": k.href,
                "ton": k.ton, "zaman": k.zaman,
            }
            for k in evidence_for(db, event.rule_key)
        ],
        "son_30g_tetik": toplam,
        "son_30g_yanlis_alarm": yanlis,
        "gurultu_uyarisi": (
            yanlis >= 3
            or (toplam >= 20 and event.threshold == 0)
        ),
        "acknowledged_at": event.acknowledged_at,
        "resolved_at": event.resolved_at,
        "resolution_note": event.resolution_note,
        "false_positive": bool(event.false_positive),
    }


def false_positive_counts(db: Session, *, days: int = 30) -> dict[str, int]:
    """Kural → son N günde 'yanlış alarm' işaretlenme sayısı (kural listesi rozeti)."""
    cutoff = _now() - timedelta(days=days)
    rows = (
        db.query(AlarmEvent.rule_key, func.count(AlarmEvent.id))
        .filter(AlarmEvent.triggered_at >= cutoff,
                AlarmEvent.false_positive.is_(True))
        .group_by(AlarmEvent.rule_key)
        .all()
    )
    return {k: int(c) for k, c in rows}
