"""Seçici veri taşıma — kaynak DB'den (local SQLite) hedef DB'ye (prod Postgres)
yalnız GERÇEK veriyi kopyalar. Test/demo junk FK-closure ile otomatik dışlanır.

Keep-set: KEEP_USERS + KEEP_INST + bunlara FK ile bağlı tüm veri. Global config
(kullanıcı FK'si olmayan) aynen kopyalanır. SKIP: alembic_version (hedef stamp'ler),
system_secrets (Fernet anahtarı farklı), feature_cards (prod'da temiz seed).

Sağlamlık:
  - Kaynak HAM okunur (exec_driver_sql) → geçersiz eski enum değerleri (study/test)
    okuma aşamasında çökmez; junk satırlar zaten keep-set dışında.
  - Hedef Postgres'te FK'ler geçici kapatılır (session_replication_role=replica)
    → academic_years↔users döngüsü + sıra sorunu olmadan yazılır → sonra açılır.
  - Kept olmayana işaret eden FK NULL'lanır (nullable ise).
  - Postgres sequence'ları max(id)'ye çekilir.

Kullanım:
  SOURCE_SQLITE=lgs.db python -m scripts.migrate_subset           # dry-run sayım
  SOURCE_SQLITE=lgs.db python -m scripts.migrate_subset --apply   # gerçek kopya (prod)
  DEST_SQLITE=_t.db SOURCE_SQLITE=lgs.db ... --apply              # lokal güvenli test
"""
from __future__ import annotations

import os
import sys
import warnings

from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.exc import SAWarning

import app.models  # noqa: F401
from app.database import Base
from app.database import engine as APP_ENGINE

warnings.filterwarnings("ignore", category=SAWarning)

KEEP_USERS = {1, 2, 4, 6, 7}
KEEP_INST = {1}
SKIP = {
    "alembic_version",          # hedef kendi stamp'ler
    "system_secrets",           # Fernet anahtarı farklı → panelden tekrar gir
    "feature_cards",            # prod'da seed_landing_cards ile temiz
    # Operasyonel log/telemetri — kullanıcı FK'si yok; prod temiz başlasın
    "feature_card_events", "feature_bandit_state", "suggestion_feedback",
    "error_events", "slow_request_logs", "suspicious_ips",
}
APPLY = "--apply" in sys.argv


def _src():
    p = os.environ.get("SOURCE_SQLITE")
    if not p:
        raise SystemExit("SOURCE_SQLITE tanımlı değil")
    return create_engine(f"sqlite:///{p}")


def _dest():
    ds = os.environ.get("DEST_SQLITE")
    return create_engine(f"sqlite:///{ds}") if ds else APP_ENGINE


def _fks(table):
    return [(fk.parent.name, fk.column.table.name) for fk in table.foreign_keys]


def main() -> int:
    src, dest = _src(), _dest()
    is_pg = dest.dialect.name == "postgresql"
    md = Base.metadata
    order = list(md.sorted_tables)  # parent→child (döngü uyarısı zararsız)

    if APPLY:
        print("APPLY — hedef şema sıfırlanıp kuruluyor...")
        md.drop_all(bind=dest)
        md.create_all(bind=dest)

    kept: dict[str, set] = {}
    summary = []

    with src.connect() as sc, dest.begin() as dc:
        if APPLY and is_pg:
            dc.execute(text("SET session_replication_role = replica"))
        for table in order:
            tn = table.name
            if tn in SKIP:
                continue
            pk = [c.name for c in table.primary_key.columns]
            fks = _fks(table)
            # Tipli okuma — Python objeleri (datetime/bool/enum) → hem sqlite hem PG
            # doğru yazılır. (Kaynak kopyada geçersiz enum'lar önceden temizlenmeli.)
            rows = [dict(r._mapping) for r in sc.execute(select(table))]
            kept.setdefault(tn, set())
            out = []
            for row in rows:
                if tn == "users":
                    ok = row["id"] in KEEP_USERS
                elif tn == "institutions":
                    ok = row["id"] in KEEP_INST
                else:
                    ok = True
                    for col, ref in fks:
                        v = row.get(col)
                        if v is None:
                            continue
                        if ref == "users" and v not in KEEP_USERS:
                            ok = False; break
                        if ref == "institutions" and v not in KEEP_INST:
                            ok = False; break
                        if ref not in ("users", "institutions") and ref in kept and v not in kept[ref]:
                            ok = False; break
                if not ok:
                    continue
                clean = dict(row)
                for col, ref in fks:
                    v = clean.get(col)
                    if v is None:
                        continue
                    ks = (KEEP_USERS if ref == "users" else KEEP_INST if ref == "institutions" else kept.get(ref))
                    if ks is not None and v not in ks and table.c[col].nullable:
                        clean[col] = None
                out.append(clean)
                if len(pk) == 1:
                    kept[tn].add(row[pk[0]])
            summary.append((tn, len(rows), len(out)))
            if APPLY and out:
                dc.execute(insert(table), out)
        if APPLY and is_pg:
            dc.execute(text("SET session_replication_role = origin"))

    if APPLY and is_pg:
        with dest.begin() as dc:
            for table in order:
                if table.name in SKIP:
                    continue
                for c in table.primary_key.columns:
                    if c.autoincrement and "INT" in str(c.type).upper():
                        dc.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('{table.name}','{c.name}'),"
                            f" COALESCE((SELECT MAX({c.name}) FROM {table.name}),1))"
                        ))

    # Gerçek prod hedefte (DEST_SQLITE override yoksa) alembic head'e stamp et —
    # şema drop/create edildi, alembic_version boş; web açılışındaki init_db
    # "users var → upgrade head" dalına girecek, bu yüzden head işaretlenmeli.
    if APPLY and not os.environ.get("DEST_SQLITE"):
        from alembic import command
        from alembic.config import Config
        command.stamp(Config("alembic.ini"), "head")
        print("alembic stamp head ✓")

    print(f"\n{'TABLO':36s} {'kaynak':>7s} {'taşınan':>8s}")
    moved = 0
    for tn, s, k in summary:
        if k or s:
            print(f"{tn:36s} {s:>7d} {k:>8d}")
        moved += k
    print(f"\nTOPLAM taşınan: {moved}  ({'APPLIED' if APPLY else 'DRY-RUN'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
