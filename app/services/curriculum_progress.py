"""Öğrenci bazlı müfredat ilerleme — hibrit omurga (Faz 1).

Resmi müfredat konularını (Topic, sıralı) omurga alır; öğrencinin atanan kitap
section'larının (topic_id eşli) ilerlemesini (SectionProgress) bunlara bindirir.
Koç "müfredatta nerede + tamamlama oranı + sıradaki konu"yu görür.

Veri zinciri:
  applicable Subjects (resmi, grade+curriculum_model) → ordered Topics →
  öğrencinin o topic'e eşli section'ları (StudentBook→Book→BookSection.topic_id) →
  SectionProgress (completed/reserved) + BookSection.test_count → durum + %.

Eşleşmemiş section'lar (topic_id NULL veya müfredat dışı topic) → "ekstra" grubu
(kaybolmaz). Hiç kaynağı olmayan resmi konu → "kaynak_yok".

DURUM: kaynak_yok | baslanmadi | planlandi | devam | tamamlandi.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models import (
    Book,
    BookSection,
    ExamSection,
    SectionProgress,
    StudentBook,
    Subject,
    Task,
    TaskStatus,
    TaskBookItem,
    Topic,
    Track,
    User,
)
from app.models.curriculum import CurriculumModel
from app.services import topic_closure
from app.services.gorev_stats import DENEME_BOOK_TYPES


@dataclass
class TopicProgress:
    topic_id: int
    name: str
    order: int
    has_resource: bool
    test_total: int
    completed: int
    reserved: int
    status: str
    pct: int            # konu içi derinlik: completed/test_total
    unit_name: str | None = None    # ait olduğu tema/ünite (Maarif) — UI gruplama
    grade_level: int | None = None  # konunun sınıfı — UI sınıf başlığı (tekrar eden tema adı ayrımı)
    # Koç "bu konu bitti" dedi mi (2026-09-07) — müfredat tamamlanmasının kaynağı
    closed: bool = False
    closed_at: str | None = None
    # Kaynaksız (kitapsız ama konuya bağlı) görevlerden çözülen test sayısı
    sourceless_completed: int = 0
    # HAVUZ (2026-10-14): açık dönemde bu konudan bekleyen birim + seansta işaretlenen kaynaksız birim
    pool_remaining: int = 0
    pool_marked: int = 0
    in_focus: bool = True             # ilerleme/projeksiyon hesabına giren konu (odak sınıf)
    # Kaynak kırılımı (2026-09-27): [(kitap adı, çözülen, toplam)] — tamamlanma
    # kuralının hangi kitaptan geldiği UI'da görünsün (deneme kitabı hariç).
    sources: list = field(default_factory=list)


@dataclass
class SubjectProgress:
    subject_id: int
    name: str
    order: int
    total_topics: int
    started_topics: int      # completed>0
    completed_topics: int    # completed>=test_total (ve test_total>0)
    no_resource_topics: int
    coverage_pct: int        # started/total (müfredat işlenme oranı)
    last_topic_name: str | None      # frontier: son işlenen (en yüksek order, started)
    next_topic_name: str | None      # frontier: sıradaki (kaynaklı, başlanmamış)
    topics: list[TopicProgress] = field(default_factory=list)
    pool_remaining: int = 0          # açık havuz döneminde bu dersten bekleyen birim (konulu kalemler)
    # ODAK SINIF (2026-10-14): yukarıdaki sayımlar öğrencinin İÇİNDE BULUNDUĞU sınıfın konularıdır
    # (9-11 / LGS 5-8). Önceki sınıfların konuları ayrıca sayılır; 12/mezunda odak yok → hepsi.
    prior_total_topics: int = 0
    prior_started_topics: int = 0
    prior_completed_topics: int = 0


@dataclass
class ExtraSection:
    section_id: int
    label: str
    book_name: str
    subject_name: str | None
    test_total: int
    completed: int


@dataclass
class PoolUnlinkedItem:
    """Açık havuz döneminde KONUSU OLMAYAN kalem (serbest metin / konusuz kitap bölümü) —
    müfredata işlenemez; koç görsün diye listelenir (kitaptaki 'eşleşmemiş ünite'nin havuz karşılığı)."""
    item_id: int
    subject_name: str
    title: str
    quantity: int
    done: int


@dataclass
class CurriculumProjection:
    has_exam: bool
    days_to_exam: int | None
    remaining_topics: int
    pace_per_week: float            # son 2 haftada işlenen farklı ODAK konu / 2
    projected_coverage_pct: int     # mevcut hızla hedef güne kadar ulaşılacak kapsama
    verdict: str                    # yetisir | risk | yetismez | sinav_yok | veri_yok
    # 2026-10-15: hedef — okulda olan öğrencide EĞİTİM YILI SONU (o sınıfın müfredatı),
    # mezunda SINAV (9-12 tüm konular). `days_to_exam` geriye uyum için hedef güne kalan gün.
    target_kind: str = "sinav"      # okul_yili_sonu | sinav
    target_date: str | None = None
    target_label: str | None = None


@dataclass
class GradeCoverage:
    grade: int | None       # None = sınıfı belirsiz konular
    total_topics: int
    started_topics: int
    completed_topics: int
    coverage_pct: int
    is_focus: bool


@dataclass
class CurriculumProgress:
    curriculum_model: str | None
    grade_level: int | None
    overall_total_topics: int
    overall_started_topics: int
    overall_coverage_pct: int
    subjects: list[SubjectProgress]
    extras: list[ExtraSection]       # müfredata eşleşmemiş kitap üniteleri
    projection: "CurriculumProjection | None" = None
    program_mode: str = "gun_gun"            # havuz → konu satırında "Havuza ekle"
    pool_period_id: int | None = None        # açık havuz dönemi
    pool_unlinked: list[PoolUnlinkedItem] = field(default_factory=list)
    # ODAK SINIF: overall_* bu sınıfın konularıdır. None → kümülatif (12/mezun/bilinmeyen).
    focus_grade: int | None = None
    cumulative_total_topics: int = 0
    cumulative_started_topics: int = 0
    cumulative_coverage_pct: int = 0
    grades: list[GradeCoverage] = field(default_factory=list)


def focus_grade_for(student: User) -> int | None:
    """Koçun önceliği öğrencinin içinde bulunduğu sınıfın müfredatıdır (koç, 2026-10-14/15).

    Okuldaki öğrenci (5-12) → o sınıf: ilerleme ve projeksiyon YALNIZ bu sınıfın konularından;
    önceki sınıfların konuları görünür ama hesaba girmez (12. sınıf öğrencisi 9-11'i de görür,
    hesap 12. sınıf konularıyla). Mezun → yok (9-12 tüm konular). Sınıfı bilinmeyen → yok."""
    g = student.grade_level
    if student.is_graduate or g is None or g > 12 or g < 5:
        return None
    return g


def topic_in_focus(grade_level: int | None, focus: int | None) -> bool:
    """Konu odak sınıfa mı ait? Odak yoksa hepsi; sınıfı belirsiz konu odaktadır."""
    return focus is None or grade_level is None or grade_level == focus


def topic_in_focus_for(t: Topic, s: Subject, focus: int | None) -> bool:
    """Konu-düzeyi odak. SINAV dersinde (TYT/AYT) sınıf ayrımı YOK — TYT ve AYT konu listesi zaten
    belli, dersin tüm konuları ilerleme ve projeksiyona girer (koç, 2026-10-15). Okul müfredatı
    dersinde konu kendi sınıfıyla karşılaştırılır (önceki sınıfların konuları görünür, hesaba girmez)."""
    if focus is None or _is_exam_subject(s):
        return True
    return t.grade_level is None or t.grade_level == focus


def school_year_end(today: "date") -> "date":
    """Eğitim öğretim yılı sonu — 15 Haziran (koç). Eylül-Haziran arası içinde bulunulan yılın
    sonu; yaz tatilinde (15 Haziran sonrası) bir sonraki yılın sonu."""
    from datetime import date as _d

    if today.month >= 9:
        return _d(today.year + 1, 6, 15)
    end = _d(today.year, 6, 15)
    return end if today <= end else _d(today.year + 1, 6, 15)


# KONU TAMAMLANMA KURALI (koç, 2026-09-27) — kaynak sayısına göre:
#  * Konu TEK kaynakta → o kaynakta konunun testlerinin %98'i çözüldüyse tamam.
#  * Konu BİRDEN FAZLA kaynakta → kaynaklardan biri tamamen bitmiş VE ikinci
#    kaynaktan da o konunun testlerinin %90'ı çözülmüşse tamam.
# Deneme kitapları (branş/genel) kaynak sayılmaz (DENEME≠TEST). Koçun kapatma
# kararı her durumda üstündür (bkz. _status). TEK MERKEZ: müfredat sekmesi,
# hafta panelindeki Müfredat bölümü ve "sıradaki üniteler" bunu kullanır.
SINGLE_SOURCE_DONE_RATIO = 0.98
PRIMARY_SOURCE_DONE_RATIO = 1.0
SECOND_SOURCE_DONE_RATIO = 0.90


def topic_sources_complete(per_book: dict) -> bool:
    """`per_book`: kitap → (çözülen, toplam test). Konu kaynak sayacına göre
    tamamlandı mı? Test sayısı olmayan kitap hesaba girmez."""
    ratios = sorted(
        (min(1.0, c / t) for c, t in per_book.values() if t and t > 0),
        reverse=True,
    )
    if not ratios:
        return False
    if len(ratios) == 1:
        return ratios[0] >= SINGLE_SOURCE_DONE_RATIO
    return (
        ratios[0] >= PRIMARY_SOURCE_DONE_RATIO
        and ratios[1] >= SECOND_SOURCE_DONE_RATIO
    )


def add_book_progress(per_book: dict, book_id: int, book_type, completed, total) -> None:
    """Bölüm satırını konunun kitap-bazlı toplamına ekler (deneme kitabı hariç)."""
    if book_type in DENEME_BOOK_TYPES:
        return
    c, t = per_book.get(book_id, (0, 0))
    per_book[book_id] = (c + int(completed or 0), t + int(total or 0))


def agg_complete(agg: dict | None) -> bool | None:
    """Konu agregatından tamamlanma: kitap bazlı kural; kaynak yalnız deneme
    kitabıysa toplam üzerinden tek-kaynak eşiği."""
    if not agg:
        return None
    if agg.get("books"):
        return topic_sources_complete(agg["books"])
    t = agg.get("test") or 0
    return bool(t > 0 and agg.get("completed", 0) / t >= SINGLE_SOURCE_DONE_RATIO)


def _status(
    has_resource: bool,
    completed: int,
    reserved: int,
    test_total: int,
    *,
    closed: bool = False,
    sourceless_completed: int = 0,
    sourceless_planned: int = 0,
    sources_complete: bool | None = None,
    pool_planned: int = 0,
) -> str:
    """Konunun durumu.

    KOÇ KARARI HER ŞEYİN ÜSTÜNDE (2026-09-07): koç öğrenciyle görüşüp konuyu
    kapattıysa konu TAMAMLANMIŞTIR — kitapta test kalmış olması bunu değiştirmez.
    Bir konunun bitip bitmediği kaynağın sayacından değil koçtan okunur.

    Kaynaksız çalışma (kitapsız ama konuya bağlı görev) da konuyu "işlenmiş"
    yapar; kitabı olmayan konu artık otomatik "kaynak_yok" değildir.

    HAVUZ (2026-10-13): açık dönemde bu konudan bekleyen kalem (`pool_planned`) rezervin
    karşılığıdır → "planlandı".
    """
    if closed:
        return "tamamlandi"
    if not has_resource:
        if sourceless_completed > 0:
            return "devam"
        if sourceless_planned > 0 or pool_planned > 0:
            return "planlandi"
        return "kaynak_yok"
    if completed <= 0:
        if reserved > 0 or sourceless_planned > 0 or pool_planned > 0:
            return "planlandi"
        return "devam" if sourceless_completed > 0 else "baslanmadi"
    done = (
        sources_complete if sources_complete is not None
        else (test_total > 0 and completed >= test_total)
    )
    return "tamamlandi" if done else "devam"


def _recent_topic_ids(db: Session, student: User, days: int = 14) -> set[int]:
    """Son `days` günde işlenen konular (kitaplı bölüm konusu + kaynaksız konulu kalem + koçun kapattığı)."""
    from datetime import date, datetime, timedelta, timezone

    from app.models import Task, TaskBookItem
    from app.models.topic_closure import TopicClosure

    start = date.today() - timedelta(days=days)
    ids = {r[0] for r in (
        db.query(BookSection.topic_id)
        .join(TaskBookItem, TaskBookItem.book_section_id == BookSection.id)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(Task.student_id == student.id, Task.date >= start, TaskBookItem.completed_count > 0,
                BookSection.topic_id.isnot(None))
        .distinct().all())}
    ids |= {r[0] for r in (
        db.query(TaskBookItem.topic_id)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(Task.student_id == student.id, Task.date >= start, TaskBookItem.completed_count > 0,
                TaskBookItem.book_id.is_(None), TaskBookItem.topic_id.isnot(None))
        .distinct().all())}
    since = datetime.now(timezone.utc) - timedelta(days=days)
    ids |= {r[0] for r in (
        db.query(TopicClosure.topic_id)
        .filter(TopicClosure.student_id == student.id, TopicClosure.closed_at >= since).all())}
    return ids


def non_test_sourceless_signals(db: Session, student_id: int) -> tuple[set[int], set[int]]:
    """Soru/sayfa birimli kaynaksız konulu kalemler (2026-10-22) — (çalışılan, planlanan) konu
    kimlikleri. Bu kalemler TEST sayısına girmez; konuya "devam/planlandı" sinyali verir."""
    rows = (
        db.query(TaskBookItem.topic_id, TaskBookItem.completed_count)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(Task.student_id == student_id, Task.is_draft.is_(False),
                TaskBookItem.book_id.is_(None), TaskBookItem.topic_id.isnot(None),
                TaskBookItem.unit.in_(("soru", "sayfa")))
        .all()
    )
    worked = {int(t) for t, c in rows if (c or 0) > 0}
    planned = {int(t) for t, c in rows if not (c or 0)}
    # Konuya bağlı ETKİNLİK görevi (video/özet/tekrar/diğer, tasks.topic_id): tamamlanınca
    # çalışıldı, değilse planlandı.
    for tid, st in (
        db.query(Task.topic_id, Task.status)
        .filter(Task.student_id == student_id, Task.is_draft.is_(False), Task.topic_id.isnot(None))
        .all()
    ):
        (worked if st == TaskStatus.COMPLETED else planned).add(int(tid))
    planned -= worked
    return worked, planned


def _compute_projection(
    db: Session, student: User, total: int, started: int,
    *, focus_topic_ids: set[int] | None = None, focus: int | None = None,
) -> "CurriculumProjection":
    """Müfredat yetişme projeksiyonu — kapsama + hedef güne kalan süre + son hız.

    HEDEF (koç, 2026-10-15): okuldaki öğrenci (odak sınıf var) o sınıfın müfredatını EĞİTİM YILI
    SONUNA (15 Haziran) kadar bitirebilir mi? — sınava girmeyen 9-11 için sınav tarihi anlamsız.
    Mezun (odak yok) → sınav tarihi, 9-12 tüm konular.
    Hız = son 14 günde işlenen farklı ODAK konu sayısı / 2 (hafta) — önceki sınıflardan verilen
    konular hızı şişirmez. Eşikler: %90 tahmini kapsama "yetişir", %70-89 "riskli", <%70 "yetişmez".
    """
    from datetime import date

    today = date.today()
    if focus is not None:
        target = school_year_end(today)
        kind, label = "okul_yili_sonu", f"Eğitim yılı sonu ({target.day} Haziran {target.year})"
    else:
        target = student.effective_exam_date
        kind = "sinav"
        label = f"{student.effective_exam_label or 'Sınav'} ({target.strftime('%d.%m.%Y')})" if target else None
    days = max(0, (target - today).days) if target is not None else None
    tdate = target.isoformat() if target is not None else None
    if total <= 0:
        return CurriculumProjection(False, days, 0, 0.0, 0, "veri_yok", kind, tdate, label)
    remaining = max(0, total - started)
    recent = _recent_topic_ids(db, student, days=14)
    if focus_topic_ids is not None:
        recent &= focus_topic_ids
    pace = round(len(recent) / 2.0, 1)
    if days is None:
        return CurriculumProjection(
            False, None, remaining, pace, round(100 * started / total), "sinav_yok", kind, tdate, label)
    weeks = days / 7.0
    projected_started = min(total, started + pace * weeks)
    proj_pct = round(100 * projected_started / total)
    if pace <= 0 and remaining > 0:
        verdict = "yetismez"
    elif proj_pct >= 90:
        verdict = "yetisir"
    elif proj_pct >= 70:
        verdict = "risk"
    else:
        verdict = "yetismez"
    return CurriculumProjection(True, days, remaining, pace, proj_pct, verdict, kind, tdate, label)


_EXAM_SECTIONS = {
    ExamSection.TYT, ExamSection.AYT_SAY, ExamSection.AYT_EA,
    ExamSection.AYT_SOZ, ExamSection.AYT_DIL,
}


def _is_exam_subject(s: Subject) -> bool:
    """Sınav-bazlı kanonik ders mi (TYT/AYT, model-bağımsız)?"""
    return s.curriculum_model is None and s.exam_section in _EXAM_SECTIONS


def _exam_base_name(name: str) -> str:
    """'TYT Matematik' / 'AYT Matematik' → 'Matematik' (okul dersiyle eşlemek için)."""
    for pfx in ("TYT ", "AYT "):
        if name.startswith(pfx):
            return name[len(pfx):].strip()
    return name


# Okul dersi adı, sınav dersi base adıyla birebir aynı değilse köprü kur.
# (örn. okul "Türk Dili ve Edebiyatı" → sınavda "Türkçe" (TYT) / "Edebiyat" (AYT)).
_SCHOOL_EXAM_SYNONYMS: dict[str, set[str]] = {
    "Türk Dili ve Edebiyatı": {"Türkçe", "Edebiyat"},
}


# YKS alanına (track) göre AYT dersleri. TYT herkese ortaktır → burada yer almaz.
TRACK_AYT_SUBJECTS: dict[Track, set[str]] = {
    Track.SAYISAL: {
        "AYT Matematik", "AYT Geometri", "AYT Fizik", "AYT Kimya", "AYT Biyoloji",
    },
    Track.EA: {
        "AYT Matematik", "AYT Geometri", "AYT Edebiyat", "AYT Tarih", "AYT Coğrafya",
    },
    Track.SOZEL: {
        "AYT Edebiyat", "AYT Tarih", "AYT Coğrafya", "AYT Felsefe Grubu",
        "AYT Din Kültürü ve Ahlak Bilgisi",
    },
    Track.DIL: set(),  # YDT (Yabancı Dil) — sistemde ayrı ders yok
}


def exam_subject_visible_for_track(s: Subject, track: Track | None) -> bool:
    """AYT sınav dersi öğrencinin alanına (track) uygun mu?

    TYT herkese görünür. AYT yalnız alanına uygun öğrenciye. Alan bilinmiyorsa
    (track None — örn. 9-10 veya henüz seçmemiş) filtre uygulanmaz (gizleme yok).
    Sınav dersi olmayan (okul) dersler etkilenmez → True.
    """
    if not _is_exam_subject(s):
        return True
    if s.exam_section == ExamSection.TYT:
        return True  # TYT tüm alanlara ortak
    if track is None:
        return True
    return s.name in TRACK_AYT_SUBJECTS.get(track, set())


def _student_resource_subject_ids(db: Session, student: User) -> set[int]:
    """Öğrencinin kitap bölümlerinin eşli olduğu konuların ders id'leri.

    'Bu öğrencinin hangi derste GERÇEK kaynağı var?' sorusunun cevabı —
    StudentBook → Book → BookSection.topic_id → Topic.subject_id (distinct).
    """
    rows = (
        db.query(Topic.subject_id)
        .join(BookSection, BookSection.topic_id == Topic.id)
        .join(Book, Book.id == BookSection.book_id)
        .join(StudentBook, StudentBook.book_id == Book.id)
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),   # P4: arşivli kaynak sayılmaz
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def _has_exam_counterpart(s: Subject, exam_by_base: dict[str, list[Subject]]) -> bool:
    bases = {s.name} | _SCHOOL_EXAM_SYNONYMS.get(s.name, set())
    return any(exam_by_base.get(b) for b in bases)


def _student_worked_subject_ids(db: Session, student: User) -> set[int]:
    """Kitabı olmasa da çalışılan dersler: kaynaksız (konulu) görev kalemi ya da havuz kalemi."""
    from app.models.pool import PoolItem

    ids = {r[0] for r in (
        db.query(Topic.subject_id)
        .join(TaskBookItem, TaskBookItem.topic_id == Topic.id)
        .join(Task, Task.id == TaskBookItem.task_id)
        .filter(Task.student_id == student.id, TaskBookItem.book_id.is_(None))
        .distinct().all()
    )}
    ids |= {r[0] for r in (
        db.query(PoolItem.subject_id)
        .filter(PoolItem.student_id == student.id, PoolItem.removed_at.is_(None),
                PoolItem.subject_id.isnot(None))
        .distinct().all()
    )}
    return ids


def _applicable_subjects(db: Session, student: User, coach_id: int) -> list[Subject]:
    """Öğrencinin müfredat dersleri (resmi/koç) — grade + curriculum_model filtreli.

    SINAV OMURGASI (TYT/AYT) YALNIZ 11-12 VE MEZUNDA tercih edilir. Orada dedup
    **kaynak-duyarlı**: öğrencinin kitapları OKUL (Maarif/Klasik) konularına
    eşliyken sınav dersinde hiç kaynağı yoksa okul dersi GÖRÜNÜR kalır; aksi
    halde sınav omurgası kazanır.

    9-10. SINIF (Maarif) FARKLI (saha 2026-09-04): bu öğrenci TYT/AYT değil,
    OKUL müfredatını takip eder → okul dersleri DAİMA görünür, TYT/AYT dersleri
    ancak koç o derse KAYNAK atadıysa listelenir (erken YKS hazırlığı).
    Önceki sürümde `is_yks = grade >= 9` olduğu için 8'den 9'a geçen öğrencinin
    (kitapları hâlâ LGS → Maarif derslerinde kaynak yok) müfredat paneli
    Maarif konuları yerine TYT konularını gösteriyordu.

    5-8 (LGS): dedup yok — okul dersleri olduğu gibi."""
    student_cm = student.effective_curriculum_model
    rows = (
        db.query(Subject)
        .filter(or_(Subject.is_builtin.is_(True), Subject.teacher_id == coach_id))
        .order_by(Subject.order, Subject.name)
        .all()
    )
    # Aday geç: grade + model filtresi + AYT alan (track) filtresi
    candidates = [
        s for s in rows
        if s.covers_grade(student.grade_level, is_graduate=student.is_graduate)
        and not (student_cm and s.curriculum_model and s.curriculum_model != student_cm)
        and exam_subject_visible_for_track(s, student.track)
    ]
    # Sınav omurgası (TYT/AYT) tercihi YALNIZ Klasik 11-12 + mezunda. MAARIF 11 (2026-2027'de
    # 9-10-11 Maarif, yalnız 12 Klasik — saha 2026-10-13 #415) okul omurgasını izler: 9-10 ile
    # aynı kural. Eskiden 11 her modelde sınav omurgasındaydı → Maarif 11 öğrencisine Maarif
    # Fizik yerine klasik içerikli AYT Fizik konuları sunuluyordu.
    maarif = student_cm == CurriculumModel.MAARIF_LISE
    exam_backbone = bool(student.is_graduate) or (
        student.grade_level is not None and student.grade_level >= 11 and not maarif
    )
    # 9-10 (+ Maarif 11): okul omurgası esas; sınav dersi yalnız KAYNAKLIYSA görünür.
    early_yks = (not exam_backbone) and student.grade_level in (9, 10, 11)
    resource_ids = (
        _student_resource_subject_ids(db, student)
        if (exam_backbone or early_yks)
        else set()
    )
    # base ad → sınav dersleri (TYT Matematik + AYT Matematik → "Matematik")
    exam_by_base: dict[str, list[Subject]] = {}
    if exam_backbone:
        for s in candidates:
            if _is_exam_subject(s):
                exam_by_base.setdefault(_exam_base_name(s.name), []).append(s)
    worked_ids = _student_worked_subject_ids(db, student) if exam_backbone else set()
    # kaynağı olan OKUL dersleri (sınav karşılığının gizlenip gizlenmeyeceği için)
    school_names_with_res = {
        s.name for s in candidates
        if not _is_exam_subject(s) and s.id in resource_ids
    } if exam_backbone else set()

    out: list[Subject] = []
    seen: set[str] = set()
    for s in candidates:
        # MEZUN (saha 2026-09-27, Emir #113): mezunun okul müfredatı yok, yalnız
        # YKS. Müfredat modeli boş olduğundan okul dersleri model filtresine
        # takılmıyordu; TYT/AYT karşılığı olmayan İngilizce / İnkılap Tarihi gibi
        # okul dersleri "0/51" diye listeleniyordu. Mezunda okul dersi YALNIZ
        # koç o derse kaynak atadıysa görünür.
        if student.is_graduate and not _is_exam_subject(s) and s.id not in resource_ids:
            continue
        # KLASİK 11-12 (2026-10-14, #414): sınav omurgasında YKS karşılığı OLMAYAN okul dersi
        # (T.C. İnkılap Tarihi, İngilizce…) yalnız kaynak atandıysa ya da çalışıldıysa görünür —
        # havuz ders seçicisi (`pool._klasik_exam_scheme`) ile aynı kural. Önceden 12 Sayısal
        # öğrencinin müfredatında "İnkılap 0/8" duruyordu.
        if (exam_backbone and not student.is_graduate and not _is_exam_subject(s)
                and s.id not in resource_ids and s.id not in worked_ids
                and not _has_exam_counterpart(s, exam_by_base)):
            continue
        if early_yks:
            # 9-10 / Maarif 11: okul dersi daima kalır, sınav dersi kaynak ister.
            if _is_exam_subject(s) and s.id not in resource_ids:
                continue
        elif exam_backbone:
            if _is_exam_subject(s):
                # Kaynaksız sınav dersi, kaynaklı okul karşılığı varsa gizlenir
                base = _exam_base_name(s.name)
                school_matches = {base} | {
                    sch for sch, syns in _SCHOOL_EXAM_SYNONYMS.items() if base in syns
                }
                if s.id not in resource_ids and (school_matches & school_names_with_res):
                    continue
            else:
                # Okul dersinin sınav karşılıkları (ad + eşanlam köprüsü)
                bases = {s.name} | _SCHOOL_EXAM_SYNONYMS.get(s.name, set())
                exam_counterparts = [e for b in bases for e in exam_by_base.get(b, [])]
                if exam_counterparts:
                    exam_has_res = any(e.id in resource_ids for e in exam_counterparts)
                    school_has_res = s.id in resource_ids
                    # Sınav dersi kaynaklı VEYA okul dersi de kaynaksız → sınav
                    # omurgası tercih (okul dersini gizle — eski davranış).
                    # Yalnız "okul kaynaklı + sınav kaynaksız" durumunda okul kalır.
                    if exam_has_res or not school_has_res:
                        continue
        if s.name in seen:  # aynı ad farklı modelden tekille (ilk geçen kalır)
            continue
        seen.add(s.name)
        out.append(s)
    return out


@dataclass
class LeafTopicSet:
    """Öğrencinin göreceği LEAF konular (ders bazında) + tema/ünite adları."""
    by_subject: dict[int, list[Topic]]
    parent_names: dict[int, str]


def leaf_topics_for_student(
    db: Session, student: User, coach_id: int, subject_ids: list[int],
) -> LeafTopicSet:
    """TEK MERKEZ (2026-09-08): müfredat sekmesi, hafta paneli (topic_board) ve
    görev kutusu (task_picker) AYNI konu kümesini görsün.
      · builtin VEYA koçun kendi konusu
      · yalnız LEAF (çocuğu olan tema/ünite başlığı gruplamadır)
      · sınıf filtresi kümülatif: grade_level <= öğrencinin sınıfı (mezun/bilinmeyen → hepsi)
      · sıra: Topic.order, id
    Daha önce topic_board ve task_picker sınıf filtresini UYGULAMIYORDU → 9-10.
    sınıf Maarif öğrencisinde hafta paneli 11-12 konularını da listeliyordu,
    sekme listelemiyordu — iki yüzey çelişiyordu.
    """
    if not subject_ids:
        return LeafTopicSet({}, {})
    all_topics = (
        db.query(Topic)
        .filter(
            Topic.subject_id.in_(subject_ids),
            or_(Topic.is_builtin.is_(True), Topic.teacher_id == coach_id),
        )
        .order_by(Topic.subject_id, Topic.order, Topic.id)
        .all()
    )
    max_grade = (
        99 if (student.is_graduate or student.grade_level is None) else student.grade_level
    )
    has_children = {t.parent_id for t in all_topics if t.parent_id is not None}
    parent_names = {t.id: t.name for t in all_topics if t.id in has_children}
    by_subject: dict[int, list[Topic]] = {}
    for t in all_topics:
        if t.id in has_children:
            continue
        if t.grade_level is not None and t.grade_level > max_grade:
            continue
        by_subject.setdefault(t.subject_id, []).append(t)
    return LeafTopicSet(by_subject, parent_names)


def compute_curriculum_progress(
    db: Session, student: User, coach_id: int,
) -> CurriculumProgress:
    # 1) Öğrencinin section ilerlemesi: topic_id bazında agregat + müfredat-dışı ekstra
    rows = (
        db.query(
            BookSection.id.label("section_id"),
            BookSection.topic_id.label("topic_id"),
            BookSection.label.label("label"),
            BookSection.test_count.label("test_count"),
            Book.subject_id.label("subject_id"),
            Book.id.label("book_id"),
            Book.type.label("book_type"),
            Book.name.label("book_name"),
            func.coalesce(SectionProgress.completed_count, 0).label("completed"),
            func.coalesce(SectionProgress.reserved_count, 0).label("reserved"),
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(
            StudentBook.student_id == student.id,
            StudentBook.archived_at.is_(None),   # P4: arşivli kitap kapsamaya girmez
        )
        .all()
    )

    # KAYNAKSIZ GÖREVLER (2026-09-07): kitapsız ama konuya bağlı kalemler.
    # Koç kitap seçmeden müfredattan konu verdiğinde de o konu "işlenmiş"
    # sayılmalı — yoksa kaynaksız çalışılan konu panelde "kaynak yok" görünür
    # ve koçun kafası karışır.
    sourceless_rows = (
        db.query(
            TaskBookItem.topic_id.label("topic_id"),
            func.coalesce(func.sum(TaskBookItem.planned_count), 0).label("planned"),
            func.coalesce(func.sum(TaskBookItem.completed_count), 0).label("completed"),
        )
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .filter(
            Task.student_id == student.id,
            Task.is_draft.is_(False),
            TaskBookItem.book_id.is_(None),
            TaskBookItem.topic_id.isnot(None),
            or_(TaskBookItem.unit.is_(None), TaskBookItem.unit == "test"),
        )
        .group_by(TaskBookItem.topic_id)
        .all()
    )
    # Soru/sayfa birimli kaynaksız kalemler (2026-10-22): test sayısına girmez ama
    # konuyu "çalışıldı/planlandı" yapar.
    nt_worked, nt_planned = non_test_sourceless_signals(db, student.id)
    sourceless: dict[int, dict] = {
        r.topic_id: {"planned": int(r.planned or 0), "completed": int(r.completed or 0)}
        for r in sourceless_rows
    }
    # HAVUZ (2026-10-13): seansta işaretlenen kaynaksız birim = kaynaksız çalışma; açık dönemde bekleyen
    # kalem = "planlandı". Gün-gün öğrencide ikisi de boş.
    from app.services.pool_mode import topic_pool_signals
    pool_sig = topic_pool_signals(db, student.id)
    for tid, n in pool_sig.session_marked.items():
        sourceless.setdefault(tid, {"planned": 0, "completed": 0})["completed"] += n
    # Koçun kapattığı konular — durum hesabının en üst otoritesi
    closures = topic_closure.closure_map(db, student.id)

    # topic_id → agregat (test/completed/reserved)
    by_topic: dict[int, dict] = {}
    book_names: dict[int, str] = {}
    extras: list[ExtraSection] = []
    subj_name_cache: dict[int, str] = {}
    for r in rows:
        if r.topic_id is not None:
            agg = by_topic.setdefault(
                r.topic_id, {"test": 0, "completed": 0, "reserved": 0, "books": {}})
            add_book_progress(agg["books"], r.book_id, r.book_type,
                              r.completed, r.test_count)
            book_names[r.book_id] = r.book_name
            agg["test"] += int(r.test_count or 0)
            agg["completed"] += int(r.completed or 0)
            agg["reserved"] += int(r.reserved or 0)
        else:
            # eşleşmemiş ünite → ekstra (yalnız test_count>0 anlamlı)
            extras.append(ExtraSection(
                section_id=r.section_id, label=r.label, book_name=r.book_name,
                subject_name=None, test_total=int(r.test_count or 0),
                completed=int(r.completed or 0),
            ))

    # 2) Uygulanabilir dersler + sıralı konular
    subjects = _applicable_subjects(db, student, coach_id)
    subj_ids = [s.id for s in subjects]
    subj_name_cache = {s.id: s.name for s in subjects}
    leaf_set = leaf_topics_for_student(db, student, coach_id, subj_ids)

    # 3) Ders bazında topic durumları
    out_subjects: list[SubjectProgress] = []
    g_total = g_started = 0
    c_total = c_started = 0
    focus = focus_grade_for(student)
    by_grade: dict[int | None, list[int]] = {}   # grade → [total, started, completed]
    focus_ids: set[int] = set()
    for s in subjects:
        # Tema/ünite (parent) topic'leri yalnız GRUPLAMA içindir; "konu" sayımı +
        # durum yalnız LEAF (alt başlık) üzerinden; sınıf filtresi kümülatif —
        # hepsi leaf_topics_for_student'ta (topic_board/task_picker ile ortak).
        topics = leaf_set.by_subject.get(s.id, [])
        if not topics:
            continue
        parent_name_by_id = leaf_set.parent_names
        tps: list[TopicProgress] = []
        started = completed_topics = no_res = 0
        p_total = p_started = p_completed = 0
        last_name: str | None = None
        next_name: str | None = None
        for t in topics:
            in_focus = topic_in_focus_for(t, s, focus)
            agg = by_topic.get(t.id)
            has_res = agg is not None
            test_total = agg["test"] if agg else 0
            comp = agg["completed"] if agg else 0
            resv = agg["reserved"] if agg else 0
            sl = sourceless.get(t.id) or {"planned": 0, "completed": 0}
            closure = closures.get(t.id)
            is_closed = closure is not None
            st = _status(
                has_res, comp, resv, test_total,
                closed=is_closed,
                sourceless_completed=sl["completed"] or (1 if t.id in nt_worked else 0),
                sourceless_planned=sl["planned"] or (1 if t.id in nt_planned else 0),
                sources_complete=agg_complete(agg),
                pool_planned=pool_sig.planned.get(t.id, 0),
            )
            if is_closed:
                pct = 100  # koç kapattı → konu bitti (kitapta test kalmış olabilir)
            elif test_total > 0:
                pct = min(100, round(100 * comp / test_total))
            else:
                pct = 0
            tps.append(TopicProgress(
                topic_id=t.id, name=t.name, order=t.order, has_resource=has_res,
                test_total=test_total, completed=comp, reserved=resv, status=st, pct=pct,
                unit_name=parent_name_by_id.get(t.parent_id) if t.parent_id else None,
                grade_level=t.grade_level,
                closed=is_closed,
                closed_at=(closure.closed_at.isoformat() if closure and closure.closed_at else None),
                sourceless_completed=sl["completed"],
                pool_remaining=pool_sig.planned.get(t.id, 0),
                pool_marked=pool_sig.session_marked.get(t.id, 0),
                in_focus=in_focus,
                sources=sorted(
                    (
                        (book_names.get(bid, "—"), c, tt)
                        for bid, (c, tt) in (agg["books"] if agg else {}).items()
                        if tt > 0
                    ),
                    key=lambda x: (-(x[1] / x[2]), x[0]),
                ),
            ))
            # "İşlendi" sayımı kaynaklı çözümü de kaynaksız çalışmayı da kapsar;
            # kapatılan konu her hâlde işlenmiş sayılır.
            is_started = comp > 0 or sl["completed"] > 0 or is_closed
            is_done = st == "tamamlandi"
            gb = by_grade.setdefault(t.grade_level, [0, 0, 0])
            gb[0] += 1
            gb[1] += int(is_started)
            gb[2] += int(is_done)
            c_total += 1
            c_started += int(is_started)
            if in_focus:
                focus_ids.add(t.id)
            if not in_focus:
                p_total += 1
                p_started += int(is_started)
                p_completed += int(is_done)
                continue
            if not has_res:
                no_res += 1
            if is_started:
                started += 1
                last_name = t.name  # order'lı → en son işlenen
            if is_done:
                completed_topics += 1
            # Sıradaki = kapatılmamış + hiç dokunulmamış ilk kaynaklı konu (odak sınıfta)
            if (
                next_name is None and has_res and comp <= 0
                and not is_closed and sl["completed"] <= 0
            ):
                next_name = t.name
        total = len(topics) - p_total
        cov = round(100 * started / total) if total else 0
        out_subjects.append(SubjectProgress(
            subject_id=s.id, name=s.name, order=s.order, total_topics=total,
            started_topics=started, completed_topics=completed_topics,
            no_resource_topics=no_res, coverage_pct=cov,
            last_topic_name=last_name, next_topic_name=next_name, topics=tps,
            pool_remaining=sum(tp.pool_remaining for tp in tps),
            prior_total_topics=p_total,
            prior_started_topics=p_started,
            prior_completed_topics=p_completed,
        ))
        g_total += total
        g_started += started

    # ekstra section'lara ders adı (book.subject_id → cache) — best effort
    if extras:
        # subject adlarını topla (müfredat dışı dersler dahil)
        extra_subj_ids = {r.subject_id for r in rows if r.topic_id is None}
        missing = [sid for sid in extra_subj_ids if sid not in subj_name_cache]
        if missing:
            for sid, nm in db.query(Subject.id, Subject.name).filter(Subject.id.in_(missing)).all():
                subj_name_cache[sid] = nm
        row_subj = {r.section_id: r.subject_id for r in rows if r.topic_id is None}
        for ex in extras:
            ex.subject_name = subj_name_cache.get(row_subj.get(ex.section_id))

    # Projeksiyon ODAK sınıfın konularıyla, hedef eğitim yılı sonu; mezunda tüm konular + sınav.
    projection = _compute_projection(db, student, g_total, g_started,
                                     focus_topic_ids=(focus_ids if focus is not None else None), focus=focus)
    grades = [
        GradeCoverage(
            grade=g, total_topics=v[0], started_topics=v[1], completed_topics=v[2],
            coverage_pct=round(100 * v[1] / v[0]) if v[0] else 0,
            is_focus=(focus is not None and topic_in_focus(g, focus)),
        )
        for g, v in sorted(by_grade.items(), key=lambda kv: (kv[0] is None, kv[0] or 0))
    ]

    program_mode = getattr(student, "program_mode", None) or "gun_gun"
    pool_period_id: int | None = None
    pool_unlinked: list[PoolUnlinkedItem] = []
    if program_mode == "havuz":
        from app.services.pool_mode import get_open_period

        op = get_open_period(db, student.id)
        if op is not None:
            pool_period_id = op.id
            for it in op.items:
                if it.removed_at is not None or not it.counts_toward_pool:
                    continue
                if it.topic_id or (it.section is not None and it.section.topic_id):
                    continue
                pool_unlinked.append(PoolUnlinkedItem(
                    item_id=it.id,
                    subject_name=(it.subject.name if it.subject is not None else "—"),
                    title=(it.label or (it.section.label if it.section is not None else None)
                           or (it.book.name if it.book is not None else "—")),
                    quantity=int(it.quantity or 0), done=int(it.done_units or 0),
                ))

    return CurriculumProgress(
        curriculum_model=(student.effective_curriculum_model.value
                          if student.effective_curriculum_model else None),
        grade_level=student.grade_level,
        overall_total_topics=g_total,
        overall_started_topics=g_started,
        overall_coverage_pct=round(100 * g_started / g_total) if g_total else 0,
        subjects=out_subjects,
        extras=extras,
        projection=projection,
        program_mode=program_mode,
        pool_period_id=pool_period_id,
        pool_unlinked=pool_unlinked,
        focus_grade=focus,
        cumulative_total_topics=c_total,
        cumulative_started_topics=c_started,
        cumulative_coverage_pct=round(100 * c_started / c_total) if c_total else 0,
        grades=grades,
    )


# ============================================================================
# Faz 2 — Sıradaki üniteler (atanabilir) + AI akıllı öncelik
# ============================================================================


@dataclass
class AssignableSection:
    book_id: int
    section_id: int
    book_name: str
    section_label: str
    test_total: int
    completed: int
    reserved: int
    remaining: int        # test_total - reserved - completed (atanabilir kapasite)


@dataclass
class NextUnit:
    subject_id: int
    subject_name: str
    topic_id: int
    topic_name: str
    order: int
    status: str           # baslanmadi | planlandi | devam
    completed: int
    test_total: int
    sections: list[AssignableSection] = field(default_factory=list)


def next_units_for_assignment(
    db: Session, student: User, coach_id: int, *, per_subject: int = 2,
) -> list[NextUnit]:
    """Her ders için SIRADAKİ atanabilir üniteler (resmi sırada, tamamlanmamış,
    kaynaklı). Her ünitenin atanabilir section'ları (kalan kapasiteli) döner →
    koç tek tıkla görev üretebilir. tamamlanmış/kaynaksız konular atlanır."""
    rows = (
        db.query(
            BookSection.id.label("section_id"),
            BookSection.topic_id.label("topic_id"),
            BookSection.label.label("label"),
            BookSection.test_count.label("test_count"),
            Book.id.label("book_id"),
            Book.type.label("book_type"),
            Book.name.label("book_name"),
            func.coalesce(SectionProgress.completed_count, 0).label("completed"),
            func.coalesce(SectionProgress.reserved_count, 0).label("reserved"),
        )
        .select_from(StudentBook)
        .join(Book, Book.id == StudentBook.book_id)
        .join(BookSection, BookSection.book_id == Book.id)
        .outerjoin(
            SectionProgress,
            and_(
                SectionProgress.student_book_id == StudentBook.id,
                SectionProgress.book_section_id == BookSection.id,
            ),
        )
        .filter(StudentBook.student_id == student.id,
                StudentBook.archived_at.is_(None),   # P4
                BookSection.topic_id.isnot(None))
        .all()
    )
    # topic_id → sections + agg
    by_topic_secs: dict[int, list] = {}
    by_topic_agg: dict[int, dict] = {}
    for r in rows:
        by_topic_secs.setdefault(r.topic_id, []).append(r)
        agg = by_topic_agg.setdefault(r.topic_id, {"test": 0, "completed": 0, "books": {}})
        add_book_progress(agg["books"], r.book_id, r.book_type, r.completed, r.test_count)
        agg["test"] += int(r.test_count or 0)
        agg["completed"] += int(r.completed or 0)

    # Koçun kapattığı konular ARTIK ÖNERİLMEZ (2026-09-07): koç görüşmede
    # "bitti" dediyse panel onu "sıradaki ünite" diye tekrar önermemeli —
    # yoksa kapatma kararı bir yüzeyde geçerli, diğerinde yok sayılmış olur.
    closed_ids = topic_closure.closed_topic_ids(db, student.id)

    subjects = _applicable_subjects(db, student, coach_id)
    subj_ids = [s.id for s in subjects]
    topics_by_subject: dict[int, list[Topic]] = {}
    if subj_ids:
        for t in (
            db.query(Topic)
            .filter(Topic.subject_id.in_(subj_ids),
                    or_(Topic.is_builtin.is_(True), Topic.teacher_id == coach_id))
            .order_by(Topic.order, Topic.id).all()
        ):
            topics_by_subject.setdefault(t.subject_id, []).append(t)

    out: list[NextUnit] = []
    for s in subjects:
        picked = 0
        for t in topics_by_subject.get(s.id, []):
            if picked >= per_subject:
                break
            if t.id in closed_ids:
                continue  # koç kapattı → atla
            agg = by_topic_agg.get(t.id)
            if agg is None:
                continue  # kaynak yok → atla
            comp = agg["completed"]
            test_total = agg["test"]
            if agg_complete(agg):
                continue  # tamamlanmış (kaynak kuralı) → atla
            # atanabilir section'lar (kalan kapasiteli)
            secs: list[AssignableSection] = []
            for r in by_topic_secs.get(t.id, []):
                rem = max(0, int(r.test_count or 0) - int(r.reserved or 0) - int(r.completed or 0))
                secs.append(AssignableSection(
                    book_id=r.book_id, section_id=r.section_id, book_name=r.book_name,
                    section_label=r.label, test_total=int(r.test_count or 0),
                    completed=int(r.completed or 0), reserved=int(r.reserved or 0),
                    remaining=rem,
                ))
            status = "devam" if comp > 0 else "baslanmadi"
            out.append(NextUnit(
                subject_id=s.id, subject_name=s.name, topic_id=t.id, topic_name=t.name,
                order=t.order, status=status, completed=comp, test_total=test_total,
                sections=secs,
            ))
            picked += 1
    return out


# ----------------------------- AI akıllı öncelik -----------------------------

class AIUnavailable(Exception):
    pass


def _parse_json(raw: str) -> dict:
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def ai_prioritize_units(
    units: list[NextUnit],
    *,
    exam_label: str | None,
    days_to_exam: int | None,
    weak_topics: list[str],
) -> dict:
    """Gemini ile sıradaki üniteleri akıllı önceliklendir (öğrenci verili → ÜCRETLİ key).

    Girdi: deterministik sıradaki üniteler + sınav yakınlığı + zayıf konular (doğruluk).
    Çıktı: {"summary": str, "priorities": {topic_id: (priority:int, reason:str)}}.
    Öneri: resmi sıra + öğrencinin zayıf olduğu/yarım kalan + sınav yakınlığı dengesi.
    """
    from app.services import gemini

    if not units:
        return {"summary": None, "priorities": {}}
    unit_lines = "\n".join(
        f"{u.topic_id}: {u.subject_name} — {u.topic_name} "
        f"(durum: {u.status}, {u.completed}/{u.test_total} test)"
        for u in units
    )
    weak = ", ".join(weak_topics[:12]) if weak_topics else "—"
    exam_ctx = (
        f"Sınav: {exam_label or 'belirsiz'}"
        + (f", {days_to_exam} gün kaldı" if days_to_exam is not None else "")
    )
    prompt = (
        "Bir koçun öğrencisine bu hafta atayabileceği SIRADAKİ müfredat üniteleri "
        "aşağıda. Resmi müfredat sırası + öğrencinin ZAYIF olduğu konular + yarım "
        "kalanlar + sınav yakınlığını dengeleyerek ÖNCELİK sırası öner (1 = en öncelikli). "
        "Her ünite için kısa, somut gerekçe (Türkçe, 1 cümle). Klinik dil değil koçluk dili.\n\n"
        f"{exam_ctx}\n"
        f"Öğrencinin doğruluğu düşük (zayıf) konular: {weak}\n\n"
        f"SIRADAKİ ÜNİTELER (topic_id: ders — konu):\n{unit_lines}\n\n"
        'Yalnız JSON: {"summary":"1-2 cümle genel öncelik mantığı",'
        '"priorities":[{"topic_id":N,"priority":1,"reason":"..."}]}'
    )
    try:
        raw = gemini.generate(
            [gemini.text_part(prompt)],
            personal_data=True, json_mode=True, max_output_tokens=8192,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_prioritize_units gemini fail: %s", e)
        raise AIUnavailable(str(e))
    data = _parse_json(raw)
    valid = {u.topic_id for u in units}
    pri: dict[int, tuple[int, str]] = {}
    for p in (data.get("priorities") or []):
        try:  # Gemini kimliği bazen metin döndürür — sayıya çevir
            tid = int(p.get("topic_id"))
        except (TypeError, ValueError):
            continue
        if tid in valid:
            pri[int(tid)] = (int(p.get("priority") or 99), str(p.get("reason") or "").strip())
    return {"summary": str(data.get("summary") or "").strip() or None, "priorities": pri}


# ----------------------- Faz 3: son dönemde işlenen üniteler ------------------

@dataclass
class CoveredUnit:
    subject_name: str
    topic_name: str
    tests_completed: int


def recently_covered_units(
    db: Session, student: User, *, days: int = 7,
) -> list[CoveredUnit]:
    """Son `days` günde İŞLENEN müfredat üniteleri (seans 'geçen hafta' analizi).

    Task.date penceresi + tamamlanan (completed_count>0) section kalemleri →
    topic'e eşli olanlar → ders+konu bazında çözülen test toplamı. En çok çözülen üstte.
    """
    from datetime import date, timedelta

    from app.models import Task, TaskBookItem

    start = date.today() - timedelta(days=days)
    rows = (
        db.query(
            Subject.name.label("subject_name"),
            Topic.name.label("topic_name"),
            # soru/sayfa birimli kalem konuyu işler ama test sayılmaz (2026-10-22)
            func.sum(case((or_(TaskBookItem.unit.is_(None), TaskBookItem.unit == "test"),
                           TaskBookItem.completed_count), else_=0)).label("tests"),
        )
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(BookSection, BookSection.id == TaskBookItem.book_section_id)
        .join(Topic, Topic.id == BookSection.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .filter(
            Task.student_id == student.id,
            Task.date >= start,
            TaskBookItem.completed_count > 0,
        )
        .group_by(Subject.name, Topic.name)
        .all()
    )
    # KAYNAKSIZ KONULU kalemler (2026-10-15): kitapsız ama konusu olan görev (havuz / müfredattan
    # verilen) de konuyu işler — konu/hafta hızına ve seans "geçen hafta" listesine girmeli.
    sourceless = (
        db.query(
            Subject.name.label("subject_name"),
            Topic.name.label("topic_name"),
            func.sum(TaskBookItem.completed_count).label("tests"),
        )
        .select_from(Task)
        .join(TaskBookItem, TaskBookItem.task_id == Task.id)
        .join(Topic, Topic.id == TaskBookItem.topic_id)
        .join(Subject, Subject.id == Topic.subject_id)
        .filter(
            Task.student_id == student.id,
            Task.date >= start,
            TaskBookItem.book_id.is_(None),
            TaskBookItem.completed_count > 0,
        )
        .group_by(Subject.name, Topic.name)
        .all()
    )
    agg: dict[tuple[str, str], int] = {}
    for r in list(rows) + list(sourceless):
        k = (r.subject_name, r.topic_name)
        agg[k] = agg.get(k, 0) + int(r.tests or 0)
    return [
        CoveredUnit(subject_name=k[0], topic_name=k[1], tests_completed=v)
        for k, v in sorted(agg.items(), key=lambda kv: -kv[1])
    ]
