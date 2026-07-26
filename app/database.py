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

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
