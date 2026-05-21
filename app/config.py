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
    # Email içindeki linkler için public URL (deploy sonrası değişir)
    app_base_url: str = "http://127.0.0.1:8081"

    # WhatsApp Cloud API (Meta Business)
    # https://developers.facebook.com/docs/whatsapp/cloud-api
    whatsapp_enabled: bool = False
    whatsapp_api_version: str = "v21.0"
    whatsapp_phone_number_id: str = ""    # Meta'nın atadığı sayısal ID
    whatsapp_access_token: str = ""        # Bearer token (kalıcı veya 60 günlük)
    whatsapp_app_secret: str = ""          # Webhook imza doğrulama için (App Secret)
    whatsapp_webhook_verify_token: str = "" # GET verify aşaması için (sen seç)
    whatsapp_default_language: str = "tr"

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


settings = Settings()
