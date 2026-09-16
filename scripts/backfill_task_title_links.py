"""Görev başlığı + video bağlantısı geriye dönük onarımı (2026-09-16).

İki bağımsız onarım (ikisi de idempotent, dry-run varsayılan):

  --titles  Otomatik biçimli başlığı ("Kitap — Bölüm: N test") kalemleriyle
            uyuşmayan görevleri kalemlerden yeniden adlandırır. Saha: haftaya
            yay sıradaki bölüme geçince kaynak başlığı kopyalanıyordu →
            "Vektörler: 4 test" yazan görevde Tork ve Denge testleri (Taha #84).
            Koçun ELLE yazdığı başlıklara DOKUNMAZ (task_titles.is_auto_title).

  --links   `link_url` boş ama notes içinde http(s) URL olan görevlerde URL'i
            kolona taşır ve notes'tan ayıklar (notes yalnız URL ise NULL olur).
            Eski web formu video linkini notes'a gömüyordu.

Kullanım:
  python -m scripts.backfill_task_title_links                # dry-run, ikisi de
  python -m scripts.backfill_task_title_links --apply        # yaz
  python -m scripts.backfill_task_title_links --titles --student-id 84 --apply
"""
from __future__ import annotations

import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from sqlalchemy.orm import joinedload

from app.database import SessionLocal
from app.models import Task, TaskBookItem
from app.services import task_titles
from app.services.task_links import extract_url, strip_urls


def run(*, apply: bool, do_titles: bool, do_links: bool, student_id: int | None) -> dict:
    out = {"titles_checked": 0, "titles_fixed": 0, "links_fixed": 0}
    with SessionLocal() as db:
        q = db.query(Task).options(
            joinedload(Task.book_items).joinedload(TaskBookItem.book),
            joinedload(Task.book_items).joinedload(TaskBookItem.section),
        )
        if student_id is not None:
            q = q.filter(Task.student_id == student_id)
        for task in q.all():
            if do_titles and any(it.book_id is not None for it in task.book_items):
                out["titles_checked"] += 1
                old = task.title
                current = (old or "").strip()
                if current and current not in ("Görev", "—") and not task_titles.is_auto_title(current):
                    continue  # koçun elle yazdığı başlık
                new = task_titles.compose_from_task(task)
                if new and new != current:
                    out["titles_fixed"] += 1
                    print(f"  [title] task {task.id} {task.date}: '{old}' → '{new}'")
                    if apply:
                        task.title = new
            if do_links and not task.link_url:
                url = extract_url(task.notes)
                if url:
                    out["links_fixed"] += 1
                    cleaned = strip_urls(task.notes)
                    print(f"  [link]  task {task.id} {task.date}: link_url='{url}' notes='{cleaned}'")
                    if apply:
                        task.link_url = url
                        task.notes = cleaned
        if apply:
            db.commit()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="Değişiklikleri yaz (varsayılan dry-run)")
    ap.add_argument("--titles", action="store_true", help="Yalnız başlık onarımı")
    ap.add_argument("--links", action="store_true", help="Yalnız bağlantı onarımı")
    ap.add_argument("--student-id", type=int, default=None)
    a = ap.parse_args()
    do_titles = a.titles or not a.links
    do_links = a.links or not a.titles
    res = run(apply=a.apply, do_titles=do_titles, do_links=do_links, student_id=a.student_id)
    mode = "APPLY" if a.apply else "DRY-RUN"
    print(f"\n[{mode}] başlık kontrol={res['titles_checked']} düzeltme={res['titles_fixed']} · "
          f"bağlantı taşıma={res['links_fixed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
