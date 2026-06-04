"""AI ile keşif adaylarını PAZARLAMA TEMASINA göre gruplama (Vitrin A2).

109 ham keşif adayını (migration/commit'ten teknik başlıklı) tek tek yayınlamak
pratik değil. Bunun yerine Gemini benzer alandaki özellikleri (WhatsApp, yapay
zeka, veli, akademik takip, program, güvenlik, ödeme/üyelik, mobil…) TEK temaya
toplar + her temaya çarpıcı pazarlama kartı (başlık + tagline + birleşik fayda
listesi + ticari ağırlık + rol) yazar. Admin ~10 temalı kartı gözden geçirip
yayınlar (generic mockup ile). Kaynak adaylar gruplanınca kuyruktan gizlenir.

Gemini ücretsiz key (kişisel veri YOK). gemini.generate + extract_json.
"""
from __future__ import annotations

import re
import secrets

from sqlalchemy.orm import Session

from app.models import FeatureCard
from app.models.feature_card import FeatureStatus
from app.services import feature_catalog as fc
from app.services import gemini
from app.services.ai_book_template import AIInvalidResponse

_VALID_DOMAINS = {"lgs", "yks", "kurumsal", "veli", "genel", "mobil"}
_VALID_ROLES = {"student", "teacher", "parent", "institution_admin", "super_admin"}

_TR = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")


def _slugify(s: str) -> str:
    s = (s or "").translate(_TR).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48] or "tema"


def _candidate_cards(db: Session, limit: int = 150) -> list[FeatureCard]:
    return (
        db.query(FeatureCard)
        .filter(
            (FeatureCard.slug.like("kesif-mig-%") | FeatureCard.slug.like("kesif-c-%")),
            FeatureCard.status == FeatureStatus.DRAFT.value,
            FeatureCard.manual_hide.is_(False),
        )
        .order_by(FeatureCard.introduced_at.desc())
        .limit(limit)
        .all()
    )


_PROMPT = """Sen deneyimli bir SaaS pazarlama stratejistisin. ETÜTKOÇ, LGS/YKS \
öğrenci koçluğu takip platformudur (kullanıcılar: koç, öğrenci, veli, kurum).

Aşağıda otomatik keşfedilmiş HAM özellik adayları var (teknik başlıklı, geliştirici \
dili). Görevin: bunları PAZARLAMA TEMASINA göre 6-12 gruba topla. Benzer alandaki \
özellikler TEK temada birleşsin (örn: WhatsApp/iletişim · yapay zeka · veli · \
akademik takip/deneme · program/planlama · güvenlik · ödeme/üyelik · mobil · \
koçluk işletme). Her tema için ziyaretçiye (koç/kurum/veli) DEĞER anlatan, çarpıcı, \
fayda-odaklı pazarlama metni üret — teknik/geliştirici dili KULLANMA.

YALNIZCA şu JSON'u döndür (başka metin yok):
{"themes":[{
  "title": "kısa çarpıcı başlık (en fazla 60 karakter)",
  "tagline": "tek cümlelik fayda vaadi",
  "category_label": "kısa rozet, örn. Yapay Zeka / İletişim / Akademik",
  "category_icon": "tek emoji",
  "domain": "genel|lgs|yks|kurumsal|veli|mobil",
  "target_roles": ["teacher" veya "institution_admin" veya "parent" veya "student"],
  "commercial_weight": 1-5 arası tam sayı (satışa/pazarlamaya katkı; en güçlü=5),
  "benefits": ["3-5 somut fayda maddesi, koça/veliye değer anlatan"],
  "source_slugs": ["bu temaya giren aday slug'ları"]
}]}

KURALLAR:
- Her aday en fazla BİR temaya girsin.
- benefits somut + fayda-odaklı olsun (örn. "Kopan öğrenciyi sen fark etmeden \
sistem yakalar", "Veliye otomatik haftalık karne gider").
- UYDURMA özellik ekleme; yalnız aşağıdaki adaylardan türet.
- domain ve target_roles'u içeriğe göre uygun seç (koç özelliği→teacher, kurum→\
institution_admin, veli→parent).
"""


def cluster_and_draft(db: Session, *, actor_id: int | None, limit: int = 150) -> dict:
    """Keşif adaylarını AI ile temaya gruplayıp DRAFT temalı kart üretir.

    Returns: {themes_created, candidates_grouped, theme_titles, message}
    """
    cards = _candidate_cards(db, limit)
    if not cards:
        return {
            "themes_created": 0,
            "candidates_grouped": 0,
            "theme_titles": [],
            "message": "Gruplanacak yeni keşif adayı yok (her şey güncel veya zaten gruplanmış).",
        }
    by_slug = {c.slug: c for c in cards}
    listing = "\n".join(
        f"- {c.slug} | {c.title} | {(c.tagline or '')[:140]} | {c.domain}" for c in cards
    )
    prompt = _PROMPT + "\n\nADAYLAR:\n" + listing

    raw = gemini.generate([gemini.text_part(prompt)], personal_data=False, json_mode=True)
    data = gemini.extract_json(raw)
    themes = data.get("themes") if isinstance(data, dict) else None
    if not isinstance(themes, list) or not themes:
        raise AIInvalidResponse("AI tema üretmedi")

    created = 0
    grouped: set[str] = set()
    titles: list[str] = []
    for t in themes:
        if not isinstance(t, dict):
            continue
        title = (t.get("title") or "").strip()
        if not title:
            continue
        benefits = [
            b.strip() for b in (t.get("benefits") or [])
            if isinstance(b, str) and b.strip()
        ][:6]
        roles = [r for r in (t.get("target_roles") or []) if r in _VALID_ROLES]
        domain = t.get("domain") if t.get("domain") in _VALID_DOMAINS else "genel"
        cw = t.get("commercial_weight")
        prio = int(cw) if isinstance(cw, (int, float)) and 1 <= cw <= 5 else 3
        slug = f"tema-{_slugify(title)}-{secrets.token_hex(2)}"
        try:
            fc.create(
                db,
                actor_id=actor_id,
                slug=slug,
                title=title[:160],
                tagline=(t.get("tagline") or "")[:400],
                category_icon=(t.get("category_icon") or "✨")[:16],
                category_label=(t.get("category_label") or "Tema")[:64],
                domain=domain,
                target_roles=roles,
                benefits=benefits,
                mockup_type="generic",
                status=FeatureStatus.DRAFT.value,
                strategic_priority=prio,
            )
        except fc.FeatureCatalogError:
            continue
        created += 1
        titles.append(title)
        for s in (t.get("source_slugs") or []):
            if isinstance(s, str) and s in by_slug:
                grouped.add(s)

    # Gruplanan ham adayları kuyruktan gizle (DB'de kalır, traceable).
    for s in grouped:
        try:
            fc.update(db, by_slug[s], actor_id=actor_id, manual_hide=True)
        except Exception:  # noqa: BLE001
            pass

    db.commit()
    return {
        "themes_created": created,
        "candidates_grouped": len(grouped),
        "theme_titles": titles,
        "message": f"{created} temalı kart üretildi · {len(grouped)} aday gruplandı. "
                   "Taslakları gözden geçirip yayınlayın.",
    }
