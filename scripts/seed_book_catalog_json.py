"""Boru hattı JSON'undan Ortak Kitap Kataloğu kaydı (dev + prod, idempotent).

`book_structure_pipeline.py` çıktısını okur → verified katalog kaydı oluşturur:
deterministik auto-map (alias katmanı) + kapalı-küme AI tamamlama (best-effort).
Aynı ad+yayınevi katalogda varsa dokunmaz; `--reset` siler + yeniden kurar.

Kullanım: PYTHONPATH=. python scripts/seed_book_catalog_json.py <json> [--reset] [--no-map]
  --no-map: müfredat eşleştirmesi YAPILMAZ (MEB müfredatıyla örtüşmeyen
  kitaplar — örn. paragraf/branş-özel yapılar; kitap yapısı olduğu gibi korunur)
"""
from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import json
from pathlib import Path

# DNS oto-yaması: sarmalayıcı DAİMA kurulur — önce normal çözüm, başarısızsa
# sabit IP (dev DNS'i aralıklı şaşıyor; prod'da normal yol hep kazanır).
import socket as _socket

_H = "generativelanguage.googleapis.com"
_IPS = ["172.217.113.4", "172.217.114.4", "172.217.117.4"]
_o = _socket.getaddrinfo


def _p(host, *a, **k):
    if host == _H:
        try:
            return _o(host, *a, **k)
        except OSError:
            pass
        last = None
        for ip in _IPS:
            try:
                return _o(ip, *a, **k)
            except OSError as e:
                last = e
        raise last
    return _o(host, *a, **k)


_socket.getaddrinfo = _p

from app.database import SessionLocal
from app.models import BookType, Subject
from app.services import book_catalog as svc


def main() -> int:
    if len(sys.argv) < 2:
        print("Kullanım: seed_book_catalog_json.py <json> [--reset]")
        return 2
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    reset = "--reset" in sys.argv

    sections = [s for s in data["sections"] if s.get("test_count")]
    skipped = [s["label"] for s in data["sections"] if not s.get("test_count")]
    if skipped:
        print(f"[!] Test sayısı boş {len(skipped)} bölüm ATLANDI (elle eklenebilir): {', '.join(skipped)}")
    if len(sections) < 2:
        print("HATA: dolu bölüm sayısı < 2 — seed edilmedi.")
        return 1

    with SessionLocal() as db:
        existing = svc.find_duplicate(db, data["name"], data.get("publisher"))
        if existing is not None:
            if not reset:
                print(f"Zaten katalogda (id={existing.id}, {existing.catalog_status}) — dokunulmadı.")
                return 0
            db.delete(existing)
            db.flush()
            print(f"--reset: eski kayıt (id={existing.id}) silindi.")

        subj = (
            db.query(Subject)
            .filter(Subject.name == data["subject"], Subject.is_builtin.is_(True))
            .first()
        )
        if subj is None:
            print(f"HATA: builtin '{data['subject']}' dersi yok.")
            return 1

        entry = svc.create_entry(
            db,
            name=data["name"],
            publisher=data.get("publisher"),
            book_type=BookType(data.get("type", "soru_bankasi")),
            subject_id=subj.id,
            target_grade_min=data.get("target_grade_min"),
            target_grade_max=data.get("target_grade_max"),
            target_graduate=bool(data.get("target_graduate")),
            sections=[{"label": s["label"], "test_count": s["test_count"]} for s in sections],
            status="verified",
            source="admin_seed",
            dedup=True,
        )
        db.flush()
        if "--no-map" in sys.argv:
            ai_n = 0
            for s in entry.sections:
                s.topic_id = None  # deterministik auto-map da geri alınır
        else:
            ai_n = svc.ai_map_sections(db, entry)
        db.commit()
        db.refresh(entry)
        mapped = sum(1 for s in entry.sections if s.topic_id is not None)
        total = sum(s.default_test_count for s in entry.sections)
        print(
            f"Kataloğa eklendi: '{entry.name}' (id={entry.id}, verified) — "
            f"{len(entry.sections)} bölüm · {total} test · {mapped}/{len(entry.sections)} müfredat eşli"
            f" (AI tamamlama: +{ai_n})"
        )
        for s in sorted(entry.sections, key=lambda x: x.order):
            t = s.topic.name if s.topic else "— (eşleşmedi)"
            print(f"  {'✓' if s.topic_id else '✗'} {s.label:<44} → {t}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
