from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# SQLite (yalnız dev): tek-yazar kilidi. Varsayılan 5 sn bekleme, uzun süren
# istek (örn. deneme PDF analizi ~40 sn Gemini) sırasında paralel yazmaları
# (oturum heartbeat'i, ziyaret izleyici) "database is locked" ile düşürüyordu.
# timeout=60 → yazan bekler, çakışma kaybolur. Prod (Postgres) etkilenmez.
connect_args = (
    {"check_same_thread": False, "timeout": 60}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
    future=True,
)

# SQLite (yalnız dev) — WAL: okuyucular yazarı, yazar okuyucuları BLOKLAMAZ.
# Varsayılan (rollback journal) modda tek bir yazma transaction'ı tüm okumaları
# da kilitliyor; uzun istekler + arka plan yazımları (comm_log, panel ziyareti,
# heartbeat) birbirini "database is locked" ile düşürüyordu. WAL bunu büyük
# ölçüde ortadan kaldırır; kalan yazar-yazar çakışmasını `timeout=60` yutar.
# Prod (Postgres) ETKİLENMEZ — event yalnız sqlite bağlantılarında çalışır.
if settings.database_url.startswith("sqlite"):
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _rec):  # pragma: no cover (dev-only)
        cur = dbapi_conn.cursor()
        try:
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=60000")
        except Exception:
            pass
        finally:
            cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
