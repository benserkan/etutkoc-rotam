"""Deneme görevleri — branş / genel deneme TEK MERKEZİ (D1, 2026-10-20).

Koç iki tür deneme verir:
  · BRANŞ denemesi — tek ders (TYT Biyoloji, LGS Matematik …). Çoğunlukla kaynaktan
    (deneme kitabı); özel ders hocasının hazırladığı gibi kaynaksız da olabilir. Fen
    gruplarında soru az (6-14) olduğundan bir görevde 2-3 deneme verilir.
  · GENEL deneme — LGS tam/sayısal/sözel, TYT, AYT, YDT.

Kural: deneme kalemi (`TaskBookItem.exam_kind` dolu) = 1 deneme → planned_count = 1.
"×2" verilen görev 1 görev, 2 kalemdir; öğrenci her denemenin sonucunu ayrı girer.
`question_count` koçun başlangıç değeridir; öğrenci kendi kaynağındaki gerçek sayıya
göre girişte değiştirebilir — sistem tutarsızlık diye zorlamaz.

Soru sayısı sırası: koçun girdiği sayı > bölüm adındaki "(N soru)" > kitabın test
başına soru bilgisi > sınav standardı.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.models import Book, BookSection, StudentBook, Subject, Task, TaskBookItem, User
from app.models.book import BookType
from app.models.curriculum import CurriculumModel

EXAM_KIND_BRANS = "brans"
EXAM_KIND_GENEL = "genel"
EXAM_KINDS = (EXAM_KIND_BRANS, EXAM_KIND_GENEL)

DENEME_BOOK_TYPES = (BookType.BRANS_DENEMESI, BookType.GENEL_DENEME)

MAX_DENEME_PER_TASK = 10
MAX_QUESTIONS = 200


def _low(s: str | None) -> str:
    return (s or "").replace("İ", "i").replace("I", "ı").lower().strip()


# ---------------------------------------------------------------------------
# Sınav türü + standart soru sayıları
# ---------------------------------------------------------------------------

# (sınav türü, ders anahtar kelimesi) → sınavda o bölümün soru sayısı.
# Sıra önemli: daha özel kelime önce ("din" "edebiyat"tan önce değil; ayrık kelimeler).
_STANDARD: dict[str, list[tuple[str, int]]] = {
    "lgs": [
        ("türkçe", 20), ("matematik", 20), ("fen", 20),
        ("inkılap", 10), ("din", 10), ("ingilizce", 10), ("yabancı", 10),
    ],
    "tyt": [
        ("türkçe", 40), ("geometri", 40), ("matematik", 40),
        ("fizik", 7), ("kimya", 7), ("biyoloji", 6),
        ("tarih", 5), ("coğrafya", 5), ("felsefe", 5), ("din", 5),
    ],
    "ayt": [
        ("geometri", 40), ("matematik", 40), ("fizik", 14), ("kimya", 13), ("biyoloji", 13),
        ("edebiyat", 24), ("türk dili", 24), ("tarih", 21), ("coğrafya", 17),
        ("felsefe", 12), ("din", 6),
    ],
}

# Genel deneme hazır türleri — (anahtar, etiket, exam_section, soru)
GENEL_PRESETS: dict[str, list[tuple[str, str, str, int]]] = {
    "lgs": [
        ("lgs_tam", "LGS Tam Deneme", "lgs", 90),
        ("lgs_sayisal", "LGS Sayısal Bölüm", "lgs", 40),
        ("lgs_sozel", "LGS Sözel Bölüm", "lgs", 50),
    ],
    "yks": [
        ("tyt", "TYT Genel Deneme", "tyt", 120),
        ("ayt_say", "AYT Sayısal Deneme", "ayt_say", 80),
        ("ayt_ea", "AYT Eşit Ağırlık Deneme", "ayt_ea", 80),
        ("ayt_soz", "AYT Sözel Deneme", "ayt_soz", 80),
        ("ydt", "YDT (Yabancı Dil) Deneme", "ayt_dil", 80),
    ],
    "okul": [
        ("okul", "Sınıf Genel Denemesi", "okul", 40),
    ],
    # 2026-10-27 (koç + yayınevi takvimleri): lisede "okul denemesi" yok — sınıf düzeyi
    # Gelişim İzleme sınavları (soru sayısı değişken; varsayılan 40, koç değiştirir) ve
    # Maarif 1. Aşama (TYT, 9-10 konuları).
    "gis_9": [("gis_9", "9. Sınıf Gelişim İzleme", "maarif_9", 40)],
    "gis_10": [("gis_10", "10. Sınıf Gelişim İzleme", "maarif_10", 40)],
    "gis_11": [("gis_11", "11. Sınıf Gelişim İzleme", "maarif_11", 40)],
    "gis_12": [("gis_12", "12. Sınıf Gelişim İzleme (AYT)", "gis_12", 40)],
    "asama_1": [("maarif_1", "Maarif 1. Aşama (TYT)", "maarif_1", 125)],
}
_TRACK_PRESET = {"SAYISAL": "ayt_say", "EA": "ayt_ea", "SOZEL": "ayt_soz", "DIL": "ydt"}

# Birleşik branş denemeleri (2026-10-25) — sınavın tek oturumunu kapsayan, birden çok
# dersten oluşan branş denemeleri. Sistemde tek bir derse karşılık gelmez: kalem
# subject_id taşımaz, adı `label`dan okunur (köprü + analiz "TYT Fen Bilimleri" serisi açar).
# (anahtar, etiket, exam_section, soru, hangi alanlara gösterilir [None = herkese], kapsam)
BRANS_GROUPS: list[tuple[str, str, str, int, tuple[str, ...] | None, str]] = [
    ("tyt_fen", "TYT Fen Bilimleri", "tyt", 20, None, "Fizik 7 · Kimya 7 · Biyoloji 6"),
    ("tyt_sosyal", "TYT Sosyal Bilimler", "tyt", 20, None,
     "Tarih 5 · Coğrafya 5 · Felsefe 5 · Din Kültürü 5"),
    ("ayt_fen", "AYT Fen Bilimleri", "ayt_say", 40, ("SAYISAL",), "Fizik 14 · Kimya 13 · Biyoloji 13"),
    ("ayt_edebiyat_sos1", "AYT Edebiyat-Sosyal Bilimler 1", "ayt_ea", 40, ("EA", "SOZEL"),
     "Edebiyat 24 · Tarih-1 10 · Coğrafya-1 6"),
    ("ayt_sos2", "AYT Sosyal Bilimler 2", "ayt_soz", 40, ("SOZEL",),
     "Tarih-2 11 · Coğrafya-2 11 · Felsefe Grubu 12 · Din Kültürü 6"),
]
BRANS_GROUP_LABELS = {k: lbl for k, lbl, *_ in BRANS_GROUPS}


@dataclass
class BransGroup:
    key: str
    label: str
    exam_section: str
    question_count: int
    covers: str


def brans_groups_for(student: User) -> list[BransGroup]:
    """Öğrenciye uygun birleşik branş denemeleri: TYT grupları lise (9+) ve mezuna;
    AYT grupları 11+/mezunda alana göre (alan bilinmiyorsa hepsi)."""
    grade = getattr(student, "grade_level", None)
    graduate = bool(getattr(student, "is_graduate", False))
    if not graduate and (grade is None or grade < 9):
        return []
    ayt_ok = graduate or (grade is not None and grade >= 11)
    track = getattr(student, "track", None)
    track_v = str(getattr(track, "value", track) or "").upper() or None
    out: list[BransGroup] = []
    for key, label, sec, n, tracks, covers in BRANS_GROUPS:
        if sec.startswith("ayt"):
            if not ayt_ok:
                continue
            if tracks and track_v and track_v not in tracks:
                continue
        out.append(BransGroup(key=key, label=label, exam_section=sec, question_count=n, covers=covers))
    return out


def brans_group_for_label(label: str | None) -> str | None:
    """Kalem etiketinden ("TYT Fen Bilimleri 2/3") birleşik branş anahtarı."""
    low = _low(re.sub(r"\s*\d+\s*/\s*\d+\s*$", "", label or ""))
    for key, lbl in BRANS_GROUP_LABELS.items():
        if _low(lbl) == low:
            return key
    return None


def exam_section_for_subject(subject: Subject | None) -> str | None:
    """Dersin sınav türü: TYT/AYT dersinde kendi alanı, LGS modelindeki derste 'lgs',
    okul (Maarif/Klasik) dersinde 'okul'."""
    if subject is None:
        return None
    sec = getattr(subject, "exam_section", None)
    if sec is not None:
        return sec.value if hasattr(sec, "value") else str(sec)
    model = getattr(subject, "curriculum_model", None)
    if model == CurriculumModel.LGS:
        return "lgs"
    name = _low(subject.name)
    if name.startswith("tyt"):
        return "tyt"
    if name.startswith("ayt"):
        return "ayt_say"
    return "okul"


def penalty_for_section(section: str | None) -> int:
    """Net cezası: LGS'de 3 yanlış 1 doğruyu, diğerlerinde 4 yanlış götürür."""
    return 3 if section == "lgs" else 4


def standard_question_count(subject: Subject | None) -> int | None:
    """Branş denemesi için sınavdaki bölüm soru sayısı (bilinmiyorsa None)."""
    if subject is None:
        return None
    sec = exam_section_for_subject(subject) or ""
    family = "lgs" if sec == "lgs" else ("tyt" if sec == "tyt" else ("ayt" if sec.startswith("ayt") else None))
    if family is None:
        return None
    name = _low(subject.name)
    for word, n in _STANDARD[family]:
        if word in name:
            return n
    return None


_LABEL_Q_RE = re.compile(r"(\d{1,3})\s*soru", re.I)


def question_count_from_label(label: str | None) -> int | None:
    """Bölüm adındaki "(20 soru)" / "40 soru" ifadesi."""
    m = _LABEL_Q_RE.search(label or "")
    if not m:
        return None
    n = int(m.group(1))
    return n if 1 <= n <= MAX_QUESTIONS else None


def resolve_question_count(
    *, book: Book | None, section: BookSection | None, subject: Subject | None,
) -> tuple[int | None, str]:
    """(soru sayısı, kaynak) — kaynak: label | book | standard | none."""
    n = question_count_from_label(section.label if section is not None else None)
    if n:
        return n, "label"
    if book is not None and book.avg_questions_per_test:
        return int(book.avg_questions_per_test), "book"
    n = standard_question_count(subject)
    if n:
        return n, "standard"
    return None, "none"


# ---------------------------------------------------------------------------
# Kalem / görev yardımcıları (gorev_stats ve serializer'lar okur)
# ---------------------------------------------------------------------------


def is_exam_item(item) -> bool:
    return getattr(item, "exam_kind", None) in EXAM_KINDS


def item_subject(item) -> Subject | None:
    book = getattr(item, "book", None)
    if book is not None and book.subject is not None:
        return book.subject
    return getattr(item, "exam_subject", None)


# ---------------------------------------------------------------------------
# Kaynak seçimi — öğrencinin o dersteki deneme kitapları + sıradaki denemeler
# ---------------------------------------------------------------------------


@dataclass
class SectionSlot:
    section_id: int
    label: str
    remaining: int


@dataclass
class DenemeBookOption:
    book_id: int
    name: str
    type: str
    subject_id: int
    question_count: int | None
    question_source: str
    remaining_total: int
    next_sections: list[SectionSlot] = field(default_factory=list)


def _section_remaining(db: Session, student_id: int, book_id: int, section: BookSection) -> int:
    from app.services.task_service import remaining_for

    kalan, _ = remaining_for(db, student_id=student_id, book_id=book_id, section_id=section.id)
    return kalan


def deneme_books_for_student(db: Session, student: User) -> list[DenemeBookOption]:
    """Öğrencinin arşivlenmemiş deneme kitapları + her kitabın sıradaki denemeleri."""
    rows = (
        db.query(Book)
        .join(StudentBook, StudentBook.book_id == Book.id)
        .options(joinedload(Book.sections), joinedload(Book.subject))
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),
            Book.type.in_(list(DENEME_BOOK_TYPES)),
        )
        .all()
    )
    out: list[DenemeBookOption] = []
    for b in sorted({b.id: b for b in rows}.values(), key=lambda x: _low(x.name)):
        slots: list[SectionSlot] = []
        total = 0
        for s in sorted(b.sections, key=lambda x: (x.order or 0, x.id)):
            r = _section_remaining(db, student.id, b.id, s)
            total += r
            if r > 0 and len(slots) < MAX_DENEME_PER_TASK:
                slots.append(SectionSlot(section_id=s.id, label=s.label, remaining=r))
        first_section = next((s for s in b.sections if s.id == slots[0].section_id), None) if slots else None
        qn, qsrc = resolve_question_count(book=b, section=first_section, subject=b.subject)
        out.append(DenemeBookOption(
            book_id=b.id, name=b.name, type=b.type.value, subject_id=b.subject_id,
            question_count=qn, question_source=qsrc,
            remaining_total=total, next_sections=slots,
        ))
    return out


def pick_sections(db: Session, student: User, book: Book, count: int) -> list[tuple[BookSection, bool]]:
    """Kitapta sıradaki `count` deneme — her biri (bölüm, kapasite_aşımı mı).

    Bölüm sırasıyla kalan kapasite tüketilir (tek bölümde birden çok deneme olabilir:
    koçun elle açtığı "Deneme · 40" gibi). Kitap biterse son bölüm kapasite aşımıyla
    tekrar kullanılır — kitabın sayısı yardımcıdır, programı engellemez (P1 kuralı).
    """
    sections = sorted(book.sections, key=lambda x: (x.order or 0, x.id))
    if not sections:
        return []
    picked: list[tuple[BookSection, bool]] = []
    for s in sections:
        r = _section_remaining(db, student.id, book.id, s)
        while r > 0 and len(picked) < count:
            picked.append((s, False))
            r -= 1
        if len(picked) >= count:
            break
    last = picked[-1][0] if picked else sections[-1]
    while len(picked) < count:
        picked.append((last, True))
    return picked


# ---------------------------------------------------------------------------
# Genel deneme türleri + koçun alışkanlığından şablon önerileri
# ---------------------------------------------------------------------------


@dataclass
class GenelPreset:
    key: str
    label: str
    exam_section: str
    question_count: int


def genel_presets_for(student: User) -> list[GenelPreset]:
    grade = getattr(student, "grade_level", None)
    graduate = bool(getattr(student, "is_graduate", False))
    out: list[tuple[str, str, str, int]] = []
    if grade == 8 or (grade is not None and grade < 8):
        out = list(GENEL_PRESETS["lgs"])
    elif graduate or (grade is not None and grade >= 11):
        track = getattr(student, "track", None)
        track_v = getattr(track, "value", track)
        preferred = _TRACK_PRESET.get(str(track_v).upper()) if track_v else None
        out = list(GENEL_PRESETS["yks"])
        if preferred:  # alanına uygun AYT önce, diğer AYT'ler sonra
            out.sort(key=lambda p: (p[0] != "tyt", p[0] != preferred))
        if grade is not None and grade < 12 and not graduate:
            # 11 (Maarif): 1. Aşama + 11. sınıf gelişim izleme (tablo, 2026-10-27)
            out = list(GENEL_PRESETS["asama_1"]) + list(GENEL_PRESETS["gis_11"])
        else:
            out = out + list(GENEL_PRESETS["gis_12"])
    elif grade == 10:
        out = list(GENEL_PRESETS["gis_10"]) + list(GENEL_PRESETS["asama_1"])
    elif grade == 9:
        out = list(GENEL_PRESETS["gis_9"])
    else:
        out = list(GENEL_PRESETS["lgs"]) + list(GENEL_PRESETS["yks"])
    return [GenelPreset(key=k, label=lbl, exam_section=sec, question_count=n) for k, lbl, sec, n in out]


@dataclass
class DenemeTemplate:
    kind: str
    label: str
    count: int
    question_count: int
    subject_id: int | None = None
    exam_section: str | None = None
    book_id: int | None = None
    uses: int = 0
    group_key: str | None = None


def coach_templates(
    db: Session, *, coach_id: int, student: User, subject_ids: set[int],
    book_ids: set[int], limit: int = 8, days: int = 120,
) -> list[DenemeTemplate]:
    """Koçun son `days` günde verdiği deneme kalıpları (tüm öğrencileri) — en sık önce.

    Kalıp anahtarı: tür + ders (ad) / kitap + adet + soru. Bu öğrenciye uygulanamayan
    (dersi/kitabı yok) kalıplar elenir; başka öğrencideki ders ADIyla eşleşir.
    """
    since = date.today() - timedelta(days=days)
    tasks = (
        db.query(Task)
        .join(User, User.id == Task.student_id)
        .options(joinedload(Task.book_items).joinedload(TaskBookItem.book).joinedload(Book.subject),
                 joinedload(Task.book_items).joinedload(TaskBookItem.exam_subject))
        .filter(User.teacher_id == coach_id, Task.date >= since)
        .filter(Task.book_items.any(TaskBookItem.exam_kind.isnot(None)))
        .all()
    )
    subj_by_name = {
        _low(s.name): s for s in db.query(Subject).filter(Subject.id.in_(subject_ids or {-1})).all()
    }
    allowed_groups = {g.key for g in brans_groups_for(student)}
    counter: Counter = Counter()
    sample: dict[tuple, DenemeTemplate] = {}
    for t in tasks:
        items = [it for it in t.book_items if is_exam_item(it)]
        if not items:
            continue
        first = items[0]
        qn = int(first.question_count or 0)
        if qn <= 0:
            continue
        kind = first.exam_kind
        if kind == EXAM_KIND_GENEL:
            if first.book_id is not None and first.book_id not in book_ids:
                continue
            key = ("genel", first.exam_section, first.book_id if first.book_id in book_ids else None,
                   len(items), qn)
            base = (first.label or "Genel Deneme").split(" — ")[0] if first.book_id is None else (
                first.book.name if first.book else "Genel Deneme")
            tpl = DenemeTemplate(kind=kind, label=base, count=len(items), question_count=qn,
                                 exam_section=first.exam_section,
                                 book_id=first.book_id if first.book_id in book_ids else None)
        else:
            subj = item_subject(first)
            if subj is None:
                gkey = brans_group_for_label(first.label)
                if gkey is None or gkey not in allowed_groups:
                    continue
                key = ("brans_group", gkey, len(items), qn)
                tpl = DenemeTemplate(kind=kind, label=BRANS_GROUP_LABELS[gkey], count=len(items),
                                     question_count=qn, exam_section=first.exam_section, group_key=gkey)
                counter[key] += 1
                sample.setdefault(key, tpl)
                continue
            local = subj if subj.id in subject_ids else subj_by_name.get(_low(subj.name))
            if local is None:
                continue
            book_id = first.book_id if first.book_id in book_ids else None
            key = ("brans", local.id, book_id, len(items), qn)
            tpl = DenemeTemplate(kind=kind, label=local.name, count=len(items), question_count=qn,
                                 subject_id=local.id, exam_section=exam_section_for_subject(local),
                                 book_id=book_id)
        counter[key] += 1
        sample.setdefault(key, tpl)
    out = []
    for key, n in counter.most_common(limit):
        tpl = sample[key]
        tpl.uses = n
        out.append(tpl)
    return out


# ---------------------------------------------------------------------------
# Görev başlığı
# ---------------------------------------------------------------------------


def _compose_title_raw(
    *, kind: str, count: int, question_count: int, subject: Subject | None = None,
    book: Book | None = None, section_labels: list[str] | None = None,
    genel_label: str | None = None, custom_name: str | None = None,
) -> str:
    q = f"({question_count} soru)" if question_count else ""
    if kind == EXAM_KIND_GENEL:
        base = custom_name or (book.name if book else None) or genel_label or "Genel Deneme"
        if custom_name and genel_label and _low(genel_label) not in _low(custom_name):
            base = f"{custom_name} · {genel_label}"
        return f"{base} ×{count} {q}" if count > 1 else f"{base} {q}"
    if book is not None:
        labels = [lbl for lbl in (section_labels or []) if lbl]
        uniq = list(dict.fromkeys(labels))
        if uniq and len(uniq) == count:
            short = ", ".join(_strip_q(lbl) for lbl in uniq)
            return f"{book.name} — {short} {q}"
        return f"{book.name} — {count} deneme {q}"
    name = custom_name or (f"{subject.name} branş denemesi" if subject else "Branş denemesi")
    return f"{name} ×{count} {q}" if count > 1 else f"{name} {q}"


def _strip_q(label: str) -> str:
    return re.sub(r"\s*\(\s*\d{1,3}\s*soru\s*\)\s*", "", label).strip()


def compose_title(**kw) -> str:
    """Deneme görevi başlığı (soru sayısı bilinmiyorsa parantez yazılmaz)."""
    return re.sub(r"\s{2,}", " ", _compose_title_raw(**kw)).strip()


# ---------------------------------------------------------------------------
# D2 — sonuç girişi (öğrenci + koç ortak)
# ---------------------------------------------------------------------------

MAX_DURATION_MIN = 600
RESULT_REMIND_AFTER_DAYS = 2


class DenemeResultError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class DenemeRow:
    item_id: int
    solved: bool = True
    correct: int | None = None
    wrong: int | None = None
    blank: int | None = None
    question_count: int | None = None
    duration_minutes: int | None = None


def item_net(item) -> float | None:
    """Kalemin neti (sonuç girildiyse): D − Y/ceza (LGS 3, diğer 4)."""
    if getattr(item, "correct_count", None) is None and getattr(item, "wrong_count", None) is None:
        return None
    c = int(item.correct_count or 0)
    w = int(item.wrong_count or 0)
    return round(c - w / penalty_for_section(getattr(item, "exam_section", None)), 2)


def result_pending(item) -> bool:
    """Deneme çözüldü (işaretli) ama doğru/yanlış girilmedi."""
    return (is_exam_item(item) and int(item.completed_count or 0) > 0
            and item.correct_count is None and item.wrong_count is None)


def apply_results(db: Session, task: Task, rows: list[DenemeRow]) -> None:
    """Bir görevin deneme satırlarına sonuç yaz (1 satır = 1 deneme).

    · solved=False → deneme çözülmedi (tamamlanan 0, sonuç temizlenir)
    · solved=True + D/Y yok → "sonucu sonra gireceğim" (çözüldü, sonuç bekliyor)
    · soru sayısı ESNEK: öğrenci kendi kaynağındaki sayıyı yazar (koçun değeri başlangıçtır);
      boş verilmezse soru − D − Y olarak hesaplanır; D+Y+B soru sayısını aşamaz.
    Rezerv/kitap sayacı task_service.set_item_completion ile (tek merkez)."""
    from app.services.task_service import set_item_completion

    by_id = {it.id: it for it in task.book_items}
    for r in rows:
        it = by_id.get(r.item_id)
        if it is None or not is_exam_item(it):
            raise DenemeResultError("item_not_found", "Deneme satırı bulunamadı.")
        for v in (r.correct, r.wrong, r.blank):
            if v is not None and v < 0:
                raise DenemeResultError("invalid_result", "Doğru, yanlış ve boş negatif olamaz.")
        if r.duration_minutes is not None and not (1 <= r.duration_minutes <= MAX_DURATION_MIN):
            raise DenemeResultError("invalid_duration", "Süre 1 ile 600 dakika arasında olmalı.")
        qn = r.question_count if r.question_count is not None else it.question_count
        if qn is not None and not (1 <= qn <= MAX_QUESTIONS):
            raise DenemeResultError("invalid_question_count", "Soru sayısı 1 ile 200 arasında olmalı.")
        if not r.solved:
            set_item_completion(db, it, 0)
            it.correct_count = it.wrong_count = it.blank_count = None
            it.duration_minutes = None
            continue
        has_result = r.correct is not None or r.wrong is not None
        c, w = int(r.correct or 0), int(r.wrong or 0)
        b = r.blank
        if has_result and b is None and qn:
            b = max(0, qn - c - w)
        if has_result and qn is not None and c + w + int(b or 0) > qn:
            raise DenemeResultError(
                "result_exceeds_questions",
                f"Doğru + yanlış + boş ({c + w + int(b or 0)}) soru sayısından ({qn}) fazla — "
                "kaynağındaki soru sayısı farklıysa soru sayısını düzelt.")
        if has_result:
            set_item_completion(db, it, 1, correct=c, wrong=w, blank=int(b or 0))
        else:
            set_item_completion(db, it, 1)
        if r.question_count is not None:
            it.question_count = r.question_count
        if r.duration_minutes is not None:
            it.duration_minutes = r.duration_minutes
    db.flush()


def pending_result_items(db: Session, *, student_id: int | None = None, older_than: date | None = None,
                         only_unreminded: bool = False) -> list[TaskBookItem]:
    """Çözülmüş ama sonucu girilmemiş deneme satırları (yayınlanmış görevler)."""
    q = (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
         .filter(TaskBookItem.exam_kind.isnot(None), TaskBookItem.completed_count > 0,
                 TaskBookItem.correct_count.is_(None), TaskBookItem.wrong_count.is_(None),
                 Task.is_draft.is_(False)))
    if student_id is not None:
        q = q.filter(Task.student_id == student_id)
    if older_than is not None:
        q = q.filter(Task.date <= older_than)
    if only_unreminded:
        q = q.filter(TaskBookItem.result_reminded_at.is_(None))
    return q.all()


def pending_result_rows(db: Session, student_id: int, today: date | None = None) -> list[dict]:
    """Sonucu eksik denemeler — öğrenci/koç listesi (en eski önce). Gün yalnız bugüne kadar."""
    from app.services.deneme_bridge import _title

    today = today or date.today()
    out = []
    for it in pending_result_items(db, student_id=student_id, older_than=today):
        out.append({
            "task_id": it.task_id, "item_id": it.id, "date": it.task.date.isoformat(),
            "task_title": it.task.title, "label": _title(it), "exam_kind": it.exam_kind,
            "question_count": it.question_count, "days_waiting": (today - it.task.date).days,
            "exam_section": it.exam_section, "duration_minutes": it.duration_minutes,
        })
    out.sort(key=lambda r: (r["date"], r["task_id"], r["item_id"]))
    return out


def run_result_reminders(db: Session, *, now) -> dict:
    """Cron: çözülmüş ama 2+ gündür sonucu girilmemiş denemeler için öğrenciye push (satır başına
    bir kez; öğrenci başına tek bildirim). Rehbere kırmızı yok — koç öğrenci sayfasında görür."""
    from datetime import timezone as _tz

    from app.services.push_notifications import safe_push

    today = now.date() if hasattr(now, "date") else date.today()
    rows = pending_result_items(db, older_than=today - timedelta(days=RESULT_REMIND_AFTER_DAYS),
                                only_unreminded=True)
    by_student: dict[int, list[TaskBookItem]] = {}
    for it in rows:
        by_student.setdefault(it.task.student_id, []).append(it)
    sent = 0
    stamp = now if getattr(now, "tzinfo", None) else now.replace(tzinfo=_tz.utc)
    for sid, items in by_student.items():
        student = db.get(User, sid)
        for it in items:
            it.result_reminded_at = stamp
        if student is None or not student.is_active:
            continue
        n = len(items)
        safe_push(db, user_id=sid, title="Deneme sonucun bekliyor",
                  body=(f"{n} denemenin doğru/yanlış sonucunu girmedin. Girersen koçun hangi "
                        "konuda net kaybettiğini görebilir."),
                  data={"type": "student", "screen": "today"})
        sent += 1
    db.commit()
    return {"students": sent, "items": len(rows)}
