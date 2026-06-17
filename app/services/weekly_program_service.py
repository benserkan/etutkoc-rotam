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
from datetime import date
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Task, User, UserRole, WeeklyProgram


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
        out.append(ProgramOverlap(
            program_id=p.id,
            label=p.label,
            start_date=p.start_date,
            end_date=p.end_date,
            overlap_days=ov_days,
            task_count_in_overlap=task_count,
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
) -> WeeklyProgram:
    """Yeni program yarat.

    `allow_overlap=False` (default): çakışan program varsa ProgramError("overlap")
    fırlatır. Endpoint bu durumu yakalayıp kullanıcıya seçenek dialog'u sunar.

    `allow_overlap=True`: kullanıcı uyarıyı gördü ve onayladı; program çakışsa
    bile yaratılır (eski program'a dokunulmaz, kullanıcı manuel olarak
    önceki adımda kısaltmış olabilir).
    """
    _validate_range(start, end)
    student = _ensure_owned_student(db, student_id, coach.id)

    if not allow_overlap:
        overlaps = find_overlapping(db, student_id=student.id, start=start, end=end)
        if overlaps:
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
    # "Ölü rezerv" telafisi: yeni program başlangıcından ÖNCEKİ haftalardan kalan,
    # tamamlanmamış görevlerin rezervi serbest bırakılır → koç aynı üniteyi yeni
    # haftada yeniden atayabilir (kapasite kilitli kalmaz). Best-effort.
    try:
        from app.services.task_service import reconcile_past_reservations

        reconcile_past_reservations(db, student_id=student.id, cutoff_date=start)
    except Exception:
        logger.exception("create_program: reconcile_past_reservations failed s=%s", student.id)
    logger.info(
        "create_program: coach=%s student=%s prog=%s %s→%s",
        coach.id, student.id, prog.id, start, end,
    )
    return prog


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
            try:
                release_task_items(db, t)
            except Exception:
                # Rezerv iadesi başarısız olsa bile devam et
                logger.exception("release_task_items failed for task %s", t.id)
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
        .order_by(WeeklyProgram.created_at.desc())
        .first()
    )


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
