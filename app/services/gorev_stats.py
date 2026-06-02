"""Görev / test / deneme sınıflandırma + sayım — TEK MERKEZ.

KAVRAM (kullanıcı standardı, 2026-06-02):
  - GÖREV = Task. Programa madde madde eklenen her madde 1 görevdir; bir görevde
    birden çok kalem OLMAZ. Örn: "TYT Fen Denemesi" = 1 görev; "AYT Türev 4 test"
    = 1 görev (4 test değil).
  - TEST = bir görevin içindeki çözülecek soru/hacim (ikincil).
  - DENEME ≠ TEST. Görev 4 kategoriye ayrılır:
      "test"       → kaynağı Soru Bankası (veya deneme-olmayan) kitap
      "deneme"     → kaynağı Branş/Genel Deneme kitabı
      "tam_deneme" → kitapsız "Deneme" görevi (book_id=None, planned>0; LGS/TYT tam deneme)
      "etkinlik"   → video/özet/tekrar/diğer (soru hacmi yok)

İLKE: GÖREV birincil birim (kaç görev / ne kadarı bitti %). TEST hacmi ikincil ve
DENEME'den AYRI tutulur. Etkinlik hacimsizdir. Tüm çıktılar (panel/mail/yazdırma)
bu özetten beslenmeli — "224/365 test" tarzı görev↔test karışıklığı yasak.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models.book import BookType
from app.models.task import Task, TaskStatus

# Deneme sayılan kitap türleri (branş + genel deneme).
_DENEME_BOOK_TYPES = {BookType.BRANS_DENEMESI, BookType.GENEL_DENEME}
DENEME_BOOK_TYPES = _DENEME_BOOK_TYPES  # public alias (analytics envanter filtresi)


def is_test_book(book) -> bool:
    """Kitap 'test' sayılır mı (soru bankası vb.) — deneme kitabı DEĞİL.

    Envanter/projeksiyon 'test' sayımında deneme kitaplarını dışlamak için.
    """
    return book is not None and book.type not in _DENEME_BOOK_TYPES


def item_is_test(item) -> bool:
    """Görev kalemi 'test' mi — kitapsız tam-deneme + deneme kitabı kalemi HARİÇ.

    Günlük seri 'test/gün' + 'test hacmi' sayımında deneme'yi dışlar.
    """
    return (
        getattr(item, "book_id", None) is not None
        and getattr(item, "book", None) is not None
        and item.book.type not in _DENEME_BOOK_TYPES
    )

GOREV_CATEGORIES = ("test", "deneme", "tam_deneme", "etkinlik")

CATEGORY_LABELS_TR = {
    "test": "Test",
    "deneme": "Deneme",
    "tam_deneme": "Tam Deneme",
    "etkinlik": "Etkinlik",
}


def _planned(task: Task) -> int:
    return sum(int(it.planned_count or 0) for it in task.book_items)


def _completed(task: Task) -> int:
    return sum(int(it.completed_count or 0) for it in task.book_items)


def classify_gorev(task: Task) -> str:
    """Görevin kategorisini döndür: test | deneme | tam_deneme | etkinlik.

    Soru hacmi 0 → etkinlik (video/özet/tekrar/diğer). Soru hacmi >0 ise:
    kitapsız kalem → tam_deneme; kitap deneme türü → deneme; aksi → test.
    """
    if _planned(task) <= 0:
        return "etkinlik"
    # Soru-hacimli görev. Görevde tek kalem olduğu için ilk kalem belirleyici.
    items = task.book_items
    if any(it.book_id is None for it in items):
        return "tam_deneme"
    for it in items:
        if it.book is not None and it.book.type in _DENEME_BOOK_TYPES:
            return "deneme"
    return "test"


def gorev_done(task: Task) -> bool:
    """Görev tamamlandı mı? (manşet % + 'X/Y görev' için)

    Durum COMPLETED → tamam (etkinlik dahil). Soru-hacimli görev → çözülen ≥
    planlanan ise tamam. Etkinlik (hacimsiz) yalnız status COMPLETED ile biter.
    """
    if task.status == TaskStatus.COMPLETED:
        return True
    p = _planned(task)
    if p <= 0:
        return False
    return _completed(task) >= p


def _primary_book(task: Task):
    for it in task.book_items:
        if it.book is not None:
            return it.book
    return None


@dataclass
class SubjectGorev:
    """Ders bazında TEST görevleri (denemeler ayrı listede)."""
    subject_id: int | None
    subject_name: str
    order: int
    gorev_total: int = 0
    gorev_done: int = 0
    test_planned: int = 0
    test_completed: int = 0

    @property
    def pct(self) -> int:
        return round(100 * self.gorev_done / self.gorev_total) if self.gorev_total else 0


@dataclass
class DenemeGorev:
    """Tek bir deneme/tam-deneme görevi (ayrı başlıkta listelenir)."""
    title: str
    subject_name: str | None
    category: str          # "deneme" | "tam_deneme"
    planned: int           # soru sayısı
    completed: int
    done: bool


@dataclass
class GorevSummary:
    gorev_total: int = 0
    gorev_done: int = 0
    # Kategori bazında görev (adet, tamamlanan)
    cat_total: dict = field(default_factory=lambda: {c: 0 for c in GOREV_CATEGORIES})
    cat_done: dict = field(default_factory=lambda: {c: 0 for c in GOREV_CATEGORIES})
    # Hacim — test (soru bankası) ve deneme (branş+tam) AYRI
    test_planned: int = 0
    test_completed: int = 0
    deneme_planned: int = 0
    deneme_completed: int = 0
    # Ders bazında TEST görevleri (sıralı)
    subjects: list[SubjectGorev] = field(default_factory=list)
    # Denemeler ayrı liste
    denemeler: list[DenemeGorev] = field(default_factory=list)
    # Etkinlik görevleri (başlık listesi)
    etkinlikler: list[str] = field(default_factory=list)

    @property
    def gorev_pct(self) -> int:
        return round(100 * self.gorev_done / self.gorev_total) if self.gorev_total else 0


def summarize(tasks: list[Task]) -> GorevSummary:
    """Görev listesini (bir gün/hafta) görev-merkezli özete çevirir.

    Beklenen: tasks book_items + book + subject joinli yüklenmiş (aksi halde lazy).
    Yalnız anlamlı görevler verilmeli (genelde is_draft=False, yayınlanmış).
    """
    s = GorevSummary()
    subj_map: dict[int | None, SubjectGorev] = {}

    for t in tasks:
        cat = classify_gorev(t)
        done = gorev_done(t)
        p, c = _planned(t), _completed(t)

        s.gorev_total += 1
        s.cat_total[cat] += 1
        if done:
            s.gorev_done += 1
            s.cat_done[cat] += 1

        if cat == "test":
            s.test_planned += p
            s.test_completed += c
            book = _primary_book(t)
            sid = book.subject_id if book is not None else None
            sg = subj_map.get(sid)
            if sg is None:
                subj = book.subject if book is not None else None
                sg = SubjectGorev(
                    subject_id=sid,
                    subject_name=(subj.name if subj else "Diğer"),
                    order=(subj.order if subj else 9999),
                )
                subj_map[sid] = sg
            sg.gorev_total += 1
            sg.test_planned += p
            sg.test_completed += c
            if done:
                sg.gorev_done += 1
        elif cat in ("deneme", "tam_deneme"):
            s.deneme_planned += p
            s.deneme_completed += c
            book = _primary_book(t)
            subj = book.subject if book is not None else None
            s.denemeler.append(DenemeGorev(
                title=t.title or "Deneme",
                subject_name=(subj.name if subj else None),
                category=cat,
                planned=p,
                completed=c,
                done=done,
            ))
        else:  # etkinlik
            s.etkinlikler.append(t.title or "Etkinlik")

    s.subjects = sorted(subj_map.values(), key=lambda x: (x.order, x.subject_id or 0))
    return s
