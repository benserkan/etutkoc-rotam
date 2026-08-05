"""Hedef Havuzu (sales_prospects) servisi — süper admin satış adayı yönetimi.

Sisteme üye olmayan kurum/koç adaylarını oluştur/listele/güncelle/sil + durum.
Üyelik teklifi (membership) bir prospect'i hedef alabilir (K1b).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import SalesProspect
from app.models.sales_prospect import (
    PROSPECT_KINDS, PROSPECT_KIND_COACH, PROSPECT_KIND_INSTITUTION,
    PROSPECT_STATUSES, PROSPECT_STATUS_NEW, PROSPECT_SOURCES,
)
from app.services.phone_service import normalize_e164_tr


def _clean_handle(v: str | None) -> str | None:
    """@user, instagram.com/user, boşluk → 'user' (küçük harf)."""
    h = (v or "").strip()
    if not h:
        return None
    for pre in ("https://", "http://", "www.", "instagram.com/", "instagr.am/"):
        if h.lower().startswith(pre):
            h = h[len(pre):]
    h = h.split("?")[0].split("/")[0].lstrip("@").strip().lower()
    return h[:80] or None


class ProspectError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_prospect(
    db: Session, *, actor_user_id: int | None,
    name: str, phone: str, kind: str = PROSPECT_KIND_COACH,
    org_name: str | None = None, email: str | None = None, city: str | None = None,
    source: str = "manual", opt_in: bool = False, note: str | None = None,
    instagram: str | None = None,
) -> SalesProspect:
    name = (name or "").strip()
    if len(name) < 2:
        raise ProspectError("invalid_name", "Ad en az 2 karakter olmalı.")
    norm = normalize_e164_tr(phone or "")
    if not norm:
        raise ProspectError("invalid_phone", "Geçerli bir cep telefonu girin (5XX...).")
    if kind not in PROSPECT_KINDS:
        kind = PROSPECT_KIND_COACH
    if source not in PROSPECT_SOURCES:
        source = "manual"
    # Aynı telefon zaten varsa tekrar ekleme (dedup)
    existing = db.query(SalesProspect).filter(SalesProspect.phone == norm).first()
    if existing is not None:
        raise ProspectError("duplicate_phone",
                            f"Bu telefon zaten havuzda: {existing.name}")
    p = SalesProspect(
        name=name, phone=norm, kind=kind,
        instagram=_clean_handle(instagram),
        org_name=(org_name or "").strip() or None,
        email=(email or "").strip() or None,
        city=(city or "").strip() or None,
        source=source, opt_in=bool(opt_in),
        note=(note or "").strip() or None,
        status=PROSPECT_STATUS_NEW, created_by_admin_id=actor_user_id,
    )
    db.add(p)
    db.flush()
    return p


def list_prospects(
    db: Session, *, status: str | None = None, kind: str | None = None,
    q: str | None = None, limit: int = 300,
) -> list[SalesProspect]:
    query = db.query(SalesProspect)
    if status and status in PROSPECT_STATUSES:
        query = query.filter(SalesProspect.status == status)
    if kind and kind in PROSPECT_KINDS:
        query = query.filter(SalesProspect.kind == kind)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            SalesProspect.name.ilike(like),
            SalesProspect.phone.ilike(like),
            SalesProspect.org_name.ilike(like),
            SalesProspect.email.ilike(like),
        ))
    return query.order_by(SalesProspect.created_at.desc()).limit(max(1, min(limit, 1000))).all()


def get_prospect(db: Session, prospect_id: int) -> SalesProspect | None:
    return db.get(SalesProspect, prospect_id)


def update_prospect(db: Session, p: SalesProspect, **fields) -> SalesProspect:
    if "name" in fields and fields["name"] is not None:
        nm = fields["name"].strip()
        if len(nm) < 2:
            raise ProspectError("invalid_name", "Ad en az 2 karakter olmalı.")
        p.name = nm
    if fields.get("phone"):
        norm = normalize_e164_tr(fields["phone"])
        if not norm:
            raise ProspectError("invalid_phone", "Geçerli cep telefonu girin.")
        dup = db.query(SalesProspect).filter(
            SalesProspect.phone == norm, SalesProspect.id != p.id).first()
        if dup is not None:
            raise ProspectError("duplicate_phone", f"Bu telefon başka adayda: {dup.name}")
        p.phone = norm
    for f in ("org_name", "email", "city", "note"):
        if f in fields:
            v = fields[f]
            setattr(p, f, (v or "").strip() or None if isinstance(v, str) else v)
    if fields.get("kind") in PROSPECT_KINDS:
        p.kind = fields["kind"]
    if "opt_in" in fields and fields["opt_in"] is not None:
        p.opt_in = bool(fields["opt_in"])
    if fields.get("status") in PROSPECT_STATUSES:
        p.status = fields["status"]
    db.flush()
    return p


def set_status(db: Session, p: SalesProspect, status: str) -> SalesProspect:
    if status not in PROSPECT_STATUSES:
        raise ProspectError("invalid_status", "Geçersiz durum.")
    p.status = status
    db.flush()
    return p


def mark_contacted(db: Session, p: SalesProspect) -> None:
    p.last_contacted_at = _now()
    if p.status == PROSPECT_STATUS_NEW:
        p.status = "contacted"
    db.flush()


def delete_prospect(db: Session, p: SalesProspect) -> None:
    db.delete(p)
    db.flush()


def counts_by_status(db: Session) -> dict[str, int]:
    from sqlalchemy import func as _f
    rows = db.query(SalesProspect.status, _f.count(SalesProspect.id)).group_by(
        SalesProspect.status).all()
    return {str(s): int(c) for s, c in rows}


# ---------------------------- Toplu içe aktarma (CSV) ----------------------------

# Kabul edilen başlıklar (TR/EN eşanlamlı) — kullanıcı Excel/Sheets'ten ne
# aktarırsa aktarsın çalışsın diye esnek.
_CSV_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "name": ("ad", "isim", "ad_soyad", "name", "isletme", "işletme", "unvan"),
    "phone": ("telefon", "tel", "phone", "gsm", "cep", "whatsapp"),
    "kind": ("tur", "tür", "kind", "tip", "kategori"),
    "org_name": ("kurum_adi", "kurum", "org", "org_name", "isletme_adi", "marka"),
    "email": ("eposta", "e-posta", "email", "mail"),
    "city": ("sehir", "şehir", "city", "il"),
    "note": ("not", "note", "aciklama", "açıklama", "notlar"),
    "instagram": ("instagram", "ig", "instagram_hesabi", "hesap"),
}


def _norm_header(h: str) -> str:
    return (h or "").strip().lower().replace("﻿", "").replace(" ", "_")


def _map_headers(fieldnames: list[str]) -> dict[str, str]:
    """CSV başlığı → model alanı eşlemesi (bulunamayan alan atlanır)."""
    out: dict[str, str] = {}
    for raw in fieldnames or []:
        key = _norm_header(raw)
        for field, aliases in _CSV_FIELD_ALIASES.items():
            if key in aliases:
                out[raw] = field
                break
    return out


def import_prospects_csv(
    db: Session, *, actor_user_id: int | None, csv_text: str,
    source: str = "manual", default_kind: str = PROSPECT_KIND_COACH,
    dry_run: bool = False, max_rows: int = 1000,
) -> dict:
    """CSV metnini Hedef Havuzu'na aktar (Faz: koç keşif listesi, 2026-08-05).

    Dürüstlük kuralları:
    - Telefon `normalize_e164_tr` ile doğrulanır; SABİT HAT KABUL EDİLMEZ
      (WhatsApp'a gönderilemez → sessizce eklemek yanlış veri olur).
    - Havuzda aynı telefon varsa ATLANIR (mevcut kayıt EZİLMEZ).
    - Aynı dosyada tekrarlayan telefon bir kez alınır.
    - `opt_in` HER ZAMAN False — toplu listeden gelen kayıt izinli sayılmaz
      (Meta politikası + KVKK; izin ancak kişi dönüş yapınca oluşur).
    - dry_run=True → hiçbir şey yazılmaz, yalnız rapor döner (önizleme).

    Dönen rapor: {created, skipped_duplicate, skipped_existing, invalid[],
    total_rows, preview[]}
    """
    import csv as _csv
    import io as _io

    text = (csv_text or "").lstrip("﻿")
    if not text.strip():
        raise ProspectError("empty_csv", "Dosya boş.")

    # Ayraç tespiti (virgül / noktalı virgül / sekme — Excel TR ; kullanır)
    first_line = text.splitlines()[0] if text.splitlines() else ""
    delim = ";" if first_line.count(";") > first_line.count(",") else (
        "	" if first_line.count("	") > first_line.count(",") else ",")

    reader = _csv.DictReader(_io.StringIO(text), delimiter=delim)
    header_map = _map_headers(list(reader.fieldnames or []))
    if "name" not in header_map.values() or "phone" not in header_map.values():
        raise ProspectError(
            "missing_columns",
            "CSV'de en az 'ad' ve 'telefon' sütunları olmalı "
            f"(bulunan başlıklar: {', '.join(reader.fieldnames or []) or 'yok'}).",
        )

    existing_phones = {
        p for (p,) in db.query(SalesProspect.phone).all() if p
    }
    seen_in_file: set[str] = set()
    created = 0
    skipped_duplicate = 0   # dosya içi tekrar
    skipped_existing = 0    # havuzda zaten var
    invalid: list[dict] = []
    preview: list[dict] = []
    total = 0

    for idx, raw_row in enumerate(reader, start=2):  # 1 = başlık satırı
        if total >= max_rows:
            invalid.append({"row": idx, "reason": f"satır sınırı ({max_rows}) aşıldı"})
            break
        total += 1
        row = {header_map[k]: (v or "").strip()
               for k, v in raw_row.items() if k in header_map}
        name = row.get("name", "")
        phone_raw = row.get("phone", "")
        if not name and not phone_raw:
            total -= 1
            continue  # tamamen boş satır
        norm = normalize_e164_tr(phone_raw)
        if len(name) < 2:
            invalid.append({"row": idx, "name": name, "phone": phone_raw,
                            "reason": "ad en az 2 karakter olmalı"})
            continue
        if not norm:
            invalid.append({"row": idx, "name": name, "phone": phone_raw,
                            "reason": "geçerli cep telefonu değil (sabit hat WhatsApp'a uygun değil)"})
            continue
        if norm in seen_in_file:
            skipped_duplicate += 1
            continue
        seen_in_file.add(norm)
        if norm in existing_phones:
            skipped_existing += 1
            continue

        kind = (row.get("kind") or default_kind).strip().lower()
        if kind in ("kurum", "institution", "kurumsal"):
            kind = PROSPECT_KIND_INSTITUTION
        elif kind in ("koç", "koc", "coach", "bağımsız koç", "bagimsiz koc"):
            kind = PROSPECT_KIND_COACH
        elif kind not in PROSPECT_KINDS:
            kind = default_kind

        if len(preview) < 20:
            preview.append({"name": name, "phone": norm, "kind": kind,
                            "city": row.get("city") or None})
        if dry_run:
            created += 1
            continue

        p = SalesProspect(
            name=name[:160], phone=norm, kind=kind,
            org_name=(row.get("org_name") or "").strip()[:200] or None,
            email=(row.get("email") or "").strip()[:200] or None,
            city=(row.get("city") or "").strip()[:80] or None,
            instagram=_clean_handle(row.get("instagram")),
            source=source if source in PROSPECT_SOURCES else "manual",
            opt_in=False,  # toplu liste ASLA izinli sayılmaz
            note=(row.get("note") or "").strip() or None,
            status=PROSPECT_STATUS_NEW, created_by_admin_id=actor_user_id,
        )
        db.add(p)
        created += 1

    if not dry_run and created:
        db.flush()

    return {
        "created": created,
        "skipped_duplicate": skipped_duplicate,
        "skipped_existing": skipped_existing,
        "invalid": invalid[:50],
        "invalid_count": len(invalid),
        "total_rows": total,
        "preview": preview,
        "dry_run": dry_run,
    }
