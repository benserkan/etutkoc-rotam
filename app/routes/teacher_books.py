from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload

from app.deps import get_db, require_teacher
from app.models import (
    Book,
    BookSection,
    BookSet,
    BookSetItem,
    BookTemplate,
    BookTemplateSection,
    BookType,
    SectionProgress,
    StudentBook,
    Subject,
    Topic,
    User,
    UserRole,
)
from app.templating import templates

router = APIRouter(prefix="/teacher/books")


def _accessible_subjects(db: Session, teacher_id: int) -> list[Subject]:
    # built-in (shared) + teacher's own
    return (
        db.query(Subject)
        .filter((Subject.is_builtin.is_(True)) | (Subject.teacher_id == teacher_id))
        .order_by(Subject.order, Subject.name)
        .all()
    )


def _accessible_topics(db: Session, subject_id: int, teacher_id: int) -> list[Topic]:
    # LEAF konular (alt başlıklar); tema/ünite parent'ları gruplama amaçlı, hariç.
    all_topics = (
        db.query(Topic)
        .filter(
            Topic.subject_id == subject_id,
            (Topic.is_builtin.is_(True)) | (Topic.teacher_id == teacher_id),
        )
        .order_by(Topic.order, Topic.name)
        .all()
    )
    parent_ids = {t.parent_id for t in all_topics if t.parent_id is not None}
    return [t for t in all_topics if t.id not in parent_ids]


@router.get("")
def list_books(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    books = (
        db.query(Book)
        .options(joinedload(Book.subject), joinedload(Book.sections))
        .filter(Book.teacher_id == user.id)
        .order_by(Book.created_at.desc())
        .all()
    )
    subjects = _accessible_subjects(db, user.id)

    # Ders bazlı gruplandırma + ders/tip/sınıf sayımları (chip filtreler ve sticky
    # bölüm başlıkları için).
    books_by_subject: dict[int, dict] = {}
    for s in subjects:
        books_by_subject[s.id] = {
            "subject": s,
            "books": [],
            "total_sections": 0,
            "total_tests": 0,
        }
    type_counts: dict[str, int] = {bt.value: 0 for bt in BookType}
    # Sınıf-bazlı kitap sayımı (chip için): bir kitap kapsadığı her seviye
    # için birer kez sayılır. "graduate" özel anahtar mezunu temsil eder.
    grade_counts: dict[str, int] = {str(g): 0 for g in range(5, 13)}
    grade_counts["graduate"] = 0

    for book in books:
        bucket = books_by_subject.get(book.subject_id)
        if bucket is None:
            # Subject erişilebilir değilse de göstereceğiz — virtual bucket
            bucket = {
                "subject": book.subject,
                "books": [],
                "total_sections": 0,
                "total_tests": 0,
            }
            books_by_subject[book.subject_id] = bucket
        bucket["books"].append(book)
        bucket["total_sections"] += len(book.sections)
        bucket["total_tests"] += book.total_tests
        type_counts[book.type.value] = type_counts.get(book.type.value, 0) + 1

        # Sınıf sayımları — kitabın hedef aralığına göre her grade için say
        lo = book.target_grade_min
        hi = book.target_grade_max
        if lo is None and hi is None and not book.target_graduate:
            # Hedef belirtilmemiş kitap — tüm seviyelere uygun varsayılır,
            # her grade'e + ekle (filtrede tüm chip'lere eşleşir).
            for g in range(5, 13):
                grade_counts[str(g)] = grade_counts[str(g)] + 1
        else:
            if lo is not None or hi is not None:
                lo_eff = lo if lo is not None else 5
                hi_eff = hi if hi is not None else 12
                for g in range(max(5, lo_eff), min(12, hi_eff) + 1):
                    grade_counts[str(g)] = grade_counts[str(g)] + 1
            if book.target_graduate:
                grade_counts["graduate"] = grade_counts["graduate"] + 1

    # Sadece kitabı olan dersleri sırala (ders order, name)
    grouped = sorted(
        [v for v in books_by_subject.values() if v["books"]],
        key=lambda g: (g["subject"].order, g["subject"].name),
    )

    overall = {
        "books": len(books),
        "sections": sum(len(b.sections) for b in books),
        "tests": sum(b.total_tests for b in books),
    }

    # Form dropdown'u için subjects'i müfredat modeli bazında grupla
    # (aynı ders adı farklı modellerde ayrı kayıt — optgroup ile ayrılır).
    from app.models import CurriculumModel
    MODEL_LABELS = {
        CurriculumModel.LGS: "LGS Müfredatı (5-8)",
        CurriculumModel.MAARIF_LISE: "Maarif Modeli (9-12)",
        CurriculumModel.KLASIK_LISE: "Klasik Lise (11-12, son nesil)",
    }
    MODEL_ORDER = [CurriculumModel.LGS, CurriculumModel.MAARIF_LISE, CurriculumModel.KLASIK_LISE]
    subjects_grouped: list[dict] = []
    seen_models: dict = {}
    for s in subjects:
        key = s.curriculum_model
        if key not in seen_models:
            seen_models[key] = []
        seen_models[key].append(s)
    # NULL (model belirtilmemiş) ders varsa "Diğer" başlığı altında en sona
    for cm in MODEL_ORDER:
        if cm in seen_models and seen_models[cm]:
            subjects_grouped.append({
                "label": MODEL_LABELS[cm],
                "subjects": seen_models[cm],
            })
    if None in seen_models and seen_models[None]:
        subjects_grouped.append({
            "label": "Diğer / Sınıflandırılmamış",
            "subjects": seen_models[None],
        })

    # Faz B: Şablonlar — yeni kitap modal'ında "Şablondan başla" select için
    teacher_templates = (
        db.query(BookTemplate)
        .filter(BookTemplate.teacher_id == user.id)
        .order_by(BookTemplate.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        "teacher/books_list.html",
        {
            "request": request,
            "user": user,
            "books": books,
            "subjects": subjects,
            "subjects_grouped": subjects_grouped,
            "BookType": BookType,
            "grouped": grouped,
            "type_counts": type_counts,
            "grade_counts": grade_counts,
            "overall": overall,
            "teacher_templates": teacher_templates,
        },
    )


@router.post("")
def create_book(
    name: str = Form(...),
    publisher: str = Form(""),
    subject_id: int = Form(...),
    type: str = Form(...),
    avg_questions_per_test: str = Form(""),
    target_grade_min: str = Form(""),
    target_grade_max: str = Form(""),
    target_graduate: str = Form(""),
    template_id: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    try:
        book_type = BookType(type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz kitap tipi")
    avg_q: int | None = None
    if avg_questions_per_test.strip():
        try:
            avg_q = int(avg_questions_per_test)
        except ValueError:
            avg_q = None

    def _parse_grade(s: str) -> int | None:
        s = (s or "").strip()
        if not s:
            return None
        try:
            v = int(s)
            return v if 4 <= v <= 12 else None
        except ValueError:
            return None

    g_min = _parse_grade(target_grade_min)
    g_max = _parse_grade(target_grade_max)
    if g_min is not None and g_max is not None and g_min > g_max:
        g_min, g_max = g_max, g_min

    is_for_graduate = target_graduate.strip().lower() in ("on", "1", "true", "yes")

    # Şablon (opsiyonel) — sections kopyalanır
    template: BookTemplate | None = None
    if template_id.strip():
        try:
            tid = int(template_id)
            template = (
                db.query(BookTemplate)
                .options(joinedload(BookTemplate.sections))
                .filter(
                    BookTemplate.id == tid,
                    BookTemplate.teacher_id == user.id,
                )
                .first()
            )
        except ValueError:
            template = None

    book = Book(
        teacher_id=user.id,
        subject_id=subject_id,
        name=name.strip(),
        publisher=publisher.strip() or None,
        type=book_type,
        avg_questions_per_test=avg_q,
        target_grade_min=g_min,
        target_grade_max=g_max,
        target_graduate=is_for_graduate,
    )
    db.add(book)
    db.flush()  # book.id lazım

    if template:
        for ts in template.sections:
            db.add(BookSection(
                book_id=book.id,
                label=ts.label,
                test_count=ts.default_test_count,
                order=ts.order,
            ))

    db.commit()
    return RedirectResponse(url=f"/teacher/books/{book.id}", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------- Şablonlar (Faz B) ----------------------------


@router.get("/templates")
def list_templates(
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
    ok: str | None = None,
    err: str | None = None,
):
    tpls = (
        db.query(BookTemplate)
        .options(joinedload(BookTemplate.sections))
        .filter(BookTemplate.teacher_id == user.id)
        .order_by(BookTemplate.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        "teacher/book_templates.html",
        {
            "request": request,
            "user": user,
            "templates": tpls,
            "BOOK_TYPE_LABELS": __import__("app.models.book", fromlist=["BOOK_TYPE_LABELS"]).BOOK_TYPE_LABELS,
            "flash_ok": ok,
            "flash_err": err,
        },
    )


@router.post("/{book_id}/save-as-template")
def save_book_as_template(
    book_id: int,
    template_name: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Mevcut kitabı (sections dahil) yeniden kullanılabilir şablon olarak kaydet."""
    book = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    if not book.sections:
        return RedirectResponse(
            url=f"/teacher/books/{book_id}?err=" + quote(
                "Şablon olarak kaydetmek için önce ünite eklemelisiniz."
            ),
            status_code=303,
        )

    name = (template_name or "").strip() or book.name

    tpl = BookTemplate(
        teacher_id=user.id,
        name=name,
        publisher=book.publisher,
        type=book.type,
        subject_id=book.subject_id,
        target_grade_min=book.target_grade_min,
        target_grade_max=book.target_grade_max,
        target_graduate=book.target_graduate,
        avg_questions_per_test=book.avg_questions_per_test,
        is_ai_generated=False,
        is_verified=True,  # Manuel oluşturulmuş = doğrulanmış
    )
    db.add(tpl)
    db.flush()
    for s in book.sections:
        db.add(BookTemplateSection(
            template_id=tpl.id,
            label=s.label,
            default_test_count=s.test_count,
            order=s.order,
        ))
    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}?ok=" + quote(f"'{name}' şablon olarak kaydedildi."),
        status_code=303,
    )


@router.post("/{book_id}/apply-template")
def apply_template_to_book(
    book_id: int,
    template_id: int = Form(...),
    overwrite: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Mevcut kitaba (boş veya değil) şablondan ünite uygula.

    overwrite=on ise mevcut ünitelerin hepsi silinir; aksi halde sadece şablonda
    olup kitapta olmayanlar eklenir (label-bazlı eşleştirme).
    """
    book = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    tpl = (
        db.query(BookTemplate)
        .options(joinedload(BookTemplate.sections))
        .filter(BookTemplate.id == template_id, BookTemplate.teacher_id == user.id)
        .first()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="Şablon bulunamadı")

    do_overwrite = overwrite.strip().lower() in ("on", "1", "true", "yes")

    if do_overwrite:
        # Mevcut sections'ları sil — fakat ilerleme/rezerv varsa engelle
        for s in book.sections:
            progresses = (
                db.query(SectionProgress)
                .filter(SectionProgress.book_section_id == s.id)
                .all()
            )
            if any(p.completed_count > 0 or p.reserved_count > 0 for p in progresses):
                return RedirectResponse(
                    url=f"/teacher/books/{book_id}?err=" + quote(
                        "Üzerine yazma yapılamıyor: bazı ünitelerde tamamlanan/rezerv test var. "
                        "Önce manuel temizleyin veya 'Üzerine yazma' kapalı olarak uygulayın."
                    ),
                    status_code=303,
                )
        for s in list(book.sections):
            db.delete(s)
        db.flush()

    existing_labels = {s.label.strip().lower() for s in book.sections}
    max_order = max((s.order for s in book.sections), default=-1)

    added = 0
    for ts in tpl.sections:
        if ts.label.strip().lower() in existing_labels:
            continue
        max_order += 1
        sec = BookSection(
            book_id=book.id,
            label=ts.label,
            test_count=ts.default_test_count,
            order=max_order,
        )
        db.add(sec)
        db.flush()
        # Atanmış öğrenciler için progress kaydı aç
        for sb in book.student_books:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=sec.id,
                reserved_count=0,
                completed_count=0,
            ))
        added += 1

    db.commit()
    msg = f"'{tpl.name}' şablonundan {added} ünite eklendi."
    return RedirectResponse(
        url=f"/teacher/books/{book_id}?ok=" + quote(msg),
        status_code=303,
    )


@router.post("/templates/{template_id}/delete")
def delete_template(
    template_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    tpl = (
        db.query(BookTemplate)
        .filter(BookTemplate.id == template_id, BookTemplate.teacher_id == user.id)
        .first()
    )
    if tpl:
        db.delete(tpl)
        db.commit()
    return RedirectResponse(url="/teacher/books/templates", status_code=303)


@router.post("/templates/{template_id}/verify")
def verify_template(
    template_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """AI önerisi şablonu kullanıcı tarafından doğrulanmış olarak işaretle."""
    tpl = (
        db.query(BookTemplate)
        .filter(BookTemplate.id == template_id, BookTemplate.teacher_id == user.id)
        .first()
    )
    if tpl:
        tpl.is_verified = True
        db.commit()
    return RedirectResponse(url="/teacher/books/templates", status_code=303)


@router.post("/{book_id}/ai-suggest")
def ai_suggest_sections(
    book_id: int,
    grade_hint: str = Form(""),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """AI ile ünite önerisi al, kitaba uygula + draft şablon olarak kaydet.

    Mevcut sections varsa tekrar uygulamaz (yanlışlıkla üzerine yazma engeli);
    önce 'Sıfırdan başla' ile temizlenmesi gerekir.
    """
    from app.models.book import BOOK_TYPE_LABELS
    from app.services.ai_book_template import (
        AIInvalidResponse,
        AIServiceUnavailable,
        suggest_sections,
    )

    book = (
        db.query(Book)
        .options(joinedload(Book.sections), joinedload(Book.subject))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    if book.sections:
        return RedirectResponse(
            url=f"/teacher/books/{book_id}?err=" + quote(
                "Mevcut üniteler var — önce 'Sıfırdan başla' ile temizleyin."
            ),
            status_code=303,
        )

    # Sınıf etiketi: kitabın target_grade veya kullanıcının verdiği hint
    grade_label = (grade_hint or "").strip()
    if not grade_label:
        if book.target_grade_min and book.target_grade_max:
            if book.target_grade_min == book.target_grade_max:
                grade_label = f"{book.target_grade_min}. sınıf"
            else:
                grade_label = (
                    f"{book.target_grade_min}-{book.target_grade_max}. sınıf"
                )
        elif book.target_graduate:
            grade_label = "Mezun (YKS)"
        else:
            grade_label = "belirtilmemiş"

    # Stage 7 — feature flag kontrolü
    from app.services.feature_flags import is_enabled
    if not is_enabled(db, "ai_book_template", institution=user.institution):
        return RedirectResponse(
            url=f"/teacher/books/{book_id}?err=" + quote(
                "AI ünite önerisi şu an kapalı (sistem yöneticisi)."
            ),
            status_code=303,
        )

    # Stage 6 — kredi kontrolü (AI çağrısı pahalı; pre-check + post-record)
    from app.models import UsageKind
    from app.services.credits import (
        CreditBlocked, CreditOwner, consume_credits,
    )
    owner = CreditOwner.for_user(user)
    try:
        with consume_credits(
            db, owner=owner, kind=UsageKind.AI_BOOK_TEMPLATE,
            actor_user_id=user.id, autocommit=False,
        ) as ctx:
            suggestions = suggest_sections(
                book_name=book.name,
                publisher=book.publisher,
                subject_name=book.subject.name if book.subject else "",
                book_type_label=BOOK_TYPE_LABELS.get(book.type, book.type.value),
                grade_label=grade_label,
            )
            ctx.set_metadata({"book_id": book.id, "subject": book.subject.name if book.subject else None})
    except CreditBlocked as e:
        return RedirectResponse(
            url=f"/teacher/books/{book_id}?err=" + quote(
                f"Kredi sınırı: {e.message}"
            ),
            status_code=303,
        )
    except AIServiceUnavailable as e:
        return RedirectResponse(
            url=f"/teacher/books/{book_id}?err=" + quote(
                f"AI servisi kullanılamıyor: {e}. .env'deki ANTHROPIC_API_KEY'i kontrol edin."
            ),
            status_code=303,
        )
    except AIInvalidResponse as e:
        return RedirectResponse(
            url=f"/teacher/books/{book_id}?err=" + quote(
                f"AI yanıtı parse edilemedi: {e}. Tekrar deneyin veya manuel girin."
            ),
            status_code=303,
        )

    # Sections'ları kitaba ekle
    for i, sec in enumerate(suggestions):
        new_sec = BookSection(
            book_id=book.id,
            label=sec["label"],
            test_count=sec["default_test_count"],
            order=i,
        )
        db.add(new_sec)
        db.flush()
        # Atanmış öğrencilere progress aç
        for sb in book.student_books:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=new_sec.id,
                reserved_count=0,
                completed_count=0,
            ))

    # Draft şablon olarak da kaydet — kullanıcı sonra doğrulayabilir
    tpl = BookTemplate(
        teacher_id=user.id,
        name=book.name,
        publisher=book.publisher,
        type=book.type,
        subject_id=book.subject_id,
        target_grade_min=book.target_grade_min,
        target_grade_max=book.target_grade_max,
        target_graduate=book.target_graduate,
        avg_questions_per_test=book.avg_questions_per_test,
        is_ai_generated=True,
        is_verified=False,
    )
    db.add(tpl)
    db.flush()
    for i, sec in enumerate(suggestions):
        db.add(BookTemplateSection(
            template_id=tpl.id,
            label=sec["label"],
            default_test_count=sec["default_test_count"],
            order=i,
        ))
    db.commit()

    return RedirectResponse(
        url=f"/teacher/books/{book_id}?ok=" + quote(
            f"✨ AI {len(suggestions)} ünite önerdi. Lütfen kontrol edip düzeltin; "
            f"şablon olarak da kaydedildi (doğrulanmadı işaretiyle)."
        ),
        status_code=303,
    )


@router.post("/{book_id}/clear-sections")
def clear_book_sections(
    book_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Tüm sections'ları sil — 'Sıfırdan başla' escape. İlerlemesi olan ünite
    varsa engellenir (öğrenci verilerini koru).
    """
    book = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")

    # Güvenlik: ilerlemesi olan section silinmez
    for s in book.sections:
        progresses = (
            db.query(SectionProgress)
            .filter(SectionProgress.book_section_id == s.id)
            .all()
        )
        if any(p.completed_count > 0 or p.reserved_count > 0 for p in progresses):
            return RedirectResponse(
                url=f"/teacher/books/{book_id}?err=" + quote(
                    "Bazı ünitelerde tamamlanan/rezerv test var — sıfırlanamaz. "
                    "Önce o üniteleri tek tek silin veya verileri taşıyın."
                ),
                status_code=303,
            )
    n = len(book.sections)
    for s in list(book.sections):
        db.delete(s)
    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}?ok=" + quote(f"{n} ünite silindi."),
        status_code=303,
    )


@router.get("/{book_id}")
def book_detail(
    book_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = (
        db.query(Book)
        .options(joinedload(Book.sections).joinedload(BookSection.topic), joinedload(Book.subject))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    topics = _accessible_topics(db, book.subject_id, user.id)
    all_students = (
        db.query(User)
        .filter(User.teacher_id == user.id, User.role == UserRole.STUDENT)
        .order_by(User.full_name)
        .all()
    )
    assigned_student_ids = {sb.student_id for sb in book.student_books}

    # Faz B: Bu kitabın dersine eşleşen veya teacher'ın tüm şablonları (apply seçimi)
    applicable_templates = (
        db.query(BookTemplate)
        .filter(BookTemplate.teacher_id == user.id)
        .order_by(BookTemplate.created_at.desc())
        .all()
    )

    from app.models.book import BOOK_TYPE_LABELS

    flash_ok = request.query_params.get("ok")
    flash_err = request.query_params.get("err")

    return templates.TemplateResponse(
        "teacher/book_detail.html",
        {
            "request": request,
            "user": user,
            "book": book,
            "topics": topics,
            "students": all_students,
            "assigned_ids": assigned_student_ids,
            "applicable_templates": applicable_templates,
            "BOOK_TYPE_LABELS": BOOK_TYPE_LABELS,
            "flash_ok": flash_ok,
            "flash_err": flash_err,
        },
    )


@router.post("/{book_id}/sections")
def add_section(
    book_id: int,
    label: str = Form(...),
    topic_id: str = Form(""),
    test_count: int = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.id == book_id, Book.teacher_id == user.id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")
    if test_count < 1:
        raise HTTPException(status_code=400, detail="Test sayısı en az 1 olmalı")
    parsed_topic_id: int | None = None
    if topic_id.strip():
        try:
            parsed_topic_id = int(topic_id)
        except ValueError:
            parsed_topic_id = None
    max_order = max((s.order for s in book.sections), default=-1)
    section = BookSection(
        book_id=book.id,
        topic_id=parsed_topic_id,
        label=label.strip(),
        test_count=test_count,
        order=max_order + 1,
    )
    db.add(section)
    db.flush()
    # Atanmış öğrencilere de bu ünite için progress kaydı aç
    for sb in book.student_books:
        db.add(SectionProgress(
            student_book_id=sb.id,
            book_section_id=section.id,
            reserved_count=0,
            completed_count=0,
        ))
    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/sections/bulk-from-catalog")
async def bulk_add_sections_from_catalog(
    book_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    """Subject'in Topic kataloğundan seçili konuları tek seferde BookSection olarak ekle.
    Form: topic_ids[] = id, test_count_<id> = N (her seçili konu için)."""
    book = (
        db.query(Book)
        .options(joinedload(Book.sections), joinedload(Book.student_books))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404, detail="Kitap bulunamadı")

    form = await request.form()
    raw_ids = form.getlist("topic_ids")
    selected_topic_ids: list[int] = []
    for v in raw_ids:
        try:
            selected_topic_ids.append(int(v))
        except (TypeError, ValueError):
            pass
    if not selected_topic_ids:
        return RedirectResponse(
            url=f"/teacher/books/{book_id}?err=" + quote("Hiç konu seçilmedi."),
            status_code=303,
        )

    accessible = {
        t.id: t for t in _accessible_topics(db, book.subject_id, user.id)
    }
    existing_topic_ids = {s.topic_id for s in book.sections if s.topic_id is not None}
    max_order = max((s.order for s in book.sections), default=-1)

    added = 0
    skipped_existing = 0
    for tid in selected_topic_ids:
        topic = accessible.get(tid)
        if topic is None:
            continue
        if tid in existing_topic_ids:
            skipped_existing += 1
            continue
        try:
            tc = int(form.get(f"test_count_{tid}", "0") or "0")
        except (TypeError, ValueError):
            tc = 0
        if tc < 1:
            tc = book.avg_questions_per_test or 5
        max_order += 1
        section = BookSection(
            book_id=book.id,
            topic_id=tid,
            label=topic.name,
            test_count=tc,
            order=max_order,
        )
        db.add(section)
        db.flush()
        for sb in book.student_books:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=section.id,
                reserved_count=0,
                completed_count=0,
            ))
        added += 1

    db.commit()
    msg_parts = [f"{added} ünite eklendi"]
    if skipped_existing:
        msg_parts.append(f"{skipped_existing} konu zaten ekliydi (atlandı)")
    return RedirectResponse(
        url=f"/teacher/books/{book_id}?ok=" + quote(" · ".join(msg_parts)),
        status_code=303,
    )


@router.post("/{book_id}/sections/{section_id}/edit")
def edit_section(
    book_id: int,
    section_id: int,
    label: str = Form(...),
    test_count: int = Form(...),
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    section = (
        db.query(BookSection)
        .join(Book)
        .filter(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
            Book.teacher_id == user.id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404)
    # Test sayısı azaltılırsa rezerv+tamamlanan'ın altına düşmesin
    progresses = (
        db.query(SectionProgress).filter(SectionProgress.book_section_id == section.id).all()
    )
    min_required = max((p.reserved_count + p.completed_count for p in progresses), default=0)
    if test_count < min_required:
        raise HTTPException(
            status_code=400,
            detail=f"Test sayısı {min_required}'dan az olamaz (rezerv+çözülen).",
        )
    section.label = label.strip()
    section.test_count = test_count
    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/sections/{section_id}/delete")
def delete_section(
    book_id: int,
    section_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    section = (
        db.query(BookSection)
        .join(Book)
        .filter(
            BookSection.id == section_id,
            BookSection.book_id == book_id,
            Book.teacher_id == user.id,
        )
        .first()
    )
    if section:
        db.delete(section)
        db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/assign")
async def assign_students(
    book_id: int,
    request: Request,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = (
        db.query(Book)
        .options(joinedload(Book.sections))
        .filter(Book.id == book_id, Book.teacher_id == user.id)
        .first()
    )
    if not book:
        raise HTTPException(status_code=404)

    form = await request.form()
    selected_ids: set[int] = set()
    for v in form.getlist("student_ids"):
        try:
            selected_ids.add(int(v))
        except (TypeError, ValueError):
            pass

    if selected_ids:
        valid_ids = {
            u.id for u in db.query(User).filter(
                User.teacher_id == user.id,
                User.role == UserRole.STUDENT,
                User.id.in_(selected_ids),
            ).all()
        }
    else:
        valid_ids = set()

    existing_sb = {
        sb.student_id: sb for sb in db.query(StudentBook)
        .filter(StudentBook.book_id == book.id).all()
    }

    # Yeni atamalar
    for sid in valid_ids:
        if sid in existing_sb:
            continue
        sb = StudentBook(student_id=sid, book_id=book.id)
        db.add(sb)
        db.flush()
        for section in book.sections:
            db.add(SectionProgress(
                student_book_id=sb.id,
                book_section_id=section.id,
                reserved_count=0,
                completed_count=0,
            ))

    # Artık seçili değilse sil (rezerv/tamamlanan varsa uyarı vermeden silme — basit MVP)
    for sid, sb in existing_sb.items():
        if sid not in valid_ids:
            # Güvenli: yalnızca hiç ilerleme yoksa sil
            has_progress = any(
                p.reserved_count > 0 or p.completed_count > 0 for p in sb.section_progress
            )
            if not has_progress:
                db.delete(sb)

    db.commit()
    return RedirectResponse(
        url=f"/teacher/books/{book_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/{book_id}/delete")
def delete_book(
    book_id: int,
    user: User = Depends(require_teacher),
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.id == book_id, Book.teacher_id == user.id).first()
    if book:
        db.delete(book)
        db.commit()
    return RedirectResponse(url="/teacher/books", status_code=status.HTTP_303_SEE_OTHER)
