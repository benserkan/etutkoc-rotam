"""Akıllı veritabanı başlatma — boş DB vs mevcut DB.

Sorun: initial migration (a75e236e10f4) tabloları ALFABETİK sırada yaratıyor
(`academic_years` FK→`users`, `users`'tan önce). SQLite FK'yi create anında
doğrulamadığı için dev'de sorun yok; Postgres doğruladığı için boş DB'de
`alembic upgrade head` "relation users does not exist" ile çöküyor.

Çözüm:
  - BOŞ DB (users yok): modellerden `Base.metadata.create_all` (SQLAlchemy FK
    bağımlılığını doğru topolojik sırada yaratır) + `alembic stamp head`
    (artık head'de sayılır; gelecek migration'lar normal uygulanır).
  - MEVCUT DB (users var): `alembic upgrade head` (artımlı, her zamanki gibi).

Modeller tek doğru kaynak; `import app.models` tüm tabloları Base.metadata'ya
kaydeder. start.sh bunu `alembic upgrade head` yerine çağırır.
"""
from __future__ import annotations

import logging

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

import app.models  # noqa: F401 — tüm tabloları Base.metadata'ya kaydeder
from app.database import Base, engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("init_db")


def main() -> None:
    tables = set(inspect(engine).get_table_names())
    cfg = Config("alembic.ini")
    if "users" not in tables:
        log.info("Boş DB algılandı → modellerden create_all + alembic stamp head")
        Base.metadata.create_all(bind=engine)
        command.stamp(cfg, "head")
        log.info("create_all + stamp head tamam")
    else:
        log.info("Mevcut DB → alembic upgrade head")
        command.upgrade(cfg, "head")
        log.info("upgrade head tamam")


if __name__ == "__main__":
    main()
