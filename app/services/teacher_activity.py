"""Öğretmen aktivite ölçümü — heatmap görünümü için günlük skor.

Aktivite kaynakları:
- LOGIN_SUCCESS audit kayıtları (öğretmen sisteme girdi mi?)
- Task.created_at (öğretmen, kendi öğrencilerine yeni görev oluşturdu mu?)
- TeacherNoteToParent.created_at (öğretmen, veliye not iletti mi?)

Tüm metrikler kurum bazlı filtrelenir; cross-tenant sızıntı yok.

Performans:
- 50 öğretmen × 28 gün = 1400 hücre
- Tek SQL ile group by (teacher, day) — 3 kaynak için 3 sorgu
- Python tarafında dict birleştirme; matrix oluşturma O(N×D)

Skor hesabı (0..1, erken doygunluk — gerçek günlük aktivite koyu yeşile ulaşsın):
- Giriş (login): VAR ise taban 0.25 + giriş yoğunluğu (≤5 girişte 0.15'e doğar)
  → giriş yapılan gün tek başına ~level 2 (görünür yeşil). Eski "binary +1 / 16"
  hatası: 23 giriş + 2 task neredeyse beyaz kalıyordu (0.19) — düzeltildi.
- Task: günde 5 task'ta doygun → 0.40 ağırlık
- Note: günde 3 not'ta doygun → 0.20 ağırlık
- activity_score = min(1.0, login_pay + task_pay + note_pay)

Bu skor öznel — UI sadece ısı göstergesi olarak kullanır (yeşilin tonu).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AuditAction,
    AuditLog,
    Task,
    User,
    UserRole,
)


logger = logging.getLogger(__name__)


# Skor sabitleri — erken doygunluk: gerçek bir aktif gün koyu yeşile ulaşmalı.
LOGIN_BASE = 0.25       # giriş yapılan gün tabanı (tek başına ~level 2 = görünür)
LOGIN_INTENSITY = 0.15  # giriş yoğunluğu ek payı (LOGIN_SAT girişte tam)
LOGIN_SAT = 5           # bu kadar girişte yoğunluk payı doygun
TASK_SAT = 5            # günde bu kadar task'ta task payı doygun
NOTE_SAT = 3            # günde bu kadar not'ta not payı doygun
TASK_WEIGHT = 0.40      # task payı toplam ağırlığı
NOTE_WEIGHT = 0.20      # note payı toplam ağırlığı
INACTIVE_DAYS = 7       # bu kadar gün hiç aktivite yok = pasif
ONBOARDING_GRACE_DAYS = 3  # yeni öğretmen (hesap < bu) hiç aktivitesiz → "pasif" değil "yeni"


@dataclass
class HeatmapCell:
    day: date
    login_count: int = 0
    tasks_created: int = 0
    notes_created: int = 0
    activity_score: float = 0.0     # 0..1, UI'da renk yoğunluğuna dönüşür

    def is_active(self) -> bool:
        return self.login_count > 0 or self.tasks_created > 0 or self.notes_created > 0


@dataclass
class TeacherHeatmap:
    teacher: User
    cells: list[HeatmapCell]            # günlere göre sıralı (eski → yeni)
    last_active_day: date | None = None
    total_logins: int = 0
    total_tasks: int = 0
    total_notes: int = 0
    is_inactive: bool = False           # son INACTIVE_DAYS hiç aktivite yok
    is_new: bool = False                # yeni hesap (onboarding) + henüz aktivite yok

    @property
    def days_since_active(self) -> int | None:
        if self.last_active_day is None:
            return None
        today = date.today()
        return max(0, (today - self.last_active_day).days)


# ---------------------------- Helpers ----------------------------


def _to_date(value) -> date:
    """SQLite func.date() string döner ('YYYY-MM-DD'); diğer DB'lerde date.

    Hem string hem date'i kabul edip date'e çevirir.
    """
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise TypeError(f"Beklenmedik tarih tipi: {type(value)} = {value!r}")


def _login_counts_per_teacher_per_day(
    db: Session, *, teacher_ids: list[int], start: date, end: date,
) -> dict[tuple[int, date], int]:
    """Tek SQL: (teacher_id, day) → login_count."""
    if not teacher_ids:
        return {}
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    rows = (
        db.query(
            AuditLog.actor_id.label("tid"),
            func.date(AuditLog.created_at).label("day"),
            func.count(AuditLog.id).label("cnt"),
        )
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(teacher_ids),
            AuditLog.created_at >= start_dt,
            AuditLog.created_at < end_dt,
        )
        .group_by(AuditLog.actor_id, func.date(AuditLog.created_at))
        .all()
    )
    return {(r.tid, _to_date(r.day)): int(r.cnt) for r in rows}


def _tasks_created_per_teacher_per_day(
    db: Session, *, teacher_ids: list[int], start: date, end: date,
) -> dict[tuple[int, date], int]:
    """Öğretmenin kendi öğrencileri için oluşturduğu task'lar (Task.student.teacher_id).

    Task.created_at zamana bakar (Task.date değil — task hangi gün için planlandığı
    farklı, hangi gün oluşturulduğu farklı; aktivite ölçümü oluşturma günü).
    """
    if not teacher_ids:
        return {}
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    rows = (
        db.query(
            User.teacher_id.label("tid"),
            func.date(Task.created_at).label("day"),
            func.count(Task.id).label("cnt"),
        )
        .select_from(Task)
        .join(User, User.id == Task.student_id)
        .filter(
            User.teacher_id.in_(teacher_ids),
            User.role == UserRole.STUDENT,
            Task.created_at >= start_dt,
            Task.created_at < end_dt,
        )
        .group_by(User.teacher_id, func.date(Task.created_at))
        .all()
    )
    return {(r.tid, _to_date(r.day)): int(r.cnt) for r in rows}


def _notes_created_per_teacher_per_day(
    db: Session, *, teacher_ids: list[int], start: date, end: date,
) -> dict[tuple[int, date], int]:
    """Öğretmenin veliye yazdığı not sayısı."""
    if not teacher_ids:
        return {}
    # TeacherNoteToParent modeli (parent.py içinde)
    from app.models.parent import TeacherNoteToParent
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    rows = (
        db.query(
            TeacherNoteToParent.teacher_id.label("tid"),
            func.date(TeacherNoteToParent.created_at).label("day"),
            func.count(TeacherNoteToParent.id).label("cnt"),
        )
        .filter(
            TeacherNoteToParent.teacher_id.in_(teacher_ids),
            TeacherNoteToParent.created_at >= start_dt,
            TeacherNoteToParent.created_at < end_dt,
        )
        .group_by(TeacherNoteToParent.teacher_id, func.date(TeacherNoteToParent.created_at))
        .all()
    )
    return {(r.tid, _to_date(r.day)): int(r.cnt) for r in rows}


def _compute_score(login: int, tasks: int, notes: int) -> float:
    """0..1 normalize skor — erken doygunluk (gerçek aktif gün koyu yeşil olur)."""
    score = 0.0
    if login > 0:
        score += LOGIN_BASE + LOGIN_INTENSITY * (min(login, LOGIN_SAT) / LOGIN_SAT)
    if tasks > 0:
        score += TASK_WEIGHT * (min(tasks, TASK_SAT) / TASK_SAT)
    if notes > 0:
        score += NOTE_WEIGHT * (min(notes, NOTE_SAT) / NOTE_SAT)
    return round(min(1.0, score), 3)


# ---------------------------- Public API ----------------------------


def teacher_activity_heatmap(
    db: Session,
    *,
    institution_id: int,
    weeks: int = 4,
    today: date | None = None,
) -> list[TeacherHeatmap]:
    """Kurumdaki tüm öğretmenler için son N hafta aktivite ısı haritası.

    Teacher listesi: full_name'e göre alfabetik sıralı.
    """
    if today is None:
        today = date.today()
    if weeks < 1:
        weeks = 1
    if weeks > 26:
        weeks = 26   # üst sınır — abuse'a karşı

    days_count = weeks * 7
    start = today - timedelta(days=days_count - 1)

    teachers = (
        db.query(User)
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.TEACHER,
        )
        .order_by(User.full_name)
        .all()
    )
    if not teachers:
        return []
    teacher_ids = [t.id for t in teachers]

    logins = _login_counts_per_teacher_per_day(
        db, teacher_ids=teacher_ids, start=start, end=today
    )
    tasks = _tasks_created_per_teacher_per_day(
        db, teacher_ids=teacher_ids, start=start, end=today
    )
    notes = _notes_created_per_teacher_per_day(
        db, teacher_ids=teacher_ids, start=start, end=today
    )

    out: list[TeacherHeatmap] = []
    for t in teachers:
        cells: list[HeatmapCell] = []
        last_active: date | None = None
        total_logins = 0
        total_tasks = 0
        total_notes = 0
        for offset in range(days_count):
            day = start + timedelta(days=offset)
            li = logins.get((t.id, day), 0)
            ta = tasks.get((t.id, day), 0)
            no = notes.get((t.id, day), 0)
            score = _compute_score(li, ta, no)
            cell = HeatmapCell(
                day=day,
                login_count=li,
                tasks_created=ta,
                notes_created=no,
                activity_score=score,
            )
            cells.append(cell)
            if cell.is_active():
                last_active = day
                total_logins += li
                total_tasks += ta
                total_notes += no

        # Onboarding grace: yeni oluşturulmuş öğretmen (hesap < grace) henüz hiç
        # aktivite üretmediyse "pasif" DEĞİL "yeni" sayılır — yanlış-pozitif önler.
        # (Kullanıcı 2026-05-23 — yeni öğretmen pasif işaretleniyordu.)
        account_age_days = (
            (today - t.created_at.date()).days if t.created_at else None
        )
        is_new = (
            last_active is None
            and account_age_days is not None
            and account_age_days < ONBOARDING_GRACE_DAYS
        )
        is_inactive = (not is_new) and (
            last_active is None
            or (today - last_active).days > INACTIVE_DAYS
        )
        out.append(TeacherHeatmap(
            teacher=t,
            cells=cells,
            last_active_day=last_active,
            total_logins=total_logins,
            total_tasks=total_tasks,
            total_notes=total_notes,
            is_inactive=is_inactive,
            is_new=is_new,
        ))
    return out


def inactive_teachers(
    db: Session, *, institution_id: int, days: int = INACTIVE_DAYS, today: date | None = None,
) -> list[User]:
    """Son N gündür hiç aktivite olmayan öğretmenleri döner — dashboard callout için.

    "Aktivite" tanımı: LOGIN_SUCCESS audit kaydı son N günde varsa aktif sayılır.
    Task/note kontrolleri dashboards'a aşırı yük olur; login yeterli proxy.
    """
    if today is None:
        today = date.today()
    cutoff = datetime.combine(today - timedelta(days=days), datetime.min.time(), tzinfo=timezone.utc)
    teachers = (
        db.query(User)
        .filter(
            User.institution_id == institution_id,
            User.role == UserRole.TEACHER,
            User.is_active.is_(True),
        )
        .all()
    )
    if not teachers:
        return []
    teacher_ids = [t.id for t in teachers]
    # Son aktivite zamanını al
    active_subq = (
        db.query(
            AuditLog.actor_id.label("tid"),
            func.max(AuditLog.created_at).label("last_active"),
        )
        .filter(
            AuditLog.action == AuditAction.LOGIN_SUCCESS,
            AuditLog.actor_id.in_(teacher_ids),
        )
        .group_by(AuditLog.actor_id)
        .all()
    )
    last_active_map = {r.tid: r.last_active for r in active_subq}

    out: list[User] = []
    for t in teachers:
        la = last_active_map.get(t.id)
        if la is None:
            # Onboarding grace: hiç giriş yapmamış YENİ öğretmen (hesap < grace)
            # "pasif" sayılmaz — yanlış-pozitif önler (heatmap ile tutarlı).
            age = (today - t.created_at.date()).days if t.created_at else None
            if age is None or age >= ONBOARDING_GRACE_DAYS:
                out.append(t)
            continue
        if la.tzinfo is None:
            la = la.replace(tzinfo=timezone.utc)
        if la < cutoff:
            out.append(t)
    return out
