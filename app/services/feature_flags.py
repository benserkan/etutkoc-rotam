"""Stage 7 — Feature flags servisi.

Kullanım:
    from app.services.feature_flags import is_enabled

    if not is_enabled(db, "ai_book_template", institution=user.institution):
        raise FeatureDisabled("AI özelliği şu an kapalı")

Karar sırası:
1. Kuruma override varsa o kullanılır (her iki yön — açma veya kapatma)
2. Yoksa flag.enabled_globally
3. Tanımsız flag → True (defansif: kod yeni özelliği eklemiş ama DB'de
   henüz yoksa, davranış değişmesin)

Cache: process içinde TTL 60 sn — runtime sorgusunu hızlandır + DB yükünü
azalt. Toggle sonrası invalidate çağrılır (admin route ediyor).
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session, joinedload

from app.models import FeatureFlag, FeatureFlagOverride, Institution


logger = logging.getLogger(__name__)


# Cache TTL — runtime cache; admin toggle yapınca explicit invalidate
CACHE_TTL_SECONDS = 60.0


class FeatureDisabled(Exception):
    """Çağrılan özellik feature flag ile kapatılmış."""
    def __init__(self, key: str, *, scope: str = "global"):
        self.key = key
        self.scope = scope
        super().__init__(f"Özellik kapalı: {key} ({scope})")


@dataclass
class _CacheEntry:
    flags_by_key: dict[str, FeatureFlag]
    overrides_by_pair: dict[tuple[int, int], FeatureFlagOverride]   # (flag_id, inst_id)
    ts: float


_cache_lock = threading.Lock()
_cache: _CacheEntry | None = None


def _load_cache(db: Session) -> _CacheEntry:
    """DB'den tüm flagleri + overrideları çek, cache'e koy."""
    flags = db.query(FeatureFlag).all()
    overrides = db.query(FeatureFlagOverride).all()
    return _CacheEntry(
        flags_by_key={f.key: f for f in flags},
        overrides_by_pair={(o.feature_flag_id, o.institution_id): o for o in overrides},
        ts=time.monotonic(),
    )


def _get_cache(db: Session) -> _CacheEntry:
    global _cache
    with _cache_lock:
        if (
            _cache is None
            or (time.monotonic() - _cache.ts) >= CACHE_TTL_SECONDS
        ):
            _cache = _load_cache(db)
        return _cache


def invalidate_cache() -> None:
    """Admin toggle / override ekleme sonrası çağrılır."""
    global _cache
    with _cache_lock:
        _cache = None


def is_enabled(
    db: Session, key: str, *, institution: Institution | None = None,
    institution_id: int | None = None,
) -> bool:
    """Bir feature flag kuruma göre etkin mi?

    Hem `institution` (ORM obj) hem `institution_id` (int) kabul eder; iki
    parametreden biri yeterli. İkisi de None ise yalnız global ayar bakılır.

    Defansif: tanımsız flag → True (yeni özellik eklenip migration koşmamışsa
    davranış patlamasın).
    """
    cache = _get_cache(db)
    flag = cache.flags_by_key.get(key)
    if flag is None:
        logger.warning("is_enabled: tanımsız flag '%s' (defansif True)", key)
        return True

    iid = institution_id
    if iid is None and institution is not None:
        iid = institution.id

    if iid is not None:
        override = cache.overrides_by_pair.get((flag.id, iid))
        if override is not None:
            return bool(override.enabled)

    return bool(flag.enabled_globally)


def require_enabled(
    db: Session, key: str, *, institution: Institution | None = None,
    institution_id: int | None = None,
) -> None:
    """is_enabled False ise FeatureDisabled fırlat — route guard pattern."""
    if not is_enabled(db, key, institution=institution, institution_id=institution_id):
        scope = "kurum" if (institution_id or institution) else "global"
        raise FeatureDisabled(key, scope=scope)


# ---------------------------- Yönetici listing ----------------------------


def all_flags_for_admin(db: Session) -> list[dict]:
    """Süper admin paneli için tüm flag'lerin override sayısıyla listesi."""
    flags = (
        db.query(FeatureFlag)
        .options(joinedload(FeatureFlag.overrides))
        .order_by(FeatureFlag.key)
        .all()
    )
    out = []
    for f in flags:
        overrides_enabled = sum(1 for o in f.overrides if o.enabled)
        overrides_disabled = sum(1 for o in f.overrides if not o.enabled)
        out.append({
            "flag": f,
            "override_enabled_count": overrides_enabled,
            "override_disabled_count": overrides_disabled,
            "override_total": len(f.overrides),
        })
    return out


def get_overrides_for_flag(db: Session, flag_id: int) -> list[FeatureFlagOverride]:
    """Bir flag'in tüm override'ları (institution joinedload)."""
    return (
        db.query(FeatureFlagOverride)
        .options(joinedload(FeatureFlagOverride.institution))
        .filter(FeatureFlagOverride.feature_flag_id == flag_id)
        .order_by(FeatureFlagOverride.institution_id)
        .all()
    )


def set_global(db: Session, key: str, enabled: bool) -> FeatureFlag:
    """Global ayar değiştir + cache invalidate."""
    flag = db.query(FeatureFlag).filter(FeatureFlag.key == key).first()
    if flag is None:
        raise ValueError(f"Bilinmeyen flag: {key}")
    flag.enabled_globally = bool(enabled)
    db.commit()
    invalidate_cache()
    return flag


def set_override(
    db: Session, *, flag_id: int, institution_id: int, enabled: bool,
    note: str | None = None,
) -> FeatureFlagOverride:
    """Per-kurum override ekle veya güncelle."""
    existing = (
        db.query(FeatureFlagOverride)
        .filter(
            FeatureFlagOverride.feature_flag_id == flag_id,
            FeatureFlagOverride.institution_id == institution_id,
        )
        .first()
    )
    if existing:
        existing.enabled = bool(enabled)
        if note is not None:
            existing.note = note
        db.commit()
        invalidate_cache()
        return existing

    o = FeatureFlagOverride(
        feature_flag_id=flag_id,
        institution_id=institution_id,
        enabled=bool(enabled),
        note=note,
    )
    db.add(o)
    db.commit()
    invalidate_cache()
    return o


def remove_override(db: Session, override_id: int) -> bool:
    """Override sil (kurum global ayara döner). True dönerse silindi."""
    o = db.get(FeatureFlagOverride, override_id)
    if o is None:
        return False
    db.delete(o)
    db.commit()
    invalidate_cache()
    return True
