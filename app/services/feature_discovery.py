"""Katman 3 — Otomatik Keşif (Auto-Discovery).

Projeye eklenen değişiklikleri tarayıp Süper Admin'in onayına sunulabilecek
TASLAK (DRAFT) özellik kartı adayları üretir. İki kaynak:

  1) Alembic migration dosyaları (alembic/versions/*.py):
     Modül docstring'inin ilk satırı = aday başlığı; geri kalanı tagline'a.
     Dosyanın git'e eklendiği commit = introduced_at + introduced_in_commit.

  2) Git commit mesajları (`git log --since=...`):
     Subject'i "feature-ish" filtreden geçenler aday olur.
     fix/chore/docs/refactor/test/style/polish/tweak/wip/revert/merge önekli
     commitler kapsam dışı.

Üretilen adaylar `FeatureCandidate` dataclass'ı olarak döner; `apply_candidates`
DB'ye `status=DRAFT` kartlar yazar (slug çakışması varsa atlar) ve
`AuditAction.FEATURE_CARD_AUTO_DISCOVERED` ile audit'ler.

Kullanım:
    from app.services import feature_discovery as fd
    candidates = fd.discover_all(since=datetime.utcnow() - timedelta(days=60))
    counts = fd.apply_candidates(db, candidates, actor_id=admin.id)

Katman 4 (onay kuyruğu) bu DRAFT'ları toplayıp süper admin'e gösterecek.
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import (
    AuditAction,
    FeatureCard,
    FeatureDomain,
    FeatureStatus,
    FeatureTier,
)
from app.services import feature_catalog as fc
from app.services.audit import log_action


logger = logging.getLogger(__name__)


REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = REPO_ROOT / "alembic" / "versions"


# Commit subject'i bu öneklerden biriyle başlıyorsa aday değil — gürültü.
SKIP_COMMIT_PREFIXES = re.compile(
    r"^(fix|chore|docs?|refactor|test|style|polish|tweak|wip|revert|merge|cleanup|format|build|ci)"
    r"[:\(\s]",
    re.IGNORECASE,
)

# Migration docstring'inde metadata satırları (atla)
_MIGRATION_META_RE = re.compile(r"^(Revision ID|Revises|Create Date)\s*:", re.IGNORECASE)


@dataclass
class FeatureCandidate:
    """Yayına geçirilmeden önce admin'in görebileceği aday kart."""
    slug: str
    title: str
    tagline: str
    domain: str
    tier: str
    introduced_at: datetime
    introduced_in_commit: str | None
    source: str  # "migration" | "commit"
    source_ref: str  # migration revision id veya commit SHA(7)
    raw_subject: str = ""

    def to_label(self) -> str:
        return f"[{self.source:9s}] {self.introduced_at:%Y-%m-%d}  {self.title[:70]}"


# ---------------------------- migration kaynağı ----------------------------


def _parse_migration_docstring(path: Path) -> tuple[str | None, str]:
    """Migration dosyasının modül docstring'inden (başlık, gövde) çıkar."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError) as e:
        logger.debug("migration parse hatası %s: %s", path.name, e)
        return None, ""
    doc = ast.get_docstring(tree)
    if not doc:
        return None, ""
    lines = [line.rstrip() for line in doc.split("\n")]
    # İlk dolu satır = başlık
    title = ""
    for line in lines:
        if line.strip():
            title = line.strip()
            break
    if not title:
        return None, ""
    # Geri kalan: metadata satırlarını ele, ilk 3 dolu satırı tagline yap
    body_lines: list[str] = []
    for line in lines[1:]:
        s = line.strip()
        if not s:
            continue
        if _MIGRATION_META_RE.match(s):
            continue
        body_lines.append(s)
        if len(body_lines) >= 3:
            break
    return title, " ".join(body_lines)


def _git_added_commit(path: Path) -> tuple[str | None, datetime | None]:
    """Dosyanın git'e eklendiği commit'in SHA + tarihini döner.

    `git log --diff-filter=A -- <path>` çıktısı: her yeni-ekleme bir satır.
    Birden fazla varsa en eski (dosya rename'lerinde olabilir) alınır.
    """
    try:
        out = subprocess.check_output(
            [
                "git", "log",
                "--diff-filter=A",
                "--pretty=format:%H|%aI",
                "--", str(path),
            ],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None
    if not out:
        return None, None
    line = out.splitlines()[-1]  # en eski (son satır)
    parts = line.split("|", 1)
    if len(parts) != 2:
        return None, None
    sha = parts[0].strip()
    try:
        ts = datetime.fromisoformat(parts[1].strip())
    except ValueError:
        return sha or None, None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return sha, ts


def discover_from_migrations(*, since: datetime) -> list[FeatureCandidate]:
    """alembic/versions/*.py altındaki dosyaları aday olarak üret.

    since tarihinden önce eklenen migration'lar dahil edilmez.
    """
    candidates: list[FeatureCandidate] = []
    if not MIGRATIONS_DIR.exists():
        return candidates
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    for path in sorted(MIGRATIONS_DIR.glob("*.py")):
        if path.name.startswith("__"):
            continue
        title, body = _parse_migration_docstring(path)
        if not title:
            continue
        sha, added_at = _git_added_commit(path)
        if added_at is None:
            # Git geçmişi yoksa (örn. yeni klonlanmış dosya) → mtime
            try:
                added_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            except OSError:
                continue
        if added_at < since:
            continue

        revision = path.stem.split("_", 1)[0]
        slug = fc.slugify(f"keşif-mig-{revision}-{title}")[:80].rstrip("-")
        candidates.append(FeatureCandidate(
            slug=slug,
            title=_clean_title(title),
            tagline=body[:380],
            domain=FeatureDomain.GENEL.value,
            tier=FeatureTier.ENHANCEMENT.value,
            introduced_at=added_at,
            introduced_in_commit=sha,
            source="migration",
            source_ref=revision,
            raw_subject=title,
        ))
    return candidates


# ---------------------------- commit kaynağı ----------------------------


def discover_from_commits(*, since: datetime) -> list[FeatureCandidate]:
    """git log üzerinden aday üret. SKIP_COMMIT_PREFIXES'e uyanlar atlanır."""
    candidates: list[FeatureCandidate] = []
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    since_iso = since.strftime("%Y-%m-%d")
    try:
        out = subprocess.check_output(
            [
                "git", "log",
                f"--since={since_iso}",
                "--pretty=format:%H|%aI|%s",
            ],
            cwd=str(REPO_ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return candidates

    for raw in out.splitlines():
        parts = raw.split("|", 2)
        if len(parts) != 3:
            continue
        sha, date_iso, subject = parts
        subject = subject.strip()
        if not subject or len(subject) < 10:
            continue
        if SKIP_COMMIT_PREFIXES.match(subject):
            continue
        try:
            ts = datetime.fromisoformat(date_iso.strip())
        except ValueError:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts < since:
            continue
        short = sha[:7]
        slug = fc.slugify(f"keşif-c-{short}-{subject}")[:80].rstrip("-")
        candidates.append(FeatureCandidate(
            slug=slug,
            title=_clean_title(subject),
            tagline="",  # commit subject zaten title; body için ayrı `%b` alabilirdik
            domain=FeatureDomain.GENEL.value,
            tier=FeatureTier.ENHANCEMENT.value,
            introduced_at=ts,
            introduced_in_commit=sha,
            source="commit",
            source_ref=short,
            raw_subject=subject,
        ))
    return candidates


# ---------------------------- birleşik tarama + DB yazma ----------------------------


def discover_all(
    *,
    since: datetime,
    sources: Iterable[str] = ("migration", "commit"),
) -> list[FeatureCandidate]:
    """Seçilen kaynaklardan aday üret, sırala (yeniden eskiye)."""
    out: list[FeatureCandidate] = []
    s = set(sources)
    if "migration" in s:
        out.extend(discover_from_migrations(since=since))
    if "commit" in s:
        out.extend(discover_from_commits(since=since))
    # Aynı commit'in hem migration hem commit tarafında çıkması olası — slug
    # benzersizliği yine de farklı (mig-/c-) olduğundan ikisi de gelir.
    out.sort(key=lambda c: c.introduced_at, reverse=True)
    return out


def run_scan(
    db: Session,
    *,
    actor_id: int | None = None,
    days: int = 120,
    sources: Iterable[str] = ("migration", "commit"),
) -> dict[str, int | list[str]]:
    """Tek adımda tara + uygula (endpoint + cron paylaşır).

    Son `days` gün içindeki migration + commit'leri tarar, yeni adayları DRAFT
    keşif kartı olarak yazar (apply_candidates idempotent → mevcutları atlar).
    Returns: {"created": N, "skipped": M, "errors": [...], "candidates": K}.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    candidates = discover_all(since=since, sources=sources)
    counts = apply_candidates(db, candidates, actor_id=actor_id)
    counts["candidates"] = len(candidates)
    return counts


def apply_candidates(
    db: Session,
    candidates: list[FeatureCandidate],
    *,
    actor_id: int | None = None,
    dry_run: bool = False,
    limit: int | None = None,
) -> dict[str, int | list[str]]:
    """Adayları DRAFT FeatureCard olarak yaz.

    - Slug çakışırsa: atla (idempotent)
    - Doğrulama hatası: skipped sayar, slug'ı `errors` listesine koyar
    - dry_run=True ise DB'ye yazmaz, sadece sayı döner
    - limit verildiyse en yeniden geriye o kadarını uygular

    Returns: {"created": N, "skipped": M, "errors": [...]}
    """
    counts: dict[str, int | list[str]] = {"created": 0, "skipped": 0, "errors": []}
    iterable = candidates[:limit] if limit is not None else candidates

    for cand in iterable:
        existing = fc.get_by_slug(db, cand.slug)
        if existing is not None:
            counts["skipped"] = int(counts["skipped"]) + 1
            continue
        if dry_run:
            counts["created"] = int(counts["created"]) + 1
            continue
        try:
            card = fc.create(
                db,
                actor_id=actor_id,
                slug=cand.slug,
                title=cand.title,
                category_icon="🆕",
                category_label="Yeni Keşif",
                tagline=cand.tagline or "(otomatik üretildi — admin düzenleyecek)",
                description_md=cand.tagline or "",
                domain=cand.domain,
                tier=cand.tier,
                status=FeatureStatus.DRAFT.value,
                target_roles=[],
                introduced_at=cand.introduced_at,
                introduced_in_commit=cand.introduced_in_commit,
                strategic_priority=2,
            )
            log_action(
                db,
                action=AuditAction.FEATURE_CARD_AUTO_DISCOVERED,
                actor_id=actor_id,
                target_type="feature_card",
                target_id=card.id,
                details={
                    "source": cand.source,
                    "source_ref": cand.source_ref,
                    "raw_subject": cand.raw_subject[:200],
                },
                autocommit=False,
            )
            counts["created"] = int(counts["created"]) + 1
        except fc.FeatureCatalogError as e:
            counts["skipped"] = int(counts["skipped"]) + 1
            counts["errors"].append(f"{cand.slug}: {e}")  # type: ignore[union-attr]
        except Exception as e:  # noqa: BLE001
            logger.warning("apply_candidates beklenmeyen hata %s: %s", cand.slug, e)
            counts["skipped"] = int(counts["skipped"]) + 1
            counts["errors"].append(f"{cand.slug}: {e!r}")  # type: ignore[union-attr]

    if not dry_run:
        db.commit()
    return counts


# ---------------------------- yardımcılar ----------------------------


def _clean_title(s: str) -> str:
    """Başlığı kırp + sonundaki noktaları temizle."""
    t = s.strip().strip(".:- ")
    return t[:155]
