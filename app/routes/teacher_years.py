from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import (
    AcademicPhase,
    AcademicPhaseKind,
    AcademicYear,
    User,
)
from app.models.academic import ExamTarget
from app.templating import templates

router = APIRouter(prefix="/teacher/years")


def _current_academic_start_year(today: date) -> int:
    """Bugün hangi öğretim yılındayız? Eylül-Ağustos ekseni."""
    return today.year if today.month >= 9 else today.year - 1


@router.get("")
def list_years(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
    err: str | None = None,
    ok: str | None = None,
):
    years = (
        db.query(AcademicYear)
        .options(joinedload(AcademicYear.phases))
        .filter(AcademicYear.teacher_id == user.id)
        .order_by(AcademicYear.name.desc())
        .all()
    )
    today = date.today()
    current = _current_academic_start_year(today)
    # Seçim listesi: current-2 → current+3 (6 yıl penceresi)
    year_choices = []
    existing_names = {y.name for y in years}
    for y in range(current - 2, current + 4):
        name = f"{y}-{y+1}"
        suffix = ""
        if y == current:
            suffix = " · şu an"
        elif y < current:
            suffix = " · geçmiş"
        elif y == current + 1:
            suffix = " · gelecek yıl"
        year_choices.append({
            "start_year": y,
            "name": name,
            "label": name + suffix,
            "exists": name in existing_names,
        })
    return templates.TemplateResponse(
        "teacher/years_list.html",
        {
            "request": request,
            "user": user,
            "years": years,
            "today": today,
            "flash_err": err,
            "flash_ok": ok,
            "year_choices": year_choices,
            "current_start_year": current,
            "PHASE_KIND_CHOICES": [
                (AcademicPhaseKind.REGULAR.name, "📚 Olağan Dönem"),
                (AcademicPhaseKind.WINTER_BREAK.name, "❄️ Yarıyıl Tatili"),
                (AcademicPhaseKind.SUMMER_CAMP.name, "🌞 Yaz Kampı"),
                (AcademicPhaseKind.EXAM_PREP.name, "🎯 Sınav Hazırlık"),
            ],
        },
    )


@router.post("")
def create_year(
    start_year: str = Form(...),  # select'ten "2026" formatında gelir
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    # start_year parse + sınır kontrol
    try:
        sy = int(start_year.strip())
        if sy < 2020 or sy > 2050:
            raise ValueError("range")
    except (ValueError, AttributeError):
        return RedirectResponse(
            url="/teacher/years?err=" + quote("Geçerli bir yıl seçin."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # name otomatik üretilir — manuel yazım hatası imkansız
    name = f"{sy}-{sy + 1}"

    # Aynı yıl zaten varsa pasif: bir akademik yıl saf takvimdir, hedef sınav
    # öğrenci seviyesinde tutulur (User.effective_exam_target). Aynı dönemde
    # LGS+YKS+mezun öğrenciler aynı yıl satırını paylaşır.
    existing = (
        db.query(AcademicYear)
        .filter(AcademicYear.teacher_id == user.id, AcademicYear.name == name)
        .first()
    )
    if existing:
        if existing.start_year != sy:
            existing.start_year = sy
            db.commit()
        return RedirectResponse(
            url="/teacher/years?ok=" + quote(f"{name} zaten kayıtlı."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # exam_target sütunu legacy — None varsayılır, kimse okumaz.
    db.add(AcademicYear(
        teacher_id=user.id,
        name=name,
        start_year=sy,
        exam_target=ExamTarget.NONE,
    ))
    db.commit()
    return RedirectResponse(
        url="/teacher/years?ok=" + quote(f"{name} eklendi."),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{year_id}/delete")
def delete_year(
    year_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    year = db.query(AcademicYear).filter(
        AcademicYear.id == year_id, AcademicYear.teacher_id == user.id
    ).first()
    if year:
        db.delete(year)
        db.commit()
    return RedirectResponse(url="/teacher/years", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------- Phase CRUD (Faz 6) ----------------------------


@router.post("/{year_id}/phases")
def create_phase(
    year_id: int,
    name: str = Form(...),
    start_date: str = Form(...),
    end_date: str = Form(...),
    kind: str = Form("REGULAR"),
    notes: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    year = db.query(AcademicYear).filter(
        AcademicYear.id == year_id, AcademicYear.teacher_id == user.id,
    ).first()
    if not year:
        raise HTTPException(status_code=404, detail="Akademik yıl bulunamadı")

    name_clean = name.strip()
    if not name_clean:
        return RedirectResponse(
            url="/teacher/years?err=" + quote("Dönem adı zorunludur."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        start = date.fromisoformat(start_date.strip())
        end = date.fromisoformat(end_date.strip())
    except ValueError:
        return RedirectResponse(
            url="/teacher/years?err=" + quote("Tarihler geçerli ISO formatında olmalı (YYYY-MM-DD)."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if start > end:
        return RedirectResponse(
            url="/teacher/years?err=" + quote("Başlangıç tarihi bitiş tarihinden sonra olamaz."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        kind_enum = AcademicPhaseKind[kind.strip().upper()]
    except (KeyError, AttributeError):
        kind_enum = AcademicPhaseKind.REGULAR

    phase = AcademicPhase(
        academic_year_id=year.id,
        name=name_clean,
        start_date=start,
        end_date=end,
        kind=kind_enum,
        notes=notes.strip() or None,
    )
    db.add(phase)
    db.commit()
    return RedirectResponse(
        url="/teacher/years?ok=" + quote(f"'{name_clean}' dönemi eklendi."),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{year_id}/phases/{phase_id}/delete")
def delete_phase(
    year_id: int,
    phase_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    phase = (
        db.query(AcademicPhase)
        .join(AcademicYear, AcademicPhase.academic_year_id == AcademicYear.id)
        .filter(
            AcademicPhase.id == phase_id,
            AcademicPhase.academic_year_id == year_id,
            AcademicYear.teacher_id == user.id,
        )
        .first()
    )
    if phase:
        db.delete(phase)
        db.commit()
    return RedirectResponse(url="/teacher/years", status_code=status.HTTP_303_SEE_OTHER)
