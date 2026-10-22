"""Haftalık görev havuzu modu — TEK MERKEZ (2026-10-12, tasarım K1–K61).

Bu dosya havuz modunun bütün yazma kurallarını toplar; uçlar ve ekranlar yalnız
buradan çağırır. Gün-gün program kodu (teacher.py görev oluşturma, iskelet,
devret, rezerv) buraya DOKUNMAZ; kap görevi mevcut Task modeline yazılır ki
bugün/hafta ekranları, D/Y/B girişi, görev-test-deneme sayımı ve veli görünümü
değişmeden çalışsın.

Kurallar (kısa):
  K6/K8/K23  dönem = seans → seans; beklenen gün çakılı değil; seans gelmezse dönem uzar
  K13/K14    kalem çekirdeği ders+miktar+birim; kaynak/konu isteğe bağlı
  K16        test/soru/sayfa/deneme kaleminde miktar zorunlu; yalnız etkinlik miktarsız (1)
  K25        11-12/mezunda alan boşsa AYT kalemi EKLENEMEZ (önce alan)
  K34/K36    kap = o güne görev; kısmi tamamlama serbest; yapılmayan gün sonu havuza döner
  K38        öğrencinin eklediği kalem onay bekler; onaysız yüzdeye/tempoya girmez
  K42        tempo birimi: test kalemi test sayısı; etkinlik/deneme/video 1 birim
  K44/K58    kap denemesi ve devir sayaçları (kaçınma sinyali Basamak 6'da okur)
  havuz      REZERV YOK — kap görevinin kitaplı kalemi released doğar
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Book, BookSection, StudentBook, Subject, Task, TaskBookItem, TaskStatus, TaskType, Topic, User,
)
from app.models.curriculum import ExamSection
from app.models.pool import (
    APPROVAL_APPROVED, APPROVAL_NA, APPROVAL_PENDING, APPROVAL_REJECTED,
    CARRY_AVOID_THRESHOLD, CUP_AVOID_THRESHOLD, LATE_ENTRY_DAYS,
    PERIOD_BREAK, PERIOD_CLOSED, PERIOD_CLOSED_NO_SESSION, PERIOD_OPEN, PERIOD_STATUSES,
    POOL_SOURCES, POOL_UNITS, PROGRAM_MODE_GUN_GUN, PROGRAM_MODE_HAVUZ, PROGRAM_MODES,
    SOURCE_CARRY, SOURCE_COACH, SOURCE_STUDENT, TOPIC_REQUIRED_EXEMPT_SOURCES, TOPIC_REQUIRED_UNITS,
    UNIT_DENEME, UNIT_ETKINLIK, UNIT_SAYFA, UNIT_SORU, UNIT_TEST,
    ClassGroup, PoolItem, StudyPeriod,
)
from app.services import task_titles

_AYT_SECTIONS = {ExamSection.AYT_SAY, ExamSection.AYT_EA, ExamSection.AYT_SOZ, ExamSection.AYT_DIL}


class PoolError(ValueError):
    """Kullanıcıya gösterilebilir havuz hatası (code + sade mesaj)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message



def tr_date(value) -> date | None:
    """DB zaman damgasını (UTC; SQLite'ta naive) Türkiye gününe çevirir (TR sabit UTC+3).
    Gece 00:00–03:00 arası eklenen kalem "dün" görünmesin diye "SON" tarihleri bununla hesaplanır."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return (value.astimezone(timezone.utc) + timedelta(hours=3)).date()

def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- mod

def mode_of(user: User) -> str:
    return getattr(user, "program_mode", None) or PROGRAM_MODE_GUN_GUN


def is_havuz(user: User) -> bool:
    return mode_of(user) == PROGRAM_MODE_HAVUZ


def havuz_student_ids(db: Session, student_ids: list[int]) -> set[int]:
    """Verilen öğrencilerden havuz modunda olanlar (paylaşılan servisler için)."""
    if not student_ids:
        return set()
    rows = (db.query(User.id)
            .filter(User.id.in_(student_ids), User.program_mode == PROGRAM_MODE_HAVUZ)
            .all())
    return {int(r[0]) for r in rows}


def set_program_mode(db: Session, student: User, mode: str) -> User:
    """Öğrencinin program modunu değiştirir. Açık dönem varken DEĞİŞMEZ (Basamak 9)."""
    if mode not in PROGRAM_MODES:
        raise PoolError("bad_mode", "Geçersiz program modu.")
    if mode_of(student) == mode:
        return student
    if get_open_period(db, student.id) is not None:
        raise PoolError("open_period", "Açık bir dönem varken mod değiştirilemez; önce dönemi kapat.")
    student.program_mode = mode
    db.flush()
    return student


# ---------------------------------------------------------------- dönem

def get_open_period(db: Session, student_id: int) -> StudyPeriod | None:
    return (db.query(StudyPeriod)
            .filter(StudyPeriod.student_id == student_id, StudyPeriod.status == PERIOD_OPEN)
            .order_by(StudyPeriod.opened_on.desc(), StudyPeriod.id.desc())
            .first())


def list_periods(db: Session, student_id: int, limit: int | None = None) -> list[StudyPeriod]:
    q = (db.query(StudyPeriod).filter(StudyPeriod.student_id == student_id)
         .order_by(StudyPeriod.opened_on.desc(), StudyPeriod.id.desc()))
    if limit:
        q = q.limit(limit)
    return q.all()


def open_period(
    db: Session, *, student: User, coach: User | None, opened_on: date,
    session_id: int | None = None, expected_next_on: date | None = None, note: str | None = None,
    carry: list[tuple[int, int | None]] | None = None,
) -> StudyPeriod:
    """Seans günü yeni dönem açar (K6). Öğrenci havuz modunda olmalı, açık dönem olmamalı.
    `carry` (Adım 6, K22/K58): son kapanmış dönemin kalan kalemlerinden seçilenler kalem kalem
    devredilir (aradan dönüş dahil); listede olmayan kalem → carry_not_leftover, hiçbir şey yazılmaz."""
    if not is_havuz(student):
        raise PoolError("not_havuz", "Öğrenci haftalık havuz modunda değil.")
    if get_open_period(db, student.id) is not None:
        raise PoolError("already_open", "Bu öğrencinin açık bir dönemi var; önce onu kapat.")
    if expected_next_on is not None and expected_next_on <= opened_on:
        raise PoolError("bad_expected", "Beklenen sonraki seans günü dönem başlangıcından sonra olmalı.")
    src, cands = carry_candidates(db, student.id) if carry else (None, [])
    by_id = {it.id: it for it in cands}
    for item_id, _q in (carry or []):
        if item_id not in by_id:
            raise PoolError("carry_not_leftover", "Devredilecek kalem son dönemin kalanlarında yok.")
    p = StudyPeriod(
        student_id=student.id, coach_id=coach.id if coach else None, opened_on=opened_on,
        opened_session_id=session_id, expected_next_on=expected_next_on, status=PERIOD_OPEN,
        note=note,
    )
    db.add(p)
    db.flush()
    for item_id, qty in (carry or []):
        carry_item(db, item=by_id[item_id], target=p, student=student, coach=coach or student, quantity=qty)
    return p


def latest_closed_period(db: Session, student_id: int) -> StudyPeriod | None:
    return (db.query(StudyPeriod)
            .filter(StudyPeriod.student_id == student_id, StudyPeriod.status != PERIOD_OPEN)
            .order_by(StudyPeriod.closed_on.desc(), StudyPeriod.id.desc()).first())


def carry_candidates(db: Session, student_id: int) -> tuple[StudyPeriod | None, list[PoolItem]]:
    """Adım 6 devir ekranı: son kapanmış dönemin kalanı olan kalemleri (onaysız/reddedilmiş hariç)."""
    src = latest_closed_period(db, student_id)
    if src is None:
        return None, []
    out = []
    for it in src.items:
        if it.removed_at is not None or not it.counts_toward_pool:
            continue
        sync_item_progress(db, it)
        if it.remaining > 0:
            out.append(it)
    return src, out


def break_state(db: Session, student_id: int) -> StudyPeriod | None:
    """K61: açık dönem yok ve son dönem 'ara' kapanışıysa öğrenci tatilde (is_paused mantığı)."""
    if get_open_period(db, student_id) is not None:
        return None
    last = latest_closed_period(db, student_id)
    return last if last is not None and last.status == PERIOD_BREAK else None


def late_entry_lock(db: Session, task: Task, today: date) -> date | None:
    """K59/K15: kap görevinin dönemi kapandıysa ve kapanıştan LATE_ENTRY_DAYS gün geçtiyse
    öğrenci kaydı kilitlenir (düzeltme yalnız rehberin seans işaretiyle). Kilit tarihini döner."""
    if task.pool_item_id is None:
        return None
    it = db.get(PoolItem, task.pool_item_id)
    if it is None or it.period is None or it.period.is_open or it.period.closed_on is None:
        return None
    lock_from = it.period.closed_on + timedelta(days=LATE_ENTRY_DAYS + 1)
    return lock_from if today >= lock_from else None


def period_history(db: Session, student_id: int, *, offset: int = 0, limit: int = 20,
                   today: date | None = None) -> tuple[int, list[dict]]:
    """K60: dönem geçmişi sınırsız — sayfalı, her dönemde ders kırılımı + devir + seans işareti."""
    today = today or date.today()
    q = (db.query(StudyPeriod).filter(StudyPeriod.student_id == student_id)
         .order_by(StudyPeriod.opened_on.desc(), StudyPeriod.id.desc()))
    total = q.count()
    rows = [history_row(db, p, today) for p in q.offset(offset).limit(limit).all()]
    return total, rows


def history_row(db: Session, p: StudyPeriod, today: date) -> dict:
    """Tek dönemin geçmiş satırı (K60): özet + ders kırılımı + devir giriş/çıkış + seans işareti."""
    s = period_summary(db, p, today)
    per: dict[int, dict] = {}
    marked = 0
    carried_in = 0
    for it in p.items:
        if not it.counts_toward_pool:
            continue
        marked += int(it.session_marked or 0)
        if it.source == SOURCE_CARRY:
            carried_in += 1
        t, d = _units(it)
        r = per.setdefault(it.subject_id or 0, {"subject": it.subject.name if it.subject is not None else "Diğer",
                                                "total": 0, "done": 0})
        r["total"] += t
        r["done"] += d
    ids = [it.id for it in p.items]
    carried_out = (db.query(func.count(PoolItem.id)).filter(PoolItem.parent_item_id.in_(ids)).scalar() or 0) if ids else 0
    return {
        "id": p.id, "opened_on": p.opened_on, "closed_on": p.closed_on, "status": p.status,
        "expected_next_on": p.expected_next_on, "note": p.note,
        "total_units": s.total_units, "done_units": s.done_units, "pct": s.pct,
        "items_total": s.items_total, "items_done": s.items_done,
        "session_marked_units": marked, "carried_in": carried_in, "carried_out": int(carried_out),
        "has_session": p.closed_session_id is not None or p.opened_session_id is not None,
        "parent_summary_sent_at": p.parent_summary_sent_at,
        "subjects": [{**r, "pct": int(round(100 * r["done"] / r["total"])) if r["total"] else 0}
                     for r in sorted(per.values(), key=lambda r: r["subject"])],
    }


@dataclass
class PeriodDetail:
    """Bir dönemin tam içeriği (geçmiş dönem penceresi, 2026-10-13):
    · items      — havuz kalemleri (kaldırılanlar DAHİL; iz kalır, ekran ayırır)
    · returns    — kalem → 'kaba girip geri döndü' sayısı (K44)
    · carried_to — kalem → devredildiği sonraki dönem id'si
    · days       — açılış → kapanış (açıksa bugün) her gün + o günün kap görevleri
                   (gün sonu kapanışı ilerlemesiz kap görevini SİLDİĞİ için 'aldı ama hiç
                   dokunmadı' gün satırında görünmez; yalnız returns sayacında kalır — K34)."""
    row: dict
    items: list[PoolItem]
    returns: dict[int, int]
    carried_to: dict[int, int]
    days: list[tuple[date, list[Task]]]


def period_detail(db: Session, period: StudyPeriod, *, today: date | None = None) -> PeriodDetail:
    today = today or date.today()
    items = sorted(period.items, key=lambda it: (it.subject_id or 0, it.id))
    live = [it for it in items if it.removed_at is None]
    for it in live:
        sync_item_progress(db, it)
    returns = cup_returns(db, items)
    ids = [it.id for it in items]
    carried_to: dict[int, int] = {}
    tasks: list[Task] = []
    if ids:
        for child in db.query(PoolItem.parent_item_id, PoolItem.period_id).filter(PoolItem.parent_item_id.in_(ids)).all():
            carried_to[int(child[0])] = int(child[1])
        tasks = (db.query(Task).options(joinedload(Task.book_items))
                 .filter(Task.pool_item_id.in_(ids))
                 .order_by(Task.date, Task.order, Task.id).all())
    by_day: dict[date, list[Task]] = {}
    for t in tasks:
        by_day.setdefault(t.date, []).append(t)
    end = period.closed_on or today
    span = {period.opened_on + timedelta(days=n) for n in range(max(0, (end - period.opened_on).days) + 1)}
    days = [(d, by_day.get(d, [])) for d in sorted(span | set(by_day))]
    return PeriodDetail(row=history_row(db, period, today), items=items, returns=returns,
                        carried_to=carried_to, days=days)


@dataclass
class PeriodDeleteImpact:
    """Dönem silmenin etkisi (önizleme + silme aynı hesabı kullanır)."""
    items: int                 # canlı kalem
    removed_items: int         # rehberin önceden kaldırdığı (iz) kalem
    tasks_kept: int            # ilerlemesi olan kap görevi → KORUNUR, havuz bağı kopar
    tasks_deleted: int         # hiç dokunulmamış kap görevi → silinir
    done_units: int            # dönemde kayıtlı yapılan birim (öğrenci + seans)
    session_marked_units: int  # seans işareti (kitap sayacındaki izli kayıt kalır)
    carried_out: int           # sonraki döneme devredilmiş kalem (bağ kopar, kalem kalır)
    parent_summary_sent: bool


def _task_has_progress(t: Task) -> bool:
    if t.status == TaskStatus.COMPLETED:
        return True
    return any(int(bi.completed_count or 0) > 0 for bi in (t.book_items or []))


def period_delete_impact(db: Session, period: StudyPeriod) -> PeriodDeleteImpact:
    items = list(period.items)
    ids = [it.id for it in items]
    tasks = (db.query(Task).options(joinedload(Task.book_items)).filter(Task.pool_item_id.in_(ids)).all()
             if ids else [])
    kept = sum(1 for t in tasks if _task_has_progress(t))
    live = [it for it in items if it.removed_at is None]
    carried_out = (db.query(func.count(PoolItem.id)).filter(PoolItem.parent_item_id.in_(ids)).scalar() or 0) if ids else 0
    return PeriodDeleteImpact(
        items=len(live), removed_items=len(items) - len(live), tasks_kept=kept, tasks_deleted=len(tasks) - kept,
        done_units=sum(it.done_units for it in live if it.counts_toward_pool),
        session_marked_units=sum(int(it.session_marked or 0) for it in live),
        carried_out=int(carried_out), parent_summary_sent=period.parent_summary_sent_at is not None,
    )


def delete_period(db: Session, period: StudyPeriod) -> PeriodDeleteImpact:
    """Kapanmış dönemi siler (2026-10-13, yerel test turu).

    · AÇIK dönem silinmez (önce kapat) — öğrencinin kabı canlı havuza bağlı.
    · Kalemler (kaldırılan izler dahil) silinir.
    · Kap görevleri: öğrencinin GERÇEKTEN çalıştığı (tamamlanmış / ilerlemeli) görev KORUNUR, yalnız havuz
      bağı kopar → Bugün/hafta geçmişi ve kitap sayacı (çözülen testler) tutarlı kalır. Hiç dokunulmamış kap
      görevi silinir (rezerv tutmadığı için iade yok).
    · Sonraki döneme devredilmiş kalemlerin köken bağı (parent_item_id) kopar; kalemler yerinde kalır.
    · Seans işaretinin kitap sayacına yazdığı izli koç kaydı (self_study) dokunulmaz.
    Prod PG'de FK'lar (CASCADE / SET NULL) aynı sonucu verir; dev SQLite'ta FK kapalı olduğundan açıkça yapılır."""
    if period.is_open:
        raise PoolError("period_open", "Açık dönem silinemez; önce dönemi kapat.")
    impact = period_delete_impact(db, period)
    items = list(period.items)
    ids = [it.id for it in items]
    if ids:
        tasks = db.query(Task).options(joinedload(Task.book_items)).filter(Task.pool_item_id.in_(ids)).all()
        for t in tasks:
            if _task_has_progress(t):
                t.pool_item_id = None
            else:
                detach_task_videos(db, t.id)
                for bi in list(t.book_items or []):
                    db.delete(bi)
                db.delete(t)
        release_pool_videos(db, ids)
        from app.models.video_basket import VideoBasketItem

        db.query(VideoBasketItem).filter(VideoBasketItem.pool_item_id.in_(ids)).update(
            {VideoBasketItem.pool_item_id: None}, synchronize_session=False)
        db.query(PoolItem).filter(PoolItem.parent_item_id.in_(ids)).update(
            {PoolItem.parent_item_id: None}, synchronize_session=False)
    db.flush()
    db.delete(period)  # kalemler ilişki kademesiyle (all, delete-orphan) silinir
    db.flush()
    return impact


def close_period(
    db: Session, period: StudyPeriod, *, closed_on: date, session_id: int | None = None,
    status: str = PERIOD_CLOSED,
) -> list[PoolItem]:
    """Dönemi kapatır; kalanı olan kalemleri (devir adayları, K22) döndürür. Kalemlere dokunmaz."""
    if status not in (PERIOD_CLOSED, PERIOD_BREAK, PERIOD_CLOSED_NO_SESSION):
        raise PoolError("bad_status", "Geçersiz kapanış durumu.")
    if not period.is_open:
        raise PoolError("not_open", "Dönem zaten kapalı.")
    if closed_on < period.opened_on:
        raise PoolError("bad_close", "Kapanış günü başlangıçtan önce olamaz.")
    for it in period.items:
        sync_item_progress(db, it)
    period.closed_on = closed_on
    period.closed_session_id = session_id
    period.status = status
    db.flush()
    return [it for it in period.items if it.removed_at is None and it.remaining > 0]


def days_without_session(period: StudyPeriod, today: date) -> int:
    return max(0, (today - period.opened_on).days)


# ---------------------------------------------------------------- kalem

def _needs_track(student: User) -> bool:
    return bool(getattr(student, "is_graduate", False)) or (student.grade_level or 0) >= 11


def _check_subject_allowed(student: User, subject: Subject) -> None:
    """K25: AYT dersi, alanı boş 11-12/mezun öğrenciye eklenemez; alan doluysa alana uygun olmalı."""
    from app.services.curriculum_progress import exam_subject_visible_for_track
    if subject.exam_section in _AYT_SECTIONS and subject.curriculum_model is None:
        if student.track is None and _needs_track(student):
            raise PoolError("track_required",
                            "Alan girilmedi — AYT dersi eklemek için önce öğrencinin alanını seç.")
        if not exam_subject_visible_for_track(subject, student.track):
            raise PoolError("subject_not_in_track", "Bu AYT dersi öğrencinin alanında yok.")


def add_item(
    db: Session, *, period: StudyPeriod, student: User, subject: Subject | None,
    quantity: int | None, unit: str, topic: Topic | None = None, book: Book | None = None,
    section: BookSection | None = None, label: str | None = None, day_hint: date | None = None,
    source: str = SOURCE_COACH, created_by: User | None = None, teacher_homework: bool = False,
    exam_result_id: int | None = None, parent_item: PoolItem | None = None,
    exam_kind: str | None = None, exam_section: str | None = None,
    question_count: int | None = None,
    page_from: int | None = None, page_to: int | None = None,
) -> PoolItem:
    """Havuza kalem ekler. Rezerv AÇMAZ. Doğrulamalar K16 / K25 / kaynak sahipliği.

    Deneme kalemi (unit=deneme, D1b): quantity = deneme adedi; tür/sınav/soru verilmezse
    kitaptan ya da dersin sınav standardından doldurulur (deneme_service)."""
    if not period.is_open:
        raise PoolError("period_closed", "Kapalı döneme kalem eklenemez.")
    if unit not in POOL_UNITS:
        raise PoolError("bad_unit", "Geçersiz birim.")
    if source not in POOL_SOURCES:
        raise PoolError("bad_source", "Geçersiz kalem kaynağı.")
    if unit == UNIT_ETKINLIK:
        quantity = quantity or 1
    # Sayfa aralığı (2026-10-22): "s. 45–50" → quantity = sayfa adedi.
    if unit != UNIT_SAYFA:
        page_from = page_to = None
    elif page_from is not None or page_to is not None:
        if page_from is None or page_to is None or page_from < 1 or page_to < page_from:
            raise PoolError("invalid_page_range", "Sayfa aralığını başlangıç ≤ bitiş olacak şekilde gir (örn. 45–50).")
        quantity = page_to - page_from + 1
    if quantity is None or quantity < 1:
        raise PoolError("quantity_required", "Bu kalemde miktar zorunlu (örn. 4 test).")
    if subject is None:
        # Yalnız GENEL deneme dersiz olabilir (LGS/TYT/AYT tam deneme — D1b).
        if not (unit == UNIT_DENEME and exam_kind == "genel"):
            raise PoolError("subject_required", "Ders seçin.")
    else:
        _check_subject_allowed(student, subject)
    if topic is not None and (subject is None or topic.subject_id != subject.id):
        raise PoolError("topic_subject_mismatch", "Konu seçilen derse ait değil.")
    if section is not None:
        if book is None or section.book_id != book.id:
            raise PoolError("section_book_mismatch", "Bölüm seçilen kitaba ait değil.")
        if topic is None and section.topic_id:
            topic = db.get(Topic, section.topic_id)
    if book is not None:
        sb = (db.query(StudentBook)
              .filter(StudentBook.student_id == student.id, StudentBook.book_id == book.id,
                      StudentBook.archived_at.is_(None)).first())
        if sb is None:
            raise PoolError("book_not_assigned", "Bu kitap öğrenciye atanmış değil.")
        if book.subject_id and subject is not None and book.subject_id != subject.id:
            raise PoolError("book_subject_mismatch", "Kitap seçilen derse ait değil.")
    if (topic is None and book is None and unit in TOPIC_REQUIRED_UNITS
            and source not in TOPIC_REQUIRED_EXEMPT_SOURCES):
        raise PoolError(
            "topic_required",
            "Test ve soru kalemi bir konuya bağlanmalı — konu seç (ya da kitabından ver). "
            "Konusuz kalem konu performansına ve müfredat haritasına işlenemez; video, sayfa ya da "
            "serbest ödev için birimi Sayfa / Etkinlik yap.",
        )
    if not label and topic is None and book is None and unit != UNIT_ETKINLIK:
        # Konu da kaynak da yok: en azından ne çalışılacağı yazılmalı (K14 serbest metin)
        raise PoolError("label_required", "Konu ya da kaynak seçilmedi; ne çalışılacağını yaz.")
    if question_count is not None and not (1 <= question_count <= 200):
        raise PoolError("invalid_question_count", "Soru sayısı 1 ile 200 arasında olmalı.")
    if unit == UNIT_DENEME:
        from app.services import deneme_service as _ds

        if exam_kind is None:
            exam_kind = (_ds.EXAM_KIND_GENEL
                         if book is not None and book.type == _ds.DENEME_BOOK_TYPES[1]
                         else _ds.EXAM_KIND_BRANS)
        if exam_section is None:
            exam_section = _ds.exam_section_for_subject(book.subject if book is not None else subject)
        if question_count is None:
            question_count, _src = _ds.resolve_question_count(
                book=book, section=section, subject=(book.subject if book is not None else subject))
    approval = APPROVAL_PENDING if source == SOURCE_STUDENT else APPROVAL_NA
    it = PoolItem(
        period_id=period.id, student_id=student.id, subject_id=subject.id if subject else None,
        topic_id=topic.id if topic else None, book_id=book.id if book else None,
        book_section_id=section.id if section else None, label=(label or None),
        quantity=quantity, unit=unit, day_hint=day_hint, source=source,
        teacher_homework=teacher_homework, approval=approval,
        created_by_id=created_by.id if created_by else None, exam_result_id=exam_result_id,
        parent_item_id=parent_item.id if parent_item else None,
        carry_count=(parent_item.carry_count + 1) if parent_item else 0,
        exam_kind=exam_kind if unit == UNIT_DENEME else None,
        exam_section=exam_section if unit == UNIT_DENEME else None,
        question_count=question_count if unit == UNIT_DENEME else None,
        page_from=page_from, page_to=page_to,
    )
    db.add(it)
    db.flush()
    return it


def remove_item(db: Session, item: PoolItem, actor: User) -> PoolItem:
    """Rehber kalemi siler — iz kalır (removed_at). Kaba alınmamış videoları sepete döner."""
    item.removed_at = _now()
    item.removed_by_id = actor.id
    release_pool_videos(db, [item.id])
    db.flush()
    return item


# ---------------------------------------------------------------- video sepeti köprüsü (2026-10-20)

def pool_item_videos(db: Session, item_id: int) -> list:
    from app.models.video_basket import VideoBasketItem

    return (db.query(VideoBasketItem).filter(VideoBasketItem.pool_item_id == item_id)
            .order_by(VideoBasketItem.order, VideoBasketItem.id).all())


def release_pool_videos(db: Session, item_ids: list[int]) -> None:
    """Kalem kaldırıldı/silindi: henüz göreve bağlanmamış videoların havuz bağı kopar (sepete döner).
    İzlenen/göreve bağlı videolar kalemi tarihçe olarak tutar."""
    from app.models.video_basket import VideoBasketItem

    if not item_ids:
        return
    db.query(VideoBasketItem).filter(VideoBasketItem.pool_item_id.in_(item_ids),
                                     VideoBasketItem.task_id.is_(None)).update(
        {VideoBasketItem.pool_item_id: None}, synchronize_session=False)


def detach_task_videos(db: Session, task_id: int) -> None:
    """Kap görevi silinmeden önce videoların görev bağını boşalt (dev SQLite'ta FK kapalı;
    prod PG'de SET NULL zaten yapar). Havuz bağı kalır → video yeniden havuzda bekler."""
    from app.models.video_basket import VideoBasketItem

    db.query(VideoBasketItem).filter(VideoBasketItem.task_id == task_id).update(
        {VideoBasketItem.task_id: None}, synchronize_session=False)


def item_min_quantity(db: Session, item: PoolItem) -> int:
    """Kalem miktarının inebileceği en küçük değer: yapılan (öğrenci kaydı + seans işareti) +
    öğrencinin kabında hâlâ açık duran (henüz yapılmamış) birimler. Altına inilirse kap görevi
    havuzda olmayan birimi taşır."""
    sync_item_progress(db, item)
    open_in_cup = 0
    for t in _cup_tasks(db, item):
        if t.status == TaskStatus.COMPLETED:
            continue
        if t.book_items:
            open_in_cup += sum(max(0, int(bi.planned_count or 0) - int(bi.completed_count or 0)) for bi in t.book_items)
        else:
            open_in_cup += _units_from_title(t)
    return max(1, item.done_units + open_in_cup)


def set_item_quantity(db: Session, item: PoolItem, quantity: int, actor: User) -> PoolItem:
    """Rehber kalemin miktarını düzeltir (7 test → 5 test). Yalnız açık dönemde; yapılan + kaptaki
    açık birimlerin altına inmez. Rezerv yok (havuz kalemi kitap sayacına rezerv açmaz)."""
    if item.removed_at is not None:
        raise PoolError("item_removed", "Bu kalem havuzdan kaldırılmış.")
    if not item.period.is_open:
        raise PoolError("period_closed", "Kapalı dönemin kalemi düzenlenemez.")
    if quantity < 1:
        raise PoolError("bad_quantity", "Miktar en az 1 olmalı; hiç verilmeyecekse kalemi kaldır.")
    mn = item_min_quantity(db, item)
    if quantity < mn:
        done = item.done_units
        raise PoolError(
            "below_done",
            f"En az {mn} olabilir: {done} {item.unit} yapıldı"
            + (f", {mn - done} {item.unit} öğrencinin kabında bekliyor" if mn > done else "") + ".",
        )
    if item.page_from is not None:
        item.page_to = item.page_from + quantity - 1  # sayfa aralığı yeni miktara göre (2026-10-22)
    item.quantity = quantity
    item.completed = min(item.quantity, item.completed or 0)
    db.flush()
    return item


def approve_item(db: Session, item: PoolItem, actor: User, approved: bool) -> PoolItem:
    """K38: öğrencinin eklediği kalemi seansta onayla/reddet."""
    if item.source != SOURCE_STUDENT:
        raise PoolError("not_student_item", "Yalnız öğrencinin eklediği kalem onaylanır.")
    item.approval = APPROVAL_APPROVED if approved else APPROVAL_REJECTED
    item.approved_at = _now()
    item.approved_by_id = actor.id
    db.flush()
    return item


def relink_item(
    db: Session, *, item: PoolItem, coach: User, subject: Subject | None = None,
    topic: Topic | None = None, book: Book | None = None, section: BookSection | None = None,
) -> PoolItem:
    """Kalemin müfredat/kitap bağını değiştir (2026-10-22): koç öğrencinin eklediği kalemi onaylamadan
    önce doğru konuya/kitaba bağlar. Yalnız hiç ilerlemesi yokken (kaba alınmamış, işaretlenmemiş):
    kap görevi kalemin bağını taşır; ilerlemeli kalemde bağ değişirse sayaçlar ayrışır.
    Miktar korunur; birim yeni bağa uyarlanır (kitapta kitabın birimi, konuda test/soru/sayfa)."""
    if item.removed_at is not None:
        raise PoolError("item_removed", "Kaldırılmış kalem değiştirilemez.")
    if item.period is not None and not item.period.is_open:
        raise PoolError("period_closed", "Kapalı dönemdeki kalem değiştirilemez.")
    if int(item.completed or 0) > 0 or int(item.session_marked or 0) > 0 or _cup_tasks(db, item):
        raise PoolError("has_progress",
                        "Kalem kaba alınmış ya da işaretlenmiş; bağı değiştirilemez. Kaldırıp doğrusunu ekle.")
    if (topic is None) == (section is None):
        raise PoolError("link_required", "Bir müfredat konusu ya da kitabın bir bölümü seç.")
    subject = subject or (db.get(Subject, item.subject_id) if item.subject_id else None)
    if subject is None:
        raise PoolError("subject_required", "Ders seçin.")
    student = db.get(User, item.student_id)
    _check_subject_allowed(student, subject)
    if topic is not None:
        if topic.subject_id != subject.id:
            raise PoolError("topic_subject_mismatch", "Konu seçilen derse ait değil.")
        if not (topic.is_builtin or topic.teacher_id == coach.id):
            raise PoolError("topic_not_found", "Konu bulunamadı.")
        item.topic_id, item.book_id, item.book_section_id = topic.id, None, None
        if item.unit not in (UNIT_TEST, UNIT_SORU, UNIT_SAYFA):
            item.unit = UNIT_TEST
        if item.unit != UNIT_SAYFA:
            item.page_from = item.page_to = None
    else:
        if book is None or section.book_id != book.id:
            raise PoolError("section_book_mismatch", "Bölüm seçilen kitaba ait değil.")
        sb = (db.query(StudentBook).filter(StudentBook.student_id == item.student_id, StudentBook.book_id == book.id,
                                           StudentBook.archived_at.is_(None)).first())
        if sb is None:
            raise PoolError("book_not_assigned", "Bu kitap öğrenciye atanmış değil.")
        if book.subject_id and book.subject_id != subject.id:
            raise PoolError("book_subject_mismatch", "Kitap seçilen derse ait değil.")
        from app.models.book import BookType as _BT
        item.book_id, item.book_section_id = book.id, section.id
        item.topic_id = section.topic_id
        item.unit = UNIT_DENEME if book.type in (_BT.BRANS_DENEMESI, _BT.GENEL_DENEME) else UNIT_TEST
        item.page_from = item.page_to = None
    item.subject_id = subject.id
    db.flush()
    return item


def carry_item(
    db: Session, *, item: PoolItem, target: StudyPeriod, student: User, coach: User,
    quantity: int | None = None,
) -> PoolItem:
    """K22/K58: kalanı yeni döneme kalem kalem devret; miktar yeniden yazılır, sayaç artar."""
    sync_item_progress(db, item)
    qty = quantity if quantity is not None else item.remaining
    if qty < 1:
        raise PoolError("nothing_to_carry", "Devredilecek kalan yok.")
    subject = db.get(Subject, item.subject_id) if item.subject_id else None
    if subject is None:
        raise PoolError("subject_missing", "Kalemin dersi silinmiş.")
    new = add_item(
        db, period=target, student=student, subject=subject, quantity=qty, unit=item.unit,
        topic=db.get(Topic, item.topic_id) if item.topic_id else None,
        book=db.get(Book, item.book_id) if item.book_id else None,
        section=db.get(BookSection, item.book_section_id) if item.book_section_id else None,
        label=item.label, source=SOURCE_CARRY, created_by=coach,
        teacher_homework=item.teacher_homework, parent_item=item,
    )
    _move_videos(db, item, new)
    return new


def _move_videos(db: Session, old: PoolItem, new: PoolItem) -> None:
    """Devirde kaba alınmamış videolar yeni döneme geçen kaleme taşınır."""
    from app.models.video_basket import VideoBasketItem

    db.query(VideoBasketItem).filter(VideoBasketItem.pool_item_id == old.id,
                                     VideoBasketItem.task_id.is_(None)).update(
        {VideoBasketItem.pool_item_id: new.id}, synchronize_session=False)


# ---------------------------------------------------------------- kap (günün görevi)

def _cup_tasks(db: Session, item: PoolItem) -> list[Task]:
    return (db.query(Task).options(joinedload(Task.book_items))
            .filter(Task.pool_item_id == item.id).all())


def sync_item_progress(db: Session, item: PoolItem) -> PoolItem:
    """Kalemin `completed` değerini kap görevlerinden yeniden kurar (tek yön: görev → kalem).
    K42: kitaplı/konulu kalemde çözülen test; kalemsiz etkinlik görevinde tamam = kaba konan miktar."""
    total = 0
    for t in _cup_tasks(db, item):
        if t.book_items:
            total += sum(int(bi.completed_count or 0) for bi in t.book_items)
        elif t.status == TaskStatus.COMPLETED:
            total += _units_from_title(t)
    item.completed = min(item.quantity, total)
    db.flush()
    return item


def _units_from_title(task: Task) -> int:
    """Kalemsiz kap görevinde kaba konan miktar başlıkta '· N birim' olarak kodlanır."""
    try:
        tail = (task.title or "").rsplit("·", 1)[-1].strip()
        n = int(tail.split()[0])
        return max(1, n)
    except Exception:
        return 1


def _deneme_meta(db: Session, item: PoolItem, book: Book | None) -> tuple[str, str | None, int | None] | None:
    """Kalem deneme mi? (tür, sınav, soru) — eski deneme kalemleri (exam_kind boş) de tanınır."""
    from app.services import deneme_service as _ds

    is_deneme_book = book is not None and book.type in _ds.DENEME_BOOK_TYPES
    if item.unit != UNIT_DENEME and not item.exam_kind and not is_deneme_book:
        return None
    subject = book.subject if book is not None else (db.get(Subject, item.subject_id) if item.subject_id else None)
    kind = item.exam_kind or (_ds.EXAM_KIND_GENEL if book is not None and book.type == _ds.DENEME_BOOK_TYPES[1]
                              else _ds.EXAM_KIND_BRANS)
    sec = item.exam_section or _ds.exam_section_for_subject(subject)
    qn = item.question_count
    if qn is None:
        section = db.get(BookSection, item.book_section_id) if item.book_section_id else None
        qn, _src = _ds.resolve_question_count(book=book, section=section, subject=subject)
    return kind, sec, qn


def _exam_sections_for(db: Session, item: PoolItem, book: Book, count: int, exclude: set[int]) -> list[BookSection]:
    """Kitaplı deneme kalemi için sıradaki `count` deneme: kalemin bölümünden başlar, bu kalemin
    daha önce kaba alınmış bölümlerini atlar; kitap biterse son bölüm tekrar kullanılır."""
    secs = sorted(book.sections, key=lambda x: (x.order or 0, x.id))
    if not secs:
        return []
    start = next((i for i, x in enumerate(secs) if x.id == item.book_section_id), 0)
    used = set(exclude)
    # Bu dönemde AYNI kitaptan kaba alınmış tüm denemeler atlanır (aynı kitaptan iki kalem
    # ikisi de "DENEME 1"den başlamasın).
    sibling_ids = [r[0] for r in db.query(PoolItem.id).filter(
        PoolItem.period_id == item.period_id, PoolItem.book_id == book.id).all()]
    if sibling_ids:
        for bi in (db.query(TaskBookItem).join(Task, Task.id == TaskBookItem.task_id)
                   .filter(Task.pool_item_id.in_(sibling_ids), TaskBookItem.book_section_id.isnot(None)).all()):
            used.add(bi.book_section_id)
    ordered = secs[start:] + secs[:start]
    picked = [x for x in ordered if x.id not in used][:count]
    while len(picked) < count:
        picked.append(picked[-1] if picked else ordered[0])
    return picked


def _exam_cup_items(db: Session, *, item: PoolItem, book: Book | None, kind: str, exam_section: str | None,
                    question_count: int | None, count: int, exclude: set[int],
                    start_index: int = 0) -> list[TaskBookItem]:
    """Kap görevinin deneme kalemleri — 1 kalem = 1 deneme (rezerv yok)."""
    fields = dict(exam_kind=kind, exam_section=exam_section, question_count=question_count,
                  planned_count=1, completed_count=0)
    if book is not None:
        return [TaskBookItem(book_id=book.id, book_section_id=sec.id, reservation_released_at=_now(), **fields)
                for sec in _exam_sections_for(db, item, book, count, exclude)]
    base = item.label or "Deneme"
    total = start_index + count
    return [TaskBookItem(book_id=None, book_section_id=None, subject_id=item.subject_id,
                         label=(f"{base} {start_index + i + 1}/{total}" if total > 1 else base), **fields)
            for i in range(count)]


def _exam_cup_title(db: Session, *, item: PoolItem, book: Book | None, items: list[TaskBookItem],
                    question_count: int | None) -> str:
    from app.services import deneme_service as _ds

    subject = book.subject if book is not None else (db.get(Subject, item.subject_id) if item.subject_id else None)
    labels = []
    for bi in items:
        sec = db.get(BookSection, bi.book_section_id) if bi.book_section_id else None
        labels.append(sec.label if sec else "")
    return _ds.compose_title(kind=items[0].exam_kind if items else _ds.EXAM_KIND_BRANS, count=len(items),
                             question_count=question_count, subject=subject, book=book,
                             section_labels=labels, custom_name=(item.label if book is None else None))


def put_in_cup(db: Session, *, item: PoolItem, day: date, count: int | None = None) -> Task:
    """K34: kalemi (ya da bir kısmını) o günün kabına koyar → o güne görev yazar.

    Rezerv AÇILMAZ: kitaplı kalem `reservation_released_at` dolu doğar; mevcut
    complete/uncomplete/set_item_completion kodu bu işareti tanır (rezerv sayacına
    dokunmaz, çözülen test kitap sayacına yazılır)."""
    if item.removed_at is not None:
        raise PoolError("item_removed", "Bu kalem havuzdan kaldırılmış.")
    if not item.period.is_open:
        raise PoolError("period_closed", "Dönem kapalı; kaba kalem alınamaz.")
    if item.source == SOURCE_STUDENT and item.approval == APPROVAL_REJECTED:
        raise PoolError("item_rejected", "Bu kalem rehber tarafından reddedildi.")
    sync_item_progress(db, item)
    # aynı kalemden hâlâ açık (tamamlanmamış) kap görevi varsa önce o kapanmalı
    for t in _cup_tasks(db, item):
        if t.status != TaskStatus.COMPLETED and t.date >= day:
            raise PoolError("already_in_cup", "Bu kalem zaten bugünün kabında.")
    remaining = item.remaining
    if remaining < 1:
        raise PoolError("item_done", "Bu kalem zaten tamamlandı.")
    qty = count if count is not None else remaining
    if qty < 1 or qty > remaining:
        raise PoolError("bad_count", f"En fazla {remaining} {item.unit} alınabilir.")

    subject = db.get(Subject, item.subject_id) if item.subject_id else None
    topic = db.get(Topic, item.topic_id) if item.topic_id else None
    book = db.get(Book, item.book_id) if item.book_id else None
    section = db.get(BookSection, item.book_section_id) if item.book_section_id else None
    order = (db.query(func.coalesce(func.max(Task.order), 0))
             .filter(Task.student_id == item.student_id, Task.date == day).scalar() or 0) + 1

    meta = _deneme_meta(db, item, book)
    if meta is not None:
        kind, sec, qn = meta
        items = _exam_cup_items(db, item=item, book=book, kind=kind, exam_section=sec,
                                question_count=qn, count=qty, exclude=set())
        task = Task(student_id=item.student_id, date=day,
                    type=TaskType.TEST if book is not None else TaskType.OTHER,
                    title=_exam_cup_title(db, item=item, book=book, items=items, question_count=qn),
                    status=TaskStatus.PENDING, order=order, is_draft=False, published_at=_now(),
                    pool_item_id=item.id, book_items=items)
        db.add(task)
        item.cup_attempts = (item.cup_attempts or 0) + 1
        db.flush()
        return task

    is_test_like = item.unit in (UNIT_TEST, UNIT_DENEME) or (item.unit != UNIT_ETKINLIK and book is not None)
    # Soru/sayfa birimli KONULU kaynaksız kalem (2026-10-22): önceden konusunu kaybedip boş
    # "Diğer" görevine dönüşüyordu → artık konuya bağlı, birimli kalem (test hacmine girmez).
    if item.unit in (UNIT_SORU, UNIT_SAYFA) and book is None and topic is not None:
        from app.services.gorev_stats import item_quantity_text

        full = qty == item.remaining and qty == item.quantity
        ti = TaskBookItem(book_id=None, book_section_id=None, topic_id=topic.id,
                          label=item.label or topic.name, planned_count=qty, completed_count=0,
                          unit=item.unit,
                          # aralık yalnız kalemin tamamı tek güne alınınca taşınır
                          page_from=item.page_from if full else None,
                          page_to=item.page_to if full else None)
        src = f" ({item.label})" if item.label and item.label != topic.name else ""
        task = Task(student_id=item.student_id, date=day, type=TaskType.TEST,
                    title=f"{topic.name}{src}: {item_quantity_text(ti)}"[:255],
                    status=TaskStatus.PENDING, order=order, is_draft=False, published_at=_now(),
                    pool_item_id=item.id, book_items=[ti])
        db.add(task)
        item.cup_attempts = (item.cup_attempts or 0) + 1
        db.flush()
        return task
    # Kalemler görevle BİRLİKTE kurulur (task.book_items=...): ilişki daha sonra tembel
    # yüklenirse dev SQLite'ta (cascade kapalı) id'si yeniden kullanılan eski görevin yetim
    # kalemleri bu göreve yapışır — prod PG'de olmaz ama servis buna dayanıklı olmalı.
    if is_test_like and (book is not None or topic is not None):
        if book is not None and section is not None:
            items = [TaskBookItem(book_id=book.id, book_section_id=section.id, planned_count=qty,
                                  completed_count=0, reservation_released_at=_now())]  # rezerv YOK
            title = task_titles.compose_single(book, section, qty)
        else:
            # kaynaksız ama konuya bağlı kalem (P2) — rezerv/kapasite yok, müfredat takibine girer
            items = [TaskBookItem(book_id=None, book_section_id=None, topic_id=topic.id if topic else None,
                                  label=item.label or (topic.name if topic else "Konu çalışması"),
                                  planned_count=qty, completed_count=0)]
            name = topic.name if topic else (item.label or "Konu çalışması")
            src = f" ({book.name})" if book is not None else ""
            title = f"{name}{src}: {qty} {item.unit}"
        task = Task(student_id=item.student_id, date=day, type=TaskType.TEST, title=title,
                    status=TaskStatus.PENDING, order=order, is_draft=False, published_at=_now(),
                    pool_item_id=item.id, book_items=items)
        db.add(task)
    else:
        # etkinlik / kitapsız deneme: kalemsiz görev; miktar başlık kuyruğunda taşınır
        what = item.label or (topic.name if topic else item.unit)
        pre = f"{subject.name} · " if subject else ""
        items = ([TaskBookItem(book_id=None, book_section_id=None, label=what, planned_count=qty, completed_count=0)]
                 if item.unit == UNIT_DENEME else [])
        vids = [v for v in pool_item_videos(db, item.id) if v.task_id is None] if item.unit == UNIT_ETKINLIK else []
        task = Task(student_id=item.student_id, date=day, type=TaskType.VIDEO if vids else TaskType.OTHER,
                    # video kalemi 1 birimdir (K42); başlık sepet başlığıyla aynı ("… — 3 video (45 dk)")
                    title=(f"{pre}{what}" if vids else f"{pre}{what} · {qty} {item.unit}")[:255],
                    status=TaskStatus.PENDING,
                    order=order, is_draft=False, published_at=_now(), pool_item_id=item.id,
                    book_items=items, link_url=vids[0].url if vids else None)
        db.add(task)
        if vids:
            # Video kalemi: videolar bu güne açılan göreve bağlanır (öğrenci görevde tek tek açar)
            db.flush()
            for v in vids:
                v.task_id = task.id
    item.cup_attempts = (item.cup_attempts or 0) + 1
    db.flush()
    return task


def cup_max_count(db: Session, task: Task) -> int | None:
    """Kap görevinin en çok kaç birime çıkarılabileceği: bu görevde yapılan + kalemin havuzdaki kalanı."""
    if task.pool_item_id is None:
        return None
    item = db.get(PoolItem, task.pool_item_id)
    if item is None:
        return None
    sync_item_progress(db, item)
    planned = sum(int(bi.planned_count or 0) for bi in task.book_items)
    done = sum(int(bi.completed_count or 0) for bi in task.book_items)
    # kalemin kalanına bu görevin henüz yapılmamış kısmı da dahil (aynı kalemden tek açık kap görevi)
    return done + max(0, item.remaining) if planned else None


def resize_cup(db: Session, *, task: Task, count: int) -> Task:
    """Öğrenci bugünkü kap görevinin sayısını KENDİ düzeltir (rehbere talep değil — kabı öğrenci kurar).

    Kurallar: yalnız açık dönemin kap görevi · kalemli görev (test/konu/deneme; kalemsiz etkinlik 1 birimdir) ·
    yeni sayı ≥ işaretlenen (önce işaretlediğini düzelt) · ≤ yapılan + kalemin havuzdaki kalanı.
    Sayı yapılana eşitlenirse görev tamamlanır. Rezerv yok (kap görevi rezerv tutmaz)."""
    if task.pool_item_id is None:
        raise PoolError("not_cup", "Bu görev havuzdan gelmiyor.")
    item = db.get(PoolItem, task.pool_item_id)
    if item is None or item.removed_at is not None or not item.period.is_open:
        raise PoolError("period_closed", "Dönem kapalı; kap düzeltilemez.")
    if task.book_items and any(bi.exam_kind for bi in task.book_items):
        return _resize_exam_cup(db, task=task, item=item, count=count)
    if not task.book_items or len(task.book_items) != 1:
        raise PoolError("not_resizable", "Bu görevin sayısı yok (etkinlik); havuza geri alabilirsin.")
    bi = task.book_items[0]
    done = int(bi.completed_count or 0)
    mx = cup_max_count(db, task) or 0
    if count < 1:
        raise PoolError("bad_count", "En az 1 olmalı; hiç çalışmayacaksan havuza geri al.")
    if count < done:
        raise PoolError("below_done", f"Bu görevde {done} işaretledin; önce işaretlediğin sayıyı düzelt.")
    if count > mx:
        raise PoolError("bad_count", f"En fazla {mx} {item.unit} olabilir (havuzdaki kalan).")
    if count != bi.planned_count and bi.page_from is not None:
        # sayfa aralığı yeni sayıya göre kısalır/uzar (başlangıç sabit) — 2026-10-22
        bi.page_to = bi.page_from + count - 1
    bi.planned_count = count
    if bi.book_id is not None and bi.book_section_id is not None:
        book = db.get(Book, bi.book_id)
        section = db.get(BookSection, bi.book_section_id)
        task.title = task_titles.compose_single(book, section, count)
    else:
        head = (task.title or "").rsplit(":", 1)[0] if ":" in (task.title or "") else None
        if head and task.type == TaskType.TEST:
            from app.services.gorev_stats import item_quantity_text

            task.title = (f"{head}: {item_quantity_text(bi)}" if bi.unit in (UNIT_SORU, UNIT_SAYFA)
                          else f"{head}: {count} {item.unit}")
        elif "·" in (task.title or ""):
            task.title = (task.title or "").rsplit("·", 1)[0].rstrip() + f" · {count} {item.unit}"
    if done >= count and task.status != TaskStatus.COMPLETED:
        task.status = TaskStatus.COMPLETED
        task.completed_at = _now()
    elif done < count and task.status == TaskStatus.COMPLETED:
        task.status = TaskStatus.PARTIAL if done > 0 else TaskStatus.PENDING
        task.completed_at = None
    db.flush()
    sync_item_progress(db, item)
    return task


def _resize_exam_cup(db: Session, *, task: Task, item: PoolItem, count: int) -> Task:
    """Deneme kap görevinde sayı = deneme satırı sayısı: artırınca yeni deneme satırı eklenir,
    azaltınca işaretlenmemiş satırlar silinir."""
    rows = sorted(task.book_items, key=lambda b: b.id)
    done = sum(1 for b in rows if (b.completed_count or 0) > 0)
    mx = cup_max_count(db, task) or 0
    if count < 1:
        raise PoolError("bad_count", "En az 1 olmalı; hiç çözmeyeceksen havuza geri al.")
    if count < done:
        raise PoolError("below_done", f"Bu görevde {done} denemeyi işaretledin; önce işaretlediğini düzelt.")
    if count > mx:
        raise PoolError("bad_count", f"En fazla {mx} deneme olabilir (havuzdaki kalan).")
    book = db.get(Book, rows[0].book_id) if rows and rows[0].book_id else None
    if count > len(rows):
        first = rows[0]
        extra = _exam_cup_items(
            db, item=item, book=book, kind=first.exam_kind, exam_section=first.exam_section,
            question_count=first.question_count, count=count - len(rows),
            exclude={b.book_section_id for b in rows if b.book_section_id}, start_index=len(rows))
        for bi in extra:
            task.book_items.append(bi)
    elif count < len(rows):
        removable = [b for b in reversed(rows) if (b.completed_count or 0) == 0][: len(rows) - count]
        for b in removable:
            task.book_items.remove(b)
            db.delete(b)
    db.flush()
    _refresh_exam_cup(db, task=task, item=item)
    sync_item_progress(db, item)
    return task


def _refresh_exam_cup(db: Session, *, task: Task, item: PoolItem) -> None:
    """Deneme kap görevinin başlığını + durumunu satırlardan yeniden kur."""
    rows = sorted(task.book_items, key=lambda x: x.id or 0)
    if not rows:
        return
    book = db.get(Book, rows[0].book_id) if rows[0].book_id else None
    if book is None:
        n = len(rows)
        base = item.label or "Deneme"
        for i, b in enumerate(rows):
            b.label = f"{base} {i + 1}/{n}" if n > 1 else base
    task.title = _exam_cup_title(db, item=item, book=book, items=rows, question_count=rows[0].question_count)
    done = sum(1 for b in rows if (b.completed_count or 0) > 0)
    if done >= len(rows) and task.status != TaskStatus.COMPLETED:
        task.status = TaskStatus.COMPLETED
        task.completed_at = _now()
    elif done < len(rows) and task.status == TaskStatus.COMPLETED:
        task.status = TaskStatus.PARTIAL if done > 0 else TaskStatus.PENDING
        task.completed_at = None
    db.flush()


def preview_distribution(items: list[PoolItem], *, start: date, days: int,
                         lesson_days: dict[str, list[int]]) -> list[dict]:
    """Haftaya dağılım ÖNERİSİ (yazılmaz): kalemin kalan birimleri önce dersin dershanede işlendiği
    günlere (şube ders programı; anahtar Pzt=0), o günler arasında en boş olana birer birer; ders
    programında günü olmayan kalemler en boş güne. Ders programı yoksa düz eşit bölme.
    Koç editörü önizlemesiyle aynı kural (web `buildPreview`)."""
    n = max(1, days)
    out = []
    for i in range(n):
        d = start + timedelta(days=i)
        out.append({"date": d, "dow": d.weekday(), "lessons": list(lesson_days.get(str(d.weekday()), [])),
                    "total": 0, "by_subject": {}})
    open_items = [it for it in items if it.removed_at is None and it.counts_toward_pool and it.remaining > 0]

    def units(it: PoolItem) -> int:
        return 1 if it.unit == UNIT_ETKINLIK else it.remaining

    def place(it: PoolItem, targets: list[dict]) -> None:
        for _ in range(units(it)):
            d = min(targets, key=lambda x: x["total"])
            d["total"] += 1
            d["by_subject"][it.subject_id] = d["by_subject"].get(it.subject_id, 0) + 1

    bound = [it for it in open_items if it.subject_id and any(it.subject_id in d["lessons"] for d in out)]
    free = [it for it in open_items if it not in bound]
    for it in bound:
        place(it, [d for d in out if it.subject_id in d["lessons"]])
    for it in free:
        place(it, out)
    return out


def cup_units_on(db: Session, *, student_id: int, day: date) -> int:
    """O günün kabındaki toplam birim (aşırı kap uyarısı için)."""
    tasks = (db.query(Task).options(joinedload(Task.book_items))
             .filter(Task.student_id == student_id, Task.date == day, Task.pool_item_id.isnot(None)).all())
    total = 0
    for t in tasks:
        total += sum(int(bi.planned_count or 0) for bi in t.book_items) if t.book_items else 1
    return total


def close_day(db: Session, *, student: User, day: date) -> dict:
    """Gün sonu (K34): kaptaki yapılmayan kısım havuza döner.

    · hiç ilerleme yok → kap görevi silinir (kalem kalanı aynen havuzda)
    · kısmi ilerleme   → görev planlanan = tamamlanan'a küçülür (kayıt kalır), kalan havuzda
    · tamam            → dokunulmaz
    Rezerv yok olduğundan silme iade üretmez."""
    tasks = (db.query(Task).options(joinedload(Task.book_items))
             .filter(Task.student_id == student.id, Task.date == day, Task.pool_item_id.isnot(None))
             .all())
    removed, shrunk, kept = 0, 0, 0
    touched: set[int] = set()
    for t in tasks:
        touched.add(t.pool_item_id)
        if t.status == TaskStatus.COMPLETED:
            kept += 1
            continue
        done = sum(int(bi.completed_count or 0) for bi in t.book_items)
        if done <= 0:
            detach_task_videos(db, t.id)
            db.delete(t)
            removed += 1
            continue
        if any(bi.exam_kind for bi in t.book_items):
            # Deneme kap görevi (1 satır = 1 deneme): çözülmeyen deneme satırı silinir (havuza döner).
            for bi in [b for b in t.book_items if (b.completed_count or 0) == 0]:
                t.book_items.remove(bi)
                db.delete(bi)
            db.flush()
            it_ = db.get(PoolItem, t.pool_item_id)
            if it_ is not None:
                _refresh_exam_cup(db, task=t, item=it_)
            t.status = TaskStatus.COMPLETED
            t.completed_at = t.completed_at or _now()
            shrunk += 1
            continue
        for bi in t.book_items:
            bi.planned_count = int(bi.completed_count or 0)
        t.status = TaskStatus.COMPLETED
        t.completed_at = _now()
        task_titles.refresh_auto_title(t)
        shrunk += 1
    db.flush()
    for pid in touched:
        it = db.get(PoolItem, pid)
        if it is not None:
            sync_item_progress(db, it)
    return {"removed": removed, "shrunk": shrunk, "kept": kept}


# ---------------------------------------------------------------- özet / tempo

@dataclass
class PeriodSummary:
    total_units: int
    done_units: int
    pct: int
    items_total: int
    items_done: int
    pending_student_items: int
    days_left: int
    per_day_needed: float
    expected_next_on: date | None


def _units(item: PoolItem) -> tuple[int, int]:
    """(toplam, tamamlanan) birim — K42: test sayısı; etkinlik/deneme/video 1 birim/adet."""
    if item.unit == UNIT_ETKINLIK:
        return 1, (1 if item.is_done else 0)
    return int(item.quantity or 0), item.done_units


def period_summary(db: Session, period: StudyPeriod, today: date) -> PeriodSummary:
    total = done = items_total = items_done = pending = 0
    for it in period.items:
        if it.removed_at is not None:
            continue
        if it.source == SOURCE_STUDENT and it.approval == APPROVAL_PENDING:
            pending += 1
        if not it.counts_toward_pool:
            continue
        t, d = _units(it)
        total += t
        done += d
        items_total += 1
        items_done += 1 if it.is_done else 0
    pct = int(round(100 * done / total)) if total else 0
    if period.expected_next_on is not None:
        # beklenen gün geçtiyse kalan gün 1 sayılır (Basamak 9 türeyen kural; sıfıra bölme yok)
        days_left = max(1, (period.expected_next_on - today).days)
    else:
        days_left = 1
    per_day = round((total - done) / days_left, 1) if total > done else 0.0
    return PeriodSummary(total, done, pct, items_total, items_done, pending, days_left, per_day,
                         period.expected_next_on)


# ---------------------------------------------------------------- şube

def scope_key_for(coach: User) -> str:
    return f"inst:{coach.institution_id}" if coach.institution_id else f"coach:{coach.id}"


def get_or_create_class_group(db: Session, *, coach: User, name: str) -> ClassGroup:
    key = scope_key_for(coach)
    cg = db.query(ClassGroup).filter(ClassGroup.scope_key == key, ClassGroup.name == name).first()
    if cg is None:
        cg = ClassGroup(scope_key=key, name=name)
        db.add(cg)
        db.flush()
    return cg


def class_group_of(db: Session, *, student: User, coach: User) -> ClassGroup | None:
    if not student.class_group:
        return None
    return (db.query(ClassGroup)
            .filter(ClassGroup.scope_key == scope_key_for(coach), ClassGroup.name == student.class_group)
            .first())


def set_topic_position(db: Session, cg: ClassGroup, *, subject_id: int, topic_id: int | None,
                       actor: User, on: date) -> ClassGroup:
    """K9: şubenin bir dersteki konu konumu (rehber öğrenciden gelen cevapla yazar)."""
    pos = cg.positions
    if topic_id is None:
        pos.pop(str(subject_id), None)
    else:
        pos[str(subject_id)] = {"topic_id": int(topic_id), "updated_on": on.isoformat(), "by": actor.id}
    cg.topic_positions = json.dumps(pos)
    db.flush()
    return cg


def set_lesson_days(db: Session, cg: ClassGroup, lessons: dict[int, list[int]]) -> ClassGroup:
    """K37: haftanın günü (0=Pzt) → dershanede işlenen dersler."""
    clean = {str(int(k)): [int(x) for x in v] for k, v in lessons.items() if 0 <= int(k) <= 6}
    cg.lesson_days = json.dumps(clean)
    db.flush()
    return cg


def subjects_taught_on(cg: ClassGroup | None, day: date) -> list[int]:
    if cg is None:
        return []
    return [int(x) for x in cg.lessons.get(str(day.weekday()), [])]


def cup_suggestions(db: Session, *, period: StudyPeriod, cg: ClassGroup | None, day: date,
                    limit: int = 3) -> list[PoolItem]:
    """K37 ek: bugünün kabı için öneri — önce gün etiketi bugün olanlar, sonra o gün
    dershanede işlenen dersin kalemleri, sonra en uzun süredir bekleyenler."""
    cands = [it for it in period.items
             if it.removed_at is None and it.remaining > 0 and it.approval != APPROVAL_REJECTED]
    taught = set(subjects_taught_on(cg, day))

    def rank(it: PoolItem) -> tuple:
        return (0 if it.day_hint == day else 1,
                0 if (it.subject_id in taught) else 1,
                -(it.cup_attempts or 0),
                it.id)
    cands.sort(key=rank)
    return cands[:limit]


# ---------------------------------------------------------------- serbest metin (K28)

_UNIT_WORDS = {
    "test": UNIT_TEST, "testi": UNIT_TEST, "tst": UNIT_TEST,
    "soru": "soru", "sorusu": "soru",
    "sayfa": "sayfa", "sayfaya": "sayfa", "sf": "sayfa", "syf": "sayfa",
    "deneme": UNIT_DENEME, "denemesi": UNIT_DENEME,
    "video": UNIT_ETKINLIK, "izle": UNIT_ETKINLIK, "özet": UNIT_ETKINLIK, "ozet": UNIT_ETKINLIK,
    "tekrar": UNIT_ETKINLIK, "etkinlik": UNIT_ETKINLIK,
}


# Hızlı yaz: metinde kitabı/dersi/konuyu bulmaya yaramayan sözcükler (eylem, ek, genel sözcükler)
_PARSE_STOP = {
    "coz", "cozsun", "cozecek", "yap", "yapsin", "ver", "verelim", "calis", "calissin", "oku", "bitir",
    "dan", "den", "tan", "ten", "da", "de", "ve", "ile", "icin", "olarak", "tane", "adet",
    "konu", "konusu", "konusundan", "kitap", "kitabi", "kitabindan", "kaynak", "kaynagi",
}
# Kitap adında bulunsa da "hangi kitap" sorusunu ayırt etmeyen sözcükler
_BOOK_GENERIC = {"tyt", "ayt", "lgs", "yks", "soru", "bankasi", "banka", "yayinlari", "yayin", "yayinevi",
                 "kitabi", "kitap", "test", "testleri", "fasikul", "fasikulu", "konu", "anlatimli", "ozetli",
                 "set", "seti", "ve", "ile", "sinif"}


# Koçların yaygın ders kısaltmaları → ders adındaki sözcük
_SUBJECT_ABBR = {"mat": "matematik", "math": "matematik", "geo": "geometri", "geom": "geometri",
                 "fiz": "fizik", "kim": "kimya", "biyo": "biyoloji", "bio": "biyoloji", "cog": "cografya",
                 "edeb": "edebiyat", "edb": "edebiyat", "tde": "edebiyati", "fel": "felsefe", "ing": "ingilizce"}


def _words(text: str) -> list[tuple[str, str]]:
    """Metin → [(özgün sözcük, normalize sözcük)]; ayraçlar da sözcük sınırı sayılır."""
    import re
    from app.services.curriculum_mapping import normalize
    out = []
    for w in re.split(r"[\s·,;/|—]+", text.strip()):
        n = normalize(w)
        for piece in n.split():
            out.append((w, _SUBJECT_ABBR.get(piece, piece)))
    return out


def parse_free_text(db: Session, *, student: User, subjects: list[Subject], text: str,
                    subject_id: int | None = None) -> dict:
    """Hızlı yaz: 'orijinal matematik mutlak değer 4 test' → çipler + taslak. Belirsizde YAZMAZ, uyarı döner.

    Deterministik, yapay zekâsız, SÖZCÜK bazlı — ayraç gerekmez (2026-10-13 saha: ayraçsız yazılan metin
    tek parça kalıp ders/kitap adına birebir uymadığı için hep "Ders anlaşılamadı" dönüyordu):
      1 miktar/birim — "4 test", "4test", "3 sayfa", "video"; birimsiz sayı kitap adında geçmiyorsa test
      2 kitap        — öğrencinin kitapları; ayırt edici sözcük (marka: "orijinal", "345", "palme") eşleşmeli,
                       genel sözcükler (tyt, soru bankası, ders adı) tek başına kitap seçtirmez
      3 ders         — seçili ders > kitabın dersi > metindeki ders adı ("matematik", "tyt fizik", "türkçe")
      4 konu         — aday derslerin konuları; konu adının TÜM sözcükleri metinde → kesin, kısmi → tahmin.
                       Ders belirsizse (TYT/AYT Matematik) konunun bulunduğu ders seçilir
      5 bölüm        — kitap + konu → konunun bölümü; kitap var konu yoksa bölüm adından
    Tanınmayan sözcükler serbest metin (label) olarak kalır."""
    import re
    from app.services.curriculum_mapping import normalize
    from app.services.curriculum_progress import _SCHOOL_EXAM_SYNONYMS, leaf_topics_for_student

    words = _words(text)
    used = [False] * len(words)

    def free_idx() -> list[int]:
        return [i for i in range(len(words)) if not used[i]]

    books = (db.query(Book).join(StudentBook, StudentBook.book_id == Book.id)
             .filter(StudentBook.student_id == student.id, StudentBook.archived_at.is_(None)).all())
    book_tokens = {b.id: set(normalize(b.name).split()) for b in books}
    all_book_tokens: set[str] = set().union(*book_tokens.values()) if book_tokens else set()

    # ---- 1 miktar / birim
    qty: int | None = None
    unit: str | None = None
    for i, (_, w) in enumerate(words):  # "4 test" / "4test"
        m = re.fullmatch(r"(\d+)([a-z]*)", w)
        if not m:
            continue
        suf = m.group(2)
        u = _UNIT_WORDS.get(suf) if suf else None
        if suf and u is None:
            continue
        if u is None and i + 1 < len(words) and words[i + 1][1] in _UNIT_WORDS:
            u = _UNIT_WORDS[words[i + 1][1]]
            used[i + 1] = True
        if u is not None:
            qty, unit = int(m.group(1)), u
            used[i] = True
            break
    if qty is None:  # birimsiz sayı ("Üslü 3") — kitap adındaki sayı ("345") değilse
        for i, (_, w) in enumerate(words):
            if not used[i] and w.isdigit() and w not in all_book_tokens:
                qty, unit = int(w), UNIT_TEST
                used[i] = True
                break
    if unit is None:  # sayısız birim: "video", "özet" (etkinlik = 1)
        for i, (_, w) in enumerate(words):
            if not used[i] and w in _UNIT_WORDS:
                unit = _UNIT_WORDS[w]
                if unit == UNIT_ETKINLIK:
                    qty = 1
                used[i] = True
                break

    subj_by_id = {s.id: s for s in subjects}
    subject_words: set[str] = set()
    for s in subjects:
        subject_words |= set(normalize(s.name).split())

    # ---- 2 kitap
    subj: Subject | None = subj_by_id.get(subject_id) if subject_id else None
    book: Book | None = None
    scored = []
    for b in books:
        toks = book_tokens[b.id]
        hit = [i for i in free_idx() if words[i][1] in toks]
        distinct = [i for i in hit if words[i][1] not in _BOOK_GENERIC and words[i][1] not in subject_words]
        if distinct:
            scored.append((len(distinct), len(hit), b, hit))
    if subj is not None:
        scored = [x for x in scored if x[2].subject_id == subj.id] or scored
    if scored:
        scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best = scored[0]
        if len(scored) == 1 or (best[0], best[1]) > (scored[1][0], scored[1][1]):
            book = best[2]
            for i in best[3]:
                used[i] = True
    book_ambiguous = bool(scored) and book is None

    # ---- 3 ders
    if subj is None and book is not None and book.subject_id in subj_by_id:
        subj = subj_by_id[book.subject_id]
    cand_subjects: list[Subject] = []
    exam_hint = {w for w in ("tyt", "ayt") if any(not used[i] and words[i][1] == w for i in range(len(words)))}
    if subj is None:
        free_set = {words[i][1] for i in free_idx()}
        for s in subjects:
            base = set(normalize(s.name).split()) - {"tyt", "ayt", "ve", "ile"}
            syn = [set(normalize(x).split()) for x in _SCHOOL_EXAM_SYNONYMS.get(s.name, set())]
            if base and (base <= free_set or any(x and x <= free_set for x in syn)):
                cand_subjects.append(s)
        if exam_hint:
            narrowed = [s for s in cand_subjects if exam_hint <= set(normalize(s.name).split())]
            cand_subjects = narrowed or cand_subjects
        if len(cand_subjects) == 1:
            subj = cand_subjects[0]
        if cand_subjects:  # ders adı sözcüklerini tüket (tyt/ayt + eşanlamlar dahil)
            names = set().union(*(set(normalize(s.name).split()) for s in cand_subjects)) | {"tyt", "ayt"}
            for s in cand_subjects:
                for y in _SCHOOL_EXAM_SYNONYMS.get(s.name, set()):
                    names |= set(normalize(y).split())
            for i in free_idx():
                if words[i][1] in names:
                    used[i] = True

    # ---- 4 konu
    topic: Topic | None = None
    topic_conf = True
    hinted = [s for s in subjects if exam_hint and exam_hint <= set(normalize(s.name).split())]
    topic_pool = [subj] if subj is not None else (cand_subjects or hinted or list(subjects))
    lt = leaf_topics_for_student(db, student, student.teacher_id or 0, [s.id for s in topic_pool])
    rest_idx = [i for i in free_idx() if words[i][1] not in _PARSE_STOP]
    rest_set = {words[i][1] for i in rest_idx}
    rest_phrase = " ".join(words[i][1] for i in rest_idx)
    book_subj = {b.subject_id for b in books}
    full: list = []
    part: list = []
    for s in topic_pool:
        tops = lt.by_subject.get(s.id) or db.query(Topic).filter(Topic.subject_id == s.id).all()
        for t in tops:
            tt = [w for w in normalize(t.name).split() if w not in ("ve", "ile")]
            if not tt:
                continue
            if set(tt) <= rest_set:
                full.append((len(tt), s, t, set(tt)))
            elif rest_phrase and (
                    (len(rest_phrase) >= 4 and rest_phrase in normalize(t.name))
                    or any(w in rest_set for w in tt if len(w) >= 3)):
                hit = {w for w in tt if w in rest_set}
                part.append((len(hit), s, t, hit))

    def _best(cands: list) -> list:
        key = lambda c: (c[0], c[1].id in book_subj)  # noqa: E731 — kitabı olan ders öne
        cands.sort(key=key, reverse=True)
        return [c for c in cands if key(c) == key(cands[0])]

    topic_subject_ambiguous: list[Subject] = []
    opt_cands: list = []  # belirsizlikte "Bunu mu demek istedin?" seçenekleri
    if full:
        top = _best(full)
        if len(top) == 1:
            topic = top[0][2]
            if subj is None:
                subj = top[0][1]
            for i in rest_idx:
                if words[i][1] in top[0][3]:
                    used[i] = True
        else:
            if subj is None and len({c[1].id for c in top}) > 1:
                topic_subject_ambiguous = [c[1] for c in top]
            opt_cands = top
    elif part:
        top = _best(part)
        if len(top) == 1:
            topic, topic_conf = top[0][2], False
            if subj is None:
                subj = top[0][1]
            for i in rest_idx:
                if words[i][1] in top[0][3]:
                    used[i] = True
        else:
            opt_cands = sorted(part, key=lambda c: (c[0], c[1].id in book_subj), reverse=True)

    # ---- 5 bölüm
    section: BookSection | None = None
    if book is not None:
        secs = db.query(BookSection).filter(BookSection.book_id == book.id).order_by(BookSection.order).all()
        if topic is not None:
            section = next((x for x in secs if x.topic_id == topic.id), None)
        else:
            rest2 = {words[i][1] for i in free_idx() if words[i][1] not in _PARSE_STOP}
            best_sec = None
            for x in secs:
                ls = [w for w in normalize(x.label).split() if w not in ("ve", "ile")]
                if ls and set(ls) <= rest2 and (best_sec is None or len(ls) > best_sec[0]):
                    best_sec = (len(ls), x, set(ls))
            if best_sec:
                section = best_sec[1]
                for i in free_idx():
                    if words[i][1] in best_sec[2]:
                        used[i] = True
                if section.topic_id:
                    topic = db.get(Topic, section.topic_id)

    if subj is not None:  # ders belli oldu → ders adı sözcükleri (tyt/ayt, kısaltma) nota kalmaz
        sn = set(normalize(subj.name).split()) | {"tyt", "ayt"}
        for y in _SCHOOL_EXAM_SYNONYMS.get(subj.name, set()):
            sn |= set(normalize(y).split())
        for i in free_idx():
            if words[i][1] in sn:
                used[i] = True
    seen: list[str] = []
    for i in free_idx():
        orig, n = words[i]
        if n not in _PARSE_STOP and orig not in seen:
            seen.append(orig)
    label = " ".join(seen).strip() or None

    chips: list[dict] = []
    if subj is not None:
        chips.append({"kind": "subject", "id": subj.id, "label": subj.name})
    if book is not None:
        chips.append({"kind": "book", "id": book.id, "label": book.name})
    if topic is not None:
        chips.append({"kind": "topic", "id": topic.id, "label": topic.name, "confident": topic_conf})
    if section is not None:
        chips.append({"kind": "section", "id": section.id, "label": section.label})
    if qty is not None:
        chips.append({"kind": "quantity", "label": str(qty)})
    if unit is not None:
        chips.append({"kind": "unit", "label": unit})
    if label:
        chips.append({"kind": "text", "label": label, "confident": False})

    # Seçenekler: konu/ders belirsiz → koç tek dokunuşla seçer (taslak YOK, sessizce yazılmaz)
    options: list[dict] = []
    if topic is None and opt_cands:
        secs_by_topic: dict[int, int] = {}
        if book is not None:
            for x in db.query(BookSection).filter(BookSection.book_id == book.id, BookSection.topic_id.isnot(None)):
                secs_by_topic.setdefault(x.topic_id, x.id)
        seen_t: set[int] = set()
        for _n, s_, t_, hit in opt_cands:
            if t_.id in seen_t:
                continue
            seen_t.add(t_.id)
            tname = normalize(t_.name)
            rest_words = [o for i in free_idx() for o, n in [words[i]]
                          if n not in _PARSE_STOP and n not in hit and n not in tname]
            options.append({
                "subject_id": s_.id, "subject_name": s_.name, "topic_id": t_.id, "topic_name": t_.name,
                "grade_level": t_.grade_level, "unit_name": lt.parent_names.get(t_.parent_id) if t_.parent_id else None,
                "book_id": book.id if book is not None and book.subject_id == s_.id else None,
                "section_id": secs_by_topic.get(t_.id) if book is not None and book.subject_id == s_.id else None,
                "label": " ".join(dict.fromkeys(rest_words)) or None,
            })
            if len(options) >= 8:
                break
    elif subj is None and len(cand_subjects) > 1:
        for s_ in cand_subjects[:6]:
            options.append({"subject_id": s_.id, "subject_name": s_.name, "topic_id": None, "topic_name": None,
                            "grade_level": None, "unit_name": None, "book_id": None, "section_id": None,
                            "label": label})
    base = {"quantity": qty, "unit": unit or UNIT_TEST}

    warning = None
    draft = None
    if options:
        what = "konuya" if options[0]["topic_id"] else "derse"
        warning = f"Birden çok {what} uyuyor — doğru olanı seç."
        if unit != UNIT_ETKINLIK and qty is None:
            warning += " Miktar da yazılmadı (örn. 4 test)."
    elif subj is None:
        many = topic_subject_ambiguous or (cand_subjects if len(cand_subjects) > 1 else [])
        if many:
            warning = ("Hangi ders? " + " / ".join(dict.fromkeys(s.name for s in many))
                       + " — 'tyt' / 'ayt' ekle ya da Adım adım'dan dersi seç.")
        elif book_ambiguous:
            warning = "Birden çok kitaba uyuyor — kitabın adını biraz daha açık yaz."
        else:
            warning = "Ders anlaşılamadı — kitap, ders ya da konu adı yaz (ör. 'Orijinal mutlak değer 4 test')."
    elif unit != UNIT_ETKINLIK and qty is None:
        warning = "Miktar yazılmadı (örn. 4 test)."
    elif topic is None and book is None and not label:
        warning = "Konu ya da kaynak anlaşılamadı."
    else:
        draft = None if (topic is None and book is None and (unit or UNIT_TEST) in TOPIC_REQUIRED_UNITS) else {
            "subject_id": subj.id, "topic_id": topic.id if topic else None,
            "book_id": book.id if book else None, "section_id": section.id if section else None,
            "label": label, "quantity": qty, "unit": unit or UNIT_TEST,
        }
        if topic is not None and not topic_conf:
            warning = f"Konu tahmini: '{topic.name}' — doğru değilse değiştir."
        elif topic is None and book is None and draft is None:
            warning = (f"Konu bulunamadı{f' ({label})' if label else ''} — test ve soru kalemi bir konuya "
                       f"bağlanmalı. Konu adını da yaz (ör. '{subj.name} <konu adı> 4 test') ya da "
                       "'Konudan seç'ten konuyu işaretle.")
        elif topic is None and section is None and label:
            warning = (f"Konu bulunamadı — '{label}' kalemin adı (not) olarak eklenir. "
                       "Konuya bağlamak için konu adını tam yaz ya da Adım adım'ı kullan.")
        elif book is not None and topic is not None and section is None:
            warning = (f"'{topic.name}' bu kitapta bölüm olarak bulunamadı — kalem konuya bağlanır, "
                       "kitap sayacı ilerlemez.")
    return {"chips": chips, "draft": draft, "warning": warning, "options": options, "base": base}


# ---------------------------------------------------------------- seans (K18–K22)

AVOID_IDLE_DAYS = 4  # K44: 4 gündür hiç kaba alınmadı


def session_mark(db: Session, *, item: PoolItem, actor: User, count: int, note: str | None = None) -> PoolItem:
    """K18 ikinci kaynak: rehber seansta öğrencinin kaynağına bakıp 'yapılmış' sayıyı yazar.

    `count` = rehberin işaretlediği toplam birim (mutlak). Kitaplı kalemde ARTIŞ kitap
    sayacına izli koç kaydı olarak yazılır (self_study, koç kaynağı = anında onaylı);
    azalış sayaca dokunmaz — sayaç onarımı kitap panelinden (K15). Erken uyarı bu
    sayıya bakmaz; yüzde ve seans değerlendirmesi bakar."""
    sync_item_progress(db, item)
    max_mark = max(0, int(item.quantity or 0) - int(item.completed or 0))
    if count < 0 or count > max_mark:
        raise PoolError("bad_count", f"En fazla {max_mark} {item.unit} işaretlenebilir.")
    old = int(item.session_marked or 0)
    delta = count - old
    item.session_marked = count
    item.session_marked_at = _now() if count > 0 else None
    if delta > 0 and _routed_to_book(item):
        from app.models import StudentBook as _SB
        from app.models.self_study import SS_SOURCE_COACH
        from app.services import self_study_service as ss
        sb = (db.query(_SB).filter(_SB.student_id == item.student_id, _SB.book_id == item.book_id).first())
        sec = db.get(BookSection, item.book_section_id)
        if sb is not None and sec is not None:
            student = db.get(User, item.student_id)
            try:
                ss.create_entries(db, student=student, actor=actor, source=SS_SOURCE_COACH,
                                  items=[(sb, sec, delta)],
                                  note=note or "Seansta işaretlendi (haftalık havuz)")
            except ss.SelfStudyError:
                pass  # kapasite dolu vb. — sayaç kitap panelinden düzeltilir, kalem işareti kalır
    db.flush()
    return item


@dataclass
class BookSectionState:
    section_id: int
    label: str
    order: int
    test_count: int
    completed: int          # kitap sayacı (öğrenci kaydı + seans işareti + bağımsız çalışma)
    reserved: int           # gün-gün rezerv (havuz rezerv tutmaz)
    in_pool: int            # AÇIK dönemde bu bölümden yazılmış, henüz yapılmamış birim
    topic_id: int | None
    last_on: date | None    # en son havuza yazıldığı / görev aldığı gün

    @property
    def remaining(self) -> int:
        return max(0, self.test_count - self.completed - self.reserved)

    @property
    def available(self) -> int:
        """Havuzdaki bekleyen de düşülmüş — yeniden vermeden önce bakılan sayı."""
        return max(0, self.remaining - self.in_pool)


@dataclass
class StudentBookState:
    book: Book
    sections: list[BookSectionState]

    @property
    def is_deneme(self) -> bool:
        from app.services.gorev_stats import DENEME_BOOK_TYPES
        return self.book.type in DENEME_BOOK_TYPES


def student_books_for_subject(db: Session, student: User, subject_id: int) -> list[StudentBookState]:
    """Havuz editörü "Nereden? → Öğrencinin kitapları" (2026-10-13): öğrencinin bu dersteki (arşivsiz) kitapları,
    kitabın KENDİ bölüm adlarıyla. Konu eşleştirmesine bakılmaz — rehber kitapta gördüğünü seçer; bölüm bir
    konuya bağlıysa müfredat ilerlemesi yine işler. Deneme kitapları dahil."""
    from app.models import SectionProgress
    rows = (db.query(StudentBook, Book)
            .join(Book, Book.id == StudentBook.book_id)
            .filter(StudentBook.student_id == student.id, StudentBook.archived_at.is_(None),
                    Book.subject_id == subject_id)
            .order_by(StudentBook.assigned_at, Book.id).all())
    if not rows:
        return []
    sb_ids = [sb.id for sb, _ in rows]
    book_ids = [b.id for _, b in rows]
    prog = {(sp.student_book_id, sp.book_section_id): sp
            for sp in db.query(SectionProgress).filter(SectionProgress.student_book_id.in_(sb_ids)).all()}
    secs = (db.query(BookSection).filter(BookSection.book_id.in_(book_ids))
            .order_by(BookSection.book_id, BookSection.order, BookSection.id).all())
    open_p = get_open_period(db, student.id)
    in_pool: dict[int, int] = {}
    if open_p is not None:
        for it in open_p.items:
            if it.removed_at is None and it.book_section_id and it.counts_toward_pool:
                in_pool[it.book_section_id] = in_pool.get(it.book_section_id, 0) + it.remaining
    last: dict[int, date] = {}
    for sid, created in (db.query(PoolItem.book_section_id, func.max(PoolItem.created_at))
                         .filter(PoolItem.student_id == student.id, PoolItem.book_section_id.isnot(None),
                                 PoolItem.removed_at.is_(None)).group_by(PoolItem.book_section_id).all()):
        if created:
            last[int(sid)] = tr_date(created)
    for sid, d in (db.query(TaskBookItem.book_section_id, func.max(Task.date))
                   .join(Task, Task.id == TaskBookItem.task_id)
                   .filter(Task.student_id == student.id, TaskBookItem.book_id.in_(book_ids))
                   .group_by(TaskBookItem.book_section_id).all()):
        if sid is not None and d and (int(sid) not in last or d > last[int(sid)]):
            last[int(sid)] = d
    out: list[StudentBookState] = []
    for sb, b in rows:
        states = []
        for sec in (x for x in secs if x.book_id == b.id):
            sp = prog.get((sb.id, sec.id))
            states.append(BookSectionState(
                section_id=sec.id, label=sec.label, order=sec.order or 0, test_count=int(sec.test_count or 0),
                completed=int(sp.completed_count or 0) if sp else 0, reserved=int(sp.reserved_count or 0) if sp else 0,
                in_pool=in_pool.get(sec.id, 0), topic_id=sec.topic_id, last_on=last.get(sec.id),
            ))
        out.append(StudentBookState(book=b, sections=states))
    return out


@dataclass
class TopicPoolSignals:
    """Havuzun müfredat ilerlemesine iki katkısı (2026-10-13, konu başına birim):

    · planned        — AÇIK dönemde yazılmış, henüz bitmemiş (kalanı olan), yüzdeye giren kalem → müfredatta
                       "planlandı" (gün-gün programdaki rezervin havuz karşılığı; havuz rezerv tutmaz).
                       Konu = kalemin konusu, yoksa kitap bölümünün eşli konusu.
    · session_marked — rehberin seansta "yapılmış" işaretlediği KAYNAKSIZ test birimi → müfredatta kaynaksız
                       çalışma ("devam"). Kitaplı test kaleminin işareti zaten kitap sayacına (self_study izli
                       koç kaydı) yazılıyor — burada SAYILMAZ (çift sayım yok). Öğrencinin kendi kaydı kap
                       görevinden gelir; seans işareti en fazla (miktar − öğrenci kaydı) olduğundan örtüşmez.
    Gün-gün öğrencide havuz kaydı olmadığından ikisi de boştur → mevcut yüzeyler değişmez."""
    planned: dict[int, int]
    session_marked: dict[int, int]


def _routed_to_book(it: PoolItem) -> bool:
    """Kalemin ilerlemesi kitap sayacına (SectionProgress) yazılır mı: kitap + bölüm + test/deneme birimi.
    Kap görevi (TaskBookItem) ve seans işareti (self_study izli koç kaydı) aynı kuralla kitaba gider."""
    return bool(it.book_id and it.book_section_id and it.unit in (UNIT_TEST, UNIT_DENEME))


def topic_pool_signals(db: Session, student_id: int) -> TopicPoolSignals:
    items = (db.query(PoolItem).options(joinedload(PoolItem.section), joinedload(PoolItem.period))
             .filter(PoolItem.student_id == student_id, PoolItem.removed_at.is_(None)).all())
    planned: dict[int, int] = {}
    marked: dict[int, int] = {}
    for it in items:
        if not it.counts_toward_pool:
            continue
        topic_id = it.topic_id or (it.section.topic_id if it.section is not None else None)
        if topic_id is None:
            continue
        if it.period is not None and it.period.is_open and it.remaining > 0:
            planned[topic_id] = planned.get(topic_id, 0) + it.remaining
        sm = int(it.session_marked or 0)
        if sm > 0 and it.unit == UNIT_TEST and not _routed_to_book(it):
            marked[topic_id] = marked.get(topic_id, 0) + sm
    return TopicPoolSignals(planned=planned, session_marked=marked)


def cup_returns(db: Session, items: list[PoolItem]) -> dict[int, int]:
    """K44 'kaba girip DÖNDÜ' sayısı = kaba alınma (cup_attempts) − ilerlemeli/açık kap görevi.
    (İlerlemesiz kap görevi gün sonunda / geri alışta silinir → kalan görev = dönmeyen alış.)"""
    ids = [it.id for it in items]
    if not ids:
        return {}
    rows = (db.query(Task.pool_item_id, func.count(Task.id))
            .filter(Task.pool_item_id.in_(ids)).group_by(Task.pool_item_id).all())
    kept = {int(i): int(n) for i, n in rows}
    return {it.id: max(0, int(it.cup_attempts or 0) - kept.get(it.id, 0)) for it in items}


def avoided_items(period: StudyPeriod, today: date, db: Session | None = None) -> list[PoolItem]:
    """K44: 3+ kez kaba girip DÖNDÜ · 3. devir · AVOID_IDLE_DAYS gündür hiç kaba alınmadı.
    `db` verilirse dönüş sayısı gerçek (cup_returns); verilmezse kaba alınma sayısı kullanılır."""
    return [it for it in avoid_reasons(period, today, db)]


def avoid_reasons(period: StudyPeriod, today: date, db: Session | None = None) -> dict[PoolItem, str]:
    # Onay bekleyen / reddedilen öğrenci kalemi henüz havuzun işi değil → kaçınma sayılmaz.
    live = [it for it in period.items
            if it.removed_at is None and it.remaining > 0 and it.counts_toward_pool]
    returns = cup_returns(db, live) if db is not None else {it.id: int(it.cup_attempts or 0) for it in live}
    out: dict[PoolItem, str] = {}
    for it in live:
        r = returns.get(it.id, 0)
        # "Hiç kaba alınmadı" süresi kalemin HAVUZA GİRDİĞİ günden ölçülür (dönem
        # ortasında eklenen kalem, dönemin yaşıyla suçlanmaz).
        since = max(period.opened_on, tr_date(it.created_at) or period.opened_on)
        idle_days = (today - since).days
        if r >= CUP_AVOID_THRESHOLD:
            out[it] = f"{r} kez kaba girip geri döndü"
        elif (it.carry_count or 0) >= CARRY_AVOID_THRESHOLD:
            out[it] = f"{it.carry_count}. kez devrediliyor"
        elif idle_days >= AVOID_IDLE_DAYS and (it.cup_attempts or 0) == 0 and it.done_units == 0:
            out[it] = f"{idle_days} gündür hiç kaba alınmadı"
    return out


def exam_strip(db: Session, *, student: User, period: StudyPeriod) -> dict | None:
    """K21: son deneme (net + aynı serideki öncekine fark) · yanlış konular · bu dönem
    çalışılan konulardan denemede kaçırılan."""
    from app.models.exam_result import EQ_RESULT_YANLIS, ExamResult, ExamResultQuestion
    from app.services.exam_scope import series_key

    exams = (db.query(ExamResult).filter(ExamResult.student_id == student.id)
             .order_by(ExamResult.exam_date.desc(), ExamResult.id.desc()).limit(12).all())
    if not exams:
        return None
    last = exams[0]
    key = series_key(last)
    prev = next((e for e in exams[1:] if series_key(e) == key), None)
    delta = round(float(last.net) - float(prev.net), 2) if prev is not None else None
    wrong_rows = (db.query(ExamResultQuestion.topic_id, func.count(ExamResultQuestion.id))
                  .filter(ExamResultQuestion.exam_result_id == last.id,
                          ExamResultQuestion.result == EQ_RESULT_YANLIS,
                          ExamResultQuestion.topic_id.isnot(None))
                  .group_by(ExamResultQuestion.topic_id).all())
    wrong = {int(t): int(n) for t, n in wrong_rows}
    tnames = {t.id: t.name for t in db.query(Topic).filter(Topic.id.in_(wrong.keys())).all()} if wrong else {}
    studied = {it.topic_id for it in period.items if it.topic_id and it.removed_at is None and it.done_units > 0}
    wrong_list = sorted(wrong.items(), key=lambda kv: -kv[1])
    return {
        "exam_id": last.id, "title": last.title, "exam_date": last.exam_date.isoformat(),
        "net": float(last.net), "delta": delta, "prev_title": prev.title if prev else None,
        "in_period": last.exam_date >= period.opened_on,
        "wrong_topics": [{"topic_id": t, "name": tnames.get(t, "—"), "wrong": n} for t, n in wrong_list[:8]],
        "studied_but_wrong": [{"topic_id": t, "name": tnames.get(t, "—"), "wrong": n}
                              for t, n in wrong_list if t in studied],
    }


def finish_session(
    db: Session, *, student: User, coach: User, period: StudyPeriod, closed_on: date,
    expected_next_on: date | None, carry: list[tuple[int, int | None]],
    record_session: bool, agenda: str | None, coach_note: str | None, next_change: str | None,
    mood: int | None, new_period_note: str | None = None,
) -> tuple[StudyPeriod, object | None]:
    """K22/K32: dönemi kapat → (isteğe bağlı) seans kaydı → yeni dönem → seçili kalemleri devret.
    Tek işlem; herhangi bir adım düşerse hiçbiri yazılmaz (çağıran commit eder)."""
    from app.models import CoachingSession
    from app.models.coaching_session import CoachingChannel, CoachingSessionStatus

    leftovers = {it.id: it for it in close_period(db, period, closed_on=closed_on, status=PERIOD_CLOSED)}
    session = None
    if record_session:
        session = CoachingSession(coach_id=coach.id, student_id=student.id, session_date=closed_on,
                                  status=CoachingSessionStatus.DONE, channel=CoachingChannel.IN_PERSON,
                                  agenda=(agenda or "Haftalık havuz değerlendirmesi")[:5000],
                                  coach_note=(coach_note or None), next_change=(next_change or None),
                                  mood=mood)
        db.add(session)
        db.flush()
        period.closed_session_id = session.id
    new_p = open_period(db, student=student, coach=coach, opened_on=closed_on,
                        session_id=session.id if session else None, expected_next_on=expected_next_on,
                        note=new_period_note)
    for item_id, qty in carry:
        it = leftovers.get(item_id)
        if it is None:
            raise PoolError("carry_not_leftover", "Devredilecek kalem bu dönemin kalanlarında yok.")
        carry_item(db, item=it, target=new_p, student=student, coach=coach, quantity=qty)
    db.flush()
    return new_p, session
