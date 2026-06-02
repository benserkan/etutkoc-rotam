"""gorev_stats çekirdeği — sınıflandırma + görev/test/deneme sayım birim testi.

GÖREV = Task. test/deneme/tam_deneme/etkinlik ayrımı + görev birincil sayım +
test hacmi (deneme'den AYRI) doğrulanır. Saf (DB'siz, mock).
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from types import SimpleNamespace

from app.models.book import BookType
from app.models.task import TaskStatus
from app.services import gorev_stats as gs

passed = 0
failed: list[str] = []


def chk(label, cond, detail=""):
    global passed
    if cond:
        passed += 1
        print(f"  [PASS] {label}")
    else:
        failed.append(label)
        print(f"  [FAIL] {label}  ({detail})")


def book(btype, sid, sname, order):
    return SimpleNamespace(type=btype, subject_id=sid,
                           subject=SimpleNamespace(name=sname, order=order))


def item(planned, completed, bk):
    return SimpleNamespace(
        planned_count=planned, completed_count=completed,
        book_id=(None if bk is None else 100 + (bk.subject_id or 0)), book=bk,
    )


def task(items, status=TaskStatus.PENDING, title="G"):
    return SimpleNamespace(book_items=list(items), status=status, title=title)


def main() -> int:
    print("\n=== gorev_stats — sınıflandırma + sayım ===\n")
    turkce = book(BookType.SORU_BANKASI, 1, "Türkçe", 1)
    mat = book(BookType.SORU_BANKASI, 2, "Matematik", 2)
    fen = book(BookType.BRANS_DENEMESI, 3, "Fen Bilimleri", 3)

    T1 = task([item(4, 4, turkce)], title="Türkçe Paragraf 4 test")        # test, done
    T2 = task([item(10, 6, mat)], title="Matematik Türev 10 test")          # test, not done
    T3 = task([item(20, 20, fen)], title="Fen Branş Denemesi")             # deneme, done
    T4 = task([item(90, 0, None)], title="LGS Tam Deneme 5")               # tam_deneme, not done
    T5 = task([], status=TaskStatus.COMPLETED, title="Trigonometri videosu")  # etkinlik, done
    T6 = task([], status=TaskStatus.PENDING, title="Konu özeti")           # etkinlik, not done

    # --- Sınıflandırma ---
    chk("T1 → test", gs.classify_gorev(T1) == "test")
    chk("T2 → test", gs.classify_gorev(T2) == "test")
    chk("T3 → deneme (branş denemesi kitabı)", gs.classify_gorev(T3) == "deneme")
    chk("T4 → tam_deneme (kitapsız)", gs.classify_gorev(T4) == "tam_deneme")
    chk("T5 → etkinlik (soru yok)", gs.classify_gorev(T5) == "etkinlik")

    # --- Görev tamamlandı mı ---
    chk("T1 done (4/4)", gs.gorev_done(T1) is True)
    chk("T2 not done (6/10)", gs.gorev_done(T2) is False)
    chk("T5 done (status COMPLETED)", gs.gorev_done(T5) is True)
    chk("T6 not done (etkinlik PENDING)", gs.gorev_done(T6) is False)

    # --- Özet ---
    s = gs.summarize([T1, T2, T3, T4, T5, T6])
    chk("görev toplam = 6", s.gorev_total == 6, str(s.gorev_total))
    chk("görev tamam = 3 (T1,T3,T5)", s.gorev_done == 3, str(s.gorev_done))
    chk("görev % = 50", s.gorev_pct == 50, str(s.gorev_pct))

    chk("kategori test=2", s.cat_total["test"] == 2, str(s.cat_total))
    chk("kategori deneme=1", s.cat_total["deneme"] == 1)
    chk("kategori tam_deneme=1", s.cat_total["tam_deneme"] == 1)
    chk("kategori etkinlik=2", s.cat_total["etkinlik"] == 2)

    # KRİTİK: test hacmi deneme'yi İÇERMEZ (ayrım)
    chk("test_planned = 14 (4+10, deneme/tam HARİÇ)", s.test_planned == 14, str(s.test_planned))
    chk("test_completed = 10 (4+6)", s.test_completed == 10, str(s.test_completed))
    chk("deneme_planned = 110 (20+90, test'ten AYRI)", s.deneme_planned == 110, str(s.deneme_planned))
    chk("deneme_completed = 20", s.deneme_completed == 20, str(s.deneme_completed))

    # Ders bazında (yalnız test görevleri)
    chk("subjects = 2 ders (Türkçe, Matematik — Fen deneme HARİÇ)",
        len(s.subjects) == 2, str([(x.subject_name) for x in s.subjects]))
    by_name = {x.subject_name: x for x in s.subjects}
    chk("Türkçe: 1 görev, 1 tamam, %100",
        by_name["Türkçe"].gorev_total == 1 and by_name["Türkçe"].gorev_done == 1
        and by_name["Türkçe"].pct == 100, str(by_name.get("Türkçe")))
    chk("Matematik: 1 görev, 0 tamam, 6/10 test",
        by_name["Matematik"].gorev_done == 0 and by_name["Matematik"].test_completed == 6
        and by_name["Matematik"].test_planned == 10, str(by_name.get("Matematik")))
    chk("ders sırası order'a göre (Türkçe önce)",
        s.subjects[0].subject_name == "Türkçe")

    # Denemeler ayrı liste
    chk("denemeler = 2 (branş + tam)", len(s.denemeler) == 2, str(len(s.denemeler)))
    cats = sorted(d.category for d in s.denemeler)
    chk("deneme kategorileri = [deneme, tam_deneme]", cats == ["deneme", "tam_deneme"], str(cats))

    # Etkinlikler
    chk("etkinlikler = 2", len(s.etkinlikler) == 2, str(s.etkinlikler))

    print(f"\n=== {passed} passed, {len(failed)} failed ===")
    for f in failed:
        print(f"  FAIL: {f}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
