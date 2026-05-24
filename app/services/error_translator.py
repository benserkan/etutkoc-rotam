"""Hata Tercümanı — ham teknik hataları süper admine sade dille açıklar.

Güvenlik Kamarası ham geliştirici hatalarını (stack trace, exception sınıfı,
SQLAlchemy iç mesajları, çıplak cron anahtarları) gösteriyordu. Bu servis her
hatayı **{kategori, sade özet, neden, ne yapmalı, şiddet}** olarak çevirir.

Hibrit yaklaşım (kullanıcı 2026-05-24):
- **Kural kataloğu**: bilinen kritik desenler anında + ücretsiz + deterministik.
- **AI yedeği** (`ai_explain_error`): katalogda olmayan hatalar için Gemini ile
  sade açıklama üretir; sonuç imzaya göre BELLEKTE önbeklenir (tekrar çağrıda
  kredi yanmaz). KVKK: hata metinleri kişisel veri içermez → personal_data=False.

Dil: sade Türkçe (jargon yasağı). Stack trace UI'da "geliştirici detayı"na iner.
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cron işlerinin dostça adı + ne işe yaradığı (job_key → ad, amaç)
# ---------------------------------------------------------------------------
CRON_LABELS_TR: dict[str, tuple[str, str]] = {
    "daily_summary": ("Günlük veli özeti", "velilere her gün öğrencinin günlük durumunu e-posta/WhatsApp ile gönderir"),
    "weekly_backstop": ("Haftalık yedek bildirim", "haftalık özet kaçanlara güvenlik ağı olarak ek bildirim gönderir"),
    "drop_alert": ("Kopan öğrenci uyarısı", "uzaklaşan/aktivitesi düşen öğrenciler için koça uyarı üretir"),
    "exam_approaching": ("Deneme yaklaşıyor hatırlatması", "yaklaşan deneme sınavları için hatırlatma gönderir"),
    "audit_cleanup": ("Denetim kaydı temizliği", "eski denetim (audit) kayıtlarını düzenli olarak temizler"),
    "admin_weekly_digest": ("Yöneticiye haftalık özet", "kurum yöneticilerine haftalık performans özetini gönderir"),
    "credits_monthly_refill": ("Aylık kredi yenileme", "ücretli hesapların aylık yapay zekâ kredisini yeniler"),
    "trial_expire": ("Deneme süresi sonu", "süresi biten denemeleri ücretsiz plana düşürür + hatırlatma/yenileme e-postaları gönderir"),
    "invoices_mark_overdue": ("Gecikmiş fatura işaretleme", "ödeme tarihi geçen faturaları 'gecikti' olarak işaretler"),
    "dunning_send_reminders": ("Ödeme hatırlatma zinciri", "ödenmemiş faturalar için kademeli hatırlatma gönderir"),
    "health_snapshot_daily": ("Günlük sağlık anlık görüntüsü", "kurum/koç sağlık skorlarının günlük fotoğrafını alır (trend için)"),
    "addons_monthly_renewal": ("Aylık ek paket yenileme", "aylık ek paket/eklentileri yeniler"),
    "subscription_resume": ("Abonelik otomatik devam", "yaz dondurması biten abonelikleri otomatik devam ettirir"),
    "subscription_guarantee_eval": ("60 gün garanti değerlendirme", "performans garantisi koşullarını günlük değerlendirir"),
    "kvkk_apply_expired_deletions": ("KVKK silme uygulaması", "süresi gelen KVKK silme taleplerini otomatik uygular"),
    "auto_pause_inactive_users": ("Pasif hesap dondurma", "uzun süre giriş yapmayan hesapları otomatik dondurur"),
    "security_alarm_evaluate": ("Güvenlik alarmı taraması", "güvenlik alarm kurallarını periyodik değerlendirir"),
    "abuse_scan": ("Suistimal taraması", "toplu davet/bildirim, çoklu hesap gibi suistimal sinyallerini tarar"),
    "error_event_retention": ("Hata kaydı temizliği", "eski yakalanan hata kayıtlarını temizler"),
    "slow_request_retention": ("Yavaş istek kaydı temizliği", "eski yavaş istek kayıtlarını temizler"),
    "security_integrity_scan": ("Veri bütünlüğü taraması", "yetim kayıt, eksik ilişki gibi veri tutarsızlıklarını tarar"),
}


def cron_label(job_key: str) -> str:
    """job_key → dostça ad (yoksa anahtarı insanlaştır)."""
    if job_key in CRON_LABELS_TR:
        return CRON_LABELS_TR[job_key][0]
    return job_key.replace("_", " ").strip().capitalize()


def cron_purpose(job_key: str) -> str:
    return CRON_LABELS_TR.get(job_key, ("", "bu otomatik arka plan görevi"))[1]


# ---------------------------------------------------------------------------
@dataclass
class ErrorExplanation:
    category: str       # database | validation | external_ai | external_email | cron | queue | disk | permission | unknown
    category_label: str
    summary: str        # ne oldu (1-2 cümle, sade)
    why: str            # olası neden
    how_to_fix: str     # ne yapmalı
    severity: str       # info | warning | critical
    is_code_bug: bool   # geliştirici düzeltmesi mi gerektiriyor (veri/güvenlik değil)
    source: str         # rule | ai | none

    def as_dict(self) -> dict:
        return asdict(self)


_CATEGORY_LABELS = {
    "database": "Veritabanı",
    "validation": "Geçersiz istek",
    "external_ai": "Yapay zekâ servisi",
    "external_email": "E-posta/Bildirim servisi",
    "cron": "Zamanlanmış görev",
    "queue": "Bildirim kuyruğu",
    "disk": "Depolama",
    "permission": "Yetki",
    "unknown": "Bilinmeyen teknik hata",
}


def _exp(category, summary, why, how_to_fix, severity, is_code_bug, source="rule") -> ErrorExplanation:
    return ErrorExplanation(
        category=category,
        category_label=_CATEGORY_LABELS.get(category, category),
        summary=summary,
        why=why,
        how_to_fix=how_to_fix,
        severity=severity,
        is_code_bug=is_code_bug,
        source=source,
    )


# ---------------------------------------------------------------------------
# Kural kataloğu — exception türü + mesaj desenine göre eşleştirme
# ---------------------------------------------------------------------------
def explain_error(exception_type: str, message: str, endpoint: str | None = None) -> ErrorExplanation:
    """Ham hatayı sade açıklamaya çevir. Eşleşme yoksa source='none' döner
    (frontend 'Bunu açıkla' AI butonu gösterir)."""
    et = (exception_type or "").strip()
    msg = (message or "")
    low = msg.lower()

    # --- Veritabanı: sorgu KURGU hatası (kod bug'ı) ---
    if "limit or offset" in low or ("filter()" in low and "limit" in low):
        return _exp(
            "database",
            "Bir sayfadaki veritabanı sorgusu kodda yanlış sırada kurulmuş "
            "(önce sayfalama, sonra filtre uygulanmış).",
            "Bu bir kod hatası — veri kaybı veya güvenlik açığı DEĞİL. SQLAlchemy "
            "sorguda filtreyi sayfalama (limit/offset) sonrasında kabul etmez.",
            "Geliştirici düzeltmesi gerekir: ilgili sorguda filtre, limit'ten önce "
            "uygulanmalı. Bu sayfayı tekrar açmadan önce düzeltilmeli.",
            "critical", is_code_bug=True,
        )
    if "database is locked" in low or "deadlock" in low:
        return _exp(
            "database",
            "Veritabanı kısa süreliğine kilitlendi (aynı anda çok sayıda yazma).",
            "Genellikle geçici bir yoğunluk; aynı anda çalışan cron/işlemler çakışmış olabilir.",
            "Sürerse: ağır toplu işleri/cron'ları seyrelt; SQLite yerine Postgres "
            "kullanımını değerlendir (eşzamanlı yazmada daha güçlü).",
            "warning", is_code_bug=False,
        )
    if et in ("OperationalError",) and ("connect" in low or "connection" in low or "could not connect" in low):
        return _exp(
            "database",
            "Uygulama veritabanına bağlanamadı.",
            "Veritabanı servisi/konteyneri durmuş, yeniden başlıyor ya da ağ bağlantısı kopmuş olabilir.",
            "Veritabanı konteynerinin (Postgres) ayakta olduğunu doğrula; "
            "bağlantı ayarlarını ve sunucu kaynaklarını kontrol et.",
            "critical", is_code_bug=False,
        )
    if et == "IntegrityError" or "integrityerror" in low or "unique constraint" in low or "foreign key" in low:
        return _exp(
            "database",
            "Bir kayıt veritabanı kuralını ihlal etti (ör. tekrar eden e-posta, "
            "zorunlu alan eksik ya da bağlı kayıt yok).",
            "Genelde aynı kaydı iki kez ekleme veya eksik/çakışan veri girişi.",
            "Tek seferlikse önemsiz. Sık tekrarlıyorsa ilgili formu/akışı gözden "
            "geçir (çift gönderim, eksik doğrulama).",
            "warning", is_code_bug=False,
        )
    if et in ("DataError", "ProgrammingError"):
        return _exp(
            "database",
            "Bir veritabanı sorgusu/verisi beklenen biçimde değildi.",
            "Genelde bir kod ya da veri biçimi uyuşmazlığı.",
            "Tekrarlıyorsa geliştiriciye ilet; tek seferlikse izlemeye devam et.",
            "warning", is_code_bug=True,
        )

    # --- Dış servisler ---
    if any(k in low for k in ("gemini", "anthropic", "openai", "ai_unavailable")) or et in ("AIServiceUnavailable",):
        return _exp(
            "external_ai",
            "Yapay zekâ servisine ulaşılamadı ya da yanıt vermedi.",
            "Genelde geçici: dış servis yoğunluğu, zaman aşımı, kota dolması ya da "
            "API anahtarı eksik/geçersiz.",
            "Süper Admin → AI Ayarları'ndan anahtarın geçerli olduğunu ve kotanın "
            "dolmadığını kontrol et. Geçiciyse kendi düzelir.",
            "warning", is_code_bug=False,
        )
    if any(k in low for k in ("smtp", "email", "mail", "whatsapp")) or et in ("ConnectError", "ConnectTimeout"):
        return _exp(
            "external_email",
            "E-posta/bildirim gönderim servisine ulaşılamadı.",
            "SMTP/WhatsApp ayarları eksik/yanlış olabilir ya da dış servis geçici olarak yanıt vermiyor.",
            "SMTP/WhatsApp ayarlarını ve API anahtarlarını kontrol et; bildirim "
            "kuyruğunun biriktiğini de izle.",
            "warning", is_code_bug=False,
        )
    if et in ("TimeoutError", "ReadTimeout") or "timed out" in low or "timeout" in low:
        return _exp(
            "external_ai",
            "Bir dış servis çağrısı zaman aşımına uğradı.",
            "Dış servis yavaş yanıt verdi ya da ağ gecikmesi oldu. Genelde geçici.",
            "Sürerse ilgili dış servisin (yapay zekâ/e-posta) durumunu ve ağ "
            "bağlantısını kontrol et.",
            "warning", is_code_bug=False,
        )

    # --- İstek doğrulama ---
    if et in ("ValidationError", "RequestValidationError") or "validation error" in low:
        return _exp(
            "validation",
            "Gelen bir istek beklenen biçimde değildi (eksik veya hatalı alan).",
            "Genelde eski/uyumsuz bir istemci ya da bozuk/elle düzenlenmiş istek.",
            "Tek seferlikse önemsiz. Sık tekrarlıyorsa ilgili formu/ekranı kontrol et.",
            "info", is_code_bug=False,
        )
    if et in ("PermissionError", "HTTPException") and ("403" in msg or "forbidden" in low or "yetki" in low):
        return _exp(
            "permission",
            "Bir kullanıcı yetkisi olmayan bir işlemi denedi.",
            "Genelde normal koruma (yetkisiz erişim engellendi). Kötü niyet işareti "
            "olabilir ama tek başına alarm değil.",
            "Sık ve aynı kişiden geliyorsa Güvenlik → Aktivite/Suistimal'den incele.",
            "info", is_code_bug=False,
        )

    # --- Eşleşme yok → AI yedeği için işaret ---
    return ErrorExplanation(
        category="unknown",
        category_label=_CATEGORY_LABELS["unknown"],
        summary="Beklenmeyen bir teknik hata oluştu.",
        why="Bu hata türü için hazır bir açıklama yok.",
        how_to_fix="“Yapay zekâ ile açıkla” ile sade bir açıklama isteyebilir ya da "
                   "ham detayı geliştiriciye iletebilirsin.",
        severity="warning",
        is_code_bug=False,
        source="none",
    )


# ---------------------------------------------------------------------------
# Cron / dispatcher / disk açıklayıcıları
# ---------------------------------------------------------------------------
def explain_cron(job_key: str, health: str, hours_since_run: float | None, schedule: str | None = None) -> ErrorExplanation:
    name = cron_label(job_key)
    purpose = cron_purpose(job_key)
    sched = f" (normalde {schedule})" if schedule else ""
    hrs = f"{int(hours_since_run)} saattir" if hours_since_run else "uzun süredir"
    if health == "never":
        return _exp(
            "cron",
            f"“{name}” görevi hiç çalışmamış.",
            "Yeni eklenmiş olabilir ya da zamanlayıcı bu görevi henüz hiç tetiklememiş. "
            f"Bu görev normalde {purpose}.",
            "Zamanlayıcı (cron) sürecinin ayakta ve bu görevin kayıtlı/açık olduğunu doğrula.",
            "warning", is_code_bug=False,
        )
    if health in ("warn", "crit"):
        return _exp(
            "cron",
            f"“{name}” görevi {hrs} çalışmadı{sched}.",
            f"Bu görev normalde {purpose}. Olası neden: zamanlayıcı süreci/konteyneri "
            "durmuş ya da görev her çalışmada hata veriyor. Durursa bu iş sessizce yapılmaz.",
            "Zamanlayıcı konteynerinin ayakta olduğunu doğrula; görev loglarına bak; "
            "gerekirse zamanlayıcıyı yeniden başlat.",
            "critical" if health == "crit" else "warning", is_code_bug=False,
        )
    return _exp("cron", f"“{name}” görevi normal çalışıyor.", "", "", "info", is_code_bug=False)


def explain_dispatcher(queued: int, failed: int, oldest_hours: float | None, health: str) -> ErrorExplanation:
    oldest = f" (en eskisi ~{int(oldest_hours)} saat bekliyor)" if oldest_hours else ""
    return _exp(
        "queue",
        f"Bildirim kuyruğunda {queued} bekleyen, {failed} başarısız mesaj var{oldest}.",
        "Kuyruk birikiyorsa gönderim (e-posta/WhatsApp) servisi durmuş ya da dağıtıcı "
        "cron'u çalışmıyor olabilir.",
        "Dağıtıcı cron'unu ve SMTP/WhatsApp ayarlarını kontrol et; başarısızlar "
        "tekrar denenebilir.",
        "critical" if health == "crit" else "warning" if health == "warn" else "info",
        is_code_bug=False,
    )


def explain_database_size(size_mb: float, health: str, threshold_mb: int) -> ErrorExplanation:
    return _exp(
        "disk",
        f"Veritabanı dosyası {int(size_mb)} MB (eşik {threshold_mb} MB).",
        "Veri büyüdükçe dosya büyür; eşiğe yaklaşmak performans/yedekleme riski taşır.",
        "Eski kayıtları arşivle/temizle ya da daha büyük bir plana/Postgres'e geç.",
        "critical" if health == "crit" else "warning" if health == "warn" else "info",
        is_code_bug=False,
    )


# ---------------------------------------------------------------------------
# AI yedeği — katalogda olmayan hatalar için Gemini (bellekte önbellekli)
# ---------------------------------------------------------------------------
_AI_CACHE: dict[str, ErrorExplanation] = {}


def ai_explain_error(exception_type: str, message: str, endpoint: str | None = None,
                     *, signature: str | None = None) -> ErrorExplanation:
    """Gemini ile sade açıklama üret. signature verilirse sonuç bellekte önbeklenir
    (aynı hata tekrar açıklanırken kredi yanmaz). Gemini yoksa kural fallback'ine döner."""
    cache_key = signature or f"{exception_type}|{message[:120]}"
    cached = _AI_CACHE.get(cache_key)
    if cached is not None:
        return cached

    from app.services.gemini import generate
    prompt = (
        "Aşağıda bir web uygulamasında oluşan teknik bir hata var. Bunu YAZILIMCI "
        "OLMAYAN bir yöneticiye SADE TÜRKÇE açıkla. Jargon kullanma. Sadece şu JSON'u "
        "döndür: {\"summary\": \"ne oldu (1-2 cümle)\", \"why\": \"olası neden\", "
        "\"how_to_fix\": \"yönetici/geliştirici ne yapmalı\", \"severity\": "
        "\"info|warning|critical\", \"is_code_bug\": true/false}.\n\n"
        f"Hata türü: {exception_type}\nMesaj: {message[:600]}\n"
        f"Nerede: {endpoint or 'bilinmiyor'}"
    )
    try:
        raw = generate([{"text": prompt}], personal_data=False, json_mode=True)
        import json
        data = json.loads(raw)
        exp = ErrorExplanation(
            category="unknown",
            category_label=_CATEGORY_LABELS["unknown"],
            summary=str(data.get("summary") or "Açıklama üretilemedi.").strip()[:600],
            why=str(data.get("why") or "").strip()[:600],
            how_to_fix=str(data.get("how_to_fix") or "").strip()[:600],
            severity=data.get("severity") if data.get("severity") in ("info", "warning", "critical") else "warning",
            is_code_bug=bool(data.get("is_code_bug", False)),
            source="ai",
        )
        _AI_CACHE[cache_key] = exp
        return exp
    except Exception:
        logger.exception("ai_explain_error failed type=%s", exception_type)
        # Gemini yoksa/başarısızsa kural fallback'i
        fallback = explain_error(exception_type, message, endpoint)
        return fallback


def clear_ai_cache() -> None:
    _AI_CACHE.clear()
