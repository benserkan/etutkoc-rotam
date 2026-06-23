from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ETÜTKOÇ Rotam"
    database_url: str = "sqlite:///./lgs.db"
    session_secret: str = "dev-only-change-me"
    debug: bool = False  # Production default; dev için .env'de DEBUG=true

    # Email (SMTP) ayarları — email_enabled false iken sadece logla, mail gönderme
    email_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "ETÜTKOÇ <noreply@etutkoc.local>"
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False  # 465 portu için True
    # ZeptoMail bounce/teslimat webhook'u — URL'ye ?token=<secret> eklenir.
    # Boş ise tüm POST'lar kabul (yine de loglanır); doluysa token eşleşmeli.
    zeptomail_webhook_secret: str = ""
    # Email içindeki linkler için public URL (deploy sonrası değişir)
    app_base_url: str = "http://127.0.0.1:8081"

    # SMS — pluggable sağlayıcı (P1 2026-05-30, VatanSMS 2026-05-31).
    # Yalnız telefon doğrulama OTP'si için kullanılır; otomatik SMS bildirimi YOK.
    # sms_enabled=false iken log-only (dev): kullanıcı paneline kod dev_test_code
    # olarak yansır.
    sms_enabled: bool = False
    # Sağlayıcı seçimi: "vatansms" (default — bireysel hesap kabul) veya "netgsm"
    sms_provider: str = "vatansms"

    # VatanSMS REST (default — TC kimlik + e-devlet belgesi ile bireysel hesap)
    vatansms_api_id: str = ""
    vatansms_api_key: str = ""
    vatansms_sender: str = ""  # onaylı başlık (sender ID)
    vatansms_base_url: str = "https://api.vatansms.net"

    # Netgsm REST (legacy — şirket gerekir)
    netgsm_user: str = ""
    netgsm_password: str = ""
    netgsm_header: str = ""  # onaylı başlık (sender ID)
    netgsm_base_url: str = "https://api.netgsm.com.tr"

    # WhatsApp Cloud API (Meta Business)
    # https://developers.facebook.com/docs/whatsapp/cloud-api
    whatsapp_enabled: bool = False
    whatsapp_api_version: str = "v21.0"
    whatsapp_phone_number_id: str = ""    # Meta'nın atadığı sayısal ID
    whatsapp_access_token: str = ""        # Bearer token (kalıcı veya 60 günlük)
    whatsapp_app_secret: str = ""          # Webhook imza doğrulama için (App Secret)
    whatsapp_webhook_verify_token: str = "" # GET verify aşaması için (sen seç)
    whatsapp_default_language: str = "tr"
    # K2 — branded üyelik teklifi şablonu (Meta'da onaylı şablon adı + görsel başlık)
    whatsapp_offer_template: str = "uyelik_teklifi"   # WhatsApp Manager'daki onaylı şablon adı
    whatsapp_offer_image_url: str = "https://rotam.etutkoc.com/wa-offer-header.png"  # IMAGE header (full-bleed banner)
    # Şablonun butonu DİNAMİK URL ise (https://.../membership/{{1}}) True → token
    # buton parametresi olarak gönderilir. Statik butonlu şablonda False (param yollama).
    whatsapp_offer_button_dynamic: bool = False

    # AI sağlayıcı anahtarları — ÖNCELİK süper admin DB (system_secrets);
    # bu alanlar yalnız env/.env fallback'i. Boş = yalnız DB'den okunur.
    # (Eski sağlayıcılar — artık tek sağlayıcı Gemini; uyumluluk için tutuldu.)
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Gemini (tek AI sağlayıcı). ÜCRETLİ key = öğrenci verili işler (no-training,
    # KVKK). FREE key(ler) = yalnız kişisel-veri-içermeyen iş (kitap şablonu);
    # virgülle birden çok ("diğerleri ücretsiz"); kota dolunca sıradakine, en son
    # ücretliye düşülür. Model adları panelden değiştirilebilir.
    gemini_api_key: str = ""                # genel/ortak Gemini key (ücretli sayılır)
    gemini_paid_api_key: str = ""           # açıkça ücretli (öncelikli)
    gemini_free_api_keys: str = ""          # virgülle ayrılmış 0..N ücretsiz key
    gemini_paid_model: str = "gemini-2.5-pro"
    gemini_free_model: str = "gemini-2.5-flash"

    # Native mobile / external API katmanı
    jwt_secret: str = "dev-only-change-me-jwt"  # production'da güçlü random secret
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 60          # access token 1 saat
    jwt_refresh_days: int = 30            # refresh token 30 gün
    # CORS allowlist — virgülle ayrılmış, "*" hepsi (sadece dev). Production'da
    # mobile app + web origin'leri yazılmalı.
    cors_origins: str = "http://localhost:8081,http://127.0.0.1:8081"
    # IP-bazlı rate limit — /api/v1/auth/login için
    api_login_rate_per_min: int = 10

    # ========================================================================
    # API v2 BFF (Backend-for-Frontend) cookie ayarları — Next.js için
    # ========================================================================
    # NOT: __Host- prefix'i Secure flag zorunlu kıldığı için sadece HTTPS
    # ardındaki production'da kullanılır. Dev/test'te lgs_* (plain) kalır.
    #
    # Production .env örneği (Caddy + Lightsail):
    #   AUTH_COOKIE_ACCESS_NAME=__Host-access
    #   AUTH_COOKIE_REFRESH_NAME=__Host-refresh
    #   AUTH_COOKIE_SECURE=true
    auth_cookie_access_name: str = "lgs_access"
    auth_cookie_refresh_name: str = "lgs_refresh"
    auth_cookie_secure: bool = False
    # SameSite: access cross-site link'lerden gelen GET için Lax,
    # refresh ise sadece /api/v2/auth/refresh'a gittiği için Strict.
    auth_cookie_samesite_access: str = "lax"
    auth_cookie_samesite_refresh: str = "strict"

    # ========================================================================
    # Ödeme — Iyzico (Ödeme Paket Ö1). Boş key + sandbox URL = test modu.
    # Üretime geçiş: IYZICO_BASE_URL=https://api.iyzipay.com + gerçek key/secret.
    # ========================================================================
    iyzico_api_key: str = ""
    iyzico_secret_key: str = ""
    iyzico_base_url: str = "https://sandbox-api.iyzipay.com"
    # Iyzico checkout sonrası bu URL'ye form-POST eder (token ile).
    # Backend olmalı (frontend değil — POST handler gerek). Bizim handler 303 ile
    # Next.js'in /payment/result sayfasına yönlendirir.
    # Dev: http://127.0.0.1:8081/api/v2/payment/iyzico/callback
    # Prod: https://rotam.etutkoc.com/api/v2/payment/iyzico/callback
    payment_callback_url: str = "http://127.0.0.1:8081/api/v2/payment/iyzico/callback"


settings = Settings()
