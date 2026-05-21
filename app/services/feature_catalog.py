"""Katman 1 — Özellik Kataloğu servisi.

CRUD + sorgu yardımcıları. Audit kaydı çağıran tarafta (admin route)
log_action ile yapılır — service katmanı sadece DB ile uğraşır.

Kullanım:
    from app.services import feature_catalog as fc

    cards = fc.list_for_admin(db)
    card = fc.get_by_slug(db, "rotam")
    fc.create(db, slug="x", title="X", domain="lgs", actor_id=user.id)

Anasayfa (Katman 2) için:
    fc.get_published_visible(db)  # status=PUBLISHED + manual_hide=False
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    FeatureCard,
    FeatureDomain,
    FeatureStatus,
    FeatureTier,
    UserRole,
)


logger = logging.getLogger(__name__)


_SLUG_RE = re.compile(r"[^a-z0-9]+")
_TR_REPLACEMENTS = {
    "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
    "Ç": "c", "Ğ": "g", "İ": "i", "Ö": "o", "Ş": "s", "Ü": "u",
}


def slugify(s: str) -> str:
    """URL-safe slug üret (Türkçe karakter dönüştür + bağlaç)."""
    s = (s or "").strip().lower()
    for k, v in _TR_REPLACEMENTS.items():
        s = s.replace(k, v)
    s = _SLUG_RE.sub("-", s).strip("-")
    return s[:80]


_HEX_COLOR_RE = re.compile(r"^#?[0-9a-fA-F]{3,8}$")


def normalize_accent_color(value: str | None) -> str:
    """Hex tonunu '#rrggbb' formuna getirir; geçersizse default mavi."""
    default = "#3b82f6"
    if not value:
        return default
    v = value.strip()
    if not _HEX_COLOR_RE.match(v):
        return default
    if not v.startswith("#"):
        v = "#" + v
    return v


class FeatureCatalogError(Exception):
    """Servis seviyesi doğrulama hatası — UI'da flash mesajı olarak gösterilir."""


# ---------------------------- Sorgular ----------------------------


def get_by_id(db: Session, card_id: int) -> FeatureCard | None:
    return db.get(FeatureCard, card_id)


def get_by_slug(db: Session, slug: str) -> FeatureCard | None:
    return db.query(FeatureCard).filter(FeatureCard.slug == slug).first()


def list_for_admin(
    db: Session, *,
    status_filter: str | None = None,
    domain_filter: str | None = None,
    tier_filter: str | None = None,
    search: str | None = None,
) -> list[FeatureCard]:
    """Süper admin listesi — filtreleme + ad/slug araması."""
    q = db.query(FeatureCard)
    if status_filter:
        q = q.filter(FeatureCard.status == status_filter)
    if domain_filter:
        q = q.filter(FeatureCard.domain == domain_filter)
    if tier_filter:
        q = q.filter(FeatureCard.tier == tier_filter)
    if search:
        like = f"%{search.lower().strip()}%"
        q = q.filter(or_(
            FeatureCard.slug.ilike(like),
            FeatureCard.title.ilike(like),
        ))
    # Sıralama: pin → priority → yeni → eski
    return (
        q.order_by(
            FeatureCard.manual_pin.desc(),
            FeatureCard.strategic_priority.desc(),
            FeatureCard.introduced_at.desc(),
        )
        .all()
    )


def get_published_visible(db: Session) -> list[FeatureCard]:
    """Yayında + gizli değil — tüm kartlar (limitsiz).

    Pin'li olanlar önce, sonra priority, sonra yeni.
    """
    cards = (
        db.query(FeatureCard)
        .filter(
            FeatureCard.status == FeatureStatus.PUBLISHED.value,
            FeatureCard.manual_hide.is_(False),
        )
        .order_by(
            FeatureCard.strategic_priority.desc(),
            FeatureCard.introduced_at.desc(),
        )
        .all()
    )
    # Pin durumu zaman-bağımlı (pin_until kontrolü), Python tarafında sırala
    now = datetime.now(timezone.utc)
    cards.sort(key=lambda c: (0 if c.is_pinned(now) else 1, -c.strategic_priority))
    return cards


def _build_landing_cards(
    db: Session,
    *,
    limit: int,
    viewer,
    session_id: str | None,
    strategy_key: str | None,
) -> tuple[list[FeatureCard], str | None]:
    """İç yardımcı — (kart listesi, variant_slug) döner.

    Strateji seçimi (Katman 9):
      1. strategy_key parametresi varsa onu kullan
      2. Aktif RUNNING deney + session_id varsa → variant ataması
      3. Aksi halde varsayılan: hybrid_full (fuzzy + bandit + MMR)
    """
    rows = (
        db.query(FeatureCard)
        .filter(
            FeatureCard.status == FeatureStatus.PUBLISHED.value,
            FeatureCard.manual_hide.is_(False),
            FeatureCard.mockup_type.isnot(None),
            FeatureCard.mockup_type != "",
        )
        .all()
    )
    if not rows:
        return [], None

    now = datetime.now(timezone.utc)

    from app.services import landing_strategies as ls
    from app.services import experiments as exp

    variant_slug: str | None = None
    chosen_key: str = strategy_key or ls.DEFAULT_STRATEGY
    if strategy_key is None and session_id:
        active = exp.get_active_experiment(db)
        if active is not None:
            variant_slug, chosen_key = exp.assign_variant(active, session_id)

    strategy = ls.get_strategy(chosen_key)

    # Pin'liler her zaman tepede — strateji yalnız non-pinned'a uygulanır
    pinned = [c for c in rows if c.is_pinned(now)]
    pinned.sort(key=lambda c: c.introduced_at)

    non_pinned = [c for c in rows if not c.is_pinned(now)]
    remaining_slots = limit - len(pinned)
    if remaining_slots <= 0:
        return pinned[:limit], variant_slug

    ranked = strategy(non_pinned, db, viewer, now, remaining_slots)
    return (pinned + ranked)[:limit], variant_slug


def get_for_landing(
    db: Session,
    *,
    limit: int = 5,
    role: str | None = None,
    viewer=None,
) -> list[FeatureCard]:
    """Anasayfa kartları — yalnız liste (eski imza, geriye uyumlu).

    A/B test variant'ına ihtiyaç varsa `get_for_landing_with_variant`
    çağrılmalıdır.
    """
    cards, _ = _build_landing_cards(
        db, limit=limit, viewer=viewer, session_id=None, strategy_key=None,
    )
    return cards


def get_for_landing_with_variant(
    db: Session,
    *,
    limit: int = 5,
    viewer=None,
    session_id: str | None = None,
    strategy_key: str | None = None,
) -> tuple[list[FeatureCard], str | None]:
    """Anasayfa kartları + variant_slug (A/B test çerçevesiyle).

    Landing route bunu kullanır; variant_slug telemetri event'lerine
    aktarılır (Katman 9 istatistik agregasyonu için).
    """
    return _build_landing_cards(
        db, limit=limit, viewer=viewer,
        session_id=session_id, strategy_key=strategy_key,
    )


def count_by_status(db: Session) -> dict[str, int]:
    """Durum bazında sayım (dashboard rozetleri için)."""
    out: dict[str, int] = {s.value: 0 for s in FeatureStatus}
    rows = (
        db.query(FeatureCard.status, FeatureCard.id)
        .all()
    )
    for status, _ in rows:
        if status in out:
            out[status] += 1
    return out


# ---------------------------- Doğrulama ----------------------------


def _validate_slug(db: Session, slug: str, *, exclude_id: int | None = None) -> str:
    """Slug normalize + uniqueness kontrol. FeatureCatalogError fırlatabilir."""
    if not slug or not slug.strip():
        raise FeatureCatalogError("Slug boş olamaz.")
    normalized = slugify(slug)
    if not normalized:
        raise FeatureCatalogError("Slug geçerli karakter içermiyor (a-z, 0-9, -).")
    existing = get_by_slug(db, normalized)
    if existing is not None and existing.id != exclude_id:
        raise FeatureCatalogError(f"'{normalized}' slug zaten kullanılıyor.")
    return normalized


def _validate_enum(value: str, enum_cls, field: str) -> str:
    """Değerin enum'da olup olmadığını kontrol et."""
    try:
        return enum_cls(value).value
    except (ValueError, TypeError) as exc:
        raise FeatureCatalogError(
            f"Geçersiz {field}: '{value}'."
        ) from exc


def _validate_priority(value: int | str | None) -> int:
    """1-5 arası int."""
    if value is None or value == "":
        return 3
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise FeatureCatalogError("Stratejik öncelik 1-5 arası tam sayı olmalı.") from exc
    if n < 1 or n > 5:
        raise FeatureCatalogError("Stratejik öncelik 1-5 aralığında olmalı.")
    return n


def _clean_role_list(roles: Iterable | None) -> list[str]:
    """UserRole.value listesi olarak temizle."""
    if not roles:
        return []
    valid = {r.value for r in UserRole}
    out: list[str] = []
    for r in roles:
        if isinstance(r, UserRole):
            out.append(r.value)
        elif isinstance(r, str) and r in valid:
            out.append(r)
    # Tekrarı kaldır, sırayı koru
    seen: set[str] = set()
    deduped: list[str] = []
    for r in out:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def _clean_str_list(items: Iterable | None, *, max_each: int = 240) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    for x in items:
        if x is None:
            continue
        s = str(x).strip()
        if s:
            out.append(s[:max_each])
    return out


# ---------------------------- CRUD ----------------------------


def create(
    db: Session, *,
    actor_id: int | None,
    slug: str,
    title: str,
    tagline: str = "",
    description_md: str = "",
    icon: str = "sparkles",
    accent_color: str = "#3b82f6",
    category_icon: str = "✨",
    category_label: str = "",
    demo_duration_label: str | None = None,
    mockup_type: str | None = None,
    target_roles: Iterable | None = None,
    benefits: Iterable | None = None,
    pain_points: Iterable | None = None,
    demo_slug: str | None = None,
    domain: str = FeatureDomain.GENEL.value,
    tier: str = FeatureTier.ENHANCEMENT.value,
    status: str = FeatureStatus.DRAFT.value,
    introduced_at: datetime | None = None,
    introduced_in_commit: str | None = None,
    pr_url: str | None = None,
    strategic_priority: int | str | None = 3,
    manual_pin: bool = False,
    pin_until: datetime | None = None,
    manual_hide: bool = False,
    cta_label: str = "Detayları gör",
    cta_url: str | None = None,
) -> FeatureCard:
    """Yeni özellik kartı oluştur — tüm alanlar doğrulanır."""
    slug = _validate_slug(db, slug)
    if not title or not title.strip():
        raise FeatureCatalogError("Başlık boş olamaz.")
    domain = _validate_enum(domain, FeatureDomain, "alan")
    tier = _validate_enum(tier, FeatureTier, "düzey")
    status = _validate_enum(status, FeatureStatus, "durum")
    priority = _validate_priority(strategic_priority)

    # Mockup_type doğrulama (registry'de mi)
    from app.services.mockup_registry import is_valid_key as _mockup_valid
    if not _mockup_valid(mockup_type):
        raise FeatureCatalogError(f"Bilinmeyen mockup şablonu: '{mockup_type}'")
    mockup_clean = (mockup_type or "").strip() or None
    if mockup_clean == "none":
        mockup_clean = None

    card = FeatureCard(
        slug=slug,
        category_icon=(category_icon or "✨").strip()[:16] or "✨",
        category_label=(category_label or "").strip()[:64],
        title=title.strip()[:160],
        tagline=(tagline or "").strip()[:400],
        description_md=description_md or "",
        icon=(icon or "sparkles").strip()[:64],
        accent_color=normalize_accent_color(accent_color),
        demo_slug=(demo_slug or "").strip() or None,
        demo_duration_label=(demo_duration_label or "").strip()[:64] or None,
        mockup_type=mockup_clean,
        domain=domain,
        tier=tier,
        status=status,
        introduced_at=introduced_at or datetime.now(timezone.utc),
        introduced_in_commit=(introduced_in_commit or "").strip() or None,
        pr_url=(pr_url or "").strip() or None,
        strategic_priority=priority,
        manual_pin=bool(manual_pin),
        pin_until=pin_until,
        manual_hide=bool(manual_hide),
        cta_label=(cta_label or "Detayları gör").strip()[:80] or "Detayları gör",
        cta_url=(cta_url or "").strip() or None,
        created_by=actor_id,
        updated_by=actor_id,
    )
    # Setter'lar JSON'a serialize eder
    card.target_roles = _clean_role_list(target_roles)
    card.benefits = _clean_str_list(benefits)
    card.pain_points = _clean_str_list(pain_points)

    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def update(
    db: Session, card: FeatureCard, *,
    actor_id: int | None,
    **fields: Any,
) -> FeatureCard:
    """Bir kartı güncelle. None olmayan alanlar uygulanır.

    'slug' verilirse uniqueness kontrolü yapılır (kendisi hariç).
    """
    if "slug" in fields and fields["slug"] is not None:
        card.slug = _validate_slug(db, fields["slug"], exclude_id=card.id)
    if "title" in fields and fields["title"] is not None:
        title = (fields["title"] or "").strip()
        if not title:
            raise FeatureCatalogError("Başlık boş olamaz.")
        card.title = title[:160]
    if "tagline" in fields:
        card.tagline = (fields["tagline"] or "").strip()[:400]
    if "category_icon" in fields:
        card.category_icon = (fields["category_icon"] or "✨").strip()[:16] or "✨"
    if "category_label" in fields:
        card.category_label = (fields["category_label"] or "").strip()[:64]
    if "demo_duration_label" in fields:
        v = (fields["demo_duration_label"] or "").strip()[:64]
        card.demo_duration_label = v or None
    if "mockup_type" in fields:
        from app.services.mockup_registry import is_valid_key as _mockup_valid
        v = (fields["mockup_type"] or "").strip() or None
        if v == "none":
            v = None
        if not _mockup_valid(v):
            raise FeatureCatalogError(f"Bilinmeyen mockup şablonu: '{v}'")
        card.mockup_type = v
    if "description_md" in fields:
        card.description_md = fields["description_md"] or ""
    if "icon" in fields and fields["icon"]:
        card.icon = str(fields["icon"]).strip()[:64]
    if "accent_color" in fields:
        card.accent_color = normalize_accent_color(fields["accent_color"])
    if "target_roles" in fields:
        card.target_roles = _clean_role_list(fields["target_roles"])
    if "benefits" in fields:
        card.benefits = _clean_str_list(fields["benefits"])
    if "pain_points" in fields:
        card.pain_points = _clean_str_list(fields["pain_points"])
    if "demo_slug" in fields:
        ds = (fields["demo_slug"] or "").strip()
        card.demo_slug = ds or None
    if "domain" in fields and fields["domain"]:
        card.domain = _validate_enum(fields["domain"], FeatureDomain, "alan")
    if "tier" in fields and fields["tier"]:
        card.tier = _validate_enum(fields["tier"], FeatureTier, "düzey")
    if "status" in fields and fields["status"]:
        card.status = _validate_enum(fields["status"], FeatureStatus, "durum")
    if "introduced_at" in fields and fields["introduced_at"]:
        card.introduced_at = fields["introduced_at"]
    if "introduced_in_commit" in fields:
        v = (fields["introduced_in_commit"] or "").strip()
        card.introduced_in_commit = v or None
    if "pr_url" in fields:
        v = (fields["pr_url"] or "").strip()
        card.pr_url = v or None
    if "strategic_priority" in fields:
        card.strategic_priority = _validate_priority(fields["strategic_priority"])
    if "manual_pin" in fields:
        card.manual_pin = bool(fields["manual_pin"])
    if "pin_until" in fields:
        card.pin_until = fields["pin_until"]
    if "manual_hide" in fields:
        card.manual_hide = bool(fields["manual_hide"])
    if "cta_label" in fields and fields["cta_label"]:
        card.cta_label = str(fields["cta_label"]).strip()[:80] or "Detayları gör"
    if "cta_url" in fields:
        v = (fields["cta_url"] or "").strip()
        card.cta_url = v or None

    card.updated_by = actor_id
    db.commit()
    db.refresh(card)
    return card


def delete(db: Session, card: FeatureCard) -> bool:
    """Kartı sil. True dönerse silindi."""
    db.delete(card)
    db.commit()
    return True


def set_status(
    db: Session, card: FeatureCard, new_status: str, *, actor_id: int | None,
) -> FeatureCard:
    """Sadece status değiştir. Audit ayrı action ile loglanır."""
    new_status = _validate_enum(new_status, FeatureStatus, "durum")
    card.status = new_status
    card.updated_by = actor_id
    db.commit()
    db.refresh(card)
    return card


def set_pin(
    db: Session, card: FeatureCard, *,
    pinned: bool, until: datetime | None = None, actor_id: int | None,
) -> FeatureCard:
    """Pin durumunu değiştir (süresiz veya tarihli)."""
    card.manual_pin = bool(pinned)
    card.pin_until = until if pinned else None
    card.updated_by = actor_id
    db.commit()
    db.refresh(card)
    return card
