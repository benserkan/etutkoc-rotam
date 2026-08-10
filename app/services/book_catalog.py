"""Ortak Kitap Kataloğu — TEK MERKEZ servis.

Katalog = global BookTemplate (teacher_id NULL + catalog_status dolu).
Bir yayınevi kitabının GERÇEK yapısı (ünite + birebir test sayısı + builtin
müfredat eşleştirmesi) bir kez tanımlanır; tüm koçlar tek tıkla kullanır.

Üç doldurma kanalı:
  1. Süper admin seed'i (örnek PDF/foto okuma veya elle)  → doğrudan verified
  2. Koç katkısı (sihirbazdan, anonim)                    → pending (admin onaylar)
  3. ai_book_structure okuma motoru her iki kanalın aracı

Görünürlük kuralları (sızıntı testleri bunları kilitler):
  - Koç YALNIZ verified kayıtları görür/kullanır.
  - Kişisel şablon sorguları (teacher_id == user.id) katalog satırı DÖNDÜRMEZ
    (teacher_id NULL olduğundan filtre doğal olarak dışlar).
  - Katalog kaydına yalnız BUILTIN ders/konu bağlanır (herkes için geçerli).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import BookTemplate, BookTemplateSection, BookType, Subject, Topic, User
from app.models.book import (
    CATALOG_STATUS_HIDDEN,
    CATALOG_STATUS_PENDING,
    CATALOG_STATUS_VERIFIED,
    CATALOG_STATUSES,
)

logger = logging.getLogger(__name__)

SEARCH_LIMIT = 20


class CatalogError(Exception):
    """code + mesaj taşıyan servis hatası (router HTTP'ye çevirir)."""

    def __init__(self, code: str, message: str, *, entry_id: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.entry_id = entry_id


# =============================================================================
# Anahtar üretimi + arama
# =============================================================================


def normalized_key(s: str | None) -> str:
    from app.services.curriculum_mapping import normalize

    return normalize(s)


def _catalog_base(db: Session):
    return (
        db.query(BookTemplate)
        .options(
            joinedload(BookTemplate.sections).joinedload(BookTemplateSection.topic),
        )
        .filter(BookTemplate.teacher_id.is_(None), BookTemplate.catalog_status.isnot(None))
    )


def search_catalog(
    db: Session,
    q: str,
    *,
    subject_id: int | None = None,
    limit: int = SEARCH_LIMIT,
) -> list[BookTemplate]:
    """Verified kayıtlarda ad/yayınevi araması.

    Sıralama: tam normalize eşleşme > ad-öneki > içerir; eşitlikte usage_count.
    Aday kümesi küçük olduğundan sıralama Python'da yapılır.
    """
    nq = normalized_key(q)
    if len(nq) < 2:
        return []
    like = f"%{nq}%"
    rows = (
        _catalog_base(db)
        .filter(
            BookTemplate.catalog_status == CATALOG_STATUS_VERIFIED,
            or_(
                BookTemplate.name_normalized.like(like),
                BookTemplate.publisher_normalized.like(like),
            ),
        )
        .all()
    )
    if subject_id is not None:
        rows = [r for r in rows if r.subject_id == subject_id]

    def rank(t: BookTemplate) -> tuple:
        name_n = t.name_normalized or ""
        if name_n == nq:
            r = 0
        elif name_n.startswith(nq):
            r = 1
        elif nq in name_n:
            r = 2
        else:
            r = 3  # yalnız yayınevi eşleşti
        return (r, -(t.usage_count or 0), t.name or "")

    return sorted(rows, key=rank)[:limit]


def find_matches(
    db: Session, title: str | None, publisher: str | None = None, *, limit: int = 5,
) -> list[BookTemplate]:
    """Kapak tanıma / sihirbaz ad-yazımı için eşleşme adayları."""
    if not title:
        return []
    matches = search_catalog(db, title, limit=limit)
    if matches or not publisher:
        return matches
    return search_catalog(db, publisher, limit=limit)


def get_catalog_entry(
    db: Session, entry_id: int, *, statuses: tuple[str, ...] = (CATALOG_STATUS_VERIFIED,),
) -> BookTemplate:
    entry = (
        _catalog_base(db)
        .filter(BookTemplate.id == entry_id, BookTemplate.catalog_status.in_(statuses))
        .first()
    )
    if not entry:
        raise CatalogError("catalog_entry_not_found", "Katalog kaydı bulunamadı.")
    return entry


def get_owned_or_catalog_template(
    db: Session, template_id: int, teacher_id: int,
) -> BookTemplate:
    """Kitap oluştururken template çözümü: koçun KENDİ şablonu VEYA verified
    katalog kaydı. Başka koçun kişisel şablonu / pending / hidden → yok sayılır
    (404 sözleşmesi router'da)."""
    tpl = (
        db.query(BookTemplate)
        .options(joinedload(BookTemplate.sections))
        .filter(
            BookTemplate.id == template_id,
            or_(
                BookTemplate.teacher_id == teacher_id,
                BookTemplate.catalog_status == CATALOG_STATUS_VERIFIED,
            ),
        )
        .first()
    )
    return tpl


def bump_usage(entry: BookTemplate) -> None:
    entry.usage_count = (entry.usage_count or 0) + 1


# =============================================================================
# Oluşturma / katkı / güncelleme
# =============================================================================


def _validate_builtin_subject(db: Session, subject_id: int | None) -> int | None:
    """Katalog kaydına yalnız builtin ders bağlanır; değilse NULL'a düşer."""
    if subject_id is None:
        return None
    row = (
        db.query(Subject.id)
        .filter(Subject.id == subject_id, Subject.is_builtin.is_(True))
        .first()
    )
    return subject_id if row else None


def _validate_builtin_topic(
    db: Session, topic_id: int | None, subject_id: int | None,
) -> int | None:
    """Katalog bölümüne yalnız builtin + aynı dersin konusu bağlanır."""
    if topic_id is None or subject_id is None:
        return None
    row = (
        db.query(Topic.id)
        .filter(
            Topic.id == topic_id,
            Topic.subject_id == subject_id,
            Topic.is_builtin.is_(True),
        )
        .first()
    )
    return topic_id if row else None


def find_duplicate(
    db: Session, name: str, publisher: str | None,
) -> BookTemplate | None:
    """Normalize ad (+ yayınevi) ile pending/verified mükerrer kontrolü."""
    nn = normalized_key(name)
    if not nn:
        return None
    q = (
        db.query(BookTemplate)
        .filter(
            BookTemplate.teacher_id.is_(None),
            BookTemplate.catalog_status.in_(
                (CATALOG_STATUS_PENDING, CATALOG_STATUS_VERIFIED)
            ),
            BookTemplate.name_normalized == nn,
        )
    )
    np = normalized_key(publisher)
    rows = q.all()
    if not rows:
        return None
    if np:
        exact = [r for r in rows if (r.publisher_normalized or "") == np]
        if exact:
            return exact[0]
        # Aynı ad + farklı yayınevi → farklı kitap sayılır
        with_pub = [r for r in rows if r.publisher_normalized]
        if with_pub:
            return None
    return rows[0]


def create_entry(
    db: Session,
    *,
    name: str,
    publisher: str | None,
    book_type: BookType,
    subject_id: int | None,
    target_grade_min: int | None,
    target_grade_max: int | None,
    target_graduate: bool,
    sections: list[dict],
    status: str,
    source: str,
    contributed_by_id: int | None = None,
    verified_by_id: int | None = None,
    dedup: bool = True,
) -> BookTemplate:
    """Katalog kaydı oluştur (admin seed → verified · koç katkısı → pending).

    sections: [{label, test_count(>=1), topic_id?}] — sıra listedeki sıradır.
    Raises CatalogError("already_in_catalog") — dedup açıkken mükerrer ad+yayınevi.
    """
    name = (name or "").strip()
    if not name:
        raise CatalogError("name_required", "Kitap adı zorunlu.")
    if status not in CATALOG_STATUSES:
        raise CatalogError("invalid_status", "Geçersiz katalog durumu.")
    clean_sections: list[dict] = []
    for s in sections:
        label = str(s.get("label") or "").strip()
        if not label:
            continue
        try:
            tc = int(s.get("test_count") or 0)
        except (TypeError, ValueError):
            tc = 0
        if tc < 1:
            raise CatalogError(
                "invalid_test_count",
                f"'{label}' bölümünün test sayısı eksik — kataloğa girmeden önce doldurun.",
            )
        clean_sections.append({
            "label": label[:255], "test_count": min(tc, 500), "topic_id": s.get("topic_id"),
        })
    if len(clean_sections) < 1:
        raise CatalogError("no_sections", "En az bir bölüm gerekli.")

    if dedup:
        dup = find_duplicate(db, name, publisher)
        if dup is not None:
            raise CatalogError(
                "already_in_catalog",
                "Bu kitap katalogda zaten var"
                + (" (onay bekliyor)" if dup.catalog_status == CATALOG_STATUS_PENDING else "")
                + ".",
                entry_id=dup.id,
            )

    subject_id = _validate_builtin_subject(db, subject_id)
    now = datetime.now(timezone.utc)
    entry = BookTemplate(
        teacher_id=None,
        name=name[:255],
        publisher=(publisher or "").strip()[:255] or None,
        type=book_type,
        subject_id=subject_id,
        target_grade_min=target_grade_min,
        target_grade_max=target_grade_max,
        target_graduate=bool(target_graduate),
        is_ai_generated=(source == "ai_read"),
        is_verified=(status == CATALOG_STATUS_VERIFIED),
        catalog_status=status,
        source=source,
        name_normalized=normalized_key(name) or None,
        publisher_normalized=normalized_key(publisher) or None,
        contributed_by_id=contributed_by_id,
        verified_by_id=verified_by_id if status == CATALOG_STATUS_VERIFIED else None,
        verified_at=now if status == CATALOG_STATUS_VERIFIED else None,
    )
    db.add(entry)
    db.flush()
    created: list[BookTemplateSection] = []
    for i, s in enumerate(clean_sections):
        sec = BookTemplateSection(
            template_id=entry.id,
            label=s["label"],
            default_test_count=s["test_count"],
            order=i,
            topic_id=_validate_builtin_topic(db, s.get("topic_id"), subject_id),
        )
        db.add(sec)
        created.append(sec)
    db.flush()
    # Eşlenmemiş bölümleri deterministik auto-map ile builtin konulara bağla
    # (best-effort — eşleşmeyen kalır, kayıt bloklanmaz).
    try:
        auto_map_sections(db, entry, created)
    except Exception:  # noqa: BLE001
        logger.warning("Katalog auto-map atlandı (entry=%s)", entry.id, exc_info=True)
    return entry


def update_entry(
    db: Session,
    entry: BookTemplate,
    *,
    name: str | None = None,
    publisher: str | None = None,
    book_type: BookType | None = None,
    subject_id: int | None = None,
    target_grade_min: int | None = None,
    target_grade_max: int | None = None,
    target_graduate: bool | None = None,
    sections: list[dict] | None = None,
) -> BookTemplate:
    """Admin düzenlemesi. sections verilirse TAMAMEN yer değiştirir.

    NOT: mevcut kitaplara kopyalanmış yapılar etkilenmez (kopya bağımsız);
    değişiklik yalnız bundan sonra katalogdan alacak koçlara yansır.
    """
    if name is not None:
        nn = name.strip()
        if not nn:
            raise CatalogError("name_required", "Kitap adı boş olamaz.")
        entry.name = nn[:255]
        entry.name_normalized = normalized_key(nn) or None
    if publisher is not None:
        entry.publisher = publisher.strip()[:255] or None
        entry.publisher_normalized = normalized_key(publisher) or None
    if book_type is not None:
        entry.type = book_type
    if subject_id is not None:
        new_subject = _validate_builtin_subject(db, subject_id)
        if new_subject != entry.subject_id:
            # Ders değişti → eski konular başka derse ait; sıfırla (Book PATCH deseni)
            for sec in entry.sections or []:
                sec.topic_id = None
        entry.subject_id = new_subject
    if target_grade_min is not None:
        entry.target_grade_min = target_grade_min if 4 <= target_grade_min <= 12 else None
    if target_grade_max is not None:
        entry.target_grade_max = target_grade_max if 4 <= target_grade_max <= 12 else None
    if target_graduate is not None:
        entry.target_graduate = bool(target_graduate)
    if sections is not None:
        clean: list[dict] = []
        for s in sections:
            label = str(s.get("label") or "").strip()
            if not label:
                continue
            try:
                tc = int(s.get("test_count") or 0)
            except (TypeError, ValueError):
                tc = 0
            if tc < 1:
                raise CatalogError(
                    "invalid_test_count",
                    f"'{label}' bölümünün test sayısı en az 1 olmalı.",
                )
            clean.append({"label": label[:255], "test_count": min(tc, 500), "topic_id": s.get("topic_id")})
        if not clean:
            raise CatalogError("no_sections", "En az bir bölüm gerekli.")
        for sec in list(entry.sections or []):
            db.delete(sec)
        db.flush()
        created: list[BookTemplateSection] = []
        for i, s in enumerate(clean):
            sec = BookTemplateSection(
                template_id=entry.id,
                label=s["label"],
                default_test_count=s["test_count"],
                order=i,
                topic_id=_validate_builtin_topic(db, s.get("topic_id"), entry.subject_id),
            )
            db.add(sec)
            created.append(sec)
        db.flush()
        try:
            auto_map_sections(db, entry, created)
        except Exception:  # noqa: BLE001
            logger.warning("Katalog auto-map atlandı (entry=%s)", entry.id, exc_info=True)
    return entry


def set_status(
    entry: BookTemplate, status: str, *, admin_id: int | None = None,
) -> BookTemplate:
    if status not in CATALOG_STATUSES:
        raise CatalogError("invalid_status", "Geçersiz katalog durumu.")
    entry.catalog_status = status
    if status == CATALOG_STATUS_VERIFIED:
        entry.is_verified = True
        entry.verified_by_id = admin_id
        entry.verified_at = datetime.now(timezone.utc)
    return entry


def contribute_from_sections(
    db: Session,
    coach: User,
    *,
    name: str,
    publisher: str | None,
    book_type: BookType,
    subject_id: int | None,
    target_grade_min: int | None,
    target_grade_max: int | None,
    target_graduate: bool,
    sections: list[dict],
) -> BookTemplate:
    """Koç katkısı → pending kayıt (anonim; contributed_by yalnız denetim izi).

    Konu bağları: koçun kitabındaki topic_id'lerden yalnız BUILTIN olanlar
    taşınır (kişisel konu kataloğa sızmaz — _validate_builtin_topic eler).
    """
    return create_entry(
        db,
        name=name,
        publisher=publisher,
        book_type=book_type,
        subject_id=subject_id,
        target_grade_min=target_grade_min,
        target_grade_max=target_grade_max,
        target_graduate=target_graduate,
        sections=sections,
        status=CATALOG_STATUS_PENDING,
        source="coach_contribution",
        contributed_by_id=coach.id,
        dedup=True,
    )


def _builtin_leaf_topics(db: Session, subject_id: int) -> list[Topic]:
    """Builtin LEAF konular (parent tema/üniteler eşleştirme adayı değil)."""
    all_topics = (
        db.query(Topic)
        .filter(Topic.subject_id == subject_id, Topic.is_builtin.is_(True))
        .order_by(Topic.order, Topic.name)
        .all()
    )
    parent_ids = {t.parent_id for t in all_topics if t.parent_id is not None}
    return [t for t in all_topics if t.id not in parent_ids]


def auto_map_sections(
    db: Session,
    entry: BookTemplate,
    sections: list[BookTemplateSection] | None = None,
) -> int:
    """Deterministik auto-map: topic'siz bölümleri etiket anahtarıyla builtin
    konulara bağlar (curriculum_mapping önek/bağlaç/alias katmanı — AI YOK,
    kredi YOK). Admin/koç elle eşleştirmek zorunda kalmaz; eşleşmeyen kalır.
    """
    if entry.subject_id is None:
        return 0
    from app.services import curriculum_mapping as cm

    topics = _builtin_leaf_topics(db, entry.subject_id)
    if not topics:
        return 0
    by_norm = cm._topics_by_norm(topics)
    n = 0
    for sec in sections if sections is not None else (entry.sections or []):
        if sec.topic_id is not None:
            continue
        t = by_norm.get(cm._label_key(sec.label))
        if t is not None:
            sec.topic_id = t.id
            n += 1
    return n


def status_counts(db: Session) -> dict[str, int]:
    rows = (
        db.query(BookTemplate.catalog_status)
        .filter(BookTemplate.teacher_id.is_(None), BookTemplate.catalog_status.isnot(None))
        .all()
    )
    out = {CATALOG_STATUS_VERIFIED: 0, CATALOG_STATUS_PENDING: 0, CATALOG_STATUS_HIDDEN: 0}
    for (s,) in rows:
        if s in out:
            out[s] += 1
    return out


def list_entries(
    db: Session, *, status: str | None = None, q: str | None = None, limit: int = 200,
) -> list[BookTemplate]:
    """Admin listesi — tüm durumlar."""
    base = _catalog_base(db)
    if status in CATALOG_STATUSES:
        base = base.filter(BookTemplate.catalog_status == status)
    if q:
        nq = normalized_key(q)
        if nq:
            like = f"%{nq}%"
            base = base.filter(
                or_(
                    BookTemplate.name_normalized.like(like),
                    BookTemplate.publisher_normalized.like(like),
                )
            )
    return (
        base.order_by(BookTemplate.created_at.desc()).limit(limit).all()
    )
