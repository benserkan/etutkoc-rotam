"""Öğrenci sınıf dönemleri — TEK MERKEZ (P2, 2026-09-04).

Neden: öğrenci sınıf atlayınca geçmiş yılın görevleri/denemeleri/kitapları
yerinde kalıyor ve "bu yıl" ile karışıyordu (Yiğit Eren 8→9 saha vakası).
Bu servis yalnız DÖNEM SINIRINI kaydeder; hiçbir veri satırı taşınmaz,
silinmez, gizlenmez. Görünüm filtreleri ayrı pakette (P3) bu sınırı okuyacak.

SINIR KURALI
    başlangıç = min(yükseltme tarihi, aynı takvim yılının 1 Eylül'ü)
    (alt sınır: önceki dönemin başlangıcından en az 1 gün sonra)

  · Geç yükseltme  — koç 10 Ekim'de yükseltir → sınır 1 Eylül'e çekilir,
    Eylül-Ekim'de yapılan çalışma YENİ sınıfa yazılır.
  · Erken yükseltme — koç 15 Temmuz'da (yaz kampı) yükseltir → sınır 15
    Temmuz kalır, yaz çalışması ESKİ sınıfa karışmaz.

DAMGA NEREDE ATILIR (kritik ayrım)
  · Sınıf Yükseltme (toplu `grade-advance/apply` + tekil `students/{id}/promote`)
    → YENİ DÖNEM açar. "Yeni öğretim yılına geçiş" demektir.
  · Profil Düzenle'den sınıf değişikliği (`PATCH students/{id}`)
    → yeni dönem AÇMAZ, güncel dönemi düzeltir. "Yanlış girilmiş bilgiyi
      düzeltme" demektir; aksi halde bir yazım hatası sahte dönem açıp veriyi
      ikiye bölerdi.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import StudentGradePeriod, User

# Öğretim yılı sınırı — 1 Eylül.
ACADEMIC_MONTH = 9
ACADEMIC_DAY = 1


# =============================================================================
# Tarih yardımcıları
# =============================================================================


def academic_year_start_date(d: date) -> date:
    """`d` tarihinin ait olduğu öğretim yılının 1 Eylül'ü.

    2026-09-04 → 2026-09-01 · 2026-05-20 → 2025-09-01
    """
    year = d.year if (d.month, d.day) >= (ACADEMIC_MONTH, ACADEMIC_DAY) else d.year - 1
    return date(year, ACADEMIC_MONTH, ACADEMIC_DAY)


def compute_boundary(
    advance_date: date, previous_started_on: date | None = None
) -> date:
    """Yeni dönemin başlangıç tarihi (yukarıdaki SINIR KURALI)."""
    boundary = min(advance_date, date(advance_date.year, ACADEMIC_MONTH, ACADEMIC_DAY))
    if previous_started_on is not None and boundary <= previous_started_on:
        # Aynı dönem içinde ikinci yükseltme: sıfır/negatif uzunlukta dönem olmaz.
        boundary = previous_started_on + timedelta(days=1)
    return boundary


# =============================================================================
# Anlık görüntü
# =============================================================================


def snapshot_of(student: User) -> dict:
    """Öğrencinin şu anki profilinden dönem alanları."""
    model = student.effective_curriculum_model
    return {
        "grade_level": student.grade_level,
        "is_graduate": bool(student.is_graduate),
        "curriculum_model": getattr(model, "value", None),
        "track": getattr(student.track, "value", None),
        "academic_year_id": student.academic_year_id,
    }


# =============================================================================
# Okuma
# =============================================================================


def list_periods(db: Session, student_id: int) -> list[StudentGradePeriod]:
    """Dönemler — en yeni önce."""
    return (
        db.query(StudentGradePeriod)
        .filter(StudentGradePeriod.student_id == student_id)
        .order_by(StudentGradePeriod.started_on.desc(), StudentGradePeriod.id.desc())
        .all()
    )


def current_period(db: Session, student_id: int) -> StudentGradePeriod | None:
    """Güncel dönem (`ended_on IS NULL`)."""
    return (
        db.query(StudentGradePeriod)
        .filter(
            StudentGradePeriod.student_id == student_id,
            StudentGradePeriod.ended_on.is_(None),
        )
        .order_by(StudentGradePeriod.started_on.desc())
        .first()
    )


def period_for_date(
    db: Session, student_id: int, d: date
) -> StudentGradePeriod | None:
    """Verilen tarihin düştüğü dönem (P3 filtreleri için)."""
    rows = (
        db.query(StudentGradePeriod)
        .filter(
            StudentGradePeriod.student_id == student_id,
            StudentGradePeriod.started_on <= d,
        )
        .order_by(StudentGradePeriod.started_on.desc())
        .all()
    )
    for p in rows:
        if p.ended_on is None or d <= p.ended_on:
            return p
    return None


# =============================================================================
# Yazma — commit ÇAĞIRANA aittir (mevcut işleme katılır)
# =============================================================================


def ensure_current(
    db: Session, student: User, *, started_on: date | None = None
) -> StudentGradePeriod:
    """Güncel dönem yoksa aç (lazy). Varsa olduğu gibi döndür."""
    cur = current_period(db, student.id)
    if cur is not None:
        return cur
    start = started_on
    if start is None:
        created = getattr(student, "created_at", None)
        start = created.date() if created is not None else date.today()
    p = StudentGradePeriod(
        student_id=student.id, started_on=start, **snapshot_of(student)
    )
    db.add(p)
    db.flush()
    return p


def stamp_advance(
    db: Session,
    student: User,
    *,
    previous_snapshot: dict,
    advance_date: date | None = None,
) -> StudentGradePeriod:
    """Sınıf yükseltmesini damgala: önceki dönemi kapat, yenisini aç.

    ÇAĞRI SIRASI: profil alanları YENİ değerlere yazıldıktan sonra çağrılır;
    `previous_snapshot` yazımdan ÖNCE `snapshot_of(student)` ile alınmalıdır
    (kapanan dönem eski sınıfı taşımalı).
    """
    today = advance_date or date.today()

    prev = current_period(db, student.id)
    if prev is None:
        # Hiç dönem yoksa: eski profille geçmiş dönemi geriye dönük aç.
        created = getattr(student, "created_at", None)
        start = created.date() if created is not None else today
        boundary = compute_boundary(today, start)
        prev = StudentGradePeriod(
            student_id=student.id,
            started_on=min(start, boundary - timedelta(days=1)),
            **previous_snapshot,
        )
        db.add(prev)
        db.flush()
    else:
        boundary = compute_boundary(today, prev.started_on)

    prev.ended_on = boundary - timedelta(days=1)

    new = StudentGradePeriod(
        student_id=student.id, started_on=boundary, **snapshot_of(student)
    )
    db.add(new)
    db.flush()
    return new


def correct_current(db: Session, student: User) -> StudentGradePeriod:
    """Profil düzeltmesi: güncel dönemin bilgilerini güncelle (yeni dönem AÇMAZ)."""
    cur = ensure_current(db, student)
    for k, v in snapshot_of(student).items():
        setattr(cur, k, v)
    db.flush()
    return cur


# =============================================================================
# Koç düzeltmeleri (sınır yanlış çıkarsa)
# =============================================================================


class GradePeriodError(ValueError):
    """(kod, mesaj) taşıyan doğrulama hatası."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _neighbours(
    db: Session, period: StudentGradePeriod
) -> tuple[StudentGradePeriod | None, StudentGradePeriod | None]:
    """(önceki, sonraki) — started_on sırasına göre."""
    rows = sorted(
        list_periods(db, period.student_id), key=lambda p: (p.started_on, p.id)
    )
    idx = next((i for i, p in enumerate(rows) if p.id == period.id), None)
    if idx is None:
        return (None, None)
    prev = rows[idx - 1] if idx > 0 else None
    nxt = rows[idx + 1] if idx + 1 < len(rows) else None
    return (prev, nxt)


def update_period_start(
    db: Session, period: StudentGradePeriod, new_start: date
) -> StudentGradePeriod:
    """Dönem başlangıcını değiştir; komşu dönemin bitişini birlikte kaydır."""
    prev, nxt = _neighbours(db, period)
    if prev is None:
        raise GradePeriodError(
            "first_period_start",
            "İlk dönemin başlangıcı değiştirilemez (öğrencinin kayıt tarihi).",
        )
    if new_start <= prev.started_on:
        raise GradePeriodError(
            "start_before_previous",
            "Yeni tarih bir önceki dönemin başlangıcından sonra olmalı.",
        )
    if period.ended_on is not None and new_start > period.ended_on:
        raise GradePeriodError(
            "start_after_end", "Yeni tarih bu dönemin bitişinden sonra olamaz."
        )
    if nxt is not None and new_start >= nxt.started_on:
        raise GradePeriodError(
            "start_after_next",
            "Yeni tarih bir sonraki dönemin başlangıcından önce olmalı.",
        )
    period.started_on = new_start
    prev.ended_on = new_start - timedelta(days=1)
    db.flush()
    return period


def delete_period(db: Session, period: StudentGradePeriod) -> None:
    """Gereksiz dönemi sil; boşluğu komşu dönem devralır (veri kaybı yok)."""
    rows = sorted(
        list_periods(db, period.student_id), key=lambda p: (p.started_on, p.id)
    )
    if len(rows) <= 1:
        raise GradePeriodError(
            "last_period", "Tek dönem silinemez — öğrencinin en az bir dönemi olmalı."
        )
    prev, nxt = _neighbours(db, period)
    if prev is not None:
        # Önceki dönem, silinenin aralığını yutar.
        prev.ended_on = period.ended_on
    elif nxt is not None:
        # İlk dönem siliniyor: sonraki dönem başlangıcı geriye çekilir.
        nxt.started_on = period.started_on
    db.delete(period)
    db.flush()


# =============================================================================
# Geriye dönük doldurma
# =============================================================================


def _previous_grade(student: User) -> tuple[int | None, bool]:
    """Bir önceki öğretim yılındaki sınıf tahmini."""
    if student.is_graduate:
        return (12, False)
    g = student.grade_level
    if g is None or g <= 5:
        return (g, False)
    return (g - 1, False)


def _model_for_grade(
    student: User, grade: int | None, is_graduate: bool
) -> str | None:
    """Geçmiş dönemin müfredat modeli (aynı öğrencinin bir önceki sınıfı için)."""
    from app.models.curriculum import derive_curriculum_model

    ay_start = None
    if student.academic_year is not None:
        ay_start = student.academic_year.start_year
        if ay_start is not None:
            ay_start -= 1  # bir önceki öğretim yılı
    model = derive_curriculum_model(
        grade_level=grade,
        is_graduate=is_graduate,
        entry_year_grade9=student.entry_year_grade9,
        academic_year_start=ay_start,
    )
    return getattr(model, "value", None)


def backfill_student(
    db: Session,
    student: User,
    *,
    today: date | None = None,
    has_old_data: bool = True,
) -> int:
    """Dönemi olmayan öğrenciye dönem(ler) aç. Zaten varsa 0 döner.

    Sınıf geçmişi kayıtlı olmadığı için tek seferlik tahmin: mevcut öğretim
    yılının 1 Eylül'ü sınır kabul edilir. Öncesinde verisi olan ve sınıf
    atlamış görünen öğrenciye ikinci (geçmiş) dönem açılır. Tahmin yanlışsa
    koç dönem listesinden düzeltir.
    """
    if list_periods(db, student.id):
        return 0

    ref = today or date.today()
    created = getattr(student, "created_at", None)
    created_on = created.date() if created is not None else ref
    boundary = academic_year_start_date(ref)

    prev_grade, prev_is_grad = _previous_grade(student)
    grade_changed = prev_grade != student.grade_level or prev_is_grad != bool(
        student.is_graduate
    )
    split = (
        has_old_data
        and created_on < boundary
        and (prev_is_grad or (prev_grade is not None and prev_grade >= 5))
        and grade_changed
    )

    snap = snapshot_of(student)
    if not split:
        db.add(
            StudentGradePeriod(
                student_id=student.id, started_on=min(created_on, ref), **snap
            )
        )
        db.flush()
        return 1

    old_snap = dict(snap)
    old_snap["grade_level"] = prev_grade
    old_snap["is_graduate"] = prev_is_grad
    # Geçmiş dönemin müfredat modeli o sınıftan türetilir (8 → LGS gibi).
    old_snap["curriculum_model"] = _model_for_grade(student, prev_grade, prev_is_grad)

    db.add(
        StudentGradePeriod(
            student_id=student.id,
            started_on=created_on,
            ended_on=boundary - timedelta(days=1),
            **old_snap,
        )
    )
    db.add(StudentGradePeriod(student_id=student.id, started_on=boundary, **snap))
    db.flush()
    return 2
