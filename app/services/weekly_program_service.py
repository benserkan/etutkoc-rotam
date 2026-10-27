"""WeeklyProgram servisi — koç "Yeni Program Oluştur" akışı (WP1).

Kullanıcı kararları (2026-05-31):
  - Süre: 1-14 gün arası (yanlışlıkla 365 gün yazma engellenir)
  - Mevcut öğrenciler: koç ilk girişte mavi banner + tek tık "Eski Dönem programı"
  - Anchor kavramı UI'dan kaldırıldı

Çakışma politikası:
  - Sistem **uyarı verir**, koç karar verir (3 seçenek: ESKİYİ KISALT,
    YENİYİ KISALT, İPTAL). Otomatik silme yok.
  - Bu servis sadece çakışmaları tespit eder (`find_overlapping`); endpoint
    çakışma varsa kullanıcıya soracak.

Geri uyumluluk: program yoksa hafta sayfası eski anchor-blok mantığını
kullanır (fallback). Bozulma yok.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Task, User, UserRole, WeeklyProgram
from app.models.task import TaskStatus


logger = logging.getLogger(__name__)


MIN_DAYS = 1
MAX_DAYS = 14


class ProgramError(Exception):
    """Servis seviyesi hata — endpoint HTTPException'a çevirir."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class ProgramOverlap:
    """Çakışan başka programın özeti (UI uyarısı için)."""

    program_id: int
    label: str
    start_date: date
    end_date: date
    overlap_days: int
    task_count_in_overlap: int  # çakışan günlerdeki kaç görev var (silme kararı için)
    # Eski program yeni programdan ÖNCE başlıyorsa, yeni başlangıçtan bir gün önce
    # bitirilerek çakışma kaldırılabilir (seans erkene alındı / program erken bitti).
    trimmable: bool = False
    trim_to: date | None = None
    # Erken bitirmede kesilen günler [yeni başlangıç, eski bitiş] — görev kırılımı
    cut_days: int = 0
    cut_untouched: int = 0      # hiç başlanmamış (iade seçilirse silinir)
    cut_partial: int = 0        # kısmen yapılmış (kalır, yapılmamış kısmın rezervi iade)
    cut_completed: int = 0      # tamamlanmış (dokunulmaz)
    cut_release_tests: int = 0  # iade seçilirse kitaba dönecek test


EARLY_END_TRANSFER = "transfer"  # kesilen günlerin görevleri yeni programa aynen geçer
EARLY_END_REFUND = "refund"      # başlanmamışlar silinir + rezerv iade, kısmi kalanın rezervi iade
EARLY_END_MODES = (EARLY_END_TRANSFER, EARLY_END_REFUND)
EARLY_END_REASON_MIN = 3


def _cut_tasks(db: Session, student_id: int, start: date, end: date) -> list[Task]:
    from sqlalchemy.orm import joinedload

    return (db.query(Task).options(joinedload(Task.book_items))
            .filter(Task.student_id == student_id, Task.date >= start, Task.date <= end)
            .order_by(Task.date, Task.id).all())


def _task_progress(t: Task) -> int:
    return sum(int(it.completed_count or 0) for it in t.book_items) + int(t.solved_count or 0)


def _live_reserve(t: Task) -> int:
    return sum(max(0, int(it.planned_count or 0) - int(it.completed_count or 0))
               for it in t.book_items
               if it.book_id is not None and it.reservation_released_at is None)


# =============================================================================
# Helpers
# =============================================================================


def _validate_range(start: date, end: date) -> None:
    """Tarih sırası + 1-14 gün aralığı kontrolü."""
    if end < start:
        raise ProgramError(
            "invalid_range",
            "Bitiş tarihi başlangıç tarihinden önce olamaz.",
        )
    days = (end - start).days + 1
    if days < MIN_DAYS:
        raise ProgramError(
            "too_short", f"Program en az {MIN_DAYS} gün olmalı."
        )
    if days > MAX_DAYS:
        raise ProgramError(
            "too_long",
            f"Program en fazla {MAX_DAYS} gün olabilir "
            f"(seçilen: {days} gün). Daha uzun bir blok için ayrı program oluşturun.",
        )


def _ensure_owned_student(db: Session, student_id: int, coach_id: int) -> User:
    """Sahiplik kontrolü — başka koçun öğrencisi 404 (servis seviyesi).

    Sahibi olmayan koç ProgramError("not_found") alır.
    """
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == coach_id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if student is None:
        raise ProgramError("not_found", "Öğrenci bulunamadı veya erişiminiz yok.")
    return student


def _owned_program(db: Session, program_id: int, coach_id: int) -> WeeklyProgram:
    """Program'ı bul + koç-sahiplik doğrula."""
    prog = db.get(WeeklyProgram, program_id)
    if prog is None:
        raise ProgramError("not_found", "Program bulunamadı.")
    # Öğrencinin teacher_id'si üzerinden doğrula (coach_id NULL olabilir SET NULL)
    student = db.get(User, prog.student_id)
    if student is None or student.teacher_id != coach_id:
        raise ProgramError("not_found", "Program bulunamadı.")
    return prog


# =============================================================================
# CRUD
# =============================================================================


def find_overlapping(
    db: Session,
    *,
    student_id: int,
    start: date,
    end: date,
    exclude_id: int | None = None,
) -> list[ProgramOverlap]:
    """Verilen tarih aralığıyla çakışan programları döndürür.

    Çakışma kriteri: [start, end] ile [prog.start_date, prog.end_date]
    kümeleri kesişiyorsa (a.start ≤ b.end VE b.start ≤ a.end).

    `exclude_id`: PATCH durumunda kendi program'ını hariç tut.
    """
    q = (
        db.query(WeeklyProgram)
        .filter(
            WeeklyProgram.student_id == student_id,
            WeeklyProgram.start_date <= end,
            WeeklyProgram.end_date >= start,
        )
        .order_by(WeeklyProgram.start_date.asc())
    )
    if exclude_id is not None:
        q = q.filter(WeeklyProgram.id != exclude_id)

    out: list[ProgramOverlap] = []
    for p in q.all():
        ov_start = max(p.start_date, start)
        ov_end = min(p.end_date, end)
        ov_days = (ov_end - ov_start).days + 1
        # Çakışan günlerdeki görev sayısı (silme kararı için info)
        task_count = (
            db.query(Task)
            .filter(
                Task.student_id == student_id,
                Task.date >= ov_start,
                Task.date <= ov_end,
            )
            .count()
        )
        trimmable = p.start_date < start
        cut = dict(days=0, untouched=0, partial=0, completed=0, release=0)
        if trimmable:
            cut["days"] = (p.end_date - start).days + 1
            for t in _cut_tasks(db, student_id, start, p.end_date):
                if t.status == TaskStatus.COMPLETED:
                    cut["completed"] += 1
                    continue
                cut["release"] += _live_reserve(t)
                if _task_progress(t) > 0:
                    cut["partial"] += 1
                else:
                    cut["untouched"] += 1
        out.append(ProgramOverlap(
            program_id=p.id,
            label=p.label,
            start_date=p.start_date,
            end_date=p.end_date,
            overlap_days=ov_days,
            task_count_in_overlap=task_count,
            trimmable=trimmable,
            trim_to=(start - timedelta(days=1)) if trimmable else None,
            cut_days=cut["days"], cut_untouched=cut["untouched"], cut_partial=cut["partial"],
            cut_completed=cut["completed"], cut_release_tests=cut["release"],
        ))
    return out


def create_program(
    db: Session,
    *,
    coach: User,
    student_id: int,
    start: date,
    end: date,
    name: str | None = None,
    notes: str | None = None,
    allow_overlap: bool = False,
    early_end_reason: str | None = None,
    early_end_mode: str | None = None,
) -> WeeklyProgram:
    """Yeni program yarat.

    ERKEN BİTİRME (koç eski program bitmeden yeni program başlatır): yeni
    programdan ÖNCE başlayan çakışan program yeni başlangıçtan bir gün önce
    bitirilir. Gerekçe ZORUNLU (eski programın notuna yazılır). Kesilen günlerin
    görevleri için `early_end_mode`:
      · transfer — görevler tarihlerinde kalır, yeni programın parçası olur
      · refund   — başlanmamış görevler silinir ve testleri kitaba iade edilir;
                   kısmen yapılanlar kalır, yapılmamış kısmın rezervi iade edilir;
                   tamamlananlara dokunulmaz
    Aynı gün ya da sonra başlayan çakışan program kırpılamaz → "overlap".

    `allow_overlap=False` (default): çakışan program varsa ProgramError("overlap")
    fırlatır. Endpoint bu durumu yakalayıp kullanıcıya seçenek dialog'u sunar.

    `allow_overlap=True`: kullanıcı uyarıyı gördü ve onayladı; program çakışsa
    bile yaratılır (eski program'a dokunulmaz, kullanıcı manuel olarak
    önceki adımda kısaltmış olabilir).
    """
    _validate_range(start, end)
    student = _ensure_owned_student(db, student_id, coach.id)

    overlaps = find_overlapping(db, student_id=student.id, start=start, end=end)
    trimmable = [o for o in overlaps if o.trimmable]
    if trimmable and early_end_mode is not None:
        reason = (early_end_reason or "").strip()
        if len(reason) < EARLY_END_REASON_MIN:
            raise ProgramError("early_end_reason_required",
                               "Önceki programı erken bitirmenin nedenini yazın.")
        if early_end_mode not in EARLY_END_MODES:
            raise ProgramError("early_end_mode_invalid", "Kalan günlerin görevleri için bir seçim yapın.")
        for o in trimmable:
            old = db.get(WeeklyProgram, o.program_id)
            if old is None:
                continue
            if early_end_mode == EARLY_END_REFUND:
                _refund_cut_tasks(db, student.id, start, old.end_date)
            what = "yeni programa aktarıldı" if early_end_mode == EARLY_END_TRANSFER else "iade edildi"
            stamp = (f"Erken bitirildi ({old.end_date.strftime('%d.%m')} yerine "
                     f"{o.trim_to.strftime('%d.%m')}): {reason} · kalan günler: {what}")
            old.notes = (f"{old.notes}\n{stamp}" if old.notes else stamp)[:2000]
            logger.info("create_program: early end prog=%s %s→%s mode=%s",
                        old.id, old.end_date, o.trim_to, early_end_mode)
            old.end_date = o.trim_to
        overlaps = [o for o in overlaps if not o.trimmable]
    if overlaps and not allow_overlap:
        # Endpoint'in bu hatayı detail içinde döndürmesi için
        raise ProgramError("overlap", "Bu tarih aralığında çakışan program var.")

    prog = WeeklyProgram(
        student_id=student.id,
        coach_id=coach.id,
        start_date=start,
        end_date=end,
        name=(name or "").strip() or None,
        notes=(notes or "").strip() or None,
    )
    db.add(prog)
    db.flush()
    # "Ölü rezerv" telafisi: GEÇMİŞ haftalardan kalan tamamlanmamış görevlerin
    # rezervi serbest bırakılır → koç aynı üniteyi yeniden atayabilir. Best-effort.
    # KRİTİK: cutoff = min(program başlangıcı, BU HAFTANIN Pazartesi'si). Program
    # GELECEK tarihliyse (örn. bugün 06-27, program 06-29) cutoff=start kullanmak
    # bu haftanın (06-22..28) hâlâ aktif rezervlerini "ölü" sanıp serbest bırakır.
    # min(...) ile yalnız GERÇEKTEN geçmiş haftalar serbest kalır.
    try:
        from datetime import date as _date, timedelta as _td

        from app.services.task_service import reconcile_past_reservations

        _today = _date.today()
        _cutoff = min(start, _today - _td(days=_today.weekday()))
        reconcile_past_reservations(db, student_id=student.id, cutoff_date=_cutoff)
    except Exception:
        logger.exception("create_program: reconcile_past_reservations failed s=%s", student.id)
    logger.info(
        "create_program: coach=%s student=%s prog=%s %s→%s",
        coach.id, student.id, prog.id, start, end,
    )
    return prog


def _refund_cut_tasks(db: Session, student_id: int, start: date, end: date) -> None:
    """Kesilen günlerde: başlanmamış görevi sil (rezerv iade), kısmi görevin kalan rezervini bırak."""
    from datetime import timezone

    from app.services.task_service import release_item, release_task_items

    now = datetime.now(timezone.utc)
    for t in _cut_tasks(db, student_id, start, end):
        if t.status == TaskStatus.COMPLETED:
            continue
        if _task_progress(t) > 0:
            for it in t.book_items:
                if it.book_id is None or it.reservation_released_at is not None:
                    continue
                rem = max(0, int(it.planned_count or 0) - int(it.completed_count or 0))
                if rem > 0:
                    release_item(db, student_id=student_id, book_id=it.book_id,
                                 section_id=it.book_section_id, count=rem)
                it.reservation_released_at = now
            continue
        release_task_items(db, student_id, list(t.book_items))
        if t.carried_from_task_id is not None:
            src = db.get(Task, t.carried_from_task_id)
            if src is not None and src.carried_at is not None:
                src.carried_at = None
        db.delete(t)
    db.flush()


def update_program(
    db: Session,
    *,
    coach: User,
    program_id: int,
    start: date | None = None,
    end: date | None = None,
    name: str | None = None,
    notes: str | None = None,
    allow_overlap: bool = False,
) -> WeeklyProgram:
    """Program'ı güncelle (tarih/etiket/not). None geçilen alan değişmez.

    Çakışma kontrolü: tarih değişiyorsa yeni aralıkla başkalarıyla çakışıyor mu.
    """
    prog = _owned_program(db, program_id, coach.id)

    new_start = start if start is not None else prog.start_date
    new_end = end if end is not None else prog.end_date

    if start is not None or end is not None:
        _validate_range(new_start, new_end)
        if not allow_overlap:
            overlaps = find_overlapping(
                db,
                student_id=prog.student_id,
                start=new_start,
                end=new_end,
                exclude_id=prog.id,
            )
            if overlaps:
                raise ProgramError("overlap", "Bu tarih aralığında çakışan program var.")
        prog.start_date = new_start
        prog.end_date = new_end

    if name is not None:
        nc = name.strip()
        prog.name = nc or None
    if notes is not None:
        nc = notes.strip()
        prog.notes = nc or None

    db.flush()
    return prog


def delete_program(
    db: Session,
    *,
    coach: User,
    program_id: int,
    delete_tasks: bool = False,
) -> dict:
    """Program'ı sil.

    `delete_tasks=False` (default): görevler korunur (program-bağı zaten yok,
    tarih aralığı kapısı kavramı vardı). Sadece WeeklyProgram satırı silinir.
    `delete_tasks=True`: program tarih aralığındaki Task'lar da silinir
    (rezerv iadesi için release_task_items kullanılır).

    Returns: {deleted: 1, tasks_deleted: N}
    """
    from sqlalchemy import delete as sa_delete
    from app.services.task_service import release_task_items

    prog = _owned_program(db, program_id, coach.id)
    tasks_deleted = 0
    if delete_tasks:
        tasks = (
            db.query(Task)
            .filter(
                Task.student_id == prog.student_id,
                Task.date >= prog.start_date,
                Task.date <= prog.end_date,
            )
            .all()
        )
        for t in tasks:
            # 2026-09-27: eskiden `release_task_items(db, t)` (yanlış imza) +
            # geniş `except` vardı → TypeError sessizce yutuluyor, görev
            # rezervi İADE EDİLMEDEN siliniyordu (Zeynep #164: 22 bölümde 46
            # sahipsiz rezerv, "sayaç uyumsuz"). İade başarısızsa silme de
            # yapılmamalı — hata artık yukarı çıkar, işlem geri alınır.
            release_task_items(db, t.student_id, list(t.book_items))
            db.delete(t)
            tasks_deleted += 1

    db.delete(prog)
    db.flush()
    return {"deleted": 1, "tasks_deleted": tasks_deleted}


# =============================================================================
# Sorgular
# =============================================================================


def list_programs(db: Session, *, student_id: int) -> list[WeeklyProgram]:
    """Tüm programlar — en yeni → en eski (sayfa dropdown'u için)."""
    return (
        db.query(WeeklyProgram)
        .filter(WeeklyProgram.student_id == student_id)
        .order_by(WeeklyProgram.start_date.desc(), WeeklyProgram.id.desc())
        .all()
    )


def get_active_program(
    db: Session, *, student_id: int, today: date | None = None,
) -> WeeklyProgram | None:
    """Bugünü içeren program (varsa).

    Birden fazla program bugünü kapsıyorsa: en son oluşturulan döner (genelde
    bayram sonrası yeni yaratılan). Bu durum sıradışı (çakışma uyarısı
    çoğunlukla engeller) ama defansif kapsama.
    """
    if today is None:
        today = date.today()
    return (
        db.query(WeeklyProgram)
        .filter(
            WeeklyProgram.student_id == student_id,
            WeeklyProgram.start_date <= today,
            WeeklyProgram.end_date >= today,
        )
        .order_by(WeeklyProgram.start_date.desc(), WeeklyProgram.created_at.desc())
        .first()
    )


def active_program_id(programs, today: date) -> int | None:
    """Bugünü içeren programlardan geçerli olan: en geç BAŞLAYAN (aynıysa en son
    oluşturulan). Çakışan iki programın ikisi de "bu hafta" sayılmaz."""
    cands = [p for p in programs if p.start_date <= today <= p.end_date]
    if not cands:
        return None
    return max(cands, key=lambda p: (p.start_date, p.created_at or datetime.min)).id


def get_most_recent_program(
    db: Session, *, student_id: int, today: date | None = None,
) -> WeeklyProgram | None:
    """Aktif yoksa fallback: en yakın gelecekteki veya en son geçmişteki.

    Sayfayı boş bırakmamak için: aktif yoksa "en yakın program" gösterilir.
    """
    if today is None:
        today = date.today()
    # Önce gelecekteki en yakın
    future = (
        db.query(WeeklyProgram)
        .filter(
            WeeklyProgram.student_id == student_id,
            WeeklyProgram.start_date > today,
        )
        .order_by(WeeklyProgram.start_date.asc())
        .first()
    )
    if future is not None:
        return future
    # Yoksa son geçmiş
    return (
        db.query(WeeklyProgram)
        .filter(
            WeeklyProgram.student_id == student_id,
            WeeklyProgram.end_date < today,
        )
        .order_by(WeeklyProgram.end_date.desc())
        .first()
    )


def effective_end(db: Session, prog: WeeklyProgram) -> date:
    """Programın GEÇERLİ bitişi: içine sonradan başlayan bir program düşüyorsa o
    programın başlangıcından bir gün önce (erken bitirme). Analiz (`weekly_progress
    ._program_weeks`) aynı kuralla keser; hafta görünümü ve yayın aralığı da bunu kullanır
    ki kesilen gün eski haftada "yapılmadı" diye görünmesin."""
    nxt = (
        db.query(WeeklyProgram.start_date)
        .filter(WeeklyProgram.student_id == prog.student_id, WeeklyProgram.id != prog.id,
                WeeklyProgram.start_date > prog.start_date,
                WeeklyProgram.start_date <= prog.end_date)
        .order_by(WeeklyProgram.start_date.asc())
        .first()
    )
    return (nxt[0] - timedelta(days=1)) if nxt else prog.end_date


def get_previous_program(
    db: Session, *, student_id: int, before_date: date,
) -> WeeklyProgram | None:
    """`before_date`'ten ÖNCE biten en son program (bir önceki hafta).

    Devret panelini yalnız 'geçen hafta' ile sınırlamak için kullanılır
    (tatil/boşluk olsa bile 'son yapılan program').
    """
    return (
        db.query(WeeklyProgram)
        .filter(
            WeeklyProgram.student_id == student_id,
            WeeklyProgram.end_date < before_date,
        )
        .order_by(WeeklyProgram.end_date.desc())
        .first()
    )


# =============================================================================
# Wrap-legacy: eski görevleri tek programa bağla (mevcut öğrenciler için)
# =============================================================================


def get_unlinked_task_summary(
    db: Session, *, student_id: int,
) -> dict | None:
    """Programa bağlı OLMAYAN görevlerin özeti (mavi banner için).

    "Programa bağlı değil" = Task'ın tarihi hiçbir WeeklyProgram aralığına
    düşmüyor. Mevcut öğrencilerde tüm görevler bu durumda.

    Returns: {count, earliest, latest} veya None (hiç unlinked yok).
    """
    # Önce öğrencinin tüm programları
    programs = list_programs(db, student_id=student_id)

    # Tüm görevlerin min/max + sayısı
    from sqlalchemy import func as sa_func

    agg = (
        db.query(
            sa_func.min(Task.date).label("earliest"),
            sa_func.max(Task.date).label("latest"),
            sa_func.count(Task.id).label("total"),
        )
        .filter(Task.student_id == student_id)
        .first()
    )
    if agg is None or agg.total == 0:
        return None

    if not programs:
        # Hiç program yok → tüm görevler unlinked
        return {
            "count": int(agg.total),
            "earliest": agg.earliest,
            "latest": agg.latest,
        }

    # Her görevi programa düşür → unlinked'leri say
    # NOT: SQL açısından "herhangi bir programa düşmeyen" daha optimum ama
    # küçük veri (max yüzlerce görev/öğrenci) → Python tarafı yeterli
    all_tasks = (
        db.query(Task.id, Task.date)
        .filter(Task.student_id == student_id)
        .all()
    )
    unlinked: list[date] = []
    for t in all_tasks:
        in_any = any(p.contains(t.date) for p in programs)
        if not in_any:
            unlinked.append(t.date)
    if not unlinked:
        return None
    return {
        "count": len(unlinked),
        "earliest": min(unlinked),
        "latest": max(unlinked),
    }


def wrap_legacy_tasks(
    db: Session, *, coach: User, student_id: int, name: str | None = None,
) -> WeeklyProgram:
    """Programa bağlı OLMAYAN tüm görevleri kapsayan tek "Eski Dönem" programı yarat.

    Tarihler: unlinked görevlerin en eski → en yeni. Çakışma kontrolü
    UYGULANMAZ (çünkü zaten programa bağlı olmayan görevleri sarıyoruz —
    mevcut program'larla zaten çakışmıyor; aksi halde unlinked sayılmazlardı).

    `name` boşsa "Eski Dönem" varsayılan etiketi.
    """
    student = _ensure_owned_student(db, student_id, coach.id)
    summary = get_unlinked_task_summary(db, student_id=student.id)
    if summary is None:
        raise ProgramError(
            "no_unlinked_tasks",
            "Bu öğrencinin programa bağlı olmayan görevi yok.",
        )

    earliest = summary["earliest"]
    latest = summary["latest"]
    days = (latest - earliest).days + 1
    if days > MAX_DAYS:
        # 14 günden uzun aralık → 2 program gerekir; ilk N gün, sonra koç
        # manuel ayarlar. Şimdilik en eski 14 günü kaplayan tek program yarat,
        # uyarı log'a düşer (UI sonra "kalan görevler için ayrıca yarat" der).
        latest = earliest + (latest - earliest)  # değişmez
        # Çoklu wrap için MAX_DAYS'lik pencereler
        # Basit yaklaşım: tek program 14 gün; kalanlar wrap_legacy tekrar çağrıldığında handle olur
        latest = min(latest, earliest.fromordinal(earliest.toordinal() + MAX_DAYS - 1))

    prog = WeeklyProgram(
        student_id=student.id,
        coach_id=coach.id,
        start_date=earliest,
        end_date=latest,
        name=(name or "Eski Dönem").strip() or "Eski Dönem",
    )
    db.add(prog)
    db.flush()
    logger.info(
        "wrap_legacy_tasks: coach=%s student=%s prog=%s wrapped %s tasks",
        coach.id, student.id, prog.id, summary["count"],
    )
    return prog
