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


settings = Settings()
