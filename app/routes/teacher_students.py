import secrets
import string
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_teacher
from app.models import (
    AcademicYear,
    GraduateMode,
    Track,
    User,
    UserRole,
    derive_curriculum_model,
)
from app.services.security import hash_password
from app.templating import templates

router = APIRouter(prefix="/teacher/students")


# 5-12 + Mezun seçim listesi UI için. "graduate" özel string'i is_graduate=True
# olarak parse edilir; diğer değerler grade_level int olur.
GRADE_CHOICES: list[tuple[str, str]] = [
    ("5", "5. Sınıf"),
    ("6", "6. Sınıf"),
    ("7", "7. Sınıf"),
    ("8", "8. Sınıf (LGS)"),
    ("9", "9. Sınıf"),
    ("10", "10. Sınıf"),
    ("11", "11. Sınıf"),
    ("12", "12. Sınıf"),
    ("graduate", "Mezun (YKS hazırlık)"),
]


def _gen_password(n: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(n))


@router.get("")
def list_students(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
    created: str | None = None,
    temp_password: str | None = None,
    err: str | None = None,
):
    students = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    years = (
        db.query(AcademicYear)
        .filter(AcademicYear.teacher_id == user.id)
        .order_by(AcademicYear.name.desc())
        .all()
    )
    return templates.TemplateResponse(
        "teacher/students_list.html",
        {
            "request": request,
            "user": user,
            "students": students,
            "years": years,
            "created_email": created,
            "temp_password": temp_password,
            "flash_err": err,
            # UI'da seçim listesi + label haritaları
            "GRADE_CHOICES": GRADE_CHOICES,
            "TRACK_CHOICES": [(t.name, t.value) for t in Track],
            "GRADUATE_MODE_CHOICES": [(g.name, g.value) for g in GraduateMode],
        },
    )


def _parse_grade_input(raw: str) -> tuple[int | None, bool]:
    """Form'dan gelen sınıf string'ini (grade_level, is_graduate) tuple'ına çevir.

    'graduate' → (None, True); '8' → (8, False); boş → (None, False).
    """
    s = (raw or "").strip().lower()
    if s == "graduate":
        return (None, True)
    if not s:
        return (None, False)
    try:
        return (int(s), False)
    except ValueError:
        return (None, False)


@router.post("")
def create_student(
    full_name: str = Form(...),
    email: str = Form(...),
    grade: str = Form("8"),  # "5"-"12" veya "graduate"
    academic_year_id: str = Form(""),
    track: str = Form(""),  # SAYISAL/EA/SOZEL/DIL veya boş
    graduate_mode: str = Form(""),  # FULL_TIME/DERSHANE veya boş
    entry_year_grade9: str = Form(""),  # opsiyonel override
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    email_norm = email.strip().lower()
    full_name_stripped = full_name.strip()
    if not email_norm or not full_name_stripped:
        return RedirectResponse(
            url="/teacher/students?err=" + quote("Ad Soyad ve e-posta zorunludur."),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if db.query(User).filter(User.email == email_norm).first():
        return RedirectResponse(
            url="/teacher/students?err=" + quote("Bu e-posta zaten kayıtlı."),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    grade_level, is_graduate = _parse_grade_input(grade)

    # Validation: 11+ ve mezun için track zorunlu
    track_requires = is_graduate or (grade_level is not None and grade_level >= 11)
    track_enum: Track | None = None
    if track.strip():
        try:
            track_enum = Track[track.strip().upper()]
        except KeyError:
            track_enum = None
    if track_requires and track_enum is None:
        return RedirectResponse(
            url="/teacher/students?err=" + quote(
                "11. sınıf, 12. sınıf ve mezunlar için alan (Sayısal/EA/Sözel/Dil) zorunludur."
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Mezun için graduate_mode zorunlu
    graduate_mode_enum: GraduateMode | None = None
    if graduate_mode.strip():
        try:
            graduate_mode_enum = GraduateMode[graduate_mode.strip().upper()]
        except KeyError:
            graduate_mode_enum = None
    if is_graduate and graduate_mode_enum is None:
        return RedirectResponse(
            url="/teacher/students?err=" + quote(
                "Mezun öğrenciler için çalışma şekli (Tam-zamanlı / Dershane) zorunludur."
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    # Akademik yıl
    parsed_year_id: int | None = None
    if academic_year_id.strip():
        try:
            parsed_year_id = int(academic_year_id)
        except ValueError:
            parsed_year_id = None

    # entry_year_grade9 override (sınıf tekrarı vb.)
    entry_year_int: int | None = None
    if entry_year_grade9.strip():
        try:
            entry_year_int = int(entry_year_grade9.strip())
            if entry_year_int < 2000 or entry_year_int > 2100:
                entry_year_int = None
        except ValueError:
            entry_year_int = None

    temp_pw = _gen_password()
    student = User(
        email=email_norm,
        password_hash=hash_password(temp_pw),
        full_name=full_name_stripped,
        role=UserRole.STUDENT,
        teacher_id=user.id,
        academic_year_id=parsed_year_id,
        grade_level=grade_level,
        is_graduate=is_graduate,
        track=track_enum,
        graduate_mode=graduate_mode_enum,
        entry_year_grade9=entry_year_int,
    )
    db.add(student)
    db.commit()
    return RedirectResponse(
        url=f"/teacher/students?created={email_norm}&temp_password={temp_pw}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _next_grade_choice(grade_level: int | None, is_graduate: bool) -> str:
    """Mantıksal bir sonraki sınıf önerisi — form default için.

    8→9, 12→Mezun, Mezun→Mezun (sınıf tekrarı varsayılmaz). 5-11 arası +1.
    """
    if is_graduate:
        return "graduate"
    if grade_level is None:
        return "8"
    if grade_level == 12:
        return "graduate"
    if 5 <= grade_level < 12:
        return str(grade_level + 1)
    return str(grade_level)


@router.get("/{student_id}/promote")
def promote_student_form(
    student_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        return RedirectResponse(url="/teacher/students", status_code=303)

    years = (
        db.query(AcademicYear)
        .filter(AcademicYear.teacher_id == user.id)
        .order_by(AcademicYear.name.desc())
        .all()
    )
    # Bir sonraki yıl önerisi: mevcut start_year > şu anki yılın start_year'ı
    suggested_year_id: int | None = None
    if student.academic_year and student.academic_year.start_year is not None:
        cur_start = student.academic_year.start_year
        # Mevcut yıldan büyük en küçük start_year'lı yıl
        candidates = [y for y in years if y.start_year and y.start_year > cur_start]
        if candidates:
            suggested_year_id = min(candidates, key=lambda y: y.start_year).id

    suggested_grade = _next_grade_choice(student.grade_level, student.is_graduate)

    return templates.TemplateResponse(
        "teacher/student_promote.html",
        {
            "request": request,
            "user": user,
            "student": student,
            "years": years,
            "suggested_year_id": suggested_year_id,
            "suggested_grade": suggested_grade,
            "GRADE_CHOICES": GRADE_CHOICES,
            "TRACK_CHOICES": [(t.name, t.value) for t in Track],
            "GRADUATE_MODE_CHOICES": [(g.name, g.value) for g in GraduateMode],
        },
    )


@router.post("/{student_id}/promote")
def promote_student(
    student_id: int,
    grade: str = Form(...),
    academic_year_id: str = Form(""),
    track: str = Form(""),
    graduate_mode: str = Form(""),
    entry_year_grade9: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = (
        db.query(User)
        .filter(
            User.id == student_id,
            User.teacher_id == user.id,
            User.role == UserRole.STUDENT,
        )
        .first()
    )
    if not student:
        return RedirectResponse(url="/teacher/students", status_code=303)

    new_grade, new_is_graduate = _parse_grade_input(grade)

    # Validation: 11+ ve mezun için track zorunlu
    track_requires = new_is_graduate or (new_grade is not None and new_grade >= 11)
    track_enum: Track | None = None
    if track.strip():
        try:
            track_enum = Track[track.strip().upper()]
        except KeyError:
            track_enum = None
    if track_requires and track_enum is None:
        return RedirectResponse(
            url=f"/teacher/students/{student_id}/promote?err=" + quote(
                "11. sınıf, 12. sınıf ve mezunlar için alan zorunlu."
            ),
            status_code=303,
        )

    graduate_mode_enum: GraduateMode | None = None
    if graduate_mode.strip():
        try:
            graduate_mode_enum = GraduateMode[graduate_mode.strip().upper()]
        except KeyError:
            graduate_mode_enum = None
    if new_is_graduate and graduate_mode_enum is None:
        return RedirectResponse(
            url=f"/teacher/students/{student_id}/promote?err=" + quote(
                "Mezun öğrenciler için çalışma şekli zorunlu."
            ),
            status_code=303,
        )

    # Akademik yıl
    parsed_year_id: int | None = None
    if academic_year_id.strip():
        try:
            parsed_year_id = int(academic_year_id)
        except ValueError:
            parsed_year_id = None

    # Sahiplik kontrolü — başkasının yılı olmasın
    if parsed_year_id is not None:
        owns = (
            db.query(AcademicYear)
            .filter(
                AcademicYear.id == parsed_year_id,
                AcademicYear.teacher_id == user.id,
            )
            .first()
        )
        if not owns:
            parsed_year_id = None

    entry_year_int: int | None = None
    if entry_year_grade9.strip():
        try:
            entry_year_int = int(entry_year_grade9.strip())
            if entry_year_int < 2000 or entry_year_int > 2100:
                entry_year_int = None
        except ValueError:
            entry_year_int = None

    # Apply — kitap ve görev tarihçesi korunur, yalnızca profil alanları güncellenir
    student.grade_level = new_grade
    student.is_graduate = new_is_graduate
    student.track = track_enum
    student.graduate_mode = graduate_mode_enum if new_is_graduate else None
    student.entry_year_grade9 = entry_year_int
    if parsed_year_id is not None:
        student.academic_year_id = parsed_year_id

    db.commit()

    # Müfredat değişimi var mı? Yeni durum görüntülenirken kullanıcıya bilgi
    new_cm = derive_curriculum_model(
        grade_level=new_grade,
        is_graduate=new_is_graduate,
        entry_year_grade9=entry_year_int,
        academic_year_start=(
            student.academic_year.start_year if student.academic_year else None
        ),
    )
    cm_label = new_cm.value if new_cm else "—"

    msg = f"{student.full_name} → {student.display_grade_label}"
    if student.academic_year:
        msg += f" · {student.academic_year.name}"
    msg += f" · müfredat: {cm_label}"

    return RedirectResponse(
        url=f"/teacher/students/{student_id}?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/{student_id}/reset-password")
def reset_password(
    student_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = db.query(User).filter(
        User.id == student_id,
        User.teacher_id == user.id,
        User.role == UserRole.STUDENT,
    ).first()
    if not student:
        return RedirectResponse(url="/teacher/students", status_code=status.HTTP_303_SEE_OTHER)
    temp_pw = _gen_password()
    student.password_hash = hash_password(temp_pw)
    db.commit()
    return RedirectResponse(
        url=f"/teacher/students?created={student.email}&temp_password={temp_pw}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post("/{student_id}/delete")
def delete_student(
    student_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    student = db.query(User).filter(
        User.id == student_id,
        User.teacher_id == user.id,
        User.role == UserRole.STUDENT,
    ).first()
    if student:
        db.delete(student)
        db.commit()
    return RedirectResponse(url="/teacher/students", status_code=status.HTTP_303_SEE_OTHER)
